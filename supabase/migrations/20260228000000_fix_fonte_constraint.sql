-- ═══════════════════════════════════════════════════════════════
-- Migração: 20260228000000_fix_fonte_constraint.sql
-- Pipeline Fuja do Mico — Débito Técnico Bloqueante (Story 3.1)
-- ═══════════════════════════════════════════════════════════════
--
-- Problema: o CHECK constraint original em conteudo_coletado.fonte
-- lista apenas as fontes do Epic 1+2. Qualquer INSERT com nova fonte
-- (research, instagram, twitter, etc.) falha silenciosamente.
--
-- Solução: substituir o constraint por lista expandida que suporta
-- todos os nodes da camada de escuta contínua (Epic 3).
--
-- Verificação recomendada antes de aplicar:
--   SELECT COUNT(*) FROM conteudo_coletado;
-- Executar novamente após aplicar e confirmar que o COUNT é idêntico.
-- ═══════════════════════════════════════════════════════════════

-- Remove o constraint inline (gerado automaticamente como conteudo_coletado_fonte_check)
ALTER TABLE conteudo_coletado
  DROP CONSTRAINT IF EXISTS conteudo_coletado_fonte_check;

-- Adiciona novo constraint com lista expandida para Epic 3
ALTER TABLE conteudo_coletado
  ADD CONSTRAINT conteudo_coletado_fonte_check
  CHECK (fonte IN (
    'gmail',
    'rss',
    'youtube',
    'social',
    'brapi',
    'fintz',
    'research',
    'concorrentes',
    'youtube_canal',
    'instagram',
    'twitter'
  ));
