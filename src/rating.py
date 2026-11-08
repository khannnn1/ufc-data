"""Nota de cada lutador em cada luta, de 0 a 10 com base 6,6 (estilo Sofascore).

nota = 6,6 + resultado + desempenho (com os pesos do estilo) + força do adversário, limitada a [3, 10]

- Estilo (Striker, Wrestler, Finalizador, Completo): sai dos números da carreira, por 15 minutos
  (golpes, quedas, % do tempo controlando, tentativas de finalização). `classificar_estilos`.
- Desempenho: os pesos de cada estatística NÃO são inventados: saem de uma regressão logística nas
  lutas decididas pelos juízes, que mede quanto cada diferença (o que você fez menos o que sofreu,
  por minuto) pesa para vencer. `aprender_pesos`. O estilo reforça o peso do que é o jogo do
  lutador no ataque (`MULTIPLICADORES`), sem perdoar o que ele sofreu.
- Resultado: vitória/derrota e método; nocaute e finalização valem mais quanto mais cedo.
- Adversário: Elo calculado em ordem cronológica; vencer (ou perder para) alguém forte pesa a favor.

Python puro + numpy (sem scikit-learn), para rodar na CI só com requirements-test.txt.
"""

import numpy as np
import pandas as pd

from src.limpeza import adicionar_duracao

BASE = 6.6
NOTA_MIN, NOTA_MAX = 3.0, 10.0

# Estatísticas do desempenho (contagem por lutador numa luta). Golpes na cabeça separados de corpo/perna
# porque o peso deles é diferente; "Ground" não entra porque já está dentro de cabeça/corpo/perna.
ESTATISTICAS = {
    "cabeca": "Head_landed",
    "corpo_perna": ["Body_landed", "Leg_landed"],
    "kd": "KD",
    "quedas": "Td_landed",
    "controle": "Ctrl_seconds",  # em minutos (dividido por 60)
    "finalizacao": "Sub. att",
    "reversao": "Rev.",
}
NOMES = list(ESTATISTICAS)

# Quanto o estilo reforça (ou alivia) cada estatística no ATAQUE. Depois de aplicados, os pesos de
# cada estilo são reescalados para que o ataque médio dos lutadores daquele estilo continue igual
# (`pesos_por_estilo`): o estilo muda o que conta, não dá vantagem a um estilo sobre outro.
MULTIPLICADORES = {
    "Striker": {"cabeca": 1.3, "corpo_perna": 1.3, "kd": 1.3, "quedas": 0.6, "controle": 0.6, "finalizacao": 0.8, "reversao": 0.8},
    "Wrestler": {"cabeca": 0.9, "corpo_perna": 0.9, "kd": 1.0, "quedas": 1.4, "controle": 1.4, "finalizacao": 1.0, "reversao": 1.2},
    "Finalizador": {"cabeca": 0.9, "corpo_perna": 0.9, "kd": 1.0, "quedas": 1.1, "controle": 1.1, "finalizacao": 1.6, "reversao": 1.3},
    "Completo": {n: 1.0 for n in NOMES},
}

# Limites do estilo (por 15 min de luta). Mediana da base: 51 golpes, 1,2 queda, 18% de controle,
# 0,4 tentativa de finalização.
MIN_LUTAS_ESTILO = 3
DESVIO_DESEMPENHO = 0.55  # desvio-padrão da parte de desempenho, em pontos de nota
MINUTOS_SUAVIZACAO = 5  # em lutas curtas, as taxas por minuto são puxadas para zero (ruído)

FINALIZACAO = "Submission"


# ---------- Estilo ----------

def _contagens(df):
    saida = pd.DataFrame(index=df.index)
    for nome, coluna in ESTATISTICAS.items():
        saida[nome] = df[coluna].sum(axis=1) if isinstance(coluna, list) else df[coluna]
    saida["controle"] = saida["controle"] / 60
    return saida.fillna(0)  # coluna sem valor numa luta com estatísticas = não aconteceu


def classificar_estilos(df):
    """Estilo de cada lutador ({nome: estilo}) pelas médias da carreira, por 15 minutos.

    Precisa de `Duracao_seg` (adicionar_duracao). Com menos de MIN_LUTAS_ESTILO lutas com
    estatísticas, o lutador fica "Completo" (pesos neutros).
    """
    com = df[df["Sig_str_landed"].notna()]
    g = com.groupby("Fighter").agg(n=("Fight_URL", "size"), golpes=("Sig_str_landed", "sum"),
                                   quedas=("Td_landed", "sum"), ctrl=("Ctrl_seconds", "sum"),
                                   fin=("Sub. att", "sum"), dur=("Duracao_seg", "sum"))
    por15 = g["dur"] / 60 / 15
    quedas15, fin15 = g["quedas"] / por15, g["fin"] / por15
    ctrl_pct = g["ctrl"] / g["dur"] * 100
    estilo = pd.Series("Completo", index=g.index)
    estilo[(ctrl_pct < 12) & (quedas15 < 1)] = "Striker"
    estilo[(ctrl_pct >= 30) | (quedas15 >= 2.5)] = "Wrestler"
    estilo[fin15 >= 1.5] = "Finalizador"
    estilo[g["n"] < MIN_LUTAS_ESTILO] = "Completo"
    return estilo.to_dict()


# ---------- Pares lutador × adversário ----------

def montar_pares(df):
    """Uma linha por lutador em cada luta, com as próprias taxas (`p_*`) e as do adversário (`a_*`),
    por minuto e suavizadas em lutas curtas. Só lutas com estatísticas dos dois lados."""
    df = df[df["Sig_str_landed"].notna() & df["Duracao_seg"].notna()]
    contagens = _contagens(df)
    minutos = df["Duracao_seg"] / 60
    taxas = contagens.div(minutos + MINUTOS_SUAVIZACAO, axis=0)
    base = df[["Fight_URL", "Fighter", "Resultado", "Method", "Final_Round", "Duracao_seg"]].join(taxas.add_prefix("p_"))
    adv = df[["Fight_URL", "Fighter"]].join(taxas.add_prefix("a_")).rename(columns={"Fighter": "Adversario"})
    pares = base.merge(adv, on="Fight_URL")
    return pares[pares["Fighter"] != pares["Adversario"]].reset_index(drop=True)


def diferencas(pares):
    return np.column_stack([pares[f"p_{n}"] - pares[f"a_{n}"] for n in NOMES])


# ---------- Pesos (regressão logística) ----------

def regressao_logistica(X, y, l2=1.0, iteracoes=50):
    """Regressão logística sem intercepto por Newton-Raphson, com penalidade L2 leve.

    Sem intercepto porque o modelo é simétrico: inverter os lados troca o sinal de X e de y.
    """
    beta = np.zeros(X.shape[1])
    for _ in range(iteracoes):
        p = 1 / (1 + np.exp(-X @ beta))
        gradiente = X.T @ (y - p) - l2 * beta
        hessiana = -(X.T * (p * (1 - p))) @ X - l2 * np.eye(X.shape[1])
        passo = np.linalg.solve(hessiana, gradiente)
        beta -= passo
        if np.abs(passo).max() < 1e-8:
            break
    return beta


def aprender_pesos(pares):
    """Pesos de cada estatística (log-odds por unidade por minuto) nas lutas decididas pelos juízes.

    Usa um lado de cada luta (o primeiro no dataset), com vencedor definido. Devolve {nome: peso}.
    """
    decisao = pares[pares["Method"].str.startswith("Decision", na=False) & pares["Resultado"].isin(["W", "L"])]
    decisao = decisao.drop_duplicates("Fight_URL")
    X = diferencas(decisao)
    y = (decisao["Resultado"] == "W").to_numpy(dtype=float)
    return dict(zip(NOMES, regressao_logistica(X, y)))


def pesos_por_estilo(pares, pesos, estilos):
    """Pesos do ataque para cada estilo: pesos universais × MULTIPLICADORES, reescalados para que o
    ataque médio dos lutadores do estilo fique igual ao calculado com os pesos universais."""
    saida = {}
    estilo_linha = pares["Fighter"].map(estilos).fillna("Completo")
    proprios = np.column_stack([pares[f"p_{n}"] for n in NOMES])
    universal = np.array([pesos[n] for n in NOMES])
    for estilo, mult in MULTIPLICADORES.items():
        bruto = universal * np.array([mult[n] for n in NOMES])
        linhas = proprios[estilo_linha.to_numpy() == estilo]
        if len(linhas) and (linhas @ bruto).mean() > 0:
            bruto = bruto * (linhas @ universal).mean() / (linhas @ bruto).mean()
        saida[estilo] = dict(zip(NOMES, bruto))
    return saida


# ---------- Resultado e adversário ----------

# Parte da nota que vem do resultado (calibrada para o vencedor médio ficar perto de 7,5 e o
# perdedor perto de 6). Nocaute/finalização: valor fixo + extra proporcional ao tempo que sobrava.
RESULTADO = {
    "vitoria_decisao": 0.35, "vitoria_dividida": 0.2, "vitoria_antes": 0.6, "vitoria_cedo": 0.5,
    "derrota_decisao": -0.25, "derrota_dividida": -0.1, "derrota_antes": -0.4, "derrota_cedo": -0.2,
}


def bonus_resultado(resultado, metodo, duracao_seg, duracao_prevista_seg):
    """Parte da nota que vem do resultado. Nocaute/finalização vale mais quanto mais cedo."""
    metodo = metodo if isinstance(metodo, str) else ""
    terminou = "KO/TKO" in metodo or "TKO - Doctor" in metodo or FINALIZACAO in metodo
    restante = max(0.0, 1 - duracao_seg / duracao_prevista_seg) if duracao_prevista_seg else 0.0
    apertada = "Split" in metodo or "Majority" in metodo
    r = RESULTADO
    if resultado == "W":
        if terminou:
            return r["vitoria_antes"] + r["vitoria_cedo"] * restante
        return r["vitoria_dividida"] if apertada else r["vitoria_decisao"]
    if resultado == "L":
        if terminou:
            return r["derrota_antes"] + r["derrota_cedo"] * restante
        return r["derrota_dividida"] if apertada else r["derrota_decisao"]
    return 0.0  # empate, sem resultado


def calcular_elo(lutas, k=32, inicial=1500):
    """Elo ANTES de cada luta. `lutas`: DataFrame em ordem cronológica com Fight_URL, Fighter,
    Adversario, Resultado (uma linha por lutador). Devolve {(Fight_URL, Fighter): elo_antes}."""
    elo, antes = {}, {}
    for url, grupo in lutas.groupby("Fight_URL", sort=False):
        if len(grupo) != 2:
            continue
        a, b = grupo.iloc[0], grupo.iloc[1]
        ea, eb = elo.get(a["Fighter"], inicial), elo.get(b["Fighter"], inicial)
        antes[(url, a["Fighter"])], antes[(url, b["Fighter"])] = ea, eb
        _atualizar_elo(elo, a["Fighter"], b["Fighter"], a["Resultado"], k, inicial)
    return antes


def _atualizar_elo(elo, a, b, resultado_a, k=32, inicial=1500):
    """Atualiza o Elo dos dois lados depois de uma luta (NC não muda nada)."""
    if resultado_a == "NC":
        return
    ea, eb = elo.get(a, inicial), elo.get(b, inicial)
    placar = {"W": 1.0, "L": 0.0}.get(resultado_a, 0.5)
    esperado = 1 / (1 + 10 ** ((eb - ea) / 400))
    elo[a] = ea + k * (placar - esperado)
    elo[b] = eb + k * ((1 - placar) - (1 - esperado))


# ---------- Top 15 pelo Elo ----------

TOP_RANKING = 15
INATIVIDADE_DIAS = 730  # sem lutar há mais de 2 anos sai do ranking
MIN_LUTAS_RANKING = 3  # estreantes e quem tem 1-2 lutas não entram
SEM_CATEGORIA_PROPRIA = {"Catch Weight"}  # peso casado: vale a categoria da luta anterior


def ordem_cronologica(df, datas_eventos):
    """Resumo em ordem de luta: por data e, no mesmo dia, do fim do card para a luta principal."""
    datas = datas_eventos.set_index("Event_URL")["Event_Date"]
    ordem = df.assign(_data=df["Event_URL"].map(datas), _pos=np.arange(len(df)))
    return ordem.sort_values(["_data", "_pos"], ascending=[True, False])


def posicoes_no_ranking(df, datas_eventos, top=TOP_RANKING, inatividade_dias=INATIVIDADE_DIAS,
                        min_lutas=MIN_LUTAS_RANKING, k=32, inicial=1500):
    """Posição de cada lutador no top `top` da categoria pelo Elo, na véspera de cada luta.

    Ranking de uma categoria numa data = lutadores cuja luta mais recente foi nela (peso casado não muda
    a categoria), que lutaram nos últimos `inatividade_dias` e têm pelo menos `min_lutas` lutas, ordenados
    pelo Elo (mesmo Elo do bônus de adversário). Não é o ranking oficial do UFC (que só existe desde 2013).
    Devolve {(Fight_URL, Fighter): posição 1..top}; quem estava fora do top não aparece.
    """
    ordem = ordem_cronologica(df, datas_eventos)
    elo, categoria, ultima, lutas = {}, {}, {}, {}
    posicoes = {}
    for data, dia in ordem.groupby("_data", sort=True):
        hoje = pd.Timestamp(data)
        limite = (hoje - pd.Timedelta(days=inatividade_dias)).strftime("%Y-%m-%d")
        rankings = {}

        def ranking(cat):
            if cat not in rankings:
                ativos = [f for f, c in categoria.items()
                          if c == cat and ultima[f] >= limite and lutas[f] >= min_lutas]
                ativos.sort(key=lambda f: (-elo.get(f, inicial), f))
                rankings[cat] = {f: i + 1 for i, f in enumerate(ativos[:top])}
            return rankings[cat]

        lutas_do_dia = [g for _, g in dia.groupby("Fight_URL", sort=False)]
        for luta in lutas_do_dia:  # posições na véspera: antes de qualquer luta do dia
            cat_luta = luta["Weight_Class"].iloc[0] if "Weight_Class" in luta else None
            for f in luta["Fighter"]:
                cat = cat_luta if isinstance(cat_luta, str) and cat_luta not in SEM_CATEGORIA_PROPRIA else categoria.get(f)
                if cat is not None and f in ranking(cat):
                    posicoes[(luta["Fight_URL"].iloc[0], f)] = ranking(cat)[f]
        for luta in lutas_do_dia:
            cat_luta = luta["Weight_Class"].iloc[0] if "Weight_Class" in luta else None
            for f in luta["Fighter"]:
                if isinstance(cat_luta, str) and cat_luta not in SEM_CATEGORIA_PROPRIA:
                    categoria[f] = cat_luta
                ultima[f] = data
                lutas[f] = lutas.get(f, 0) + 1
            if len(luta) == 2:
                a, b = luta.iloc[0], luta.iloc[1]
                _atualizar_elo(elo, a["Fighter"], b["Fighter"], a["Resultado"], k, inicial)
    return posicoes


def bonus_adversario(elo_adversario, inicial=1500):
    """Até ±0,4: adversário 200 pontos de Elo acima da média vale +0,2."""
    return float(np.clip((elo_adversario - inicial) / 1000, -0.4, 0.4))


# ---------- Nota ----------

def duracao_prevista(df):
    """Duração marcada da luta em segundos (3 ou 5 rounds de 5 min), pelo Time_Format quando houver."""
    formato = df.get("Time_Format", pd.Series(index=df.index, dtype=object)).fillna("")
    rounds = formato.str.extract(r"^(\d+) Rnd")[0].astype(float)
    minutos = formato.str.extract(r"\(([\d-]+)\)")[0].fillna("").map(
        lambda s: sum(int(x) for x in s.split("-")) if s else np.nan)
    padrao = np.where(df["Title_Bout"].fillna(0).astype(int) == 1, 25, 15) * 60
    return (minutos * 60).fillna(pd.Series(rounds * 300, index=df.index)).fillna(pd.Series(padrao, index=df.index))


def calcular_notas(df, datas_eventos, escala=None):
    """Nota de cada lutador em cada luta com estatísticas.

    df: resumo limpo (com Weight_Class/Title_Bout); datas_eventos: DataFrame com Event_URL e Event_Date.
    Devolve (notas, info): notas = DataFrame com Fight_URL, Fighter, Adversario, Estilo, Resultado,
    resultado, desempenho, adversario, Nota; info = pesos, pesos por estilo e escala usada.
    """
    df = adicionar_duracao(df.copy())
    df["Prevista_seg"] = duracao_prevista(df)
    estilos = classificar_estilos(df)
    pares = montar_pares(df)
    pesos = aprender_pesos(pares)
    pesos_estilo = pesos_por_estilo(pares, pesos, estilos)

    pares["Estilo"] = pares["Fighter"].map(estilos).fillna("Completo")
    universal = np.array([pesos[n] for n in NOMES])
    proprios = np.column_stack([pares[f"p_{n}"] for n in NOMES])
    sofridos = np.column_stack([pares[f"a_{n}"] for n in NOMES])
    ataque = np.array([proprios[i] @ np.array([pesos_estilo[e][n] for n in NOMES])
                       for i, e in enumerate(pares["Estilo"])])
    defesa = -(sofridos @ universal)
    bruto = ataque + defesa  # log-odds de vencer na visão dos juízes, com o ataque no peso do estilo
    if escala is None:
        escala = DESVIO_DESEMPENHO / bruto.std()
    pares["desempenho"] = escala * bruto

    prevista = df.drop_duplicates("Fight_URL").set_index("Fight_URL")["Prevista_seg"]
    pares["resultado"] = [bonus_resultado(r, m, d, prevista.get(u))
                          for r, m, d, u in zip(pares["Resultado"], pares["Method"], pares["Duracao_seg"], pares["Fight_URL"])]

    ordem = ordem_cronologica(df, datas_eventos)  # card: luta principal por último no dia
    adv = ordem.merge(ordem[["Fight_URL", "Fighter"]].rename(columns={"Fighter": "Adversario"}), on="Fight_URL")
    adv = adv[adv["Fighter"] != adv["Adversario"]].sort_values(["_data", "_pos"], ascending=[True, False])
    elo = calcular_elo(adv[["Fight_URL", "Fighter", "Adversario", "Resultado"]])
    pares["adversario"] = [bonus_adversario(elo.get((u, a), 1500)) for u, a in zip(pares["Fight_URL"], pares["Adversario"])]

    pares["Nota"] = (BASE + pares["resultado"] + pares["desempenho"] + pares["adversario"]).clip(NOTA_MIN, NOTA_MAX).round(1)
    colunas = ["Fight_URL", "Fighter", "Adversario", "Estilo", "Resultado", "Method", "resultado", "desempenho", "adversario", "Nota"]
    info = {"pesos": pesos, "pesos_estilo": pesos_estilo, "escala": escala, "estilos": estilos}
    return pares[colunas], info
