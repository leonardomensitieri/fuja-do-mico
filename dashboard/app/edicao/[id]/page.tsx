/**
 * app/edicao/[id]/page.tsx
 * ========================
 * Detalhe de uma edição — busca edicao + ultima execucao no Supabase.
 * AC: 6
 */

import { notFound } from 'next/navigation'
import Link from 'next/link'
import { createServerClient, Edicao, Execucao } from '@/lib/supabase'
import EdicaoDetail from '@/components/EdicaoDetail'

interface PageProps {
  params: { id: string }
}

export default async function EdicaoPage({ params }: PageProps) {
  const supabase = createServerClient()

  // Busca a edição
  const { data: edicaoData, error: edicaoError } = await supabase
    .from('edicoes')
    .select('*')
    .eq('id', params.id)
    .single()

  if (edicaoError || !edicaoData) {
    notFound()
  }

  // Busca a execução mais recente associada
  const { data: execucaoData } = await supabase
    .from('execucoes')
    .select('*')
    .eq('edicao_id', params.id)
    .order('timestamp_inicio', { ascending: false })
    .limit(1)
    .single()

  const edicao = edicaoData as Edicao
  const execucao = (execucaoData as Execucao) ?? null

  return (
    <div>
      {/* Breadcrumb */}
      <div className="mb-6 text-sm text-gray-500">
        <Link href="/" className="hover:text-gray-900">
          ← Edições
        </Link>
      </div>

      <EdicaoDetail edicao={edicao} execucao={execucao} />
    </div>
  )
}
