import pandas as pd

from src.exportar import agregar_lutadores, historico_vantagens


def test_agregar_lutadores_cartel_metodos_e_duracao(resumo):
    agregado = agregar_lutadores(resumo).set_index("nome")
    a, c = agregado.loc["A"], agregado.loc["C"]
    assert (a["n"], a["w"], a["l"], a["ko"], a["subw"]) == (2, 2, 0, 1, 1)
    assert (c["n"], c["w"], c["l"]) == (2, 1, 1)
    # Duração: F1 = 2:30 no 1º round (150 s), F3 = 1:00 no 2º round (360 s)
    assert a["dur"] == 150 + 360
    assert a["sl"] == 20 + 15 and a["kd"] == 1


def _duelo(fight, venc, perd, dob_v, dob_p, env_v, env_p, base_v, base_p):
    """Uma luta com vencedor: devolve as duas linhas do resumo e as duas do cadastro de lutadores."""
    resumo = [{"Fight_URL": fight, "Event_URL": "E", "Fighter_URL": venc, "Resultado": "W"},
              {"Fight_URL": fight, "Event_URL": "E", "Fighter_URL": perd, "Resultado": "L"}]
    cadastro = [{"Fighter_URL": venc, "DOB": dob_v, "Reach_cm": env_v * 2.54, "Stance": base_v},
                {"Fighter_URL": perd, "DOB": dob_p, "Reach_cm": env_p * 2.54, "Stance": base_p}]
    return resumo, cadastro


def test_historico_vantagens_uma_luta_por_faixa():
    # Cada luta cai numa faixa de idade e numa de envergadura (limites: 2/5/8 anos e 1/2/3 polegadas)
    duelos = [
        _duelo("F1", "v1", "p1", "1990-01-01", "1989-01-01", 72, 71, "Southpaw", "Orthodox"),  # 1 ano mais novo venceu; +1"
        _duelo("F2", "v2", "p2", "1987-01-01", "1990-01-01", 70, 72, "Orthodox", "Southpaw"),  # 3 anos mais velho venceu; -2"
        _duelo("F3", "v3", "p3", "1996-01-01", "1990-01-01", 75, 72, "Switch", "Orthodox"),    # 6 mais novo venceu; +3"
        _duelo("F4", "v4", "p4", "2000-01-01", "1990-01-01", 70, 75, "Southpaw", "Switch"),    # 10 mais novo venceu; -5"
    ]
    resumo = pd.DataFrame([linha for r, _ in duelos for linha in r])
    lutadores = pd.DataFrame([linha for _, c in duelos for linha in c])
    datas = pd.DataFrame({"Event_URL": ["E"], "Event_Date": ["2024-01-01"]})

    historico = historico_vantagens(resumo, lutadores, datas)
    assert historico["idade"] == [[2, 100.0, 1], [5, 0.0, 1], [8, 100.0, 1], [None, 100.0, 1]]
    assert historico["env"] == [[1, 100.0, 1], [2, 0.0, 1], [3, 100.0, 1], [None, 0.0, 1]]
    # [base_a, base_b, vitórias de base_a, lutas]
    assert historico["bases"] == [["Southpaw", "Orthodox", 1, 2], ["Switch", "Orthodox", 1, 1], ["Switch", "Southpaw", 0, 1]]


def test_lutas_sem_estatisticas_contam_no_cartel_mas_nao_nas_medias(resumo):
    import numpy as np
    resumo = resumo.copy()
    sem = resumo["Fight_URL"] == "F1"  # como uma luta antiga sem estatísticas
    resumo.loc[sem, ["Sig_str_landed", "Sig_str_attempted"]] = np.nan
    a = agregar_lutadores(resumo).set_index("nome").loc["A"]
    assert (a["n"], a["ne"]) == (2, 1)
    assert a["de"] == 360 and a["dur"] == 510  # F3 (2º round, 1:00) só; F1 durou 2:30


def test_exportar_um_json_por_periodo(resumo, por_round, datas_eventos, lutadores, tmp_path, monkeypatch):
    import json

    import src.exportar as exportar
    resumo.to_csv(tmp_path / "resumo.csv", index=False)
    por_round.to_csv(tmp_path / "round.csv", index=False)
    datas_eventos.to_csv(tmp_path / "eventos.csv", index=False)
    lutadores.to_csv(tmp_path / "lutadores.csv", index=False)
    monkeypatch.setattr(exportar, "ARQUIVO_EVENTOS", tmp_path / "eventos.csv")
    monkeypatch.setattr(exportar, "ARQUIVO_LUTADORES", tmp_path / "lutadores.csv")
    # E1 em 2024-03-01, E2 em 2024-02-01: um corte em 2024-02-15 deixa só E1 (F1 e F2)
    monkeypatch.setattr(exportar, "PERIODOS", {"tudo": {"rotulo": "Tudo", "inicio": None},
                                               "corte": {"rotulo": "Corte", "inicio": "2024-02-15"}})
    exportar.exportar_lutadores(tmp_path / "resumo.csv", tmp_path / "round.csv", tmp_path)

    tudo = json.loads((tmp_path / "lutadores.json").read_text(encoding="utf-8"))
    corte = json.loads((tmp_path / "lutadores_corte.json").read_text(encoding="utf-8"))
    assert (tudo["lutas"], corte["lutas"]) == (3, 2)
    assert corte["periodo"] == {"inicio": "2024-03-01", "fim": "2024-03-01"}
    assert corte["filtro"] == "corte" and corte["periodos"] == {"tudo": "Tudo", "corte": "Corte"}
    a = {l["nome"]: l for l in corte["lutadores"]}["A"]
    assert (a["n"], a["w"]) == (1, 1)
    assert len(a["r"]) == 1  # rounds só das lutas do recorte


def test_inicio_do_periodo_relativo_a_hoje():
    from datetime import date

    from src.exportar import inicio_do_periodo
    assert inicio_do_periodo({"anos": 3}, hoje=date(2026, 11, 7)) == "2023-11-07"
    assert inicio_do_periodo({"inicio": "2001-01-01"}) == "2001-01-01"
    assert inicio_do_periodo({"inicio": None}) is None
