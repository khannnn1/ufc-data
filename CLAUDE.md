# UFC Data — Contexto do Projeto

Projeto de portfólio de estatísticas de MMA/UFC (estilo @DataFut), cobrindo
scraping, limpeza e visualização de dados em Python. Objetivo: portfólio para
transição de carreira para Análise de Dados / BI.

Repositório: github.com/khannnn1/ufc-data (privado)
Site publicado (público): https://khannnn1.github.io/ufc-data/

## Stack
Python 3.14 em venv isolado. Bibliotecas: requests, beautifulsoup4, pandas,
numpy, matplotlib, seaborn, jupyter, ipykernel, selenium, lxml.

## Estrutura de diretórios
```
ProjetoUFC/
├── data/
│   ├── raw/          # dados brutos do scraper (não versionado)
│   └── processed/    # dados limpos (não versionado)
├── figures/           # gráficos exportados (.png)
├── notebooks/
│   ├── 00_teste_ambiente.ipynb
│   ├── 01_scrapper_test_luta.ipynb   # coleta e limpeza
│   └── 02_visualizacao.ipynb          # geração dos gráficos
├── src/
│   ├── scraper.py       # coleta (Selenium + BeautifulSoup)
│   ├── limpeza.py        # tratamento de dados
│   ├── visualizacao.py   # estilo e funções de plotagem
│   └── config.py         # constantes (COLUNAS_OF, COLUNAS_PCT)
├── index.html          # página estática publicada via GitHub Pages
├── requirements.txt
└── README.md
```

## Padrão visual (dark mode / editorial)
Definido em `src/visualizacao.py`:
- Fundo `#0d0d0d`, texto `#f5f5f5`, bordas removidas, grid sutil `#2a2a2a`
- Cores de destaque: `COR_VERMELHO = "#e63946"`, `COR_AZUL = "#457b9d"`
- Gráficos de barra horizontal, sem eixo numérico, valores escritos na ponta
  da barra (funções `estilizar_grafico` e `adicionar_valores_barras`)
- `aplicar_estilo_dark()` deve ser chamado ANTES de `plt.subplots()` —
  `plt.rcParams` não é retroativo a uma figura já criada

## Descobertas técnicas de scraping (ufcstats.com)
- `requests` puro recebe página de verificação anti-bot (exige JavaScript).
  Solução: Selenium (`webdriver.Chrome`, `--headless=new`,
  `--disable-blink-features=AutomationControlled`, user-agent customizado),
  lendo `driver.page_source` depois do JS rodar.
- Mapeamento HTML de uma luta:
  - Lutador: `div.b-fight-details__person` (nome em
    `a.b-link.b-fight-details__person-link`, resultado W/L em
    `i.b-fight-details__person-status`)
  - Método/round/tempo/referee: `p.b-fight-details__text`
  - Tabelas: `td.b-fight-details__table-col` com dois
    `p.b-fight-details__table-text` (um por lutador) — `pd.read_html` NÃO
    separa isso corretamente, precisa de parsing manual com BeautifulSoup
  - Página de luta tem 4 tabelas: Totals resumo, Totals por round,
    Sig. Strikes resumo, Sig. Strikes por round. A tabela "Totals por round"
    tem cabeçalho HTML sujo (contaminado por abas de navegação) — headers
    fixados manualmente no código.
- Página de evento: lutas em `tr.b-fight-details__table-row`, URL da luta no
  atributo `data-link` (não é um `<a href>`)
- Listagem de eventos: `a.b-link.b-link_style_black`; paginação simples via
  `?page=N` na URL (sem JavaScript)
- Loops de coleta em lote sempre com `try/except` por item, para não
  interromper tudo por uma falha isolada. `extrair_varios_eventos` salva
  incrementalmente em CSV (`mode="a"`) para resistir a quedas de internet.

## Módulos em src/
- **scraper.py**: `criar_driver`, `extrair_tabela_por_lutador`,
  `extrair_dados_luta(url, driver)`, `extrair_urls_evento`, `extrair_evento`,
  `extrair_varios_eventos(eventos, driver, limite)`,
  `extrair_eventos_multiplas_paginas(driver, num_paginas)`
- **limpeza.py**: `separar_landed_attempted` (split "X of Y" em
  landed/attempted), `limpar_percentual` (remove %, trata "---" como NaN),
  `tempo_para_segundos` (formato "M:SS" -> segundos)
- **visualizacao.py**: `aplicar_estilo_dark`, `estilizar_grafico`,
  `adicionar_valores_barras`, `COR_VERMELHO`, `COR_AZUL`
- **config.py**: `COLUNAS_OF`, `COLUNAS_PCT`

Os notebooks importam esses módulos via:
```python
import sys
sys.path.append("..")
from src.scraper import ...
from src.limpeza import ...
from src.visualizacao import ...
from src.config import COLUNAS_OF, COLUNAS_PCT
```

## Dados
Escopo definido: recorte de ~149 eventos recentes do UFC (não o histórico
completo de 600+), priorizando qualidade de análise sobre volume.

Datasets finais processados:
- `data/processed/dataset_final_resumo_limpo.csv` — (3674, 24), uma linha
  por lutador-luta
- `data/processed/dataset_final_round_limpo.csv` — (8910, 20), uma linha
  por lutador-luta-round

Colunas principais do dataset resumo (ATENÇÃO aos nomes exatos, em inglês,
sem acento): `Fighter`, `KD`, `Sig. str. %`, `Td %`, `Sub. att`, `Rev.`,
`Resultado` (W/L), `Method` (ex: "Decision - Unanimous", "KO/TKO",
"Submission"), `Final_Round`, `Time`, `Referee`, `Fight_URL`, `Event_URL`,
`Event_Name`, e pares `_landed`/`_attempted` para Sig_str, Total_str, Td,
Head, Body, Leg, Distance, Clinch, Ground, além de `Ctrl_seconds`.
O dataset por round tem as mesmas colunas + `Round` (1-5), sem as colunas
de metadados da luta (Method, Time, Referee etc, que só existem no resumo).

Casos de borda conhecidos: valores "---" nas colunas de percentual (Sig.
str. %, Td %) indicam zero tentativas, tratados como NaN (não 0%).

## Gráficos já criados (figures/)
1. `top10_kd.png` — top 10 por Knockdowns
2. `top10_ctrl.png` — top 10 por tempo de controle (minutos)
3. `metodos_vitoria.png` — distribuição de métodos de vitória
4. `top10_precisao.png` — top 10 por precisão de golpes (filtro mín. 50 tentativas)
5. `comparacao_*.png` — comparação "cara a cara" entre 2 lutadores (função
   `comparar_lutadores(nome1, nome2, df)`), usando MÉDIAS por luta (não somas,
   que distorceriam por volume de amostra desigual) e mostrando o nº de lutas
   de cada um na legenda
6. `evolucao_golpes_por_round.png` — gráfico de linha, média de golpes por
   round (tende a aumentar por viés de sobrevivência dos dados: rounds
   avançados só existem em lutas de decisão/atrito)
7. `top10_vitorias.png` — top 10 por número de vitórias no período (favorece
   quem lutou mais vezes no recorte, não necessariamente taxa de vitória)
8. `top10_finalizacoes.png` — top 10 por finalizações via submission
9. `top10_nocautes.png` — top 10 por vitórias via KO/TKO (barras em azul)
10. `vencedores_vs_perdedores.png` — médias por luta de W vs L (golpes sig.,
    quedas, controle, tent. de finalização, KD), um painel por métrica
    (escalas diferentes), com a razão "N× mais" no título de cada painel;
    exclui empates (D) e NC
11. `volume_vs_precisao.png` — dispersão: golpes sig. TENTADOS por minuto
    de luta (duração = (Final_Round-1)*300 + Time em segundos) × precisão,
    lutadores com >= 4 lutas, medianas tracejadas como quadrantes, extremos
    rotulados em vermelho. Único gráfico com eixos numéricos visíveis

## Workflow de Git
Usamos Git Flow: `main` (estável) + `develop` (integração) + `feature/*`
(uma por funcionalidade). Fluxo padrão:
```bash
git checkout develop
git checkout -b feature/nome-da-feature
# ... trabalho ...
git add .
git commit -m "mensagem"
git checkout develop
git merge feature/nome-da-feature
git push origin develop
# periodicamente, consolidar:
git checkout main
git merge develop
git push origin main
```

## Próximos passos / direção atual
Projeto já é considerado pronto para uso em currículo como está. Trabalho
atual é por aprendizado: continuar criando gráficos, e depois evoluir a
página estática (`index.html`, hoje com imagens PNG fixas) para uma versão
**interativa**, permitindo ao visitante criar os próprios gráficos e comparar
lutadores arbitrariamente. Isso vai exigir, futuramente:
- Exportar os dados (ou um subconjunto agregado) como JSON/CSV consumível
  pelo navegador, em vez de só imagens estáticas
- Introduzir JavaScript no projeto pela primeira vez, provavelmente com uma
  lib de gráficos como Chart.js
