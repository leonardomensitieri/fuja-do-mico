/**
 * lib/supabase.ts
 * ===============
 * Factory do cliente Supabase para uso no dashboard.
 *
 * Duas instâncias distintas:
 *   createBrowserClient() — usa NEXT_PUBLIC_* (seguro para o browser via RLS)
 *   createServerClient()  — também usa anon key (leitura pública, sem service key)
 *
 * A service key NUNCA é usada aqui — ela fica exclusivamente no pipeline Python.
 */

import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

/**
 * Cliente Supabase para componentes client-side.
 * Singleton — reutilizado em todo o browser.
 */
export function createBrowserClient() {
  return createClient(supabaseUrl, supabaseAnonKey)
}

/**
 * Cliente Supabase para Server Components e API routes.
 * Usa a mesma anon key — RLS garante a segurança.
 */
export function createServerClient() {
  return createClient(supabaseUrl, supabaseAnonKey)
}

// Tipos das tabelas do banco (Story 2.2)
export type Edicao = {
  id: string
  numero: number
  titulo: string | null
  tipo_edicao: 'completa' | 'reduzida' | 'abortada' | null
  status:
    | 'em_coleta'
    | 'triagem'
    | 'geracao'
    | 'aguardando_aprovacao'
    | 'distribuida'
    | 'abortada'
  github_run_id: string | null
  criada_em: string
  atualizada_em: string
}

export type Execucao = {
  id: string
  edicao_id: string
  timestamp_inicio: string
  timestamp_fim: string | null
  orchestration_report: Record<string, unknown> | null
  sucesso: boolean | null
  erro_mensagem: string | null
}

// Mapeamento status → rótulo legível
export const STATUS_LABELS: Record<Edicao['status'], string> = {
  em_coleta: 'Coletando',
  triagem: 'Triagem',
  geracao: 'Gerando',
  aguardando_aprovacao: 'Aguardando Aprovação',
  distribuida: 'Distribuída',
  abortada: 'Abortada',
}

// Ordem das colunas no Kanban
export const KANBAN_COLUNAS: Edicao['status'][] = [
  'em_coleta',
  'triagem',
  'geracao',
  'aguardando_aprovacao',
  'distribuida',
  'abortada',
]
