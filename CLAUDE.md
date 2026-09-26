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
│   ├── 02_visualizacao.ipynb          # geração dos gráficos
│   └── 03_sql.ipynb                   # mesmas perguntas em SQL + conferência com Pandas
├── sql/
│   ├── schema.sql       # esquema do banco SQLite (4 tabelas)
│   └── consultas.sql    # consultas nomeadas ("-- nome: x")
├── src/
│   ├── scraper.py       # coleta (Selenium + BeautifulSoup)
│   ├── limpeza.py        # tratamento de dados
│   ├── visualizacao.py   # estilo e funções de plotagem
│   ├── exportar.py       # gera dados/lutadores.json para o site interativo
│   ├── banco.py          # monta data/ufc.db (SQLite) a partir dos CSVs limpos
│   ├── consultas.py      # lê e executa as consultas de sql/consultas.sql
│   └── config.py         # constantes (COLUNAS_OF, COLUNAS_PCT)
├── dados/
│   └── lutadores.json  # totais por lutador (VERSIONADO: o site lê daqui)
├── js/
│   └── interativo.js   # lógica da página interativa (Chart.js)
├── index.html          # página estática publicada via GitHub Pages
├── interativo.html     # comparador de lutadores + montador de rankings
├── requirements.txt
└── README.md
```

## Padrão visual (dark mode / editorial)
Definido em `src/visualizacao.py`:
- Fundo `#0d0d0d`, texto `#f5f5f5`, bordas removidas, grid sutil `#2a2a2a`
- Cores de destaque: `COR_VERMELHO = "#e63946"`, `COR_AZUL = "#457b9d"`;
  `COR_AMARELO = "#c08a1e"` como terceira cor quando há 3 grupos (validada
  para dark mode e daltonismo; cinza e amarelos mais claros não passaram)
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
  `adicionar_valores_barras`, `COR_VERMELHO`, `COR_AZUL`, `COR_AMARELO`
- **config.py**: `COLUNAS_OF`, `COLUNAS_PCT`
- **exportar.py**: `agregar_lutadores(df)`, `exportar_lutadores()` — gera
  `dados/lutadores.json` para o site interativo
- **banco.py**: `montar_tabelas(resumo, por_round)`, `criar_banco()` —
  recria `data/ufc.db` (não versionado, `data/*.db` no .gitignore);
  `python -m src.banco` na raiz
- **consultas.py**: `carregar_consultas()` ({nome: sql}),
  `consultar(nome)` (DataFrame)

## Banco SQL (SQLite)
Tabelas: `eventos` (evento_id, url, nome) → `lutas` (luta_id, url,
evento_id, metodo, round_final, tempo_final, duracao_seg, arbitro) →
`desempenho` (PK luta_id+lutador; resultado W/L/D/NC; kd, sig_acertados,
sig_tentados, total_*, quedas, quedas_tentadas, tent_finalizacao,
reversoes, controle_seg, cabeca/corpo/perna, distancia/clinch/chao) →
`desempenho_round` (mesmas estatísticas + round, sem resultado).
`evento_id` segue a ordem da coleta: 1 = mais recente (UFC 331), 149 = mais
antigo (UFC 287) — usado para ordenar lutas no tempo (não há coluna de data).
Consultas novas vão em `sql/consultas.sql` com `-- nome: x` na linha acima.

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
3. `metodos_vitoria.png` — distribuição de métodos de vitória, uma linha
   por luta (`drop_duplicates("Fight_URL")`; antes contava cada luta 2×)
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
12. `top10_taxa_vitoria.png` — top 10 por taxa de vitória, W / (W+L+D), NC
    excluído, mín. 6 lutas (com menos o top 10 vira só invictos), desempate
    pelo nº de vitórias; cartel "V-D" escrito na ponta da barra
13. `round_final_por_metodo.png` — barras agrupadas: % de nocautes (azul,
    inclui "TKO - Doctor's Stoppage") e de finalizações (vermelho) por round
    final, uma linha por luta (drop_duplicates em Fight_URL), rounds 4 e 5
    agrupados; percentual dentro de cada método
14. `alvo_dos_golpes.png` — barras 100% empilhadas cabeça/corpo/perna
    (vermelho/azul/amarelo): média geral + 3 lutadores mais especializados
    em cada alvo (mín. 150 golpes sig. acertados no período)
15. `origem_dos_golpes.png` — mesmo formato do 14, para distância/clinch/
    chão; resumo no topo com todos, vencedores (W) e perdedores (L) —
    vencedores acertam 13% no chão vs 3,5% dos perdedores
16. `top10_precisao_quedas.png` — Td_landed / Td_attempted, mín. 15
    tentativas E 3 lutas (sem o 2º filtro entra quem tentou muito numa luta
    só); "X de Y" na ponta da barra; linha tracejada na média geral (36%)
17. `arbitros_finalizacoes.png` — 10 árbitros com mais lutas, % das lutas
    encerradas antes da decisão (KO/TKO, TKO médico, submission), uma linha
    por luta; aviso no rodapé: reflete as lutas recebidas, não o árbitro

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
atual é por aprendizado. `index.html` segue com os PNGs fixos e linka para
`interativo.html`, a versão **interativa** (1ª versão):
- `python -m src.exportar` (na raiz, com o venv) regenera
  `dados/lutadores.json` a partir dos datasets limpos (resumo e por round). O JSON guarda
  TOTAIS por lutador (chaves curtas: n, w, l, d, nc, ko, subw, kd, sl, sa,
  tl, ta, tdl, tda, sub, ctrl, head, body, leg, dist, clinch, ground, dur);
  médias e percentuais são calculados no JS (`METRICAS` em
  `js/interativo.js`). Rodar de novo sempre que o dataset mudar.
- Comparador: 2 lutadores (datalist com autocomplete), cartões com cartel e
  um painel Chart.js por métrica (escalas diferentes, sem eixo único).
  O `<datalist>` filtra pelo texto do campo, então com um nome preenchido
  só ele aparece na lista: por isso `configurarCampoLutador` esvazia o
  campo no foco (nome vira placeholder) e restaura ao sair sem escolher.
  Redesenha no evento `input` quando o texto bate com um nome.
- Rankings: métrica + mín. de lutas + top N; clique na barra leva o lutador
  ao comparador; tabela equivalente em `<details>`. Precisões exigem
  amostra mínima de tentativas (`requisito` em cada métrica).
- Round a round (`#rounds`): cada lutador no JSON tem `r` =
  `[[round, rounds, sl, sa, tdl, tda, ctrl, kd], ...]` (lista compacta,
  ordem fixa em `COLUNAS_ROUND` de `src/exportar.py` e em `roundsDe` no JS —
  mudar os dois juntos). Linha dos 2 lutadores do comparador + média geral
  tracejada; métrica em `METRICAS_ROUND`, na URL como `rm`. Tooltip mostra
  quantos rounds entram em cada média (4º/5º têm amostra pequena).
- Dispersão volume × precisão (`#dispersao`): mesmo recorte do PNG (4+
  lutas, volume por minuto). Os 2 lutadores do comparador aparecem
  destacados (azul/vermelho, com nome) — `desenharComparador` chama
  `desenharDispersao`, então link compartilhável também destaca. Plugin
  `guiasDispersao` desenha medianas, quadrantes e nomes. Clique leva ao
  comparador; destacado com <4 lutas aparece com aviso na nota.
- Link compartilhável: o estado vai para a URL (`?a=&b=&m=&min=&top=&rm=`, via
  `history.replaceState`, sem poluir o histórico) e é lido na abertura por
  `lerEstadoDaUrl` (valores inválidos caem em `PADROES`). Botões "Copiar
  link" por seção (âncora `#comparador` / `#ranking`); título da aba mostra
  "A × B". Se entrar um parâmetro novo, atualizar ler/atualizar juntos.
- **Cache**: o GitHub Pages guarda arquivos por ~10 min. A tag do script em
  `interativo.html` tem `?v=N`: AUMENTAR o N a cada mudança em
  `js/interativo.js`. O JSON é buscado com `cache: "no-cache"` (sempre
  revalida), então regenerá-lo não exige mudar versão.
- Testes no Chrome em segundo plano: animações e eventos do Chart.js ficam
  pausados (barras com largura 0, cliques ignorados) e a área de
  transferência é negada — não é bug do site; testar a lógica chamando
  `chart.options.onClick(...)` ou com a janela em primeiro plano.
- Chart.js 4.4.1 via jsdelivr; plugin próprio `valoresNaPonta` escreve o
  valor na ponta da barra (mesmo padrão dos PNGs).
- Testar localmente com `python -m http.server` (o `fetch` do JSON não
  funciona abrindo o HTML direto do disco).
