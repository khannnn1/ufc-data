"""Índice de Cartel (src/cartel.py), com um mini lutas.json sintético."""

import pytest

from src import cartel
from src.cartel import (ajuste_de_epoca, cronologia, dificuldade, lutas_por_lutador, melhor_trecho, montar_cartel,
                        percorrer_elo, pontos)


def lado(nome, res, posicao=None):
    return [nome, res, 0, 0, 0, 0, 0, 0, None, None, posicao]


def luta(evento, a, b, res_a="W", metodo="Decision - Unanimous", cinturao=0, cat="Lightweight", pos_a=None, pos_b=None):
    res_b = {"W": "L", "L": "W"}.get(res_a, res_a)
    return [evento, cat, metodo, 3, "5:00", cinturao, 0, 0, lado(a, res_a, pos_a), lado(b, res_b, pos_b)]


def dados(*lutas, eventos=None):
    """lutas da mais antiga para a mais recente, uma por evento; o arquivo real guarda ao contrário."""
    n = len(lutas)
    eventos = eventos or [[f"Evento {i}", f"2020-01-{n - i:02d}", f"id{i}"] for i in range(n)]
    return {"eventos": eventos, "lutas": [[n - 1 - i, *l[1:]] for i, l in enumerate(lutas)][::-1]}


def test_dificuldade_e_pontos():
    assert dificuldade(cartel.REFERENCIA) == pytest.approx(0.5)
    forte, fraco = 1900, 1400
    assert pontos("W", forte) > pontos("W", fraco) > 0
    # derrota para alguém forte custa pouco, para alguém fraco custa muito
    assert -0.2 < pontos("L", forte) < 0 and pontos("L", fraco) < -0.6
    assert pontos("D", cartel.REFERENCIA) == pytest.approx(0)
    base = pontos("W", 1700)
    assert pontos("W", 1700, cinturao=1) == pytest.approx(base * cartel.BONUS_CINTURAO)
    assert pontos("W", 1700, cinturao=2) == pytest.approx(base)  # final do TUF não é cinturão
    assert pontos("W", 1700, "KO/TKO") == pytest.approx(base * cartel.BONUS_FINALIZACAO)
    assert pontos("W", 1700, "Submission") == pytest.approx(base * cartel.BONUS_FINALIZACAO)
    assert pontos("W", 1700, "Decision - Split") == pytest.approx(base * cartel.FATOR_APERTADA)
    assert pontos("L", 1700, "Decision - Majority") == pytest.approx(pontos("L", 1700) * cartel.FATOR_APERTADA)


def test_cronologia_inverte_o_arquivo():
    d = dados(luta(0, "A", "B"), luta(0, "C", "D"))
    em_ordem = cronologia(d)
    assert [l[8][0] for _, l in em_ordem] == ["A", "C"]
    assert [data for data, _ in em_ordem] == sorted(data for data, _ in em_ordem)


def test_elo_igual_ao_do_rating():
    import pandas as pd

    from src.rating import calcular_elo

    lutas = [luta(0, "A", "B"), luta(0, "B", "C", metodo="Decision - Split"), luta(0, "A", "C", "D"), luta(0, "C", "A")]
    elos = percorrer_elo(cronologia(dados(*lutas)))
    linhas = []
    for i, l in enumerate(lutas):
        for eu, adv in ((l[8], l[9]), (l[9], l[8])):
            linhas.append({"Fight_URL": f"F{i}", "Fighter": eu[0], "Adversario": adv[0], "Resultado": eu[1], "Method": l[2]})
    antes = calcular_elo(pd.DataFrame(linhas))
    for i, (l, (ea, _, eb, _)) in enumerate(zip(lutas, elos)):
        assert antes[(f"F{i}", l[8][0])] == pytest.approx(ea)
        assert antes[(f"F{i}", l[9][0])] == pytest.approx(eb)


def test_retrospecto_valoriza_quem_cresceu_depois():
    # X vence B; depois B vence 5 seguidas e sobe. A força de B na luta com X fica acima do Elo daquela época.
    seguidas = [luta(0, "B", f"V{i}") for i in range(5)]
    por, _ = lutas_por_lutador(dados(luta(0, "X", "B"), *seguidas), ajustar=False)
    forca = por["X"][0]["forca"]
    assert forca > cartel.ELO_INICIAL
    so_epoca, _ = lutas_por_lutador(dados(luta(0, "X", "B"), *seguidas), peso_epoca=1.0, ajustar=False)
    assert so_epoca["X"][0]["forca"] == pytest.approx(cartel.ELO_INICIAL)


def test_desclassificacao_e_sem_resultado_nao_contam():
    por, _ = lutas_por_lutador(dados(luta(0, "A", "B", metodo="DQ"), luta(0, "A", "C", "NC", "Overturned"), luta(0, "A", "D")))
    assert [l["adv"] for l in por["A"]] == ["D"]
    assert "B" not in por and "C" not in por


def test_ajuste_de_epoca():
    niveis = {"M": {2000: 1600.0, 2005: 1650.0, 2026: 1800.0}, "F": {2020: 1700.0}}
    assert ajuste_de_epoca(niveis, "1999-05-01", "M") == 0  # antes de 2001: sem ajuste
    assert ajuste_de_epoca(niveis, "2005-05-01", "M") == pytest.approx(150)
    assert ajuste_de_epoca(niveis, "2026-05-01", "M") == 0
    assert ajuste_de_epoca(niveis, "2003-05-01", "M") == pytest.approx(150)  # ano sem medida: o mais próximo
    assert ajuste_de_epoca(niveis, "2015-05-01", "F") == pytest.approx(100)  # mulheres: elite feminina -> escala de hoje


def test_melhor_trecho():
    lutas = [{"pontos": p} for p in [0.1, -0.5, 0.9, 0.9, 0.2]]
    assert melhor_trecho(lutas, janela=2) == 2
    assert melhor_trecho(lutas, janela=6) is None


def test_montar_cartel(monkeypatch):
    monkeypatch.setattr(cartel, "JANELA_AUGE", 3)
    lutas = [luta(0, "A", f"H{i}") for i in range(4)]
    lutas += [luta(0, "M", f"W{i}", cat="Women's Flyweight") for i in range(3)]
    lutas += [luta(0, "M", "W9", "L", cat="Catch Weight")]  # peso casado entre mulheres continua feminino
    saida = montar_cartel(dados(*lutas), min_lutas=4)
    por_nome = {l["nome"]: l for l in saida["lutadores"]}
    assert set(por_nome) == {"A", "M"}  # só quem tem 4+ lutas
    a, m = por_nome["A"], por_nome["M"]
    assert a["g"] == "M" and m["g"] == "F"
    assert a["cartel"] == "4-0" and m["cartel"] == "3-1"
    assert a["qual"] == pytest.approx(a["long"] / (4 + cartel.LUTAS_FANTASMAS), abs=1e-3)
    assert a["auge"] > 0 and a["trecho"][2] == "3-0"
    assert m["pior"][0] == "W9" and "pior" not in a
    assert saida["parametros"]["peso_epoca"] == cartel.PESO_EPOCA
