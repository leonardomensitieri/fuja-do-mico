/**
 * app/api/approve/route.ts
 * ========================
 * API route para aprovação/rejeição de edição via dashboard Vercel.
 * Recebe { runId, action, edicaoId } e chama a GitHub API.
 *
 * Variáveis de ambiente (Vercel — server-side apenas):
 *   GITHUB_TOKEN   — PAT com scope repo + actions:write
 *   GITHUB_OWNER   — leonardomensitieri
 *   GITHUB_REPO    — fuja-do-mico
 */

export const runtime = 'nodejs'

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

export async function POST(request: Request) {
  const githubToken = process.env.GITHUB_TOKEN
  const owner = process.env.GITHUB_OWNER ?? 'leonardomensitieri'
  const repo = process.env.GITHUB_REPO ?? 'fuja-do-mico'

  if (!githubToken) {
    return Response.json({ error: 'GITHUB_TOKEN não configurado' }, { status: 500 })
  }

  let body: { runId?: string; action?: string }
  try {
    body = await request.json()
  } catch {
    return Response.json({ error: 'Body inválido' }, { status: 400 })
  }

  const { runId, action } = body

  if (!runId || !['approve', 'reject'].includes(action ?? '')) {
    return Response.json({ error: 'runId e action (approve|reject) são obrigatórios' }, { status: 400 })
  }

  const environmentId = await buscarEnvironmentId(owner, repo, githubToken)
  if (!environmentId) {
    return Response.json({ error: 'Environment "aprovacao-humana" não encontrado' }, { status: 404 })
  }

  const state = action === 'approve' ? 'approved' : 'rejected'
  const res = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/actions/runs/${runId}/pending_deployments`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${githubToken}`,
        Accept: 'application/vnd.github+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        environment_ids: [environmentId],
        state,
        comment: `${state === 'approved' ? 'Aprovado' : 'Rejeitado'} via Dashboard`,
      }),
    }
  )

  if (!res.ok) {
    const erro = await res.text()
    return Response.json({ error: `GitHub API: ${erro}` }, { status: res.status })
  }

  return Response.json({ ok: true, state })
}
