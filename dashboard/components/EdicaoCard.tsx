'use client'

/**
 * EdicaoCard.tsx
 * ==============
 * Card individual de uma edição no Kanban.
 * Exibe: número, título, tipo e data de criação.
 * Quando status = aguardando_aprovacao: exibe botões Aprovar / Rejeitar (Story 2.4).
 */

import { useState } from 'react'
import Link from 'next/link'
import { Edicao } from '@/lib/supabase'

interface EdicaoCardProps {
  edicao: Edicao
}

// Cor de fundo por tipo de edição
const TIPO_CORES: Record<string, string> = {
  completa: 'bg-blue-50 text-blue-700',
  reduzida: 'bg-yellow-50 text-yellow-700',
  abortada: 'bg-red-50 text-red-700',
}

function formatarData(iso: string): string {
  return new Date(iso).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
  })
}

function BotoesAprovacao({ edicao }: { edicao: Edicao }) {
  const [loading, setLoading] = useState<'approve' | 'reject' | null>(null)
  const [resultado, setResultado] = useState<string | null>(null)

  async function executarAcao(action: 'approve' | 'reject') {
    if (!edicao.github_run_id) {
      setResultado('Run ID não disponível')
      return
    }
    setLoading(action)
    try {
      const res = await fetch('/api/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ runId: edicao.github_run_id, action, edicaoId: edicao.id }),
      })
      const data = await res.json()
      if (data.ok) {
        setResultado(action === 'approve' ? '✅ Aprovado!' : '❌ Rejeitado')
      } else {
        setResultado(`Erro: ${data.error ?? 'desconhecido'}`)
      }
    } catch (e) {
      setResultado('Erro de rede')
    } finally {
      setLoading(null)
    }
  }

  if (resultado) {
    return <p className="text-xs text-center mt-2 font-medium text-gray-600">{resultado}</p>
  }

  return (
    <div className="flex gap-1 mt-2" onClick={(e) => e.preventDefault()}>
      <button
        onClick={() => executarAcao('approve')}
        disabled={loading !== null}
        className="flex-1 text-xs py-1 rounded bg-green-100 text-green-700 hover:bg-green-200 disabled:opacity-50 font-medium transition-colors"
      >
        {loading === 'approve' ? '...' : '✅ Aprovar'}
      </button>
      <button
        onClick={() => executarAcao('reject')}
        disabled={loading !== null}
        className="flex-1 text-xs py-1 rounded bg-red-100 text-red-700 hover:bg-red-200 disabled:opacity-50 font-medium transition-colors"
      >
        {loading === 'reject' ? '...' : '❌ Rejeitar'}
      </button>
    </div>
  )
}

export default function EdicaoCard({ edicao }: EdicaoCardProps) {
  const tipoCor = edicao.tipo_edicao ? TIPO_CORES[edicao.tipo_edicao] ?? '' : ''
  const aguardandoAprovacao = edicao.status === 'aguardando_aprovacao'

  return (
    <Link href={`/edicao/${edicao.id}`}>
      <div className="bg-white border border-gray-200 rounded p-3 hover:border-gray-400 hover:shadow-sm transition-all cursor-pointer">
        {/* Número da edição */}
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-bold text-gray-400">#{edicao.numero}</span>
          {edicao.tipo_edicao && (
            <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${tipoCor}`}>
              {edicao.tipo_edicao}
            </span>
          )}
        </div>

        {/* Título */}
        <p className="text-sm font-medium text-gray-900 line-clamp-2 mb-2">
          {edicao.titulo ?? <span className="text-gray-400 italic">sem título</span>}
        </p>

        {/* Data */}
        <p className="text-xs text-gray-400">{formatarData(edicao.criada_em)}</p>

        {/* Botões de aprovação — apenas quando aguardando aprovação */}
        {aguardandoAprovacao && <BotoesAprovacao edicao={edicao} />}
      </div>
    </Link>
  )
}
