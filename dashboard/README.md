# Fuja do Mico — Dashboard

Dashboard operacional da newsletter Liga HUB Finance.
Construído com Next.js 14 + Supabase + Tailwind CSS.

## Funcionalidades

- **Kanban de edições** — visualização em tempo real via Supabase Realtime
- **Detalhe de edição** — orchestration report completo, Gates, métricas
- **Chat com IA** — Claude Sonnet responde perguntas sobre o pipeline

## Setup Local

### Pré-requisitos

- Node.js 18+
- Projeto Supabase configurado (Story 2.2)
- Chave da Anthropic API

### Instalação

```bash
cd dashboard
npm install
cp .env.local.example .env.local
```

Editar `.env.local` com os valores reais:

```env
NEXT_PUBLIC_SUPABASE_URL=https://SEU_PROJETO.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
ANTHROPIC_API_KEY=sk-ant-...
```

> **Onde obter as credenciais:**
> - Supabase URL e Anon Key: Supabase → Settings → API
> - Anthropic API Key: console.anthropic.com → API Keys

### Rodar localmente

```bash
npm run dev
# Abrir http://localhost:3000
```

## Deploy no Vercel

### Opção 1 — Interface web (recomendado)

1. Acesse [vercel.com](https://vercel.com) e conecte o repositório GitHub
2. Defina o **Root Directory** como `fuja-do-mico-gh/dashboard`
3. Adicione as variáveis de ambiente no painel Vercel:

   | Nome | Valor |
   |------|-------|
   | `NEXT_PUBLIC_SUPABASE_URL` | URL do Supabase |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Anon key do Supabase |
   | `ANTHROPIC_API_KEY` | Chave da Anthropic API |

4. Clique em **Deploy** → URL gerada automaticamente (`.vercel.app`)

### Opção 2 — CLI

```bash
npm install -g vercel
cd dashboard
vercel
# Seguir o assistente interativo
# Configurar variáveis de ambiente quando solicitado
```

### Deploy automático

Após conectar ao Vercel, todo push na branch `main` dispara um novo deploy automaticamente.

## Arquitetura

```
app/
├── page.tsx              # Kanban (Server Component → KanbanBoard client)
├── edicao/[id]/page.tsx  # Detalhe da edição
├── chat/page.tsx         # Chat com IA (Server Component → ChatInterface client)
└── api/chat/route.ts     # API Route server-side (ANTHROPIC_API_KEY aqui)

components/
├── KanbanBoard.tsx        # Board com Realtime subscription
├── EdicaoCard.tsx         # Card individual
├── EdicaoDetail.tsx       # Detalhe formatado
└── ChatInterface.tsx      # Interface de chat

lib/
└── supabase.ts            # Cliente Supabase + tipos + constantes
```

## Segurança

- A **service key** do Supabase **nunca** está neste projeto — fica exclusivamente no pipeline Python
- A **ANTHROPIC_API_KEY** só existe em variáveis server-side (sem prefixo `NEXT_PUBLIC_`)
- O dashboard usa a **anon key** com RLS habilitado — somente leitura pública das tabelas configuradas
- Sem autenticação de usuário no MVP — acesso por URL privada compartilhada com membros da Liga

## Tecnologias

| Camada | Tecnologia |
|--------|-----------|
| Framework | Next.js 14 (App Router) |
| Database | Supabase (PostgreSQL + Realtime) |
| Styling | Tailwind CSS |
| AI | Claude Sonnet via Anthropic SDK |
| Deploy | Vercel |
