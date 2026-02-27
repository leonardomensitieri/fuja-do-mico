'use client'

/**
 * ChatInterface.tsx
 * =================
 * Interface de chat com Claude Sonnet via API route server-side.
 * Injeta contexto do pipeline (última edição, contagem por status) em cada envio.
 * AC: 7
 */

import { useState, useRef, useEffect } from 'react'
import { Edicao } from '@/lib/supabase'

interface Mensagem {
  papel: 'usuario' | 'assistente'
  texto: string
}

interface ChatInterfaceProps {
  edicoesContexto: Edicao[]
}

function montarContexto(edicoes: Edicao[]) {
  const total = edicoes.length
  const porStatus: Record<string, number> = {}
  for (const e of edicoes) {
    porStatus[e.status] = (porStatus[e.status] ?? 0) + 1
  }
  const ultima = edicoes[0] ?? null
  return {
    total_edicoes: total,
    contagem_por_status: porStatus,
    ultima_edicao: ultima
      ? {
          numero: ultima.numero,
          titulo: ultima.titulo,
          status: ultima.status,
          tipo: ultima.tipo_edicao,
          criada_em: ultima.criada_em,
        }
      : null,
  }
}

export default function ChatInterface({ edicoesContexto }: ChatInterfaceProps) {
  const [mensagens, setMensagens] = useState<Mensagem[]>([
    {
      papel: 'assistente',
      texto:
        'Olá! Sou o assistente operacional do Fuja do Mico. Posso responder perguntas sobre as edições da newsletter, status do pipeline e métricas de execução. Como posso ajudar?',
    },
  ])
  const [input, setInput] = useState('')
  const [carregando, setCarregando] = useState(false)
  const fimRef = useRef<HTMLDivElement>(null)

  // Scroll automático para última mensagem
  useEffect(() => {
    fimRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensagens])

  async function enviar() {
    const texto = input.trim()
    if (!texto || carregando) return

    setInput('')
    setMensagens((prev) => [...prev, { papel: 'usuario', texto }])
    setCarregando(true)

    try {
      const contexto = montarContexto(edicoesContexto)

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: texto, contexto }),
      })

      const json = await res.json()

      setMensagens((prev) => [
        ...prev,
        {
          papel: 'assistente',
          texto: json.resposta ?? json.erro ?? 'Resposta vazia.',
        },
      ])
    } catch {
      setMensagens((prev) => [
        ...prev,
        { papel: 'assistente', texto: 'Erro de conexão. Tente novamente.' },
      ])
    } finally {
      setCarregando(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      enviar()
    }
  }

  return (
    <div className="flex flex-col h-[600px] border border-gray-200 rounded-lg overflow-hidden">
      {/* Histórico */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
        {mensagens.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.papel === 'usuario' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] px-4 py-2 rounded-lg text-sm whitespace-pre-wrap ${
                m.papel === 'usuario'
                  ? 'bg-gray-900 text-white'
                  : 'bg-white border border-gray-200 text-gray-900'
              }`}
            >
              {m.texto}
            </div>
          </div>
        ))}

        {carregando && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-400">
              Pensando...
            </div>
          </div>
        )}

        <div ref={fimRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-4 bg-white">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Pergunte sobre as edições... (Enter para enviar)"
            rows={2}
            className="flex-1 resize-none border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:border-gray-400"
          />
          <button
            onClick={enviar}
            disabled={carregando || !input.trim()}
            className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Enviar
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-1">
          Shift+Enter para nova linha · Enter para enviar
        </p>
      </div>
    </div>
  )
}
