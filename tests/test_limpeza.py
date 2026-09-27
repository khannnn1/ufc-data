import math

import pandas as pd

from src.limpeza import (limpar_dataset, limpar_lutadores, limpar_percentual, medida_para_cm,
                         separar_landed_attempted, tempo_para_segundos)


def test_separar_landed_attempted_cria_duas_colunas_numericas():
    df = pd.DataFrame({"Sig. str.": ["12 of 30", "0 of 0"]})
    resultado = separar_landed_attempted(df, "Sig. str.")
    assert list(resultado.columns) == ["Sig_str_landed", "Sig_str_attempted"]
    assert resultado["Sig_str_landed"].tolist() == [12, 0]
    assert resultado["Sig_str_attempted"].tolist() == [30, 0]


def test_limpar_percentual_trata_tracos_como_ausente_e_nao_zero():
    # "---" = nenhuma tentativa: precisão indefinida, não 0%
    df = pd.DataFrame({"Td %": ["50%", "---", "0%"]})
    valores = limpar_percentual(df, "Td %")["Td %"].tolist()
    assert valores[0] == 50 and valores[2] == 0
    assert math.isnan(valores[1])


def test_tempo_para_segundos():
    df = pd.DataFrame({"Ctrl": ["4:56", "0:00", "--"]})
    resultado = tempo_para_segundos(df, "Ctrl")
    assert "Ctrl" not in resultado.columns
    assert resultado["Ctrl_seconds"].tolist()[:2] == [296, 0]
    assert pd.isna(resultado["Ctrl_seconds"].iloc[2])


def test_limpar_dataset_aplica_todas_as_etapas():
    colunas_of = ["Sig. str.", "Total str.", "Td", "Head", "Body", "Leg", "Distance", "Clinch", "Ground"]
    bruto = pd.DataFrame([{**{c: "3 of 5" for c in colunas_of}, "Sig. str. %": "60%", "Td %": "---", "Ctrl": "1:05"}])
    limpo = limpar_dataset(bruto)
    assert limpo.loc[0, "Td_landed"] == 3 and limpo.loc[0, "Ground_attempted"] == 5
    assert limpo.loc[0, "Sig. str. %"] == 60 and pd.isna(limpo.loc[0, "Td %"])
    assert limpo.loc[0, "Ctrl_seconds"] == 65
    assert bruto.loc[0, "Ctrl"] == "1:05"  # não altera o DataFrame original


def test_medida_para_cm_pes_e_polegadas_ou_so_polegadas():
    assert medida_para_cm("5' 11\"") == 180.3  # 71 polegadas
    assert medida_para_cm("72\"") == 182.9
    assert medida_para_cm("--") is None
    assert medida_para_cm(float("nan")) is None


def test_limpar_lutadores_converte_medidas_e_data():
    bruto = pd.DataFrame({"Fighter_URL": ["u1", "u2"], "Name": ["A", "B"], "Height": ["6' 0\"", "--"],
                          "Reach": ["74\"", "--"], "Stance": ["Southpaw", "--"], "DOB": ["Jul 07, 1987", "--"]})
    limpo = limpar_lutadores(bruto)
    assert limpo.loc[0, "Height_cm"] == 182.9 and limpo.loc[0, "Reach_cm"] == 188.0
    assert limpo.loc[0, "DOB"] == "1987-07-07"
    assert pd.isna(limpo.loc[1, "Stance"]) and pd.isna(limpo.loc[1, "DOB"]) and pd.isna(limpo.loc[1, "Height_cm"])
