/**
 * EdicaoCard.tsx
 * ==============
 * Card individual de uma edição no Kanban.
 * Exibe: número, título, tipo e data de criação.
 */

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

export default function EdicaoCard({ edicao }: EdicaoCardProps) {
  const tipoCor = edicao.tipo_edicao ? TIPO_CORES[edicao.tipo_edicao] ?? '' : ''

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
      </div>
    </Link>
  )
}
