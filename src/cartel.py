"""Índice de Cartel: quanto vale o cartel de cada lutador pela força de quem ele enfrentou.

Mede QUEM o lutador venceu (e para quem perdeu), não COMO lutou (isso é a nota de src/rating.py).

Cada luta vale pontos pela força do adversário naquele dia:
- força = 75% do Elo do adversário na véspera + 25% do maior Elo que ele teve dali em diante (`PESO_EPOCA`):
  vencer alguém que depois virou elite ganha um pouco de crédito em retrospecto, sem valer o mesmo que
  vencê-lo no auge. O Elo é o mesmo do rating e da previsão (`_atualizar_elo`, K maior nas 3 primeiras lutas).
- ajuste de época: o Elo do topo sobe com os anos (mais lutas acumuladas). Cada Elo é somado à diferença
  entre a elite de hoje e a elite do ano da luta (elite = Elo médio de quem estava no top 5 da categoria,
  média móvel de 3 anos). Só de `INICIO_AJUSTE` (2001) em diante: nos torneios antigos havia pouca gente e
  a elite do ano é mal medida. A elite feminina é medida à parte (as divisões femininas têm menos lutas e o
  Elo delas sobe menos), e o ajuste leva as duas para a mesma escala.
- dificuldade = chance de esse adversário vencer um lutador de referência (Elo `REFERENCIA`).
  Vitória soma a dificuldade; derrota tira (1 − dificuldade): perder para o campeão custa pouco, perder
  para alguém fraco custa muito. Empate = metade de cada.
- bônus: vitória em disputa de cinturão ×1,25 (final do TUF não conta), nocaute/finalização ×1,1, decisão
  dividida ou majoritária ×0,75 (vale também para a derrota). Desclassificação e luta sem resultado não contam.

Três visões, cada uma responde a uma pergunta:
- Qualidade = soma ÷ (lutas + `LUTAS_FANTASMAS`): o cartel mais forte por luta.
- Longevidade = soma: quem acumulou mais.
- Auge = melhor trecho de `JANELA_AUGE` lutas seguidas ÷ `JANELA_AUGE`: o melhor período.
- Geral = média das três em desvios-padrão (`anexar_geral`): quem é forte em todas.
Homens e mulheres em rankings separados.

Entrada: o dicionário de dados/lutas.json (`montar_lutas` em exportar.py). `python -m src.cartel` regenera
dados/cartel.json a partir de dados/lutas.json (não precisa de data/).
"""

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

from src.rating import ELO_INICIAL, _atualizar_elo, _k

PESO_EPOCA = 0.75
REFERENCIA = 1600  # lutador de referência: um pouco acima da média do UFC
INICIO_AJUSTE = 2001
TOP_ELITE = 5
ANOS_JANELA = 1  # média móvel: o ano, o anterior e o seguinte
MIN_AMOSTRA_ELITE = 20  # lados no top 5 dentro da janela para medir a elite do ano
BONUS_CINTURAO = 1.25
BONUS_FINALIZACAO = 1.1
FATOR_APERTADA = 0.75
LUTAS_FANTASMAS = 2
MIN_LUTAS = 8
JANELA_AUGE = 10
ELITE = 1750  # força a partir da qual o adversário conta como "elite" (~5% mais fortes)
NAO_CONTAM = {"DQ"}  # métodos fora do índice (além das lutas sem resultado)

PASTA_DADOS = Path(__file__).resolve().parent.parent / "dados"


def eh_feminina(categoria):
    return isinstance(categoria, str) and categoria.startswith("Women")


def lutadoras(dados_lutas):
    """Nomes de quem lutou em alguma categoria feminina (peso casado entre mulheres não tem "Women")."""
    return {lado[0] for luta in dados_lutas["lutas"] if eh_feminina(luta[1]) for lado in (luta[8], luta[9])}


def genero_da_luta(luta, mulheres):
    return "F" if luta[8][0] in mulheres or luta[9][0] in mulheres else "M"


def finalizacao(metodo):
    return isinstance(metodo, str) and (metodo.startswith("KO") or metodo.startswith("TKO") or metodo == "Submission")


def apertada(metodo):
    return isinstance(metodo, str) and ("Split" in metodo or "Majority" in metodo)


def dificuldade(forca, referencia=REFERENCIA):
    """Chance de um adversário com essa força vencer o lutador de referência (fórmula do Elo)."""
    return 1 / (1 + 10 ** ((referencia - forca) / 400))


def pontos(resultado, forca, metodo=None, cinturao=0):
    """Pontos de uma luta para quem teve `resultado` (W/L/D) contra um adversário de força `forca`."""
    p = dificuldade(forca)
    fator = FATOR_APERTADA if apertada(metodo) else 1.0
    if resultado == "W":
        return p * fator * (BONUS_CINTURAO if cinturao == 1 else 1.0) * (BONUS_FINALIZACAO if finalizacao(metodo) else 1.0)
    if resultado == "L":
        return -(1 - p) * fator
    if resultado == "D":
        return 0.5 * p - 0.5 * (1 - p)
    return 0.0


def cronologia(dados_lutas):
    """Lutas de lutas.json da mais antiga para a mais recente, com a data.

    O arquivo vem da mais recente para a mais antiga e, dentro do evento, da luta principal para a primeira
    do card: ao contrário, fica na ordem em que as lutas aconteceram (a mesma de `ordem_cronologica`)."""
    eventos = dados_lutas["eventos"]
    return [(eventos[luta[0]][1], luta) for luta in reversed(dados_lutas["lutas"])]


def percorrer_elo(lutas_em_ordem, inicial=ELO_INICIAL):
    """Elo de cada lado antes e depois de cada luta: [(antes_1, depois_1, antes_2, depois_2)], na ordem dada."""
    elo, n, saida = {}, {}, []
    for _, luta in lutas_em_ordem:
        a, b = luta[8][0], luta[9][0]
        ea, eb = elo.get(a, inicial), elo.get(b, inicial)
        _atualizar_elo(elo, a, b, luta[8][1], luta[2], _k(n.get(a, 0)), _k(n.get(b, 0)), inicial)
        n[a], n[b] = n.get(a, 0) + 1, n.get(b, 0) + 1
        saida.append((ea, elo.get(a, ea), eb, elo.get(b, eb)))
    return saida


def nivel_da_elite(lutas_em_ordem, elos, mulheres, top=TOP_ELITE):
    """{"M": {ano: elo}, "F": {ano: elo}}: Elo médio na véspera de quem estava no top `top` da categoria
    (posição de lutas.json, lado[10]), em média móvel de 2×ANOS_JANELA+1 anos."""
    por_ano = {"M": defaultdict(list), "F": defaultdict(list)}
    for (data, luta), (ea, _, eb, _) in zip(lutas_em_ordem, elos):
        genero = genero_da_luta(luta, mulheres)
        for lado, e in ((luta[8], ea), (luta[9], eb)):
            if len(lado) > 10 and lado[10] and lado[10] <= top:
                por_ano[genero][int(data[:4])].append(e)
    nivel = {}
    for genero, anos in por_ano.items():
        nivel[genero] = {}
        if not anos:
            continue
        for ano in range(min(anos), max(anos) + 1):
            amostra = [e for a in range(ano - ANOS_JANELA, ano + ANOS_JANELA + 1) for e in anos.get(a, [])]
            if len(amostra) >= MIN_AMOSTRA_ELITE:
                nivel[genero][ano] = round(float(np.mean(amostra)), 1)
    return nivel


def _elite_no_ano(niveis, ano):
    """Nível do ano; fora da faixa medida, o do ano medido mais próximo."""
    if ano in niveis:
        return niveis[ano]
    return niveis[min(niveis, key=lambda a: (abs(a - ano), -a))]


def ajuste_de_epoca(niveis, data, genero, inicio=INICIO_AJUSTE):
    """Quanto somar a um Elo dessa data para levá-lo à escala de hoje (elite masculina do último ano)."""
    ano = int(data[:4])
    if ano < inicio or not niveis.get(genero) or not niveis.get("M"):
        return 0.0
    hoje = niveis["M"][max(niveis["M"])]
    return hoje - _elite_no_ano(niveis[genero], ano)


def lutas_por_lutador(dados_lutas, peso_epoca=PESO_EPOCA, ajustar=True):
    """{nome: [luta, ...]} na ordem cronológica, cada luta = dict com data, adversário, resultado, força do
    adversário (já com época e retrospecto), pontos e posição do adversário. Desclassificação e NC ficam de fora."""
    em_ordem = cronologia(dados_lutas)
    elos = percorrer_elo(em_ordem)
    mulheres = lutadoras(dados_lutas)
    niveis = nivel_da_elite(em_ordem, elos, mulheres)

    # Elo ajustado de cada lado antes/depois de cada luta, e o pico de cada lutador dali em diante
    historico = defaultdict(list)  # nome -> [(i, antes, depois)]
    ajustados = []
    for i, ((data, luta), (ea, da, eb, db)) in enumerate(zip(em_ordem, elos)):
        genero = genero_da_luta(luta, mulheres)
        soma = ajuste_de_epoca(niveis, data, genero) if ajustar else 0.0
        ajustados.append((ea + soma, eb + soma))
        historico[luta[8][0]].append((i, ea + soma, da + soma))
        historico[luta[9][0]].append((i, eb + soma, db + soma))
    pico = {}
    for nome, h in historico.items():
        maior = -np.inf
        for i, antes, depois in reversed(h):
            maior = max(maior, depois)
            pico[(i, nome)] = max(antes, maior)

    por = defaultdict(list)
    for i, (data, luta) in enumerate(em_ordem):
        metodo, cinturao = luta[2], luta[5]
        if metodo in NAO_CONTAM:
            continue
        for eu, adv, elo_adv in ((luta[8], luta[9], ajustados[i][1]), (luta[9], luta[8], ajustados[i][0])):
            if eu[1] not in ("W", "L", "D"):
                continue
            forca = peso_epoca * elo_adv + (1 - peso_epoca) * pico[(i, adv[0])]
            por[eu[0]].append({"data": data, "adv": adv[0], "res": eu[1], "forca": forca, "cat": luta[1],
                               "g": genero_da_luta(luta, mulheres),
                               "metodo": metodo, "cinturao": cinturao, "pontos": pontos(eu[1], forca, metodo, cinturao)})
    return por, niveis


def melhor_trecho(lutas, janela=None):
    """Índice inicial do trecho de `janela` (padrão JANELA_AUGE) lutas seguidas com mais pontos (o mais antigo
    no empate), ou None se não houver lutas suficientes."""
    janela = janela or JANELA_AUGE
    if len(lutas) < janela:
        return None
    somas = np.convolve([l["pontos"] for l in lutas], np.ones(janela), mode="valid")
    return int(np.argmax(somas))


def _cartel(lutas):
    w = sum(l["res"] == "W" for l in lutas)
    d = sum(l["res"] == "D" for l in lutas)
    return f"{w}-{sum(l['res'] == 'L' for l in lutas)}" + (f"-{d}" if d else "")


def resumo_do_lutador(nome, lutas):
    """Linha do lutador em cartel.json (chaves curtas, valores arredondados)."""
    soma = sum(l["pontos"] for l in lutas)
    vitorias = [l for l in lutas if l["res"] == "W"]
    derrotas = [l for l in lutas if l["res"] == "L"]
    linha = {
        "nome": nome,
        "g": lutas[-1]["g"],
        "cartel": _cartel(lutas),
        "n": len(lutas),
        "qual": round(soma / (len(lutas) + LUTAS_FANTASMAS), 4),
        "long": round(soma, 3),
        "elite": sum(l["forca"] >= ELITE for l in vitorias),
        "forca": round(float(np.mean([l["forca"] for l in lutas]))),
        "anos": [int(lutas[0]["data"][:4]), int(lutas[-1]["data"][:4])],
        "ultima": lutas[-1]["data"],
    }
    if vitorias:
        m = max(vitorias, key=lambda l: (l["forca"], l["data"]))
        linha["melhor"] = [m["adv"], round(m["forca"]), m["data"]]
    if derrotas:
        p = min(derrotas, key=lambda l: (l["forca"], l["data"]))
        linha["pior"] = [p["adv"], round(p["forca"]), p["data"]]
    inicio = melhor_trecho(lutas)
    if inicio is not None:
        trecho = lutas[inicio:inicio + JANELA_AUGE]
        linha["auge"] = round(sum(l["pontos"] for l in trecho) / JANELA_AUGE, 4)
        linha["trecho"] = [trecho[0]["data"], trecho[-1]["data"], _cartel(trecho),
                           sum(l["res"] == "W" and l["forca"] >= ELITE for l in trecho)]
    return linha


VISOES = ("qual", "long", "auge")


def anexar_geral(lutadores):
    """Visão Geral: média das três visões em desvios-padrão (z), entre os do mesmo gênero que têm as três
    (as escalas são diferentes: ~0,8 por luta × ~19 na soma). Pesos iguais: entre os 100 melhores, as visões
    concordam só em parte (correlação 0,53 a 0,69), então cada uma traz informação própria, e o Auge fica
    entre as outras duas. Quem não tem o Auge (menos de JANELA_AUGE lutas) fica sem Geral."""
    for genero in ("M", "F"):
        grupo = [l for l in lutadores if l["g"] == genero and all(l.get(v) is not None for v in VISOES)]
        if len(grupo) < 2:
            continue
        valores = np.array([[l[v] for v in VISOES] for l in grupo], dtype=float)
        z = (valores - valores.mean(axis=0)) / valores.std(axis=0)
        for l, linha in zip(grupo, z.mean(axis=1)):
            l["geral"] = round(float(linha), 3)
    return lutadores


def montar_cartel(dados_lutas, min_lutas=MIN_LUTAS):
    """Conteúdo de dados/cartel.json: parâmetros, nível da elite por ano e um resumo por lutador com
    `min_lutas`+ lutas que contam. As posições de cada visão são calculadas no navegador (por gênero e filtro)."""
    por, niveis = lutas_por_lutador(dados_lutas)
    lutadores = anexar_geral([resumo_do_lutador(nome, lutas) for nome, lutas in sorted(por.items()) if len(lutas) >= min_lutas])
    return {
        "parametros": {"peso_epoca": PESO_EPOCA, "referencia": REFERENCIA, "inicio_ajuste": INICIO_AJUSTE,
                       "elite": ELITE, "min_lutas": min_lutas, "janela_auge": JANELA_AUGE,
                       "fantasmas": LUTAS_FANTASMAS, "bonus_cinturao": BONUS_CINTURAO,
                       "bonus_finalizacao": BONUS_FINALIZACAO, "fator_apertada": FATOR_APERTADA},
        "elite_por_ano": {g: {str(a): v for a, v in anos.items()} for g, anos in niveis.items()},
        "lutadores": lutadores,
    }


def exportar_cartel(dados_lutas, pasta=PASTA_DADOS):
    saida = {"gerado_em": date.today().isoformat(), **montar_cartel(dados_lutas)}
    with open(Path(pasta) / "cartel.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, separators=(",", ":"))
    return saida


if __name__ == "__main__":
    with open(PASTA_DADOS / "lutas.json", encoding="utf-8") as f:
        resultado = exportar_cartel(json.load(f))
    por_genero = defaultdict(int)
    for l in resultado["lutadores"]:
        por_genero[l["g"]] += 1
    print(f"{len(resultado['lutadores'])} lutadores ({por_genero['M']} homens, {por_genero['F']} mulheres) -> dados/cartel.json")
