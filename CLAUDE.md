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
│   ├── atualizar.py      # `python -m src.atualizar`: busca eventos novos e regenera tudo
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
├── tests/              # pytest: conftest.py (mini-dataset de 3 lutas) + test_*.py
├── pytest.ini          # testpaths = tests, pythonpath = .
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
  `extrair_eventos_multiplas_paginas(driver, num_paginas)`,
  `extrair_eventos_da_pagina(html)` — eventos da listagem já com a data
  (`{"nome", "url", "data": "AAAA-MM-DD"}`),
  `extrair_lutas_da_pagina_evento(html)` / `extrair_lutas_evento(url, driver)`
  — lutadores (nome e link de cada um), categoria de peso, cinturão e bônus
  de cada luta, lidos da página do evento (categoria = texto da célula
  "Weight class"; ícones belt.png, fight.png = Luta da Noite, perf.png =
  Performance da Noite), `extrair_lutador(url, driver)` — altura,
  envergadura, base e nascimento da página do lutador (texto cru). Usa
  `WebDriverWait` em vez de sleep fixo: só o 1º acesso da sessão passa pelo
  anti-bot, depois cada página carrega em < 1 s
- **limpeza.py**: `separar_landed_attempted` (split "X of Y" em
  landed/attempted), `limpar_percentual` (remove %, trata "---" como NaN),
  `tempo_para_segundos` (formato "M:SS" -> segundos), `limpar_dataset(df)`
  (aplica as três a um CSV bruto; reproduz exatamente os processados),
  `medida_para_cm` (5' 11" ou 72" -> cm), `limpar_lutadores(df)`
- **visualizacao.py**: `aplicar_estilo_dark`, `estilizar_grafico`,
  `adicionar_valores_barras`, `top_com_desempate(valores, lutas, n)`,
  `COR_VERMELHO`, `COR_AZUL`, `COR_AMARELO`
- **config.py**: `COLUNAS_OF`, `COLUNAS_PCT`
- **exportar.py**: `agregar_lutadores(df)`, `exportar_lutadores()` — gera
  `dados/lutadores.json` para o site interativo
- **banco.py**: `montar_tabelas(resumo, por_round, datas, lutadores)`, `criar_banco()` —
  recria `data/ufc.db` (não versionado, `data/*.db` no .gitignore);
  `python -m src.banco` na raiz
- **consultas.py**: `carregar_consultas()` ({nome: sql}),
  `consultar(nome)` (DataFrame)

## Testes
`python -m pytest` na raiz (22 testes, ~1 s, sem rede e sem data/). `tests/conftest.py`
tem um mini-dataset sintético (3 lutas, 2 eventos, 4 lutadores) no formato dos CSVs
limpos; `test_banco_sql.py` monta o SQLite em memória com o `schema.sql` real (FK ligada)
e roda TODAS as consultas nomeadas, então consulta nova já é testada contra o schema.
Função nova em src/ com lógica pura (limpeza, parsing, agregação): adicionar teste.
CI: `.github/workflows/testes.yml` roda o pytest no GitHub Actions (Ubuntu, Python 3.14)
a cada push em main/develop, instalando só `requirements-test.txt` (o requirements.txt
tem pywinpty, só Windows). Import novo em src/ -> incluir no requirements-test.txt.

## Banco SQL (SQLite)
Tabelas: `eventos` (evento_id, url, nome) → `lutas` (luta_id, url,
evento_id, metodo, round_final, tempo_final, duracao_seg, arbitro,
categoria, disputa_titulo, bonus_luta, bonus_performance — flags 0/1) →
`desempenho` (PK luta_id+lutador; lutador_url → `lutadores` (url PK, nome,
altura_cm, envergadura_cm, base, nascimento); resultado W/L/D/NC; kd, sig_acertados,
sig_tentados, total_*, quedas, quedas_tentadas, tent_finalizacao,
reversoes, controle_seg, cabeca/corpo/perna, distancia/clinch/chao) →
`desempenho_round` (mesmas estatísticas + round, sem resultado).
`eventos.data` ('AAAA-MM-DD', vinda de `data/processed/eventos.csv`) é a
referência de tempo: ordenar lutas por `e.data`. `evento_id` é atribuído em
ordem de data decrescente (1 = mais recente, UFC 331; 149 = UFC 287).
Consultas novas vão em `sql/consultas.sql` com `-- nome: x` na linha acima.
O `03_sql.ipynb` confere com Pandas (assert) cada gráfico refeito em SQL, inclusive
`confronto_bases` (self-join vencedor × perdedor + `lutadores`), `disputas_titulo`,
`finalizacoes_por_categoria` (HAVING + RANK), `idade_envergadura` (julianday + faixas
em CASE) e `luta_da_noite` (CTE do perdedor + LEFT JOIN; AVG ignora NULL das lutas
sem vencedor). Conferir com `nbconvert --execute` e checar que TODAS as células rodaram:
se uma falha, o nbconvert não grava e as saídas antigas enganam na contagem de "OK".
Em assert entre Series, alinhar a ordem (`reindex`) — o SQL ordena diferente do Pandas.

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
completo de 600+), priorizando qualidade de análise sobre volume. Período:
UFC 287 (2023-04-08) a UFC 331 (2026-09-19). Ampliar para eventos mais
antigos foi considerado e descartado (muda o sentido de "no período").

## Atualização da base
`python -m src.atualizar` (na raiz, com o venv; ~15 s sem eventos novos):
lê a listagem do ufcstats até achar a base, coleta só eventos MAIS NOVOS
que o último (data <= hoje) com `extrair_varios_eventos` (append nos CSVs
brutos), refaz os processados com `limpar_dataset`, grava
`data/processed/eventos.csv` (Event_URL, Event_Name, Event_Date), completa
`data/raw/lutas_evento.csv` (uma linha por luta: lutadores com link,
categoria/cinturão/bônus; lê a página de cada evento da base que ainda não
esteja nele, ~7 s cada), completa `data/raw/lutadores.csv` (página de cada
lutador que falte, ~1 s cada; salva a cada 25), junta categoria/bônus e
`Fighter_URL` ao resumo limpo (`adicionar_dados_das_lutas`), grava
`data/processed/lutadores.csv` (`limpar_lutadores`) e regenera
`dados/lutadores.json` e `data/ufc.db`. `--graficos` também reexecuta os
notebooks 02 e 03. Textos com números fixos (badges/legendas do
`index.html`, README) NÃO se atualizam sozinhos. Testado de ponta a ponta
numa cópia da base sem o UFC 331: recoletou o evento idêntico ao original.

Datasets finais processados:
- `data/processed/dataset_final_resumo_limpo.csv` — (3674, 38), uma linha
  por lutador-luta
- `data/processed/dataset_final_round_limpo.csv` — (8910, 20), uma linha
  por lutador-luta-round
- `data/processed/lutadores.csv` — (964, 6): `Fighter_URL`, `Name`,
  `Height_cm`, `Reach_cm`, `Stance` (Orthodox 709, Southpaw 160, Switch 92,
  3 vazios), `DOB` ('AAAA-MM-DD'); altura/envergadura/nascimento completos

Colunas principais do dataset resumo (ATENÇÃO aos nomes exatos, em inglês,
sem acento): `Fighter`, `KD`, `Sig. str. %`, `Td %`, `Sub. att`, `Rev.`,
`Resultado` (W/L), `Method` (ex: "Decision - Unanimous", "KO/TKO",
"Submission"), `Final_Round`, `Time`, `Referee`, `Fight_URL`, `Event_URL`,
`Event_Name`, e pares `_landed`/`_attempted` para Sig_str, Total_str, Td,
Head, Body, Leg, Distance, Clinch, Ground, além de `Ctrl_seconds`.
Dados da luta vindos da página do evento: `Weight_Class` (ex: "Lightweight",
"Women's Strawweight", "Catch Weight" = peso casado, 28 lutas; "Women's
Featherweight" só tem 4), `Title_Bout`, `Fight_Bonus`, `Perf_Bonus` (0/1;
76 disputas de cinturão, 101 Lutas da Noite, 408 Performances no período).
`Fighter_URL` é o identificador único do lutador: 964 pessoas para 963
nomes. Homônimos ganham o ano de nascimento no `Fighter` dos processados
(resumo e por round), via `desambiguar_homonimos` no `src.atualizar`:
"Bruno Silva (1989)" (médio) e "Bruno Silva (1990)" (mosca). Assim tudo
que agrupa por nome (gráficos, JSON do site, SQL) os separa; `Name` em
`lutadores.csv` continua o nome do site.

Desempate nos top 10: rankings de TOTAIS usam `top_com_desempate` (valor,
depois MENOS lutas, depois nome); precisão desempata por MAIS tentativas.
Sem isso, com muitos empatados no corte (15 lutadores com 7 vitórias para
8 vagas), quem aparecia mudava a cada atualização. O site interativo usa
a mesma regra nos totais (ver Rankings abaixo).
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
18. `finalizacoes_por_categoria.png` — barras empilhadas por categoria de
    peso: % de lutas encerradas por nocaute (azul, inclui TKO médico) e por
    finalização (vermelho), uma linha por luta, total na ponta, média geral
    tracejada (50%); fora peso casado e categorias com < 20 lutas (pena
    feminino). Meio-pesado lidera (68%), pesado só 53%, mosca fem. 31%
19. `idade_vs_envergadura.png` — 2 painéis de barras verticais: % de
    vitória de quem é mais novo (vermelho) por faixa de diferença de idade
    (até 2 / 2–5 / 5–8 / 8+ anos) e de quem tem mais envergadura (azul) por
    diferença em polegadas (1/2/3/4+), lutas com vencedor, junção por
    `Fighter_URL` com `data/processed/lutadores.csv`; idade na data do
    evento; envergadura igual fica de fora. Mais novo vence 60% (73% com 8+
    anos), envergadura 51% (55% com 4"+); tracejado em 50%
20. `base_canhoto_vs_ortodoxo.png` — barras verticais por confronto de bases
    diferentes (canhoto × ortodoxo, troca de base × ortodoxo, troca de base
    × canhoto), % de vitórias do 1º lado com intervalo de 95% (Wilson),
    lutas com vencedor, base via `Fighter_URL`. Canhoto 53% (245 de 465,
    IC 48–57%, não descarta o acaso), switch × ortodoxo 52%, switch ×
    canhoto 62% em só 55 lutas; tracejado em 50%
21. `disputas_de_cinturao.png` — painéis (formato do 10) disputa de
    cinturão (amarelo) × demais lutas (azul), uma linha por luta: duração
    média 16,8 × 10,7 min, golpes sig. por minuto por lutador 4,0 × 4,0,
    KD a cada 15 min 0,21 × 0,31 (só 36 KDs), Luta da Noite 18% × 5%
    (3,7×), Performance 32% × 22%; rodapé: disputa fecha o card
22. `luta_da_noite.png` — mesmos painéis, Luta da Noite (vermelho) × demais
    (azul), uma linha por luta: golpes sig./min por lutador 5,8 × 3,8, lutas
    com KD 50% × 37%, "ida e volta" (perdedor também derrubou) 12% × 4%,
    equilibradas (perdedor com 40%+ dos golpes) 61% × 49%, tempo com alguém
    no controle 27% × 38%, decisão 65% × 48% (só 3% no 1º round × 27%;
    98% das Performances da Noite vão para finalizações)

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
  tl, ta, tdl, tda, sub, ctrl, head, body, leg, dist, clinch, ground, dur)
  e, quando houver, dados para os cartões (`dados_fisicos`): cat (categoria
  da luta mais recente, ignorando peso casado), alt/env (cm inteiros), base,
  nasc ('AAAA-MM-DD'; a idade é calculada no navegador, na data de hoje);
  médias e percentuais são calculados no JS (`METRICAS` em
  `js/interativo.js`). Rodar de novo sempre que o dataset mudar.
- Comparador: 2 lutadores (datalist com autocomplete), cartões com cartel e
  um painel Chart.js por métrica (escalas diferentes, sem eixo único).
  O `<datalist>` filtra pelo texto do campo, então com um nome preenchido
  só ele aparece na lista: por isso `configurarCampoLutador` esvazia o
  campo no foco (nome vira placeholder) e restaura ao sair sem escolher.
  Redesenha no evento `input` quando o texto bate com um nome. Cartões:
  categoria em PT (`CATEGORIAS`), cartel, e linha física (idade, altura,
  envergadura, base em PT via `BASES`; `linhaFisico`).
  Caixa "No papel" (`#no-papel`, `desenharNoPapel`/`linhasNoPapel`): quem é
  mais novo / tem mais envergadura e a taxa histórica de vitória de quem tem
  essa vantagem na mesma faixa, lida de `vantagens` no JSON
  (`{"idade": [[limite, pct, lutas], ...], "env": [...], "bases": [[a, b,
  vitorias_a, lutas], ...]}`, limite null = última faixa; bases com aviso de
  acaso quando o intervalo de Wilson inclui 50%, `intervaloWilson`), gerado por `historico_vantagens` em `src/exportar.py` com as faixas do
  gráfico 19 (`FAIXAS_VANTAGEM`). Oculta sem os 2 lutadores ou com o mesmo nos dois.
- Rankings: métrica + categoria + base + idade + mín. de lutas + top N; clique na barra leva o lutador
  ao comparador; tabela equivalente em `<details>`. Precisões exigem
  amostra mínima de tentativas (`requisito` em cada métrica). Filtro de
  categoria (`CATEGORIAS_RANKING`, sem peso casado) usa `l.cat`, a categoria
  da luta mais recente: quem mudou de divisão entra com todas as lutas.
  Desempate: métricas com `total: true` (vitórias, KO, sub, KD) por MENOS
  lutas, como nos PNGs; médias/taxas por MAIS lutas; depois nome.
  Filtro de base (`BASES_RANKING`, usa `l.base`) e de faixa de idade
  (`FAIXAS_IDADE`: ate25/26a30/31a35/36mais, idade de HOJE via `idade(l.nasc)`,
  como nos cartões; quem não tem nascimento sai quando filtrado).
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
- Link compartilhável: o estado vai para a URL (`?a=&b=&m=&min=&top=&rm=&cat=&base=&idade=`; `cat`, `base` e `idade` só se filtrados, via
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
  funciona abrindo o HTML direto do disco). Subir o servidor como tarefa em
  segundo plano própria: lançado com `( ... &)` dentro de outro comando ele
  trava e o `fetch` do JSON fica pendente no Chrome.
- Textos sobre lutadores no JS: formas neutras ("tem 3 anos a menos", "quem é
  mais novo"), porque há lutadoras no mesmo comparador.
