-- ═══════════════════════════════════════════════════════════════
-- Migração: 20260228020000_add_titulo_to_conteudo_raw.sql
-- Adiciona coluna titulo à tabela conteudo_raw
-- ═══════════════════════════════════════════════════════════════
--
-- titulo: campo dedicado para o título do conteúdo.
-- Útil para todas as fontes:
--   - youtube  → título do vídeo
--   - rss      → título do artigo
--   - gmail    → assunto do email
--   - instagram → primeira linha da caption
--   - twitter  → primeiros 100 chars do tweet
--   - research → query principal da pesquisa
--
-- Métricas (views, likes) ficam em metadata jsonb por serem
-- específicas de cada plataforma.
-- ═══════════════════════════════════════════════════════════════

ALTER TABLE conteudo_raw ADD COLUMN IF NOT EXISTS titulo text;

-- Índice para busca por título (dashboard e triagem)
CREATE INDEX IF NOT EXISTS idx_conteudo_raw_titulo
  ON conteudo_raw USING gin(to_tsvector('portuguese', coalesce(titulo, '')));
