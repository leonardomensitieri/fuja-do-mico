/**
 * EdicaoDetail.tsx
 * ================
 * Exibe os detalhes completos de uma edição:
 * metadados, decisões dos Gates e métricas de coleta.
 * AC: 6
 */

import { Edicao, Execucao, STATUS_LABELS } from '@/lib/supabase'

interface EdicaoDetailProps {
  edicao: Edicao
  execucao: Execucao | null
}

function formatarDataHora(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function SecaoTitulo({ titulo }: { titulo: string }) {
  return (
    <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 mt-6">
      {titulo}
    </h2>
  )
}

function Campo({ label, valor }: { label: string; valor: React.ReactNode }) {
  return (
    <div className="flex gap-2 text-sm mb-1">
      <span className="text-gray-500 min-w-40">{label}</span>
      <span className="text-gray-900">{valor ?? <em className="text-gray-300">—</em>}</span>
    </div>
  )
}

export default function EdicaoDetail({ edicao, execucao }: EdicaoDetailProps) {
  const report = execucao?.orchestration_report as Record<string, unknown> | null
  const decisao = report?.decisao as Record<string, unknown> | undefined
  const metricas = report?.metricas as Record<string, unknown> | undefined
  const gate_financeiro = decisao?.gate_financeiro as Record<string, unknown> | undefined

  return (
    <div className="max-w-2xl">
      {/* Cabeçalho */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <h1 className="text-2xl font-bold text-gray-900">
            Edição #{edicao.numero}
          </h1>
          <span className="text-sm bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
            {STATUS_LABELS[edicao.status]}
          </span>
        </div>
        {edicao.titulo && (
          <p className="text-gray-600">{edicao.titulo}</p>
        )}
      </div>

      {/* Metadados */}
      <SecaoTitulo titulo="Metadados" />
      <Campo label="Tipo" valor={edicao.tipo_edicao} />
      <Campo label="Status" valor={STATUS_LABELS[edicao.status]} />
      <Campo label="Criada em" valor={formatarDataHora(edicao.criada_em)} />
      <Campo label="Atualizada em" valor={formatarDataHora(edicao.atualizada_em)} />

      {/* Execução */}
      {execucao && (
        <>
          <SecaoTitulo titulo="Execução do Pipeline" />
          <Campo
            label="Início"
            valor={formatarDataHora(execucao.timestamp_inicio)}
          />
          {execucao.timestamp_fim && (
            <Campo
              label="Fim"
              valor={formatarDataHora(execucao.timestamp_fim)}
            />
          )}
          <Campo
            label="Resultado"
            valor={
              execucao.sucesso ? (
                <span className="text-green-600 font-medium">Sucesso</span>
              ) : (
                <span className="text-red-600 font-medium">Falha</span>
              )
            }
          />
          {execucao.erro_mensagem && (
            <Campo label="Erro" valor={execucao.erro_mensagem} />
          )}
        </>
      )}

      {/* Decisão do orquestrador */}
      {decisao && (
        <>
          <SecaoTitulo titulo="Decisão do Orquestrador" />
          {decisao.tipo_edicao != null && (
            <Campo label="Tipo decidido" valor={String(decisao.tipo_edicao)} />
          )}
          {decisao.justificativa != null && (
            <Campo label="Justificativa" valor={String(decisao.justificativa)} />
          )}

          {/* Gate financeiro */}
          {gate_financeiro && (
            <>
              <div className="mt-3 mb-1 text-xs font-semibold text-gray-400">Gate Financeiro</div>
              <Campo
                label="Brapi"
                valor={gate_financeiro.chamar_brapi ? 'sim' : 'não'}
              />
              <Campo
                label="Fintz"
                valor={gate_financeiro.chamar_fintz ? 'sim' : 'não'}
              />
              {Array.isArray(gate_financeiro.tickers) && gate_financeiro.tickers.length > 0 && (
                <Campo
                  label="Tickers"
                  valor={(gate_financeiro.tickers as string[]).join(', ')}
                />
              )}
              {gate_financeiro.clone_detectado != null && (
                <Campo
                  label="Clone sugerido"
                  valor={String(gate_financeiro.clone_detectado)}
                />
              )}
            </>
          )}
        </>
      )}

      {/* Métricas de coleta */}
      {metricas && (
        <>
          <SecaoTitulo titulo="Métricas de Coleta" />
          {Object.entries(metricas).map(([chave, valor]) => (
            <Campo
              key={chave}
              label={chave.replace(/_/g, ' ')}
              valor={String(valor)}
            />
          ))}
        </>
      )}

      {/* Orchestration report completo (colapsável) */}
      {report && (
        <>
          <SecaoTitulo titulo="Relatório Completo (JSON)" />
          <details className="mt-2">
            <summary className="text-sm text-gray-500 cursor-pointer hover:text-gray-900">
              Expandir JSON completo
            </summary>
            <pre className="mt-3 p-4 bg-gray-50 border border-gray-200 rounded text-xs overflow-x-auto text-gray-700">
              {JSON.stringify(report, null, 2)}
            </pre>
          </details>
        </>
      )}
    </div>
  )
}
