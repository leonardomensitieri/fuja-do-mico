/**
 * app/api/chat/route.ts
 * =====================
 * API Route server-side para o chat com Claude Sonnet.
 *
 * SEGURANÇA: ANTHROPIC_API_KEY é lida apenas aqui (server-side).
 * Nunca exposta ao browser — não usar prefixo NEXT_PUBLIC_.
 * AC: 7, 9
 */

import Anthropic from '@anthropic-ai/sdk'

export async function POST(request: Request) {
  try {
    const { message, contexto } = await request.json()

    if (!message || typeof message !== 'string') {
      return Response.json({ erro: 'Mensagem inválida' }, { status: 400 })
    }

    const client = new Anthropic()
    // ANTHROPIC_API_KEY lida automaticamente da variável de ambiente server-side

    const contextoTexto = contexto
      ? `\n\nContexto atual do pipeline:\n${JSON.stringify(contexto, null, 2)}`
      : ''

    const response = await client.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 1024,
      system: `Você é o assistente operacional do pipeline Fuja do Mico — sistema de automação da newsletter Liga HUB Finance.
Responda em português, de forma concisa e factual.
Quando perguntado sobre edições, use os dados do contexto fornecido.
Não invente dados que não estejam no contexto.${contextoTexto}`,
      messages: [{ role: 'user', content: message }],
    })

    const texto = response.content[0].type === 'text' ? response.content[0].text : ''

    return Response.json({ resposta: texto })
  } catch (erro) {
    console.error('Erro na API route /api/chat:', erro)
    return Response.json(
      { erro: 'Erro ao processar mensagem. Tente novamente.' },
      { status: 500 }
    )
  }
}
