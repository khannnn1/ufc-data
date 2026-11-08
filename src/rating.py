"""Nota de cada lutador em cada luta, de 0 a 10 com base 6,6 (estilo Sofascore).

nota = 6,6 + resultado + desempenho (com os pesos do estilo) + força do adversário, limitada a [3, 10]

- Estilo (Striker, Wrestler, Finalizador, Completo): sai dos números por 15 minutos (golpes, quedas,
  % do tempo controlando, tentativas de finalização). Na nota de cada luta, só das lutas ANTERIORES
  (`estilos_por_luta`); o rótulo do site usa a carreira até hoje (`classificar_estilos`).
- Desempenho: os pesos de cada estatística NÃO são inventados: saem de uma regressão logística nas
  lutas decididas pelos juízes, que mede quanto cada diferença (o que você fez menos o que sofreu,
  por minuto) pesa para vencer. `aprender_pesos`. O estilo reforça o peso do que é o jogo do
  lutador no ataque (`MULTIPLICADORES`), sem perdoar o que ele sofreu.
- Resultado: vitória/derrota e método; nocaute e finalização valem mais quanto mais cedo.
- Adversário: Elo calculado em ordem cronológica, em desvios-padrão; vencer alguém forte pesa a favor
  (perder para ele, metade).

Python puro + numpy (sem scikit-learn), para rodar na CI só com requirements-test.txt.
"""

import numpy as np
import pandas as pd

from src.limpeza import adicionar_duracao

BASE = 6.6
NOTA_MIN, NOTA_MAX = 3.0, 10.0

# Estatísticas do desempenho (contagem por lutador numa luta). Golpes na cabeça separados de corpo/perna
# porque o peso deles é diferente; "Ground" não entra porque já está dentro de cabeça/corpo/perna.
# Lista = soma das colunas; tupla = primeira menos a segunda.
ESTATISTICAS = {
    "cabeca": "Head_landed",
    "corpo_perna": ["Body_landed", "Leg_landed"],
    "kd": "KD",
    "quedas": "Td_landed",
    "controle": "Ctrl_seconds",  # em minutos (dividido por 60)
    "finalizacao": "Sub. att",
    "reversao": "Rev.",
    "quedas_erradas": ("Td_attempted", "Td_landed"),  # tentadas - certas: os juízes punem a queda errada
}
NOMES = list(ESTATISTICAS)

# Quanto o estilo reforça (ou alivia) cada estatística no ATAQUE. Depois de aplicados, os pesos de
# cada estilo são reescalados para que o ataque médio dos lutadores daquele estilo continue igual
# (`pesos_por_estilo`): o estilo muda o que conta, não dá vantagem a um estilo sobre outro.
MULTIPLICADORES = {
    "Striker": {"cabeca": 1.3, "corpo_perna": 1.3, "kd": 1.3, "quedas": 0.6, "controle": 0.6, "finalizacao": 0.8, "reversao": 0.8,
                "quedas_erradas": 1.0},
    "Wrestler": {"cabeca": 0.9, "corpo_perna": 0.9, "kd": 1.0, "quedas": 1.4, "controle": 1.4, "finalizacao": 1.0, "reversao": 1.2,
                 "quedas_erradas": 1.0},
    "Finalizador": {"cabeca": 0.9, "corpo_perna": 0.9, "kd": 1.0, "quedas": 1.1, "controle": 1.1, "finalizacao": 1.6, "reversao": 1.3,
                    "quedas_erradas": 1.0},
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
        if isinstance(coluna, list):
            saida[nome] = df[coluna].sum(axis=1)
        elif isinstance(coluna, tuple):
            saida[nome] = df[coluna[0]] - df[coluna[1]]
        else:
            saida[nome] = df[coluna]
    saida["controle"] = saida["controle"] / 60
    return saida.fillna(0)  # coluna sem valor numa luta com estatísticas = não aconteceu


def _rotular(n, golpes, quedas, ctrl, fin, dur):
    """Estilo a partir das somas de lutas, golpes, quedas, controle (s), finalizações e duração (s)."""
    por15 = dur / 60 / 15
    quedas15, fin15 = quedas / por15, fin / por15
    ctrl_pct = ctrl / dur * 100
    estilo = pd.Series("Completo", index=n.index)
    estilo[(ctrl_pct < 12) & (quedas15 < 1)] = "Striker"
    estilo[(ctrl_pct >= 30) | (quedas15 >= 2.5)] = "Wrestler"
    estilo[fin15 >= 1.5] = "Finalizador"
    estilo[n < MIN_LUTAS_ESTILO] = "Completo"
    return estilo


COLUNAS_ESTILO = {"golpes": "Sig_str_landed", "quedas": "Td_landed", "ctrl": "Ctrl_seconds", "fin": "Sub. att", "dur": "Duracao_seg"}


def classificar_estilos(df):
    """Estilo de cada lutador HOJE ({nome: estilo}) pelas médias da carreira, por 15 minutos.

    Precisa de `Duracao_seg` (adicionar_duracao). Com menos de MIN_LUTAS_ESTILO lutas com
    estatísticas, o lutador fica "Completo" (pesos neutros). É o rótulo mostrado no site; a nota de
    cada luta usa `estilos_por_luta`, que só olha as lutas anteriores.
    """
    com = df[df["Sig_str_landed"].notna()]
    g = com.groupby("Fighter").agg(n=("Fight_URL", "size"), **{k: (c, "sum") for k, c in COLUNAS_ESTILO.items()})
    return _rotular(g["n"], g["golpes"], g["quedas"], g["ctrl"], g["fin"], g["dur"]).to_dict()


def estilos_por_luta(df, datas_eventos):
    """Estilo de cada lutador na véspera de cada luta, só com as lutas ANTERIORES (sem olhar o futuro).

    Devolve {(Fight_URL, Fighter): estilo}. Antes de MIN_LUTAS_ESTILO lutas com estatísticas = "Completo".
    """
    com = ordem_cronologica(df[df["Sig_str_landed"].notna()], datas_eventos)
    valores = com[list(COLUNAS_ESTILO.values())].fillna(0)
    somas = valores.groupby(com["Fighter"]).cumsum() - valores  # só as lutas anteriores
    n = com.groupby("Fighter").cumcount()
    c = {k: somas[col] for k, col in COLUNAS_ESTILO.items()}
    with np.errstate(divide="ignore", invalid="ignore"):
        estilo = _rotular(n, c["golpes"], c["quedas"], c["ctrl"], c["fin"], c["dur"])
    return dict(zip(zip(com["Fight_URL"], com["Fighter"]), estilo))


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
    # Padroniza antes da penalidade L2: sem isso, estatísticas raras (knockdown, finalização, por minuto
    # valores pequenos) precisam de coeficientes grandes e a L2 os encolhe (o knockdown valia 1,5 golpe
    # na cabeça em vez de ~8). Depois volta à escala original.
    desvio = X.std(axis=0)
    desvio[desvio == 0] = 1.0
    return dict(zip(NOMES, regressao_logistica(X / desvio, y) / desvio))


def pesos_por_estilo(pares, pesos):
    """Pesos do ataque para cada estilo: pesos universais × MULTIPLICADORES, reescalados para que o
    ataque médio das atuações daquele estilo (coluna `Estilo` de `pares`) fique igual ao calculado
    com os pesos universais."""
    saida = {}
    estilo_linha = pares["Estilo"]
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


# Elo: K maior nas primeiras lutas (o estreante ainda não tem nível conhecido) e decisão dividida ou
# majoritária vale menos que uma vitória clara (0,6 em vez de 1), como no Fight Matrix. Testado na base:
# acerta 57% das lutas contra 55% do Elo simples com K = 32, e o Elo fica 2× mais espalhado.
K_ELO = 64
K_ELO_NOVATO = 128
LUTAS_NOVATO = 3
PLACAR_APERTADO = 0.6
ELO_INICIAL = 1500


def _k(lutas_antes):
    return K_ELO_NOVATO if lutas_antes < LUTAS_NOVATO else K_ELO


def _atualizar_elo(elo, a, b, resultado_a, metodo=None, k_a=K_ELO, k_b=K_ELO, inicial=ELO_INICIAL):
    """Atualiza o Elo dos dois lados depois de uma luta (NC não muda nada)."""
    if resultado_a == "NC":
        return
    ea, eb = elo.get(a, inicial), elo.get(b, inicial)
    placar = {"W": 1.0, "L": 0.0}.get(resultado_a, 0.5)
    if placar != 0.5 and isinstance(metodo, str) and ("Split" in metodo or "Majority" in metodo):
        placar = PLACAR_APERTADO if placar == 1.0 else 1 - PLACAR_APERTADO
    esperado = 1 / (1 + 10 ** ((eb - ea) / 400))
    elo[a] = ea + k_a * (placar - esperado)
    elo[b] = eb + k_b * ((1 - placar) - (1 - esperado))


def calcular_elo(lutas, inicial=ELO_INICIAL):
    """Elo ANTES de cada luta. `lutas`: DataFrame em ordem cronológica com Fight_URL, Fighter,
    Adversario, Resultado e (opcional) Method, uma linha por lutador. Devolve {(Fight_URL, Fighter): elo_antes}."""
    elo, antes, n = {}, {}, {}
    for url, grupo in lutas.groupby("Fight_URL", sort=False):
        if len(grupo) != 2:
            continue
        a, b = grupo.iloc[0], grupo.iloc[1]
        fa, fb = a["Fighter"], b["Fighter"]
        antes[(url, fa)], antes[(url, fb)] = elo.get(fa, inicial), elo.get(fb, inicial)
        _atualizar_elo(elo, fa, fb, a["Resultado"], a.get("Method"), _k(n.get(fa, 0)), _k(n.get(fb, 0)), inicial)
        n[fa], n[fb] = n.get(fa, 0) + 1, n.get(fb, 0) + 1
    return antes


# Adversário: Elo do adversário em desvios-padrão (z) × PESO_ADVERSARIO, limitado a ±0,4. Vale cheio para
# quem vence; quem perde para alguém forte leva só metade do bônus (perder para alguém fraco tira cheio).
PESO_ADVERSARIO = 0.2
LIMITE_ADVERSARIO = 0.4


def bonus_adversario(elo_adversario, resultado="W", media=ELO_INICIAL, desvio=100.0):
    """Parte da nota que vem da força do adversário (Elo antes da luta)."""
    z = (elo_adversario - media) / desvio if desvio else 0.0
    valor = float(np.clip(PESO_ADVERSARIO * z, -LIMITE_ADVERSARIO, LIMITE_ADVERSARIO))
    if resultado != "W" and valor > 0:
        valor *= 0.5
    return valor


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
                        min_lutas=MIN_LUTAS_RANKING, inicial=ELO_INICIAL):
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
            if len(luta) == 2:
                a, b = luta.iloc[0], luta.iloc[1]
                _atualizar_elo(elo, a["Fighter"], b["Fighter"], a["Resultado"], a.get("Method"),
                               _k(lutas.get(a["Fighter"], 0)), _k(lutas.get(b["Fighter"], 0)), inicial)
            for f in luta["Fighter"]:
                if isinstance(cat_luta, str) and cat_luta not in SEM_CATEGORIA_PROPRIA:
                    categoria[f] = cat_luta
                ultima[f] = data
                lutas[f] = lutas.get(f, 0) + 1
    return posicoes


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
    estilos = classificar_estilos(df)  # rótulo de hoje (site)
    pares = montar_pares(df)
    na_vespera = estilos_por_luta(df, datas_eventos)  # o peso de cada luta só usa as lutas anteriores
    pares["Estilo"] = [na_vespera.get(chave, "Completo") for chave in zip(pares["Fight_URL"], pares["Fighter"])]
    pesos = aprender_pesos(pares)
    pesos_estilo = pesos_por_estilo(pares, pesos)

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
    elo = calcular_elo(adv[["Fight_URL", "Fighter", "Adversario", "Resultado", "Method"]])
    valores = np.array(list(elo.values()))
    media, desvio = valores.mean(), valores.std()
    pares["adversario"] = [bonus_adversario(elo.get((u, a), ELO_INICIAL), r, media, desvio)
                           for u, a, r in zip(pares["Fight_URL"], pares["Adversario"], pares["Resultado"])]

    pares["Nota"] = (BASE + pares["resultado"] + pares["desempenho"] + pares["adversario"]).clip(NOTA_MIN, NOTA_MAX).round(1)
    colunas = ["Fight_URL", "Fighter", "Adversario", "Estilo", "Resultado", "Method", "resultado", "desempenho", "adversario", "Nota"]
    info = {"pesos": pesos, "pesos_estilo": pesos_estilo, "escala": escala, "estilos": estilos,
            "elo_media": media, "elo_desvio": desvio}
    return pares[colunas], info
