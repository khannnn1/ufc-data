import pandas as pd
import pytest

from src.atualizar import desambiguar_homonimos
from src.visualizacao import top_com_desempate


def test_top_com_desempate_menos_lutas_e_depois_nome():
    vitorias = pd.Series({"Carlos": 7, "Ana": 7, "Bia": 7, "Duda": 9}, name="W")
    lutas = pd.Series({"Carlos": 8, "Ana": 10, "Bia": 8, "Duda": 12})
    top = top_com_desempate(vitorias, lutas, n=3)
    # Duda tem mais vitórias; entre os empatados em 7, vem antes quem lutou menos (Bia e Carlos, 8), depois o nome
    assert top.index.tolist() == ["Duda", "Bia", "Carlos"]
    assert top.name == "W"


def test_top_com_desempate_nao_depende_da_ordem_de_entrada():
    vitorias = pd.Series({"Carlos": 7, "Ana": 7, "Bia": 7})
    lutas = pd.Series({"Carlos": 8, "Ana": 8, "Bia": 8})
    embaralhado = vitorias.iloc[[2, 0, 1]]
    assert top_com_desempate(vitorias, lutas, 2).index.tolist() == top_com_desempate(embaralhado, lutas, 2).index.tolist()


def _bases_homonimos(anos):
    resumo = pd.DataFrame({
        "Fight_URL": ["F1", "F1", "F2", "F2"],
        "Fighter": ["Bruno Silva", "Outro", "Bruno Silva", "Mais Um"],
        "Fighter_URL": ["url/bruno-medio", "url/outro", "url/bruno-mosca", "url/mais-um"],
    })
    por_round = pd.DataFrame({"Fight_URL": ["F1", "F1", "F2"], "Fighter": ["Bruno Silva", "Bruno Silva", "Bruno Silva"],
                              "Round": [1, 2, 1]})
    lutadores = pd.DataFrame({"Fighter_URL": ["url/bruno-medio", "url/bruno-mosca", "url/outro", "url/mais-um"],
                              "DOB": [f"{anos[0]}-03-01", f"{anos[1]}-08-01", "1995-01-01", "1996-01-01"]})
    return resumo, por_round, lutadores


def test_desambiguar_homonimos_usa_o_ano_de_nascimento_nos_dois_datasets():
    resumo, por_round, lutadores = _bases_homonimos(("1989", "1990"))
    novo_resumo, novo_round = desambiguar_homonimos(resumo, por_round, lutadores)
    assert novo_resumo["Fighter"].tolist() == ["Bruno Silva (1989)", "Outro", "Bruno Silva (1990)", "Mais Um"]
    # O dataset por round não tem link: o par (luta, nome) identifica cada um
    assert novo_round["Fighter"].tolist() == ["Bruno Silva (1989)", "Bruno Silva (1989)", "Bruno Silva (1990)"]
    assert resumo["Fighter"].iloc[0] == "Bruno Silva"  # não altera o original


def test_desambiguar_homonimos_com_o_mesmo_ano_falha_em_vez_de_misturar():
    resumo, por_round, lutadores = _bases_homonimos(("1990", "1990"))
    with pytest.raises(ValueError):
        desambiguar_homonimos(resumo, por_round, lutadores)


def test_sem_homonimos_nada_muda():
    resumo, por_round, lutadores = _bases_homonimos(("1989", "1990"))
    resumo.loc[2, "Fighter"] = "Bruno Souza"
    novo_resumo, novo_round = desambiguar_homonimos(resumo, por_round, lutadores)
    assert novo_resumo is resumo and novo_round is por_round
