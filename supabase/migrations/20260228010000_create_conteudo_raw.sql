-- ═══════════════════════════════════════════════════════════════
-- Migração: 20260228010000_create_conteudo_raw.sql
-- Pipeline Fuja do Mico — Base de Conhecimento Contínua (Story 3.1)
-- ═══════════════════════════════════════════════════════════════
--
-- Cria a tabela conteudo_raw — pool central de conteúdo capturado
-- pelos nodes de escuta contínua (Node Concorrentes, Node Notícias,
-- Node Gmail). Cada registro é um item individual capturado.
--
-- Fluxo de estados:
--   processado=false, status_triagem=null  → aguardando triagem
--   processado=true,  status_triagem=APROVADO   → entra no pool
--   processado=true,  status_triagem=DESCARTADO → ignorado
--   processado=true,  status_triagem=PENDENTE   → revisão humana
--
-- Nota: a tabela conteudo_coletado (Epic 1+2) é mantida intacta.
-- Ambas coexistem durante a transição. conteudo_raw é o novo pool
-- da camada de escuta contínua — não substitui conteudo_coletado.
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE conteudo_raw (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Identificação da origem
  fonte           text        NOT NULL,
  -- valores: 'rss', 'gmail', 'youtube', 'instagram', 'twitter', 'research'

  plataforma      text,
  -- valores: 'web', 'youtube', 'instagram', 'twitter', 'email'

  tipo_conteudo   text,
  -- valores: 'artigo', 'video', 'short', 'post', 'carrossel', 'reel', 'tweet', 'newsletter', 'research'

  conta_origem    text,
  -- handle ou canal de onde veio (ex: 'thiago.nigro', '@primorico')

  -- Conteúdo
  conteudo_texto  text,
  -- texto extraído: caption, transcrição, body do email, output do research

  url_original    text,

  -- Timestamps
  data_captura    timestamptz DEFAULT now(),
  data_publicacao timestamptz,

  -- Estado de triagem
  processado      boolean     DEFAULT false,
  -- true após 12_triage_pool.py processar este item

  status_triagem  text        CHECK (status_triagem IN ('APROVADO', 'DESCARTADO', 'PENDENTE')),

  -- Sugestões da triagem automática
  linha_editorial_sugerida text,
  -- valores: 'analise_financeira', 'noticia', 'mentalidade', 'macro', 'erros', 'narrativa'

  clone_sugerido  text,
  -- valores: 'graham', 'buffett', 'barsi', 'damodaran', 'lynch'

  -- Metadados específicos por plataforma
  metadata        jsonb
  -- Instagram: {likes, tipo_post, num_slides}
  -- YouTube: {duracao_segundos, view_count, is_short}
  -- Twitter: {like_count, retweet_count}
  -- Research: {query, iteracoes, data_pesquisa}
);


-- ═══════════════════════════════════════════
-- Índices de performance
-- ═══════════════════════════════════════════

-- Triagem: busca eficiente de itens não processados
CREATE INDEX idx_conteudo_raw_processado
  ON conteudo_raw(processado)
  WHERE processado = false;

-- Filtro por status (pool aprovado pelo orquestrador)
CREATE INDEX idx_conteudo_raw_status
  ON conteudo_raw(status_triagem);

-- Janela temporal (orquestrador busca últimos 7 dias)
CREATE INDEX idx_conteudo_raw_data_captura
  ON conteudo_raw(data_captura DESC);

-- Filtros operacionais por plataforma e conta
CREATE INDEX idx_conteudo_raw_plataforma
  ON conteudo_raw(plataforma);

CREATE INDEX idx_conteudo_raw_conta_origem
  ON conteudo_raw(conta_origem);


-- ═══════════════════════════════════════════
-- RLS (Row Level Security)
-- Consistente com as demais tabelas do projeto
-- ═══════════════════════════════════════════
ALTER TABLE conteudo_raw ENABLE ROW LEVEL SECURITY;

-- Leitura pública — Dashboard Vercel usa anon key para visualizar o pool
CREATE POLICY "leitura_publica_conteudo_raw"
  ON conteudo_raw FOR SELECT USING (true);

-- Escrita restrita ao service_role — apenas o pipeline grava via service key
CREATE POLICY "escrita_service_role_conteudo_raw"
  ON conteudo_raw FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');
