"""Previsão de luta (src/previsao.py): confrontos em ordem, Elo igual ao do rating, modelo e avaliação."""

import numpy as np
import pandas as pd
import pytest

from src.previsao import avaliar, chance, confrontos_do_resumo, matriz, montar_previsao, percorrer_elo
from src.rating import calcular_elo, ordem_cronologica


def test_confrontos_em_ordem_cronologica_com_dados_fisicos(resumo, datas_eventos, lutadores):
    c = confrontos_do_resumo(resumo, datas_eventos, lutadores)
    # E2 (F3) é de fevereiro, E1 (F1, F2) de março; no mesmo dia, do fim do card para a luta principal
    assert list(c["data"]) == ["2024-02-01", "2024-03-01", "2024-03-01"]
    assert {c.iloc[0]["a"], c.iloc[0]["b"]} == {"A", "C"}
    linha = c.iloc[0]
    nasc = {"A": "1995-01-01", "C": "1992-06-15"}
    assert (linha["nasc_a"], linha["nasc_b"]) == (nasc[linha["a"]], nasc[linha["b"]])


def test_elo_igual_ao_do_rating(resumo, datas_eventos, lutadores):
    c, final = percorrer_elo(confrontos_do_resumo(resumo, datas_eventos, lutadores))
    ordem = ordem_cronologica(resumo, datas_eventos)
    adv = ordem.merge(ordem[["Fight_URL", "Fighter"]].rename(columns={"Fighter": "Adversario"}), on="Fight_URL")
    adv = adv[adv["Fighter"] != adv["Adversario"]].sort_values(["_data", "_pos"], ascending=[True, False])
    antes = calcular_elo(adv[["Fight_URL", "Fighter", "Adversario", "Resultado", "Method"]])
    assert sorted(antes.values()) == pytest.approx(sorted([*c["elo_a"], *c["elo_b"]]))
    assert final["A"][1] == 2 and final["A"][0] > 1500 > final["B"][0]


def test_matriz_usa_zero_quando_falta_dado():
    c = pd.DataFrame({"data": ["2024-01-01"] * 2, "elo_a": [1600, 1500], "elo_b": [1500, 1500],
                      "nasc_a": ["1994-01-01", None], "nasc_b": ["1990-01-01", "1990-01-01"],
                      "env_a": [180.0, None], "env_b": [175.0, 170.0]})
    X = matriz(c)
    assert X[0] == pytest.approx([1.0, -4.0, 5.0], abs=0.01)
    assert list(X[1]) == [0.0, 0.0, 0.0]


def test_modelo_simetrico():
    X = np.array([[1.0, -3.0, 4.0]])
    pesos = [0.5, -0.07, 0.01]
    assert chance(X, pesos)[0] + chance(-X, pesos)[0] == pytest.approx(1.0)


def test_avaliar_acerto_e_calibracao():
    p = np.array([0.8, 0.3, 0.6, 0.5])
    y = np.array([1, 1, 1, 0])  # favoritos: a (venceu), b (perdeu), a (venceu); a 4ª não tem favorito
    r = avaliar(p, y)
    assert r["lutas"] == 4 and r["acerto"] == pytest.approx(2 / 3, abs=0.001)
    faixas = {f[0]: f for f in r["calibracao"]}
    assert faixas[0.75][3] == 1 and faixas[0.75][2] == 1.0
    assert faixas[0.7][2] == 0.0  # favorito de 70% (b) perdeu


def test_montar_previsao_separa_treino_e_teste(resumo, datas_eventos, lutadores):
    c = confrontos_do_resumo(resumo, datas_eventos, lutadores)
    r = montar_previsao(c, corte="2024-02-15")  # treino = F3 (fev), teste = F1 e F2 (mar)
    assert r["teste"]["treino"] == 1 and r["teste"]["lutas"] == 2
    assert set(r["pesos"]) == {"elo", "idade", "env"}
    assert r["elo"]["A"][1:] == [2, "2024-03-01"]
    assert "teste" not in montar_previsao(c, corte="2000-01-01")  # sem lutas de treino, sem teste


def test_zebras_so_vencedores_com_chance_baixa():
    from src.previsao import zebras
    d = pd.DataFrame({"data": ["2020-01-01", "2020-02-01", "2020-03-01"], "a": ["X", "Y", "Z"], "b": ["P", "Q", "R"],
                      "resultado_a": ["W", "L", "W"], "elo_a": [1400, 1700, 1600], "elo_b": [1600, 1500, 1500]})
    z = zebras(d, np.array([0.3, 0.8, 0.7]))
    # X venceu com 30%; Q venceu Y com 20%; Z era favorito e venceu: não é zebra
    assert [r[1] for r in z] == ["Q", "X"]
    assert z[0][:4] == ["2020-02-01", "Q", "Y", 0.2] and z[0][4:] == [1500, 1700]
