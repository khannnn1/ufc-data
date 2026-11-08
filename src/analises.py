"""Números das análises da página inicial (index.html), por período do site.

Mesmas contas dos gráficos PNG do notebook 02 (ver CLAUDE.md, "Gráficos já criados"), agregadas
aqui para o navegador desenhar com Chart.js e trocar de período sem recalcular nada.
Gerado junto com os JSONs dos lutadores por `python -m src.exportar` -> dados/analises.json.
"""

import pandas as pd

from src.limpeza import adicionar_duracao

NOCAUTE = "KO/TKO|TKO - Doctor"
FINALIZACAO = "Submission"
MIN_LUTAS_CATEGORIA = 20  # mesmo filtro do gráfico finalizacoes_por_categoria.png
FORA_DAS_CATEGORIAS = {"Catch Weight", "Open Weight"}


def _pct(parte, total):
    return round(float(parte) / total * 100, 1) if total else None


def _por_luta(df):
    """Uma linha por luta (dados da luta são iguais nas duas linhas)."""
    return df.drop_duplicates("Fight_URL")


def numeros_chave(df):
    lutas = _por_luta(df)
    antes = lutas["Method"].str.contains(f"{NOCAUTE}|{FINALIZACAO}", na=False).sum()
    return {"eventos": int(df["Event_URL"].nunique()), "lutas": int(len(lutas)),
            "lutadores": int(df["Fighter"].nunique()), "pct_antes_decisao": _pct(antes, len(lutas))}


def metodos(df):
    """[[método, lutas], ...] do mais comum ao menos comum (uma linha por luta)."""
    contagem = _por_luta(df)["Method"].value_counts()
    return [[m, int(n)] for m, n in contagem.items()]


def round_final(df):
    """% dos nocautes e das finalizações que terminam em cada round (4º e 5º juntos).

    {"rounds": ["1", "2", "3", "4-5"], "ko": [...], "sub": [...], "n_ko": n, "n_sub": n}
    """
    lutas = _por_luta(df)
    rotulo = lutas["Final_Round"].clip(upper=4).astype(int).astype(str).replace("4", "4-5")
    saida = {"rounds": ["1", "2", "3", "4-5"]}
    for chave, padrao in [("ko", NOCAUTE), ("sub", FINALIZACAO)]:
        doMetodo = lutas["Method"].str.contains(padrao, na=False)
        contagem = rotulo[doMetodo].value_counts()
        saida[chave] = [_pct(contagem.get(r, 0), doMetodo.sum()) for r in saida["rounds"]]
        saida[f"n_{chave}"] = int(doMetodo.sum())
    return saida


def por_categoria(df):
    """[[categoria, lutas, % nocaute, % finalização], ...] do maior ao menor % antes da decisão."""
    lutas = _por_luta(df)
    lutas = lutas[~lutas["Weight_Class"].isin(FORA_DAS_CATEGORIAS) & lutas["Weight_Class"].notna()]
    linhas = []
    for categoria, grupo in lutas.groupby("Weight_Class"):
        if len(grupo) < MIN_LUTAS_CATEGORIA:
            continue
        ko = grupo["Method"].str.contains(NOCAUTE, na=False).sum()
        sub = grupo["Method"].str.contains(FINALIZACAO, na=False).sum()
        linhas.append([categoria, int(len(grupo)), _pct(ko, len(grupo)), _pct(sub, len(grupo))])
    return sorted(linhas, key=lambda l: -(l[2] + l[3]))


def vencedores_perdedores(df):
    """Médias por luta de vencedores (W) e perdedores (L), só lutas com estatísticas.

    [[métrica, média W, média L], ...] com métrica em golpes, quedas, controle (min), tentativas
    de finalização e knockdowns (mesmo gráfico vencedores_vs_perdedores.png).
    """
    com = df[df["Sig_str_landed"].notna() & df["Resultado"].isin(["W", "L"])]
    colunas = [("golpes", "Sig_str_landed", 1), ("quedas", "Td_landed", 1), ("controle", "Ctrl_seconds", 1 / 60),
               ("finalizacoes", "Sub. att", 1), ("kd", "KD", 1)]
    medias = com.groupby("Resultado")[[c for _, c, _ in colunas]].mean()
    return [[nome, round(float(medias.loc["W", c]) * f, 2), round(float(medias.loc["L", c]) * f, 2)]
            for nome, c, f in colunas if {"W", "L"} <= set(medias.index)]


def distribuicao(df, partes):
    """% dos golpes significativos acertados em cada parte (ex.: cabeça/corpo/perna), para
    todos, vencedores e perdedores: {"todos": [...], "W": [...], "L": [...]}."""
    colunas = [f"{p}_landed" for p in partes]
    com = df[df[colunas[0]].notna()]
    saida = {}
    for chave, recorte in [("todos", com), ("W", com[com["Resultado"] == "W"]), ("L", com[com["Resultado"] == "L"])]:
        somas = recorte[colunas].sum()
        total = somas.sum()
        saida[chave] = [_pct(somas[c], total) for c in colunas]
    return saida


def disputas_cinturao(df):
    """Disputa de cinturão × demais lutas: [[métrica, cinturão, demais], ...]."""
    lutas = adicionar_duracao(_por_luta(df))
    golpes = df.groupby("Fight_URL")["Sig_str_landed"].sum(min_count=1)
    lutas = lutas.assign(golpes_luta=lutas["Fight_URL"].map(golpes))
    linhas = []
    grupos = {True: lutas[lutas["Title_Bout"] == 1], False: lutas[lutas["Title_Bout"] != 1]}
    for chave, f in [("duracao", lambda g: g["Duracao_seg"].mean() / 60),
                     ("golpes_min", lambda g: (g["golpes_luta"].sum() / 2) / (g.loc[g["golpes_luta"].notna(), "Duracao_seg"].sum() / 60)),
                     ("luta_noite", lambda g: g["Fight_Bonus"].mean() * 100),
                     ("performance", lambda g: g["Perf_Bonus"].mean() * 100)]:
        valores = [f(grupos[True]) if len(grupos[True]) else None, f(grupos[False]) if len(grupos[False]) else None]
        linhas.append([chave, *[None if v is None or pd.isna(v) else round(float(v), 2) for v in valores]])
    return {"n": int(len(grupos[True])), "linhas": linhas}


def golpes_por_round(df_round):
    """Média de golpes sig. acertados por lutador em cada round: [[round, média, rounds], ...]."""
    g = df_round.groupby("Round")["Sig_str_landed"].agg(["mean", "size"])
    return [[int(r), round(float(linha["mean"]), 2), int(linha["size"])] for r, linha in g.iterrows()]


def arbitros(df, n=10):
    """Os n árbitros com mais lutas: [[nome, lutas, % antes da decisão], ...]."""
    lutas = _por_luta(df).dropna(subset=["Referee"])
    antes = lutas["Method"].str.contains(f"{NOCAUTE}|{FINALIZACAO}", na=False)
    g = antes.groupby(lutas["Referee"]).agg(["size", "mean"]).sort_values("size", ascending=False).head(n)
    return [[nome, int(linha["size"]), round(float(linha["mean"]) * 100, 1)] for nome, linha in g.iterrows()]


ORDEM_ESTILOS = ["Striker", "Wrestler", "Finalizador", "Completo"]


def notas_do_periodo(df, notas, datas_eventos, n=5):
    """Notas por luta (src/rating.py) das lutas do recorte.

    {"media": nota média, "estilos": [[estilo, atuações, lutadores, nota média, % de vitórias], ...],
     "melhores": [[nome, nota, [resultado, desempenho, adversário], adversário, evento, data, id do evento,
                   método, round, resultado W/L/D/NC, estilo], ...]} (as n maiores notas; empate: desempenho, mais recente).
    O estilo é o da carreira inteira, como no site.
    """
    notas = notas[notas["Fight_URL"].isin(set(df["Fight_URL"]))]
    if notas.empty:
        return {"media": None, "estilos": [], "melhores": []}
    estilos = []
    for estilo in ORDEM_ESTILOS:
        grupo = notas[notas["Estilo"] == estilo]
        if len(grupo):
            estilos.append([estilo, int(len(grupo)), int(grupo["Fighter"].nunique()), round(float(grupo["Nota"].mean()), 2),
                            _pct((grupo["Resultado"] == "W").sum(), len(grupo))])
    lutas = (df.drop_duplicates("Fight_URL")[["Fight_URL", "Event_URL", "Event_Name", "Final_Round"]]
             .merge(datas_eventos[["Event_URL", "Event_Date"]], on="Event_URL", how="left"))
    topo = notas.merge(lutas, on="Fight_URL", how="left")
    topo = topo.sort_values(["Nota", "desempenho", "Event_Date"], ascending=False).head(n)
    melhores = [[l.Fighter, float(l.Nota), [round(float(l.resultado), 2), round(float(l.desempenho), 2), round(float(l.adversario), 2)],
                 l.Adversario, l.Event_Name, l.Event_Date, l.Event_URL.rstrip("/").rsplit("/", 1)[-1], l.Method,
                 None if pd.isna(l.Final_Round) else int(l.Final_Round), l.Resultado, l.Estilo]
                for l in topo.itertuples(index=False)]
    return {"media": round(float(notas["Nota"].mean()), 2), "estilos": estilos, "melhores": melhores}


def montar_analises(df, df_round, notas=None, datas_eventos=None):
    """Todas as análises de um recorte (já filtrado pelo período); `notas` = 1º retorno de calcular_notas."""
    extra = {} if notas is None else {"notas": notas_do_periodo(df, notas, datas_eventos)}
    return {
        "numeros": numeros_chave(df),
        "metodos": metodos(df),
        "round_final": round_final(df),
        "categorias": por_categoria(df),
        "vencedores_perdedores": vencedores_perdedores(df),
        "alvo": distribuicao(df, ["Head", "Body", "Leg"]),
        "origem": distribuicao(df, ["Distance", "Clinch", "Ground"]),
        "cinturao": disputas_cinturao(df),
        "rounds": golpes_por_round(df_round),
        "arbitros": arbitros(df),
        **extra,
    }
