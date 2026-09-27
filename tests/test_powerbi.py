import pandas as pd

from src.banco import montar_tabelas
from src.powerbi import grupo_metodo, montar_modelo


def test_grupo_metodo():
    assert grupo_metodo("KO/TKO") == "Nocaute"
    assert grupo_metodo("TKO - Doctor's Stoppage") == "Nocaute"
    assert grupo_metodo("Submission") == "Finalização"
    assert grupo_metodo("Decision - Split") == "Decisão"
    assert grupo_metodo("Overturned") == "Outro"
    assert grupo_metodo(None) == "Outro"


def test_montar_modelo(resumo, por_round, datas_eventos, lutadores):
    modelo = montar_modelo(montar_tabelas(resumo, por_round, datas_eventos, lutadores))
    fato, luta, lutador = modelo["fato_desempenho"], modelo["dim_luta"], modelo["dim_lutador"]

    # Duas linhas por luta, cada lutador com o outro como adversário
    assert fato.groupby("luta_id").size().eq(2).all()
    pares = set(zip(fato["lutador_id"], fato["adversario_id"]))
    assert all((b, a) in pares for a, b in pares)
    assert fato["vitoria"].sum() == 3 and fato["derrota"].sum() == 3

    # Chaves da fato existem nas dimensões; round com o lutador certo
    assert set(fato["lutador_id"]) <= set(lutador["lutador_id"])
    assert set(fato["luta_id"]) <= set(luta["luta_id"])
    assert modelo["fato_round"]["lutador_id"].notna().all()

    # Traduções e método agrupado
    assert set(luta["metodo_grupo"]) == {"Nocaute", "Decisão", "Finalização"}
    assert set(luta["categoria"]) == {"Leve", "Meio-médio"}
    assert set(lutador["base"]) == {"Canhoto", "Ortodoxo", "Troca de base"}

    # Idade na luta: A nasceu em 1995-01-01 e lutou em 2024-03-01 (E1)
    id_a = lutador.loc[lutador["nome"] == "A", "lutador_id"].iloc[0]
    luta_f1 = luta.loc[luta["evento_id"] == 1, "luta_id"]
    idade = fato.loc[(fato["lutador_id"] == id_a) & fato["luta_id"].isin(luta_f1), "idade_na_luta"].iloc[0]
    assert idade == 29.2

    # Calendário contínuo cobrindo os anos do período, sem datas repetidas
    calendario = modelo["dim_calendario"]
    assert calendario["data"].is_unique and len(calendario) == 366  # 2024 é bissexto
    assert set(fato["data"]) <= set(calendario["data"])
