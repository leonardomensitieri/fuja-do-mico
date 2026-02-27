-- ═══════════════════════════════════════════════════════════════
-- Migração: 20260227000000_add_github_run_id.sql
-- Story 2.4 — Aprovação via Telegram e Dashboard
-- ═══════════════════════════════════════════════════════════════

-- Adiciona github_run_id na tabela edicoes para correlacionar com o workflow
-- Permite que o dashboard e o webhook Telegram identifiquem o run a aprovar
ALTER TABLE edicoes ADD COLUMN IF NOT EXISTS github_run_id text;

CREATE INDEX IF NOT EXISTS idx_edicoes_run_id ON edicoes(github_run_id);
