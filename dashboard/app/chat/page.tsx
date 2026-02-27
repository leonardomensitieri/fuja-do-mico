/**
 * app/chat/page.tsx
 * =================
 * Página de chat com IA — busca contexto do pipeline e renderiza ChatInterface.
 * AC: 7
 */

import { createServerClient, Edicao } from '@/lib/supabase'
import ChatInterface from '@/components/ChatInterface'

export default async function ChatPage() {
  const supabase = createServerClient()

  // Busca as últimas 50 edições para compor o contexto do assistente
  const { data } = await supabase
    .from('edicoes')
    .select('*')
    .order('numero', { ascending: false })
    .limit(50)

  const edicoes: Edicao[] = data ?? []

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Chat com IA</h1>
        <p className="text-sm text-gray-500 mt-1">
          Pergunte sobre edições, status do pipeline ou métricas de execução
        </p>
      </div>

      <div className="mb-3 text-xs text-gray-400">
        Exemplos: &quot;Qual foi a última edição gerada?&quot; ·{' '}
        &quot;Quantas edições foram distribuídas?&quot; ·{' '}
        &quot;O que aconteceu na última execução?&quot;
      </div>

      <ChatInterface edicoesContexto={edicoes} />
    </div>
  )
}
