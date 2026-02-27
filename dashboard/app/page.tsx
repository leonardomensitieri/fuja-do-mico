/**
 * app/page.tsx
 * ============
 * Página principal — Kanban de edições da newsletter.
 * Server Component: busca dados no Supabase e passa para KanbanBoard (client).
 */

import { createServerClient, Edicao } from '@/lib/supabase'
import KanbanBoard from '@/components/KanbanBoard'

// Revalidar a cada 60s (fallback para ambientes sem Realtime)
export const revalidate = 60

export default async function Home() {
  const supabase = createServerClient()

  const { data, error } = await supabase
    .from('edicoes')
    .select('*')
    .order('numero', { ascending: false })

  const edicoes: Edicao[] = error ? [] : (data ?? [])

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Edições da Newsletter</h1>
        <p className="text-sm text-gray-500 mt-1">
          Atualizado em tempo real via Supabase Realtime
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          Erro ao carregar edições: {error.message}
        </div>
      )}

      <KanbanBoard edicoesIniciais={edicoes} />
    </div>
  )
}
