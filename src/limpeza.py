"""Funções de limpeza e transformação dos dados extraídos do ufcstats.com."""

import pandas as pd

from src.config import COLUNAS_OF, COLUNAS_PCT


def separar_landed_attempted(df, coluna):
    """Separa uma coluna no formato 'X of Y' em duas colunas numéricas: landed e attempted."""
    novo_nome_landed = coluna.replace(" ", "_").replace(".", "") + "_landed"
    novo_nome_attempted = coluna.replace(" ", "_").replace(".", "") + "_attempted"

    split = df[coluna].str.split(" of ", expand=True)
    df[novo_nome_landed] = pd.to_numeric(split[0], errors="coerce")
    df[novo_nome_attempted] = pd.to_numeric(split[1], errors="coerce")

    return df.drop(columns=[coluna])


def limpar_percentual(df, coluna):
    """Remove o símbolo % e converte para número; trata '---' como valor ausente (NaN)."""
    df[coluna] = df[coluna].replace("---", None)
    df[coluna] = df[coluna].str.replace("%", "", regex=False)
    df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    return df


def tempo_para_segundos(df, coluna):
    """Converte uma coluna de tempo no formato 'M:SS' para segundos totais."""
    def converter(valor):
        if pd.isna(valor) or valor == "--":
            return None
        minutos, segundos = valor.split(":")
        return int(minutos) * 60 + int(segundos)

    df[coluna + "_seconds"] = df[coluna].apply(converter)
    return df.drop(columns=[coluna])


def limpar_dataset(df):
    """Aplica toda a limpeza a um dataset bruto (resumo ou por round): 'X of Y', percentuais e Ctrl."""
    df = df.copy()
    for coluna in COLUNAS_OF:
        df = separar_landed_attempted(df, coluna)
    for coluna in COLUNAS_PCT:
        df = limpar_percentual(df, coluna)
    return tempo_para_segundos(df, "Ctrl")
