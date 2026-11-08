from src.analises import (arbitros, disputas_cinturao, distribuicao, metodos, montar_analises, numeros_chave,
                          por_categoria, round_final, vencedores_perdedores)


def test_numeros_e_metodos_uma_linha_por_luta(resumo):
    assert numeros_chave(resumo) == {"eventos": 2, "lutas": 3, "lutadores": 4, "pct_antes_decisao": 66.7}
    assert sorted(metodos(resumo)) == [["Decision - Unanimous", 1], ["KO/TKO", 1], ["Submission", 1]]


def test_round_final_percentual_dentro_do_metodo(resumo):
    r = round_final(resumo)
    assert r["ko"] == [100.0, 0.0, 0.0, 0.0] and r["n_ko"] == 1  # F1: nocaute no 1º round
    assert r["sub"] == [0.0, 100.0, 0.0, 0.0]  # F3: finalização no 2º


def test_categoria_com_poucas_lutas_fica_de_fora(resumo, monkeypatch):
    import src.analises as analises
    assert por_categoria(resumo) == []  # menos de 20 lutas
    monkeypatch.setattr(analises, "MIN_LUTAS_CATEGORIA", 1)
    # Lightweight: F1 nocaute + F3 finalização; Welterweight: F2 decisão
    assert analises.por_categoria(resumo) == [["Lightweight", 2, 50.0, 50.0], ["Welterweight", 1, 0.0, 0.0]]


def test_vencedores_perdedores_e_distribuicao(resumo):
    medias = {m: (w, l) for m, w, l in vencedores_perdedores(resumo)}
    # Golpes: vencedores A(20), C(60), A(15); perdedores B(5), D(50), C(10)
    assert medias["golpes"] == (round(95 / 3, 2), round(65 / 3, 2))
    assert medias["kd"] == (round(1 / 3, 2), round(1 / 3, 2))
    assert distribuicao(resumo, ["Head", "Body", "Leg"])["todos"] == [100.0, 0.0, 0.0]


def test_cinturao_e_arbitros(resumo):
    c = {m: (t, d) for m, t, d in disputas_cinturao(resumo)["linhas"]}
    assert disputas_cinturao(resumo)["n"] == 1
    assert c["duracao"] == (6.0, round((150 + 900) / 2 / 60, 2))  # F3 = 1 round de 5 min + 1:00
    assert arbitros(resumo) == [["Juiz", 3, 66.7]]


def test_montar_analises_tem_todas_as_secoes(resumo, por_round):
    chaves = set(montar_analises(resumo, por_round))
    assert chaves == {"numeros", "metodos", "round_final", "categorias", "vencedores_perdedores", "alvo",
                      "origem", "cinturao", "rounds", "arbitros"}
