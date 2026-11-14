"""Previsão de luta: chance de cada lado vencer, pelo Elo, pela idade e pela envergadura.

Modelo: regressão logística sem intercepto (simétrica: trocar os lados troca o sinal) sobre três
diferenças conhecidas ANTES da luta:
- Elo (src/rating.py, o mesmo do bônus de adversário e do top 15), em centenas de pontos;
- idade na data da luta, em anos (quem é mais novo tende a vencer, ver gráfico 19);
- envergadura, em cm.
Diferença que não dá para calcular (sem nascimento ou envergadura) entra como 0: o modelo usa o que houver.

Teste honesto: os pesos que medem o acerto são aprendidos só nas lutas ANTES de `CORTE` e avaliados nas
lutas a partir dele (o Elo de cada luta já usa só as lutas anteriores). Os pesos que o site usa para
lutas futuras são aprendidos com todas as lutas.
Só lutas com vencedor (W/L) entram no treino e no teste; empate e sem resultado ficam de fora.
"""

from datetime import date

import numpy as np
import pandas as pd

from src.rating import ELO_INICIAL, _atualizar_elo, _k, ordem_cronologica, regressao_logistica

CORTE = "2020-01-01"
VARIAVEIS = ["elo", "idade", "env"]  # ordem das colunas de X e dos pesos no JSON
# Faixas da chance dada ao favorito, para conferir se "70%" acontece mesmo ~70% das vezes
FAIXAS_CALIBRACAO = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75]
L2 = 1.0
ZEBRA = 0.5  # vencedor com chance abaixo disso na véspera = zebra


def confrontos_do_resumo(df, datas_eventos, lutadores):
    """Uma linha por luta, em ordem cronológica (como o Elo do rating): data, a, b, resultado de a,
    método, nascimento e envergadura (cm) dos dois. `lutadores` = data/processed/lutadores.csv (junção
    por Fighter_URL, como nos gráficos 19 e 20)."""
    ordem = ordem_cronologica(df, datas_eventos)
    fisico = lutadores.set_index("Fighter_URL")
    linhas = []
    for url, luta in ordem.groupby("Fight_URL", sort=False):
        if len(luta) != 2:
            continue
        a, b = luta.iloc[0], luta.iloc[1]

        def dado(lado, coluna):
            fu = lado.get("Fighter_URL")
            if not isinstance(fu, str) or fu not in fisico.index:
                return None
            valor = fisico.at[fu, coluna]
            return None if pd.isna(valor) else valor

        linhas.append({"data": a["_data"], "a": a["Fighter"], "b": b["Fighter"], "resultado_a": a["Resultado"],
                       "metodo": a.get("Method"), "nasc_a": dado(a, "DOB"), "nasc_b": dado(b, "DOB"),
                       "env_a": dado(a, "Reach_cm"), "env_b": dado(b, "Reach_cm")})
    return pd.DataFrame(linhas, columns=["data", "a", "b", "resultado_a", "metodo", "nasc_a", "nasc_b", "env_a", "env_b"])


def _anos(nascimento, dia):
    if not isinstance(nascimento, str) or not isinstance(dia, str):
        return None
    n, d = date.fromisoformat(nascimento[:10]), date.fromisoformat(dia[:10])
    return (d - n).days / 365.25


def percorrer_elo(confrontos, inicial=ELO_INICIAL):
    """Elo de a e de b na véspera de cada luta (colunas elo_a, elo_b) e, ao fim, o Elo e o nº de lutas de
    cada lutador. Mesma conta de `calcular_elo` (rating.py): K maior nas 3 primeiras lutas, decisão
    dividida/majoritária vale 0,6, sem resultado não muda nada."""
    elo, n, ultima = {}, {}, {}
    antes_a, antes_b = [], []
    for luta in confrontos.itertuples(index=False):
        antes_a.append(elo.get(luta.a, inicial))
        antes_b.append(elo.get(luta.b, inicial))
        _atualizar_elo(elo, luta.a, luta.b, luta.resultado_a, luta.metodo, _k(n.get(luta.a, 0)), _k(n.get(luta.b, 0)), inicial)
        for f in (luta.a, luta.b):
            n[f] = n.get(f, 0) + 1
            ultima[f] = luta.data
    return confrontos.assign(elo_a=antes_a, elo_b=antes_b), {f: (elo.get(f, inicial), n[f], ultima[f]) for f in n}


def matriz(confrontos):
    """X (diferenças a − b: Elo/100, idade em anos, envergadura em cm; ausente = 0) de cada luta."""
    elo = (confrontos["elo_a"] - confrontos["elo_b"]) / 100
    idade = [(_anos(na, d) - _anos(nb, d)) if _anos(na, d) is not None and _anos(nb, d) is not None else 0.0
             for na, nb, d in zip(confrontos["nasc_a"], confrontos["nasc_b"], confrontos["data"])]
    env = [(ea - eb) if ea is not None and eb is not None and not pd.isna(ea) and not pd.isna(eb) else 0.0
           for ea, eb in zip(confrontos["env_a"], confrontos["env_b"])]
    return np.column_stack([np.asarray(elo, dtype=float), np.asarray(idade, dtype=float), np.asarray(env, dtype=float)])


def chance(X, pesos):
    """Chance de a vencer em cada linha de X."""
    return 1 / (1 + np.exp(-(X @ np.asarray(pesos, dtype=float))))


def avaliar(p, y):
    """Acerto (favorito venceu), log-loss, Brier e calibração por faixa da chance do favorito.

    `p` = chance de a, `y` = 1 se a venceu. Luta com p = 0,5 exata não tem favorito: fica fora do acerto
    e da calibração (entra no log-loss e no Brier)."""
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    favorito = np.where(p >= 0.5, p, 1 - p)
    acertou = np.where(p >= 0.5, y, 1 - y)
    com_favorito = p != 0.5
    calibracao = []
    limites = FAIXAS_CALIBRACAO + [1.0001]
    for ini, fim in zip(limites, limites[1:]):
        g = com_favorito & (favorito >= ini) & (favorito < fim)
        if g.sum():
            calibracao.append([ini, round(float(favorito[g].mean()), 3), round(float(acertou[g].mean()), 3), int(g.sum())])
    pc = np.clip(p, 1e-9, 1 - 1e-9)
    acerto = round(float(acertou[com_favorito].mean()), 3) if com_favorito.any() else None
    return {"lutas": int(len(y)), "acerto": acerto,
            "log_loss": round(float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc))), 4),
            "brier": round(float(np.mean((p - y) ** 2)), 4), "calibracao": calibracao}


def zebras(decididas, p, limite=ZEBRA):
    """Vitórias de quem tinha chance < `limite` (p = chance de a, em `decididas`, só lutas W/L)."""
    lista = []
    for luta, chance_a in zip(decididas.itertuples(index=False), p):
        venceu_a = luta.resultado_a == "W"
        chance_v = chance_a if venceu_a else 1 - chance_a
        if chance_v >= limite:
            continue
        v, d = (luta.a, luta.b) if venceu_a else (luta.b, luta.a)
        elo_v, elo_d = (luta.elo_a, luta.elo_b) if venceu_a else (luta.elo_b, luta.elo_a)
        lista.append([luta.data, v, d, round(float(chance_v), 3), round(elo_v), round(elo_d)])
    return sorted(lista, key=lambda z: (z[3], z[0]))


def montar_previsao(confrontos, corte=CORTE):
    """Tudo o que o site precisa para prever (dados/previsao.json).

    {"pesos": {elo, idade, env} (todas as lutas), "corte": data,
     "teste": {lutas, acerto, log_loss, brier, calibracao: [[faixa, chance média, acerto, lutas], ...],
               "so_elo": acerto/log_loss do Elo sozinho, "treino": lutas do treino},
     "elo": {nome: [Elo hoje, lutas, data da última luta]},
     "zebras": [[data, vencedor, perdedor, chance do vencedor, Elo do vencedor, Elo do perdedor], ...]}
    Zebras: lutas em que o vencedor tinha chance abaixo de `ZEBRA` na véspera, com os pesos de todas as
    lutas e o Elo, a idade e a envergadura daquele dia; da mais improvável para a menos.
    """
    confrontos, final = percorrer_elo(confrontos)
    decididas = confrontos[confrontos["resultado_a"].isin(["W", "L"])].reset_index(drop=True)
    X = matriz(decididas)
    y = (decididas["resultado_a"] == "W").to_numpy(dtype=float)
    treino = (decididas["data"] < corte).to_numpy()
    teste = ~treino
    resultado = {"corte": corte, "variaveis": VARIAVEIS}
    if treino.sum() and teste.sum():
        pesos_treino = regressao_logistica(X[treino], y[treino], l2=L2)
        so_elo = regressao_logistica(X[treino][:, :1], y[treino], l2=L2)
        avaliacao = avaliar(chance(X[teste], pesos_treino), y[teste])
        base = avaliar(chance(X[teste][:, :1], so_elo), y[teste])
        resultado["teste"] = {**avaliacao, "treino": int(treino.sum()),
                              "so_elo": {"acerto": base["acerto"], "log_loss": base["log_loss"]}}
    pesos = regressao_logistica(X, y, l2=L2) if len(y) else np.zeros(len(VARIAVEIS))
    resultado["pesos"] = {nome: round(float(v), 5) for nome, v in zip(VARIAVEIS, pesos)}
    resultado["zebras"] = zebras(decididas, chance(X, pesos))
    resultado["elo"] = {nome: [round(e), n, ultima] for nome, (e, n, ultima) in sorted(final.items())}
    return resultado
