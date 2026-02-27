/**
 * app/api/debug/route.ts
 * =====================
 * Endpoint de diagnóstico — verifica se as env vars e o token GitHub estão ok.
 * REMOVER após validação end-to-end.
 */

export const runtime = 'nodejs'

export async function GET() {
  const githubToken = process.env.GITHUB_TOKEN
  const owner = process.env.GITHUB_OWNER ?? 'leonardomensitieri'
  const repo = process.env.GITHUB_REPO ?? 'fuja-do-mico'
  const telegramToken = process.env.TELEGRAM_BOT_TOKEN

  const resultado: Record<string, unknown> = {
    env: {
      GITHUB_TOKEN: githubToken ? `✅ configurado (${githubToken.slice(0, 8)}...)` : '❌ ausente',
      GITHUB_OWNER: owner,
      GITHUB_REPO: repo,
      TELEGRAM_BOT_TOKEN: telegramToken ? '✅ configurado' : '❌ ausente',
    },
  }

  if (!githubToken) {
    return Response.json({ ...resultado, erro: 'GITHUB_TOKEN não configurado' })
  }

  // Testa acesso ao repo
  const repoRes = await fetch(`https://api.github.com/repos/${owner}/${repo}`, {
    headers: {
      Authorization: `Bearer ${githubToken}`,
      Accept: 'application/vnd.github+json',
    },
  })
  resultado.repo_acesso = repoRes.ok
    ? `✅ ${repoRes.status}`
    : `❌ ${repoRes.status}: ${await repoRes.text()}`

  // Testa listagem de environments
  const envRes = await fetch(`https://api.github.com/repos/${owner}/${repo}/environments`, {
    headers: {
      Authorization: `Bearer ${githubToken}`,
      Accept: 'application/vnd.github+json',
    },
  })
  if (envRes.ok) {
    const data = await envRes.json()
    const envs = (data.environments ?? []).map((e: { name: string; id: number }) => ({
      name: e.name,
      id: e.id,
    }))
    resultado.environments = envs
    const aprovacao = envs.find((e: { name: string }) => e.name === 'aprovacao-humana')
    resultado.environment_aprovacao = aprovacao
      ? `✅ encontrado (id: ${aprovacao.id})`
      : `❌ não encontrado — environments disponíveis: ${envs.map((e: { name: string }) => e.name).join(', ')}`
  } else {
    resultado.environments = `❌ ${envRes.status}: ${await envRes.text()}`
  }

  return Response.json(resultado, { status: 200 })
}
