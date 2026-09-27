# Painel em Power BI

Os mesmos dados do projeto num modelo estrela, prontos para o Power BI Desktop.

| Arquivo | O que é |
|---|---|
| `dados/*.csv` | Tabelas do modelo, geradas por `python -m src.powerbi` (e atualizadas pelo `src.atualizar`) |
| `medidas.dax` | Todas as medidas DAX, prontas para colar |
| `tema_ufc.json` | Tema escuro com as cores dos gráficos do projeto |

Os CSVs usam `;` e vírgula decimal, o formato que o Power BI em português lê direto.

## O modelo

```
                 dim_calendario
                       │ data
                       ▼
dim_lutador ◄── fato_desempenho ──► dim_luta
  lutador_id    (lutador × luta)     luta_id
      ▲                                  ▲
      └─────────── fato_round ───────────┘
               (lutador × luta × round)
```

- **fato_desempenho** (3.674 linhas): uma linha por lutador em cada luta. Traz o resultado (`vitoria`, `derrota`, `empate` em 0/1), as estatísticas, a duração da luta (para medidas por minuto), a idade na data da luta e o `adversario_id`.
- **fato_round** (8.910 linhas): as mesmas estatísticas por round.
- **dim_luta** (1.837 linhas): evento, data, categoria em português, método e `metodo_grupo` (Nocaute / Finalização / Decisão / Outro), round, duração, árbitro, cinturão e bônus.
- **dim_lutador** (964 linhas): nome, altura, envergadura, base em português e nascimento.
- **dim_calendario**: um dia por linha, de 2023 a 2026, com ano, trimestre e mês.

## Passo a passo

### 1. Importar os dados
1. **Página Inicial > Obter dados > Texto/CSV**. Importe os 5 arquivos de `dados/`, um de cada vez, com **Carregar**.
2. Confira os tipos no **Transformar dados**: as colunas `data` e `nascimento` como **Data**, `duracao_min`, `altura_cm`, `envergadura_cm` e `idade_na_luta` como **Número decimal**. As demais já chegam certas.

### 2. Relacionamentos
Em **Exibição de modelo**, deixe exatamente estes 5, todos de muitos para um com filtro em direção única. Apague qualquer outro que o Power BI tenha criado sozinho, como `dim_luta[data]` com `dim_calendario`, que deixaria dois caminhos até o calendário.

| De (muitos) | Para (um) |
|---|---|
| `fato_desempenho[luta_id]` | `dim_luta[luta_id]` |
| `fato_desempenho[lutador_id]` | `dim_lutador[lutador_id]` |
| `fato_desempenho[data]` | `dim_calendario[data]` |
| `fato_round[luta_id]` | `dim_luta[luta_id]` |
| `fato_round[lutador_id]` | `dim_lutador[lutador_id]` |

Depois:
- Selecione `dim_calendario` e use **Marcar como tabela de datas**, com a coluna `data`.
- Em `dim_calendario`, **Classificar por coluna**: `mes` por `mes_num` e `ano_mes` por `ano_mes_ordem`.
- Oculte da exibição de relatório as colunas de id (`luta_id`, `lutador_id`, `adversario_id`, `evento_id`).

### 3. Medidas e parâmetro
1. **Modelagem > Nova tabela**: `Mínimo de lutas = GENERATESERIES ( 1, 12, 1 )`.
2. Selecione `fato_desempenho` e crie cada medida de `medidas.dax` com **Nova medida**, uma por vez (cole a linha `Nome = expressão`). As duas últimas são de round a round: crie-as em `fato_round`.
3. Formate as medidas que são percentuais (as que começam com `%`, as de taxa e as de precisão) como **Porcentagem**, com uma casa decimal.

### 4. Tema
**Exibição > Temas > Procurar temas** e escolha `tema_ufc.json`.

### 5. Páginas sugeridas

**Visão geral**
- Cartões: `Lutas`, `Eventos`, `Lutadores`, `% Antes da decisão`.
- Gráfico de barras: eixo `dim_luta[metodo_grupo]`, valor `Lutas`.
- Gráfico de colunas agrupadas: eixo `dim_calendario[ano]`, valores `% Nocaute`, `% Finalização` e `% Decisão`.
- Segmentações: `dim_calendario[ano]` e `dim_luta[categoria]`.

**Ranking**
- Segmentações: `dim_luta[categoria]`, `dim_lutador[base]` e `'Mínimo de lutas'[Value]` (seleção única).
- Gráfico de barras: eixo `dim_lutador[nome]`, valor `Taxa de vitória (ranking)`. No painel de filtros, filtro **N superior** = 10 por essa mesma medida. Na categoria, contam só as lutas feitas nela.
- Tabela ao lado: `nome`, `Cartel`, `Participações`, `Golpes sig. por minuto` e `Precisão de golpes`.

**Perfil do lutador**
- Segmentação de `dim_lutador[nome]` com pesquisa e seleção única.
- Cartões: `Cartel`, `Taxa de vitória`, `Vitórias por nocaute`, `Vitórias por finalização`.
- Gráfico de barras agrupadas ou tabela com o lutador e a média de todos lado a lado: `Golpes sig. por minuto` × `Média geral - golpes sig. por minuto` (e o mesmo para precisão, quedas e controle).
- Gráfico de linhas: eixo `fato_round[round]`, valores `Golpes sig. por round` e `Média geral - golpes sig. por round`.

**Lutas**
- Barras empilhadas: eixo `dim_luta[categoria]`, valores `% Nocaute` e `% Finalização`, classificadas pelo total. Filtre para excluir `Peso casado` e `Pena (fem.)`, como no gráfico do site.
- Tabela com linhas `dim_luta[bonus_luta]` (0/1) e colunas `Lutas`, `Golpes sig. por minuto`, `% Decisão` e `Duração média (min)`. É a comparação da Luta da Noite, e dá para repetir com `disputa_titulo`.

### 6. Salvar
Salve como `powerbi/ufc.pbix` e exporte um print de cada página para `powerbi/prints/`. Os prints vão para o README do projeto.

## Conferência
Com o painel sem filtros, os números devem bater com o resto do projeto: 1.837 lutas, 149 eventos, 964 lutadores, 49,5% das lutas antes da decisão, 32,5% por nocaute (597 lutas) e Luta da Noite em 5,5% (101 lutas).
