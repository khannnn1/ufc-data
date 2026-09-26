# UFC Data — Análise Estatística de MMA

🔗 **[Ver os gráficos](https://khannnn1.github.io/ufc-data/)** · **[Explorar os dados (interativo)](https://khannnn1.github.io/ufc-data/interativo.html)**

Projeto de ponta a ponta com dados de lutas do UFC: **coleta** por web scraping, **limpeza** e **análise** em Python e **SQL**, **visualização** em estilo editorial (inspirado em contas de dados esportivos como @DataFut) e um **site interativo** em JavaScript, onde o visitante compara lutadores e monta os próprios rankings.

![O que separa vencedores de perdedores](figures/vencedores_vs_perdedores.png)

## Destaques da análise

Recorte de **149 eventos recentes do UFC: 1.837 lutas e 963 lutadores**.

- **Metade das lutas termina antes da decisão dos juízes:** 32% por nocaute e 17% por finalização.
- **Knockdown é o que mais separa vencedores de perdedores:** quem vence derruba o adversário 8,4× mais. Nos golpes significativos a diferença é bem menor (1,5×): quem perde também troca bastante.
- **A luta se decide no chão:** vencedores acertam 13% dos golpes no chão, contra 3,5% dos perdedores, quase 4× mais.
- **Nocautes acontecem mais cedo que finalizações:** 54% dos nocautes saem no 1º round, contra 46% das finalizações, que pesam mais no 2º e 3º rounds.
- **Volume e precisão quase não se relacionam** (correlação de −0,15): há lutadores de todos os estilos, de quem arrisca muito a quem espera o golpe certo.
- **63% dos golpes significativos acertam a cabeça**, mas há especialistas que acertam mais nas pernas do que em qualquer outro alvo.

## O site

- **[Gráficos](https://khannnn1.github.io/ufc-data/)** (`index.html`): 17 gráficos com a leitura de cada um.
- **[Explorar os dados](https://khannnn1.github.io/ufc-data/interativo.html)** (`interativo.html`):
  - **Comparar lutadores:** escolha dois lutadores quaisquer e veja cartel e médias por luta lado a lado.
  - **Volume × precisão:** dispersão com todos os lutadores; os dois do comparador aparecem destacados, e passar o mouse mostra quem é cada ponto.
  - **Monte o seu ranking:** escolha a métrica (13 opções), o mínimo de lutas e o tamanho do top. Clique numa barra para levar o lutador ao comparador.
  - **Compartilhe:** a comparação e o ranking escolhidos ficam no endereço da página, e o botão "Copiar link" gera um link que abre exatamente aquela tela. Exemplo: [Alex Pereira × Jon Jones](https://khannnn1.github.io/ufc-data/interativo.html?a=Alex+Pereira&b=Jon+Jones#comparador).

## Pipeline

```
ufcstats.com
   │  scraper.py (Selenium + BeautifulSoup)
   ▼
data/raw/*.csv
   │  limpeza.py
   ▼
data/processed/*.csv
   ├──► notebooks (Matplotlib) ──► figures/*.png ──► index.html
   ├──► exportar.py ──► dados/lutadores.json ──► interativo.html (Chart.js)
   └──► banco.py ──► data/ufc.db (SQLite) ──► sql/consultas.sql
```

1. **Coleta** (`src/scraper.py`): o ufcstats.com bloqueia requisições simples com uma verificação anti-bot que exige JavaScript, então a coleta usa Selenium em modo headless e lê o HTML depois que a página carrega. As tabelas de estatísticas trazem os dois lutadores na mesma célula, e o `pandas.read_html` não separa isso, por isso o parsing é feito manualmente com BeautifulSoup. A coleta em lote salva cada evento no CSV assim que termina, para não perder o progresso se a conexão cair.
2. **Limpeza** (`src/limpeza.py`): converte `"181 of 305"` em duas colunas numéricas (acertados/tentados), percentuais em número e tempos `M:SS` em segundos. `"---"` (nenhuma tentativa) vira ausente, e não 0%.
3. **Análise e gráficos** (`notebooks/02_visualizacao.ipynb` + `src/visualizacao.py`): padrão visual único (fundo escuro, barras com o valor escrito na ponta, sem eixo quando ele não acrescenta).
4. **Exportação** (`src/exportar.py`): agrega os totais por lutador em um JSON pequeno (≈210 KB); médias e percentuais são calculados no navegador.
5. **SQL** (`src/banco.py`, `sql/`, `notebooks/03_sql.ipynb`): os CSVs, com uma linha por lutador em cada luta e os dados da luta repetidos, viram um banco SQLite com quatro tabelas relacionadas — `eventos` → `lutas` → `desempenho` → `desempenho_round` —, com chaves primárias e estrangeiras. As perguntas dos gráficos são respondidas de novo em SQL (JOINs, `GROUP BY`/`HAVING` para as amostras mínimas, CTEs e funções de janela como `RANK`, `ROW_NUMBER` e `SUM() OVER (PARTITION BY ...)`), e o notebook **confere cada resposta com o resultado em Pandas**. Duas consultas só existem em SQL: o destaque de cada evento e a maior sequência de vitórias de cada lutador (*gaps and islands*).

## Decisões de análise

Alguns cuidados que mudam o resultado e que estão aplicados nos gráficos:

- **Médias por luta, não somas**, ao comparar lutadores com números de lutas diferentes.
- **Amostra mínima em todo ranking de taxa ou precisão** (ex.: taxa de vitória só com 6+ lutas; precisão de quedas com 15+ tentativas e 3+ lutas). Sem isso, o topo vira quem tentou pouco e acertou tudo.
- **Uma linha por luta** quando a pergunta é sobre lutas. O dataset tem uma linha por lutador em cada luta, e contar direto dobraria tudo (um erro que o projeto teve e corrigiu).
- **Volume por minuto, não por luta**, para não penalizar quem finaliza cedo.
- **Associação não é causa**, e isso aparece nas legendas: um knockdown muitas vezes já é o começo do fim da luta; a taxa de finalização de um árbitro reflete as lutas que ele recebe, não o estilo dele.
- **Viés de sobrevivência**: rounds avançados só existem em lutas longas, então médias por round não comparam as mesmas lutas.

## Gráficos

| Tema | Gráficos |
|---|---|
| Como as lutas terminam | métodos de vitória · round em que as lutas terminam, por método · lutas encerradas antes da decisão, por árbitro |
| O que decide a luta | vencedores × perdedores · de onde saem os golpes (distância, clinch, chão) |
| Estilo de luta | volume × precisão (dispersão) · onde os golpes acertam (cabeça, corpo, perna) · evolução de golpes por round |
| Rankings | vitórias · taxa de vitória · nocautes · finalizações · knockdowns · tempo de controle · precisão de golpes · precisão de quedas |
| Lutadores | comparação cara a cara entre dois lutadores |

Todas as imagens estão em [`figures/`](figures/), e o código de cada uma em [`notebooks/02_visualizacao.ipynb`](notebooks/02_visualizacao.ipynb).

## Stack

**Python** (Pandas, NumPy, Matplotlib, Selenium, BeautifulSoup, Jupyter) · **SQL** (SQLite) · **JavaScript** (Chart.js) · **HTML/CSS** · **Git** (Git Flow) · **GitHub Pages**

## Estrutura do projeto

```
├── data/                  # CSVs brutos e limpos (não versionados)
├── dados/lutadores.json   # dados agregados que o site interativo lê
├── figures/               # gráficos exportados (.png)
├── js/interativo.js       # lógica do site interativo
├── notebooks/
│   ├── 00_teste_ambiente.ipynb
│   ├── 01_scrapper_test_luta.ipynb   # coleta e limpeza
│   ├── 02_visualizacao.ipynb         # análise e gráficos
│   └── 03_sql.ipynb                  # as mesmas perguntas em SQL
├── sql/
│   ├── schema.sql         # esquema do banco (4 tabelas)
│   └── consultas.sql      # consultas SQL
├── src/
│   ├── scraper.py         # coleta (Selenium + BeautifulSoup)
│   ├── limpeza.py         # tratamento dos dados
│   ├── visualizacao.py    # padrão visual e funções de plotagem
│   ├── exportar.py        # gera dados/lutadores.json
│   ├── banco.py           # monta o banco SQLite
│   ├── consultas.py       # executa as consultas de sql/consultas.sql
│   └── config.py          # constantes
├── index.html             # página com os gráficos
├── interativo.html        # comparador e rankings
└── requirements.txt
```

## Como rodar

```bash
python -m venv venv
venv\Scripts\Activate.ps1          # Windows (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
```

- **Coleta e limpeza:** `notebooks/01_scrapper_test_luta.ipynb` (precisa do Google Chrome instalado para o Selenium).
- **Gráficos:** `notebooks/02_visualizacao.ipynb`.
- **SQL:** `notebooks/03_sql.ipynb` recria o banco (`data/ufc.db`) e roda as consultas. Para só gerar o banco: `python -m src.banco`.
- **Dados do site interativo:** `python -m src.exportar` (na raiz do projeto) regenera `dados/lutadores.json`.
- **Ver o site localmente:** `python -m http.server` e abrir `http://localhost:8000`. Abrir o HTML direto do disco não funciona, porque o navegador bloqueia a leitura do JSON.

## Próximos passos

- Evolução por round de cada lutador no site interativo (usando o dataset por round).
- Atualizar a base com os eventos mais recentes.
