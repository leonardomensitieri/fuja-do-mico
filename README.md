# 🐒 Fuja do Mico — GitHub Actions + Python
### Versão sem n8n, sem servidor, zero dependência visual

> Pipeline completo de newsletter financeira automatizada.
> Roda no GitHub. Zero servidor próprio. Zero plataforma visual.
> A aprovação humana acontece no GitHub — ou no WhatsApp (opcional).

---

## Por que essa versão existe

A versão n8n (pasta `fuja-do-mico/`) funciona, mas tem um teto:
a lógica fica presa dentro de nodes JSON difíceis de auditar.
Aqui, **cada passo é um arquivo Python legível**, comentado em português,
com o raciocínio do decision tree documentado no cabeçalho.

---

## Como funciona em 30 segundos

```
Toda segunda, 8h (Brasília)
         ↓
GitHub Actions dispara automaticamente
         ↓
Scripts Python rodam em sequência:
  01 → Coleta emails das newsletters assinadas (Gmail)
  02 → Coleta notícias dos feeds RSS
  03 → Coleta vídeos do YouTube (concorrentes)
  04 → Coleta dados financeiros da B3 (Brapi)
  05 → IA faz triagem: ALTO / MEDIO / BAIXO
  06 → IA gera a edição completa (Claude Sonnet)
  07 → Popula o template HTML com o conteúdo
  08 → Manda mensagem no WhatsApp (ou email) avisando que está pronto
         ↓
⏸ PAUSA — você recebe o aviso e precisa aprovar
         ↓
Você vai no GitHub → Actions → Review deployments → Approve
         ↓
  09 → Brevo dispara a newsletter para a lista de inscritos
```

---

## Estrutura do Repositório

```
fuja-do-mico-gh/
├── .github/
│   └── workflows/
│       └── newsletter.yml         ← Orquestrador (substitui o n8n)
├── scripts/
│   ├── 01_collect_gmail.py        ← Worker com API: Gmail
│   ├── 02_collect_rss.py          ← Worker com API: RSS feeds
│   ├── 03_collect_youtube.py      ← Worker com API: YouTube
│   ├── 04_collect_brapi.py        ← Worker com API: Brapi (B3)
│   ├── 05_triage.py               ← Clone com Heurísticas: triagem
│   ├── 06_generate.py             ← Clone com Heurísticas: geração
│   ├── 07_populate_template.py    ← Worker Script: template
│   ├── 08_notify.py               ← HUMANO: canal de notificação
│   └── 09_distribute.py           ← Worker com API: Brevo
├── prompts/
│   ├── 01-triage.md               ← Prompt de triagem (heurísticas editoriais)
│   ├── 02-content-generation.md   ← Prompt de geração de conteúdo
│   └── clones/
│       └── finance-investments/   ← Clones: Graham · Buffett · Lynch · Damodaran · Barsi
│           ├── benjamin-graham.md
│           ├── warren-buffett.md
│           ├── peter-lynch.md
│           ├── aswath-damodaran.md
│           └── luiz-barsi.md
├── templates/
│   └── newsletter.html            ← Template visual da newsletter
├── config/
│   └── rss_feeds.txt              ← URLs dos feeds RSS monitorados
├── requirements.txt
└── README.md
```

---

## Setup em 4 passos

### Passo 1 — Criar o repositório no GitHub
1. Crie um novo repositório privado no GitHub
2. Suba todos os arquivos desta pasta

### Passo 2 — Configurar o Environment de Aprovação
Este é o mecanismo que pausa o workflow e exige aprovação humana.

1. No GitHub: **Settings → Environments → New environment**
2. Nome: `aprovacao-humana`
3. Em "Required reviewers": adicione seu usuário GitHub
4. Salve

Pronto. A partir de agora, quando o workflow chegar no passo de distribuição, ele pausará automaticamente e o GitHub enviará um email para você.

### Passo 3 — Configurar os Secrets
No GitHub: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Obrigatório | Descrição |
|--------|-------------|-----------|
| `ANTHROPIC_API_KEY` | ✅ Sim | API key da Anthropic (console.anthropic.com) |
| `BREVO_API_KEY` | ✅ Sim | API key do Brevo (app.brevo.com) |
| `BREVO_LIST_ID` | ✅ Sim | ID da lista de contatos no Brevo |
| `EMAIL_REMETENTE` | ✅ Sim | Email remetente configurado no Brevo |
| `BRAPI_TOKEN` | ✅ Sim | Token do Brapi (brapi.dev) |
| `TICKERS` | ✅ Sim | Ex: `PETR4,VALE3,ITUB4,BBDC4,WEGE3` |
| `GMAIL_CREDENTIALS_JSON` | ⚡ Recomendado | Credenciais Gmail para newsletters |
| `GMAIL_REMETENTES` | ⚡ Recomendado | Ex: `newsletter@infomoney.com.br,...` |
| `YOUTUBE_API_KEY` | ⚡ Recomendado | YouTube Data API v3 |
| `TWILIO_ACCOUNT_SID` | 🔔 Opcional | Para notificação via WhatsApp |
| `TWILIO_AUTH_TOKEN` | 🔔 Opcional | Para notificação via WhatsApp |
| `TWILIO_WHATSAPP_FROM` | 🔔 Opcional | Ex: `whatsapp:+14155238886` |
| `WHATSAPP_REVISOR` | 🔔 Opcional | Ex: `whatsapp:+5511999999999` |
| `SENDGRID_API_KEY` | 🔔 Opcional | Para notificação via email (fallback) |
| `EMAIL_REVISOR` | 🔔 Opcional | Email para notificação de revisão |

> **Nota:** Se nenhum canal de notificação (WhatsApp/email) estiver configurado,
> o GitHub Actions ainda enviará email automático para os reviewers do environment.
> A aprovação sempre funciona — a notificação personalizada é opcional.

### Passo 4 — Ativar o workflow
1. Vá em **Actions** no repositório
2. Clique em "Newsletter — Fuja do Mico"
3. Clique em "Enable workflow"

O pipeline rodará automaticamente toda segunda às 8h (Brasília).
Para testar antes: clique em **"Run workflow"** e rode manualmente.

---

## Como é o fluxo de aprovação

Quando a edição estiver pronta, você receberá:
- **WhatsApp** (se configurado): mensagem com link direto para aprovação
- **Email do GitHub** (sempre): notificação automática de revisão pendente

Para aprovar:
1. Acesse o link recebido (ou vá direto em GitHub → Actions)
2. Clique na execução pendente
3. Clique em **"Review deployments"**
4. Selecione **"aprovacao-humana"**
5. Clique **"Approve and deploy"**

O Brevo dispara a newsletter imediatamente após a aprovação.

---

## Para usar com OpenClaw (WhatsApp nativo)
Se você preferir a aprovação pelo WhatsApp sem Twilio,
instale o OpenClaw numa VPS com o canal WhatsApp configurado.
No `08_notify.py`, adicione um step que chama o webhook do OpenClaw
passando a URL de aprovação. O OpenClaw entrega a mensagem no WhatsApp
e você responde lá — mas a aprovação final ainda acontece no GitHub.

---

## Rodando localmente (para testar)
```bash
# Instalar dependências
pip install -r requirements.txt

# Criar pasta de dados
mkdir data output

# Configurar variáveis (crie um arquivo .env)
export ANTHROPIC_API_KEY="sua-chave-aqui"
export BRAPI_TOKEN="seu-token-aqui"
export TICKERS="PETR4,VALE3,ITUB4"

# Rodar cada script manualmente
python scripts/02_collect_rss.py      # Não precisa de credenciais
python scripts/04_collect_brapi.py    # Precisa de BRAPI_TOKEN
python scripts/05_triage.py           # Precisa de ANTHROPIC_API_KEY
python scripts/06_generate.py         # Precisa de ANTHROPIC_API_KEY
python scripts/07_populate_template.py
# Abra output/newsletter_final.html no browser para ver o resultado
```

---

## Custos estimados por edição
| Serviço | Custo |
|---------|-------|
| GitHub Actions | Gratuito (2.000 min/mês no plano free) |
| Claude API (triagem + geração) | ~$0.05–0.15 por edição |
| Brapi | Gratuito |
| YouTube API | Gratuito (dentro da quota) |
| Brevo | Gratuito até 300 emails/dia |
| Twilio WhatsApp | ~$0.005 por mensagem |
| **Total por edição** | **~$0.10–0.20** |

---

*Fuja do Mico — Liga Financeira · Conteúdo educativo, não recomendação de investimento.*
