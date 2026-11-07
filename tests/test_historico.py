"""Coleta do histórico completo: páginas de luta antigas, duração por formato de tempo e retomada da coleta."""

import pandas as pd
import pytest

from src.atualizar import eventos_a_coletar, lutas_faltantes
from src.limpeza import adicionar_duracao, duracao_segundos, duracoes_dos_rounds
from src.scraper import anexar_csv, extrair_dados_luta_html


def _celula(a, b):
    return (f'<td class="b-fight-details__table-col"><p class="b-fight-details__table-text">{a}</p>'
            f'<p class="b-fight-details__table-text">{b}</p></td>')


def _tabela(cabecalho, linhas):
    ths = "".join(f"<th>{c}</th>" for c in cabecalho)
    corpo = "".join("<tr>" + "".join(_celula(a, b) for a, b in linha) + "</tr>" for linha in linhas)
    return f"<table><tr>{ths}</tr>{corpo}</table>"


TOTAIS = ["Fighter", "KD", "Sig. str.", "Sig. str. %", "Total str.", "Td", "Td %", "Sub. att", "Rev.", "Ctrl"]
SIG = ["Fighter", "Sig. str", "Sig. str. %", "Head", "Body", "Leg", "Distance", "Clinch", "Ground"]
LINHA_TOTAIS = [("A", "B"), ("1", "0"), ("20 of 40", "5 of 30"), ("50%", "16%"), ("30 of 50", "10 of 40"),
                ("1 of 2", "0 of 0"), ("50%", "---"), ("0", "1"), ("0", "0"), ("2:10", "0:05")]
LINHA_SIG = [("A", "B"), ("20 of 40", "5 of 30"), ("50%", "16%"), ("15 of 30", "3 of 20"), ("3 of 5", "1 of 5"),
             ("2 of 5", "1 of 5"), ("18 of 36", "5 of 30"), ("2 of 4", "0 of 0"), ("0 of 0", "0 of 0")]


def _pagina_luta(tabelas, formato="3 Rnd (5-5-5)"):
    pessoas = "".join(
        f'<div class="b-fight-details__person"><i class="b-fight-details__person-status">{r}</i>'
        f'<a class="b-link b-fight-details__person-link">{n}</a></div>' for n, r in [("A", "W"), ("B", "L")])
    itens = "".join(f'<i class="b-fight-details__text-item"><i class="b-fight-details__label">{rotulo}</i> {valor}</i>'
                    for rotulo, valor in [("Method:", "KO/TKO"), ("Round:", "2"), ("Time:", "1:30"),
                                          ("Time format:", formato), ("Referee:", "Juiz")])
    return f'{pessoas}<p class="b-fight-details__text">{itens}</p>{"".join(tabelas)}'


def test_luta_recente_com_as_4_tabelas():
    html = _pagina_luta([_tabela(TOTAIS, [LINHA_TOTAIS]), _tabela(TOTAIS, [LINHA_TOTAIS, LINHA_TOTAIS]),
                         _tabela(SIG, [LINHA_SIG]), _tabela(SIG, [LINHA_SIG, LINHA_SIG])])
    resumo, por_round = extrair_dados_luta_html(html, "F1")
    assert resumo["Fighter"].tolist() == ["A", "B"]
    assert resumo["Resultado"].tolist() == ["W", "L"]
    assert resumo.loc[0, "Sig. str."] == "20 of 40" and resumo.loc[1, "Head"] == "3 of 20"
    assert resumo.loc[0, "Time_Format"] == "3 Rnd (5-5-5)"
    assert por_round["Round"].tolist() == [1, 2, 1, 2]
    assert por_round["Fight_URL"].eq("F1").all()


def test_luta_antiga_sem_tabelas_por_round():
    html = _pagina_luta([_tabela(TOTAIS, [LINHA_TOTAIS]), _tabela(SIG, [LINHA_SIG])], formato="No Time Limit")
    resumo, por_round = extrair_dados_luta_html(html, "F1")
    assert resumo.loc[0, "KD"] == "1" and resumo.loc[0, "Leg"] == "2 of 5"
    assert por_round.empty and "Round" in por_round.columns


def test_luta_antiga_sem_estatisticas_mantem_resultado():
    resumo, por_round = extrair_dados_luta_html(_pagina_luta([]), "F1")
    assert resumo["Fighter"].tolist() == ["A", "B"] and resumo["Method"].eq("KO/TKO").all()
    assert resumo["KD"].isna().all() and resumo["Head"].isna().all()
    assert por_round.empty


@pytest.mark.parametrize("formato, esperado", [
    ("3 Rnd (5-5-5)", [5, 5, 5]),
    ("1 Rnd + OT (15-3)", [15, 3]),
    ("1 Rnd (20)", [20]),
    ("No Time Limit", []),
    (None, None),
])
def test_duracoes_dos_rounds(formato, esperado):
    assert duracoes_dos_rounds(formato) == esperado


@pytest.mark.parametrize("round_final, tempo, formato, esperado", [
    (3, 300, "3 Rnd (5-5-5)", 900),
    (2, 90, None, 390),                  # sem formato: rounds de 5 min, como antes
    (2, 60, "1 Rnd + OT (15-3)", 960),   # prorrogação depois de 15 min
    (1, 1569, "No Time Limit", 1569),
    (3, 30, "2 Rnd (10-10)", 1230),      # round além do formato repete o último
])
def test_duracao_segundos(round_final, tempo, formato, esperado):
    assert duracao_segundos(round_final, tempo, formato) == esperado


def test_adicionar_duracao_sem_e_com_coluna_de_formato():
    df = pd.DataFrame({"Final_Round": [2, 1], "Time": ["1:30", "26:09"]})
    assert adicionar_duracao(df)["Duracao_seg"].tolist() == [390, 1569]
    df["Time_Format"] = [None, "No Time Limit"]
    assert adicionar_duracao(df)["Duracao_seg"].tolist() == [390, 1569]


def test_anexar_csv_com_coluna_nova_reescreve_uma_vez(tmp_path):
    arquivo = tmp_path / "bruto.csv"
    pd.DataFrame({"Fight_URL": ["F1"], "KD": ["0"], "Ctrl": ["0:05"]}).to_csv(arquivo, index=False)
    anexar_csv(pd.DataFrame({"KD": ["1"], "Fight_URL": ["F2"], "Ctrl": ["1:00"], "Time_Format": ["No Time Limit"]}), arquivo)
    anexar_csv(pd.DataFrame({"Time_Format": ["3 Rnd (5-5-5)"], "Fight_URL": ["F3"], "KD": ["2"], "Ctrl": ["0:00"]}), arquivo)
    df = pd.read_csv(arquivo, dtype=str)
    assert df.columns.tolist() == ["Fight_URL", "KD", "Ctrl", "Time_Format"]
    assert df["Fight_URL"].tolist() == ["F1", "F2", "F3"]
    assert df["Ctrl"].tolist() == ["0:05", "1:00", "0:00"]  # texto preservado na reescrita
    assert df["Time_Format"].isna().tolist() == [True, False, False]


LISTAGEM = [
    {"nome": "Futuro", "url": "E5", "data": "2030-01-01"},
    {"nome": "Novo", "url": "E4", "data": "2026-10-01"},
    {"nome": "Base recente", "url": "E3", "data": "2026-09-19"},
    {"nome": "Base antiga", "url": "E2", "data": "2023-04-08"},
    {"nome": "UFC antigo", "url": "E1", "data": "1993-11-12"},
]
DATAS = {"E3": "2026-09-19", "E2": "2023-04-08"}


def test_eventos_a_coletar_sem_historico_so_os_mais_novos():
    assert [e["url"] for e in eventos_a_coletar(LISTAGEM, ["E3", "E2"], DATAS, "2026-11-07")] == ["E4"]


def test_eventos_a_coletar_com_historico_inclui_os_antigos_e_ignora_o_futuro():
    novos = eventos_a_coletar(LISTAGEM, ["E3", "E2"], DATAS, "2026-11-07", historico=True)
    assert [e["url"] for e in novos] == ["E4", "E1"]


def test_lutas_faltantes_so_de_eventos_ja_coletados():
    lutas_evento = pd.DataFrame({"Event_URL": ["E1", "E1", "E2"], "Fight_URL": ["F1", "F2", "F3"]})
    bruto = pd.DataFrame({"Event_URL": ["E1", "E1"], "Fight_URL": ["F1", "F1"]})
    assert lutas_faltantes(lutas_evento, bruto)["Fight_URL"].tolist() == ["F2"]
