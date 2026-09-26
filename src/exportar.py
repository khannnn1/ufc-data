"""Exporta os dados agregados por lutador em JSON, para a página interativa (interativo.html)."""

import json
from datetime import date
from pathlib import Path

import pandas as pd

from src.limpeza import tempo_para_segundos

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_RESUMO = RAIZ / "data" / "processed" / "dataset_final_resumo_limpo.csv"
ARQUIVO_SAIDA = RAIZ / "dados" / "lutadores.json"

# Totais somados por lutador. Nomes curtos para o JSON ficar pequeno; o navegador calcula
# médias por luta e percentuais a partir deles.
SOMAS = {
    "kd": "KD",
    "sl": "Sig_str_landed", "sa": "Sig_str_attempted",
    "tl": "Total_str_landed", "ta": "Total_str_attempted",
    "tdl": "Td_landed", "tda": "Td_attempted",
    "sub": "Sub. att",
    "ctrl": "Ctrl_seconds",
    "head": "Head_landed", "body": "Body_landed", "leg": "Leg_landed",
    "dist": "Distance_landed", "clinch": "Clinch_landed", "ground": "Ground_landed",
    "dur": "Duracao_seg",
}


def agregar_lutadores(df):
    """Uma linha por lutador: cartel, vitórias por método e totais das estatísticas no período."""
    df = tempo_para_segundos(df.copy(), "Time")
    df["Duracao_seg"] = (df["Final_Round"] - 1) * 300 + df["Time_seconds"]

    vitoria = df["Resultado"] == "W"
    df["ko"] = (vitoria & df["Method"].str.contains("KO/TKO|TKO - Doctor", na=False)).astype(int)
    df["subw"] = (vitoria & df["Method"].str.contains("Submission", na=False)).astype(int)
    for resultado in ["W", "L", "D", "NC"]:
        df[resultado] = (df["Resultado"] == resultado).astype(int)

    colunas = {"n": ("Fight_URL", "nunique"), "w": ("W", "sum"), "l": ("L", "sum"),
               "d": ("D", "sum"), "nc": ("NC", "sum"), "ko": ("ko", "sum"), "subw": ("subw", "sum")}
    colunas.update({curto: (original, "sum") for curto, original in SOMAS.items()})

    agregado = df.groupby("Fighter").agg(**colunas).reset_index()
    return agregado.rename(columns={"Fighter": "nome"})


def exportar_lutadores(caminho_csv=ARQUIVO_RESUMO, caminho_saida=ARQUIVO_SAIDA):
    """Lê o dataset resumo limpo e grava o JSON consumido pela página interativa."""
    df = pd.read_csv(caminho_csv)
    agregado = agregar_lutadores(df)

    saida = {
        "gerado_em": date.today().isoformat(),
        "eventos": int(df["Event_URL"].nunique()),
        "lutas": int(df["Fight_URL"].nunique()),
        "lutadores": [
            {k: (int(v) if isinstance(v, (int, float)) and k != "nome" else v) for k, v in linha.items()}
            for linha in agregado.to_dict(orient="records")
        ],
    }

    Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)
    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, separators=(",", ":"))
    return saida


if __name__ == "__main__":
    resultado = exportar_lutadores()
    print(f"{len(resultado['lutadores'])} lutadores, {resultado['lutas']} lutas, "
          f"{resultado['eventos']} eventos -> {ARQUIVO_SAIDA}")
