# skill: financial-data

## Propósito

Acesso a dados financeiros de ações da B3 e do Tesouro Direto para enriquecer análises,
tabelas comparativas e perspectivas de investidores clones.

Duas APIs disponíveis com papéis complementares: **Brapi** (cobertura ampla, cotações) e
**Fintz** (profundidade: DY, proventos, endividamento, Tesouro Direto).

---

## Quando ativar dados financeiros

### Gatilhos — ativar se o conteúdo triado contiver qualquer um destes temas

```
VALUATION:   P/L, P/VP, EV/EBITDA, P/EBITDA, preço/valor, múltiplos, valuation,
             margem de segurança, desconto, valor intrínseco, PEG ratio

RENTABILIDADE: ROE, ROA, ROIC, margens, margem líquida, margem EBITDA,
               retorno sobre capital, lucratividade

DIVIDENDOS:  DY, dividend yield, dividendos, JCP, proventos, renda passiva,
             yield on cost, carteira de dividendos, Barsi

ENDIVIDAMENTO: dívida, alavancagem, dívida/PL, dívida/EBITDA, liquidez,
               cobertura de juros, balanço patrimonial

MERCADO:     cotação, preço atual, variação, máxima/mínima 52 semanas,
             resultado trimestral, lucro por ação, market cap

RENDA FIXA:  Tesouro Direto, IPCA+, Selic, Prefixado, taxa livre de risco,
             renda fixa vs variável, NTN-B, LFT

TICKERS:     qualquer código B3 identificado no conteúdo (ex: PETR4, VALE3, MGLU3...)
```

### Não ativar para

```
- História de investidores sem análise de ativos atuais
- Filosofia/psicologia do investimento pura
- Macroeconomia sem ações específicas mencionadas
- Educação conceitual sem dados de mercado
- Conteúdo sobre cripto, day trade, análise técnica pura
```

---

## Mapeamento clone → dados necessários

Ao decidir incluir a perspectiva de um investidor clone, consultar a seção correspondente:

### Benjamin Graham
```
OBRIGATÓRIO (Brapi ou Fintz):
  pl                    → P/L — critério: < 15x (defensivo) | < 25x (máximo)
  pvp                   → P/VP — critério: < 1,5x
  pl × pvp combinado    → critério: < 22,5

OBRIGATÓRIO (Fintz):
  divida_bruta_pl       → Dívida Bruta/PL — critério: < 100% industrial | < 200% utilities
  proventos_12m         → histórico de dividendos — critério: consistência (mínimo 20 anos ideal)

COMPLEMENTAR:
  lpa                   → Lucro por ação (crescimento 10 anos)
  margem_liquida        → tendência de margens
```

### Warren Buffett
```
OBRIGATÓRIO (Brapi):
  roe                   → ROE — critério: > 15% sustentado por 10+ anos
  margem_liquida        → consistente e preferencialmente crescente

OBRIGATÓRIO (Fintz):
  roic                  → ROIC — critério: > custo de capital (~12%)
  divida_liq_ebitda     → Dívida Líquida/EBITDA — critério: < 3x
  ev_ebitda             → contexto de valuation

COMPLEMENTAR:
  margem_ebitda         → qualidade operacional
  crescimento_lucro     → (Brapi) sustentabilidade do crescimento
```

### Luiz Barsi
```
OBRIGATÓRIO (Fintz):
  dy                    → Dividend Yield — critério: > 6% a.a.
  proventos_12m         → histórico de pagamentos — consistência e valor acumulado
  proventos_total_12m   → proventos pagos nos últimos 12 meses

COMPLEMENTAR (Brapi):
  preco                 → cotação atual (para calcular yield on cost)
  setor                 → utilities, bancos, seguros (setores preferidos)
  margem_liquida        → saúde financeira da empresa
```

### Peter Lynch
```
OBRIGATÓRIO (Brapi):
  pl                    → P/L — para calcular PEG Ratio
  peg                   → PEG Ratio direto — critério: < 1,0 (ideal) | < 1,5 (tolerável)
  crescimento_lucro     → taxa de crescimento de lucros

COMPLEMENTAR (Fintz):
  divida_bruta_pl       → endividamento (Lynch evita empresas muito alavancadas)
  margem_liquida        → tendência de margens
```

### Aswath Damodaran
```
OBRIGATÓRIO (Fintz):
  roic                  → ROIC vs. custo de capital — cria ou destrói valor?
  ev_ebitda             → múltiplo de valuation contextualizado
  margem_ebitda         → eficiência operacional

OBRIGATÓRIO (Brapi):
  fcl                   → Fluxo de Caixa Livre — positivo e crescente
  crescimento_receita   → crescimento sustentável

COMPLEMENTAR:
  margem_bruta          → tendência de pricing power
  roa                   → retorno sobre ativos
```

---

## Campos completos disponíveis

### Brapi — 1.842 tickers B3

**Identificação:**
| Campo | Descrição |
|-------|-----------|
| `ticker` | Código B3 (ex: PETR4) |
| `nome` | Nome completo da empresa |
| `setor` | Setor de atuação |
| `industria` | Subsetor/indústria |
| `descricao` | Descrição do negócio |

**Cotação:**
| Campo | Descrição |
|-------|-----------|
| `preco` | Preço atual de mercado (R$) |
| `variacao_pct` | Variação percentual no dia |
| `min_52s` | Mínima das últimas 52 semanas |
| `max_52s` | Máxima das últimas 52 semanas |

**Valuation:**
| Campo | API original | Descrição |
|-------|-------------|-----------|
| `pl` | `trailingPE` | P/L — Preço sobre Lucro |
| `pvp` | `priceToBook` | P/VP — Preço sobre Valor Patrimonial |
| `peg` | `pegRatio` | PEG Ratio (P/L ÷ crescimento) |
| `lpa` | `trailingEps` | Lucro Por Ação (trailing 12m) |
| `vpa` | `bookValue` | Valor Patrimonial Por Ação |
| `market_cap` | `marketCap` | Capitalização de mercado |

**Rentabilidade:**
| Campo | API original | Descrição |
|-------|-------------|-----------|
| `roe` | `returnOnEquity` | Retorno sobre Patrimônio Líquido |
| `roa` | `returnOnAssets` | Retorno sobre Ativos |
| `margem_liquida` | `profitMargins` | Margem Líquida |
| `margem_bruta` | `grossMargins` | Margem Bruta |
| `fcl` | `freeCashflow` | Fluxo de Caixa Livre |
| `lucro_liquido` | `netIncomeToCommon` | Lucro Líquido (R$) |
| `receita` | `totalRevenue` | Receita Total (R$) |

**Crescimento:**
| Campo | API original | Descrição |
|-------|-------------|-----------|
| `crescimento_lucro` | `earningsGrowth` | Crescimento de Lucros (YoY) |
| `crescimento_receita` | `revenueGrowth` | Crescimento de Receita (YoY) |

---

### Fintz — 533 tickers B3 + Tesouro Direto

**Indicadores por ticker** (endpoint: `/bolsa/b3/avista/indicadores/por-ticker/`):

**Valuation:**
| Campo normalizado | Indicador Fintz | Descrição |
|------------------|----------------|-----------|
| `pl` | `P_L` | P/L — Preço sobre Lucro |
| `pvp` | `P_VP` | P/VP — Preço sobre Valor Patrimonial |
| `dy` | `DividendYield` | Dividend Yield — **ausente no Brapi gratuito** |
| `ev_ebitda` | `EV_EBITDA` | EV/EBITDA |
| `p_ebitda` | `P_EBITDA` | Preço/EBITDA |
| `p_ebit` | `P_EBIT` | Preço/EBIT |
| `p_receita` | `P_SR` | Preço/Receita Líquida |
| `p_ativos` | `P_Ativos` | Preço/Ativos Totais |
| `lpa` | `LPA` | Lucro Por Ação |
| `vpa` | `VPA` | Valor Patrimonial Por Ação |
| `valor_mercado` | `ValorDeMercado` | Capitalização de mercado |
| `ev` | `EV` | Enterprise Value |

**Rentabilidade:**
| Campo normalizado | Indicador Fintz | Descrição |
|------------------|----------------|-----------|
| `roe` | `ROE` | Retorno sobre Patrimônio Líquido |
| `roa` | `ROA` | Retorno sobre Ativos |
| `roic` | `ROIC` | Retorno sobre Capital Investido |
| `margem_bruta` | `MargemBruta` | Margem Bruta |
| `margem_ebit` | `MargemEBIT` | Margem EBIT |
| `margem_ebitda` | `MargemEBITDA` | Margem EBITDA |
| `margem_liquida` | `MargemLiquida` | Margem Líquida |
| `giro_ativos` | `GiroAtivos` | Giro dos Ativos |

**Endividamento:**
| Campo normalizado | Indicador Fintz | Descrição |
|------------------|----------------|-----------|
| `divida_bruta_pl` | `DividaBruta_PatrimonioLiquido` | Dívida Bruta / PL |
| `divida_liq_pl` | `DividaLiquida_PatrimonioLiquido` | Dívida Líquida / PL |
| `divida_liq_ebit` | `DividaLiquida_EBIT` | Dívida Líquida / EBIT |
| `divida_liq_ebitda` | `DividaLiquida_EBITDA` | Dívida Líquida / EBITDA |
| `cobertura_juros_ebitda` | `EBITDA_DespesasFinanceiras` | Cobertura de Juros (EBITDA) |
| `cobertura_juros_ebit` | `EBIT_DespesasFinanceiras` | Cobertura de Juros (EBIT) |
| `liquidez_corrente` | `LiquidezCorrente` | Liquidez Corrente |
| `passivos_ativos` | `Passivos_Ativos` | Passivo Total / Ativos |
| `pl_ativos` | `PatrimonioLiquido_Ativos` | PL / Ativos |

**Proventos** (endpoint: `/bolsa/b3/avista/proventos/`):
| Campo | Descrição |
|-------|-----------|
| `data_com` | Data COM (quem tem na carteira recebe) |
| `data_pagamento` | Data de pagamento efetivo |
| `valor` | Valor por ação (R$) |
| `tipo` | `"DIVIDENDO"` ou `"JRS CAP PROPRIO"` |

**Tesouro Direto** (endpoint: `/titulos-publicos/tesouro/`):
| Campo | Descrição |
|-------|-----------|
| `codigo` | Código do título (ex: NTNB20290515) |
| `nome` | Nome completo (ex: Tesouro IPCA+ 2029) |
| `vencimento` | Data de vencimento |
| `investivel` | Se está disponível para compra hoje |

---

## Como chamar on-demand (durante a geração)

Quando o agente de conteúdo decide incluir dados de um ticker específico que não estava
no batch pré-carregado, pode importar e chamar diretamente:

```python
# Busca múltiplos básicos de um ticker (Brapi)
from scripts.collect_brapi import buscar_tickers
dados = buscar_tickers(["MGLU3"], token=os.environ["BRAPI_TOKEN"])

# Busca indicadores completos + proventos (Fintz)
from scripts.collect_fintz import buscar_dados_fintz
dados = buscar_dados_fintz(["MGLU3"], token=os.environ["FINTZ_API_KEY"])
```

---

## Protocolo de escalação humana

Quando o agente precisar passar a decisão para o humano (via Telegram), incluir
no contexto da notificação:

```
Dados financeiros consultados nesta edição:
  - Tickers: [lista dos tickers buscados]
  - APIs: Brapi + Fintz / apenas Brapi / nenhuma
  - Campos ausentes: [campos que o clone precisava mas não tinham dados]

Se quiser que eu consulte dados de um ticker específico antes do envio,
responda com o código (ex: "MGLU3") e eu atualizo a edição.
```

---

## Regras de uso no conteúdo

- Dados de mercado **mudam diariamente** — sempre indicar a data de referência
- Múltiplos financeiros variam por metodologia — citar a fonte (Brapi/Fintz)
- Não apresentar dados como recomendação de investimento
- Valores percentuais (DY, ROE): multiplicar por 100 antes de exibir ao leitor
- Tabelas com cores semânticas: verde `#1a7f37` (bom), amarelo `#9a6700` (neutro), vermelho `#cf222e` (atenção)
