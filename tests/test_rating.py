import numpy as np
import pandas as pd

from src.limpeza import adicionar_duracao
from src.rating import (BASE, NOMES, NOTA_MAX, NOTA_MIN, RESULTADO, bonus_adversario, bonus_resultado, calcular_elo,
                        calcular_notas, classificar_estilos, montar_pares, regressao_logistica)


def test_regressao_recupera_pesos_conhecidos():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(4000, 2))
    beta = np.array([1.5, -0.5])
    y = (rng.random(4000) < 1 / (1 + np.exp(-X @ beta))).astype(float)
    estimado = regressao_logistica(X, y, l2=0)
    assert np.allclose(estimado, beta, atol=0.15)


def _carreira(nome, lutas, golpes, quedas, ctrl_seg, fin):
    return pd.DataFrame({"Fighter": nome, "Fight_URL": [f"{nome}{i}" for i in range(lutas)], "Duracao_seg": 900,
                         "Sig_str_landed": golpes, "Td_landed": quedas, "Ctrl_seconds": ctrl_seg, "Sub. att": fin})


def test_estilo_sai_dos_numeros():
    df = pd.concat([_carreira("Trocador", 4, 90, 0, 30, 0), _carreira("Lutador", 4, 30, 4, 450, 0),
                    _carreira("Faixa-preta", 4, 30, 2, 200, 3), _carreira("Misto", 4, 50, 1, 200, 0.4),
                    _carreira("Novato", 2, 90, 0, 0, 0)])
    assert classificar_estilos(df) == {"Faixa-preta": "Finalizador", "Lutador": "Wrestler", "Misto": "Completo",
                                       "Novato": "Completo", "Trocador": "Striker"}


def test_resultado_premia_quem_termina_cedo():
    cedo = bonus_resultado("W", "KO/TKO", 60, 900)
    tarde = bonus_resultado("W", "KO/TKO", 890, 900)
    assert cedo > tarde > bonus_resultado("W", "Decision - Unanimous", 900, 900) > bonus_resultado("W", "Decision - Split", 900, 900)
    assert bonus_resultado("L", "Submission", 60, 900) < bonus_resultado("L", "Decision - Unanimous", 900, 900) < 0
    assert bonus_resultado("NC", "Overturned", 300, 900) == 0
    assert tarde == RESULTADO["vitoria_antes"] + RESULTADO["vitoria_cedo"] * (10 / 900)


def test_elo_antes_da_luta_e_adversario_forte_vale_mais():
    lutas = pd.DataFrame({"Fight_URL": ["L1", "L1", "L2", "L2"], "Fighter": ["A", "B", "A", "C"],
                          "Adversario": ["B", "A", "C", "A"], "Resultado": ["W", "L", "L", "W"]})
    elo = calcular_elo(lutas)
    assert elo[("L1", "A")] == elo[("L1", "B")] == 1500
    assert elo[("L2", "A")] == 1564 and elo[("L2", "C")] == 1500  # estreia: K = 128, chance de 50% -> +64
    # decisão dividida vale 0,6 para o vencedor: sobe menos
    dividida = calcular_elo(lutas.assign(Method=["Decision - Split"] * 4))
    assert 1500 < dividida[("L2", "A")] < 1564
    # adversário em desvios-padrão; quem perde para alguém forte leva metade, para alguém fraco perde cheio
    assert bonus_adversario(1700, "W", 1500, 100) == 0.4 > bonus_adversario(1600, "W", 1500, 100) == 0.2
    assert bonus_adversario(1600, "L", 1500, 100) == 0.1 and bonus_adversario(1400, "L", 1500, 100) == -0.2
    assert bonus_adversario(1500, "W", 1500, 100) == 0


def test_estilo_na_vespera_nao_olha_o_futuro():
    from src.rating import estilos_por_luta
    df = _carreira("X", 6, 90, 0, 30, 0)
    # as 3 primeiras lutas trocando, as 3 últimas no chão: na 4ª ainda é striker, na 6ª já é wrestler (como na carreira toda)
    df.loc[3:, ["Sig_str_landed", "Td_landed", "Ctrl_seconds"]] = [10, 6, 700]
    df["Event_URL"] = [f"e{i}" for i in range(6)]
    datas = pd.DataFrame({"Event_URL": df["Event_URL"], "Event_Date": [f"2020-0{i + 1}-01" for i in range(6)]})
    vespera = estilos_por_luta(df, datas)
    assert [vespera[(f"X{i}", "X")] for i in range(6)] == ["Completo"] * 3 + ["Striker", "Completo", "Wrestler"]
    assert classificar_estilos(df)["X"] == "Wrestler"


def test_pares_tem_o_proprio_e_o_sofrido(resumo):
    pares = montar_pares(adicionar_duracao(resumo))
    assert len(pares) == 6
    a = pares[(pares["Fight_URL"] == "F1") & (pares["Fighter"] == "A")].iloc[0]
    # F1 durou 2:30; golpes na cabeça por minuto, suavizados com +5 min: 20/7,5 e 5/7,5
    assert a["Adversario"] == "B" and np.isclose(a["p_cabeca"], 20 / 7.5) and np.isclose(a["a_cabeca"], 5 / 7.5)


def test_notas_do_mini_dataset(resumo, datas_eventos):
    notas, info = calcular_notas(resumo, datas_eventos)
    assert len(notas) == 6 and set(info["pesos"]) == set(NOMES)
    assert notas["Nota"].between(NOTA_MIN, NOTA_MAX).all()
    vencedores = notas[notas["Resultado"] == "W"].set_index("Fight_URL")["Nota"]
    perdedores = notas[notas["Resultado"] == "L"].set_index("Fight_URL")["Nota"]
    assert (vencedores > perdedores).all() and (vencedores > BASE).all()
    # nota = base + partes, arredondada
    linha = notas.iloc[0]
    assert linha["Nota"] == round(BASE + linha["resultado"] + linha["desempenho"] + linha["adversario"], 1)


def _lutas_ranking():
    linhas = [  # (luta, evento, categoria, vencedor, perdedor)
        ("f1", "e1", "Lightweight", "A", "B"),
        ("f2", "e2", "Lightweight", "A", "C"),
        ("f3", "e3", "Catch Weight", "B", "C"),
    ]
    df = pd.DataFrame([{"Fight_URL": f, "Event_URL": e, "Weight_Class": c, "Fighter": x, "Resultado": r}
                       for f, e, c, v, p in linhas for x, r in [(v, "W"), (p, "L")]])
    datas = pd.DataFrame({"Event_URL": ["e1", "e2", "e3"], "Event_Date": ["2020-01-01", "2020-06-01", "2023-01-01"]})
    return df, datas


def test_posicoes_no_ranking_na_vespera_da_luta():
    from src.rating import posicoes_no_ranking
    df, datas = _lutas_ranking()
    # f1: ninguém tinha lutas; f2: A venceu B e lidera (C estreia, fora); f3 (peso casado) usa o peso-leve:
    # A 1º, C 2º (perdeu para quem tinha Elo maior, perde menos pontos que B), B 3º
    assert posicoes_no_ranking(df, datas, top=2, min_lutas=1, inatividade_dias=10_000) == {("f2", "A"): 1, ("f3", "C"): 2}
    assert posicoes_no_ranking(df, datas, top=3, min_lutas=1, inatividade_dias=10_000)[("f3", "B")] == 3
    # inatividade: em 2023, quem não luta há mais de 2 anos sai do ranking
    assert posicoes_no_ranking(df, datas, top=3, min_lutas=1, inatividade_dias=730) == {("f2", "A"): 1}
    # mínimo de lutas: B e C têm só 1 luta antes de f3
    assert posicoes_no_ranking(df, datas, top=3, min_lutas=2, inatividade_dias=10_000) == {}
