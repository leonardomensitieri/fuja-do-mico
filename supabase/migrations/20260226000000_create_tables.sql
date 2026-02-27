-- ═══════════════════════════════════════════════════════════════
-- Migração: 20260226000000_create_tables.sql
-- Pipeline Fuja do Mico — Banco de Dados Supabase (Story 2.2)
-- ═══════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════
-- Função auxiliar: atualiza atualizada_em automaticamente
-- ═══════════════════════════════════════════
CREATE OR REPLACE FUNCTION atualizar_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.atualizada_em = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ═══════════════════════════════════════════
-- Tabela: edicoes
-- Registra cada edição produzida pelo pipeline
-- ═══════════════════════════════════════════
CREATE TABLE edicoes (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  numero        integer     UNIQUE NOT NULL,
  titulo        text,
  tipo_edicao   text        CHECK (tipo_edicao IN ('completa', 'reduzida', 'abortada')),
  status        text        DEFAULT 'em_coleta'
                            CHECK (status IN (
                              'em_coleta', 'triagem', 'geracao',
                              'aguardando_aprovacao', 'distribuida', 'abortada'
                            )),
  criada_em     timestamptz DEFAULT now(),
  atualizada_em timestamptz DEFAULT now()
);

-- Índices para queries por status e data (Dashboard)
CREATE INDEX idx_edicoes_status    ON edicoes(status);
CREATE INDEX idx_edicoes_criada_em ON edicoes(criada_em DESC);

-- Trigger: mantém atualizada_em sincronizado
CREATE TRIGGER tr_edicoes_atualizada_em
  BEFORE UPDATE ON edicoes
  FOR EACH ROW EXECUTE FUNCTION atualizar_timestamp();


-- ═══════════════════════════════════════════
-- Tabela: execucoes
-- Log de cada execução do pipeline (1 por edição, mas pode ter retentativas)
-- ═══════════════════════════════════════════
CREATE TABLE execucoes (
  id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  edicao_id            uuid        REFERENCES edicoes(id) ON DELETE CASCADE,
  timestamp_inicio     timestamptz DEFAULT now(),
  timestamp_fim        timestamptz,
  orchestration_report jsonb,
  sucesso              boolean,
  erro_mensagem        text
);

-- Índices para queries por edição e por data
CREATE INDEX idx_execucoes_edicao_id  ON execucoes(edicao_id);
CREATE INDEX idx_execucoes_timestamp  ON execucoes(timestamp_inicio DESC);


-- ═══════════════════════════════════════════
-- Tabela: conteudo_coletado
-- Arquiva o conteúdo coletado por edição e fonte
-- Ativada somente quando SUPABASE_SALVAR_CONTEUDO=true
-- ═══════════════════════════════════════════
CREATE TABLE conteudo_coletado (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  edicao_id   uuid        REFERENCES edicoes(id) ON DELETE CASCADE,
  fonte       text        NOT NULL
                          CHECK (fonte IN ('gmail', 'rss', 'youtube', 'social', 'brapi', 'fintz')),
  itens       jsonb,
  coletado_em timestamptz DEFAULT now()
);

CREATE INDEX idx_conteudo_edicao_id ON conteudo_coletado(edicao_id);
CREATE INDEX idx_conteudo_fonte     ON conteudo_coletado(fonte);


-- ═══════════════════════════════════════════
-- RLS (Row Level Security)
-- Service Key bypassa RLS — pipeline usa service key
-- Anon Key respeita RLS — dashboard usará anon key (Story 2.3)
-- ═══════════════════════════════════════════
ALTER TABLE edicoes           ENABLE ROW LEVEL SECURITY;
ALTER TABLE execucoes         ENABLE ROW LEVEL SECURITY;
ALTER TABLE conteudo_coletado ENABLE ROW LEVEL SECURITY;

-- Política de leitura pública (Story 2.3 refinará com autenticação)
CREATE POLICY "leitura_publica_edicoes"
  ON edicoes FOR SELECT USING (true);

CREATE POLICY "leitura_publica_execucoes"
  ON execucoes FOR SELECT USING (true);

CREATE POLICY "leitura_publica_conteudo"
  ON conteudo_coletado FOR SELECT USING (true);
