'use client'

/**
 * KanbanBoard.tsx
 * ===============
 * Board Kanban com 6 colunas de status.
 * Mantém subscription Realtime com o Supabase para atualizações ao vivo.
 * AC: 3, 4, 5
 */

import { useEffect, useState } from 'react'
import { createBrowserClient, Edicao, KANBAN_COLUNAS, STATUS_LABELS } from '@/lib/supabase'
import EdicaoCard from './EdicaoCard'

interface KanbanBoardProps {
  edicoesIniciais: Edicao[]
}

// Agrupa edições por status
function agruparPorStatus(edicoes: Edicao[]): Record<string, Edicao[]> {
  const grupos: Record<string, Edicao[]> = {}
  for (const col of KANBAN_COLUNAS) {
    grupos[col] = []
  }
  for (const e of edicoes) {
    if (grupos[e.status]) {
      grupos[e.status].push(e)
    }
  }
  return grupos
}

// Upsert de uma edição no array local (para Realtime)
function upsertEdicao(lista: Edicao[], nova: Edicao): Edicao[] {
  const idx = lista.findIndex((e) => e.id === nova.id)
  if (idx >= 0) {
    const copia = [...lista]
    copia[idx] = nova
    return copia
  }
  return [nova, ...lista]
}

export default function KanbanBoard({ edicoesIniciais }: KanbanBoardProps) {
  const [edicoes, setEdicoes] = useState<Edicao[]>(edicoesIniciais)

  useEffect(() => {
    const supabase = createBrowserClient()

    // Subscription Realtime — qualquer mudança na tabela edicoes (AC: 3)
    const channel = supabase
      .channel('edicoes-realtime')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'edicoes' },
        (payload) => {
          if (payload.eventType === 'DELETE') {
            setEdicoes((prev) => prev.filter((e) => e.id !== payload.old.id))
          } else {
            setEdicoes((prev) => upsertEdicao(prev, payload.new as Edicao))
          }
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [])

  const grupos = agruparPorStatus(edicoes)

  return (
    <div className="overflow-x-auto">
      <div className="flex gap-4 min-w-max pb-4">
        {KANBAN_COLUNAS.map((status) => (
          <div key={status} className="w-56 flex-shrink-0">
            {/* Cabeçalho da coluna */}
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                {STATUS_LABELS[status]}
              </h3>
              <span className="text-xs text-gray-400 bg-gray-100 rounded-full px-2 py-0.5">
                {grupos[status].length}
              </span>
            </div>

            {/* Cards da coluna */}
            <div className="flex flex-col gap-2">
              {grupos[status].length === 0 ? (
                <div className="border border-dashed border-gray-200 rounded p-4 text-xs text-gray-300 text-center">
                  vazio
                </div>
              ) : (
                grupos[status].map((e) => <EdicaoCard key={e.id} edicao={e} />)
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
