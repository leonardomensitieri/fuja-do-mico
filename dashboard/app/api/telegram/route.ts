/**
 * app/api/telegram/route.ts
 * =========================
 * Webhook do Telegram — recebe callback_query dos botões inline de aprovação.
 * Chama a GitHub API para aprovar ou rejeitar o deployment do pipeline.
 *
 * Fluxo:
 *   Bot Telegram envia mensagem com botões → usuário clica
 *   → Telegram POST neste endpoint → GitHub API approve/reject
 *   → Telegram answerCallbackQuery (fecha o loading do botão)
 *
 * Variáveis de ambiente (Vercel):
 *   TELEGRAM_BOT_TOKEN  — token do @fuja_do_mico_bot
 *   GITHUB_TOKEN        — PAT com scope repo + actions:write
 *   GITHUB_OWNER        — leonardomensitieri
 *   GITHUB_REPO         — fuja-do-mico
 */

export const runtime = 'nodejs'

// Busca o environment_id do environment 'aprovacao-humana' via GitHub API
async function buscarEnvironmentId(owner: string, repo: string, token: string): Promise<number | null> {
  const res = await fetch(`https://api.github.com/repos/${owner}/${repo}/environments`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
    },
  })
  if (!res.ok) return null
  const data = await res.json()
  const env = (data.environments ?? []).find((e: { name: string; id: number }) => e.name === 'aprovacao-humana')
  return env?.id ?? null
}

// Aprova ou rejeita o pending deployment via GitHub API
async function executarAcaoGitHub(
  runId: string,
  action: 'approved' | 'rejected',
  owner: string,
  repo: string,
  token: string
): Promise<boolean> {
  const environmentId = await buscarEnvironmentId(owner, repo, token)
  if (!environmentId) {
    console.error('Environment "aprovacao-humana" não encontrado')
    return false
  }

  const res = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/actions/runs/${runId}/pending_deployments`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        environment_ids: [environmentId],
        state: action,
        comment: `${action === 'approved' ? 'Aprovado' : 'Rejeitado'} via Telegram`,
      }),
    }
  )
  return res.ok
}

// Responde ao Telegram para fechar o loading do botão
async function responderCallbackQuery(callbackQueryId: string, texto: string, token: string) {
  await fetch(`https://api.telegram.org/bot${token}/answerCallbackQuery`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      callback_query_id: callbackQueryId,
      text: texto,
      show_alert: false,
    }),
  })
}

export async function POST(request: Request) {
  const botToken = process.env.TELEGRAM_BOT_TOKEN
  const githubToken = process.env.GITHUB_TOKEN
  const owner = process.env.GITHUB_OWNER ?? 'leonardomensitieri'
  const repo = process.env.GITHUB_REPO ?? 'fuja-do-mico'

  if (!botToken || !githubToken) {
    return Response.json({ error: 'Credenciais não configuradas' }, { status: 500 })
  }

  let body: Record<string, unknown>
  try {
    body = await request.json()
  } catch {
    return Response.json({ error: 'Body inválido' }, { status: 400 })
  }

  // Telegram envia callback_query quando botão inline é clicado
  const callbackQuery = body.callback_query as {
    id: string
    data: string
    from: { first_name: string }
  } | undefined

  if (!callbackQuery) {
    // Outros updates do Telegram (mensagens, etc.) — ignorar silenciosamente
    return Response.json({ ok: true })
  }

  const { id: callbackQueryId, data: callbackData } = callbackQuery

  // callback_data formato: "approve:{run_id}:{edicao_id}" ou "reject:{run_id}:{edicao_id}"
  const partes = callbackData?.split(':')
  if (!partes || partes.length < 2) {
    await responderCallbackQuery(callbackQueryId, '❌ Dados inválidos', botToken)
    return Response.json({ ok: true })
  }

  const acao = partes[0] as 'approve' | 'reject'
  const runId = partes[1]

  if (!['approve', 'reject'].includes(acao) || !runId) {
    await responderCallbackQuery(callbackQueryId, '❌ Ação inválida', botToken)
    return Response.json({ ok: true })
  }

  const githubAcao = acao === 'approve' ? 'approved' : 'rejected'
  const sucesso = await executarAcaoGitHub(runId, githubAcao, owner, repo, githubToken)

  const textoResposta = sucesso
    ? acao === 'approve'
      ? '✅ Edição aprovada! Distribuição iniciada.'
      : '❌ Edição rejeitada.'
    : '⚠️ Erro ao processar. Tente pelo GitHub.'

  await responderCallbackQuery(callbackQueryId, textoResposta, botToken)

  return Response.json({ ok: true })
}
