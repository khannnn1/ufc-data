"""Exporta os dados agregados por lutador em JSON, para a página interativa (interativo.html)."""

import json
from datetime import date
from pathlib import Path

import pandas as pd

from src.limpeza import tempo_para_segundos

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_RESUMO = RAIZ / "data" / "processed" / "dataset_final_resumo_limpo.csv"
ARQUIVO_ROUND = RAIZ / "data" / "processed" / "dataset_final_round_limpo.csv"
ARQUIVO_EVENTOS = RAIZ / "data" / "processed" / "eventos.csv"
ARQUIVO_LUTADORES = RAIZ / "data" / "processed" / "lutadores.csv"
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


# Ordem das colunas de cada round no JSON: [round, rounds disputados, sl, sa, tdl, tda, ctrl, kd].
# Lista em vez de objeto para o arquivo ficar pequeno; o JS lê com essa mesma ordem.
COLUNAS_ROUND = ["Sig_str_landed", "Sig_str_attempted", "Td_landed", "Td_attempted", "Ctrl_seconds", "KD"]


def agregar_rounds(df_round):
    """{lutador: [[round, rounds, sl, sa, tdl, tda, ctrl, kd], ...]} com os totais de cada round."""
    totais = df_round.groupby(["Fighter", "Round"]).agg(
        rounds=("Fight_URL", "size"), **{col: (col, "sum") for col in COLUNAS_ROUND}
    ).reset_index()
    por_lutador = {}
    for linha in totais.itertuples(index=False):
        valores = [int(linha.Round), int(linha.rounds)] + [int(getattr(linha, col)) for col in COLUNAS_ROUND]
        por_lutador.setdefault(linha.Fighter, []).append(valores)
    return por_lutador


def dados_fisicos(df, lutadores, datas_eventos):
    """{nome: {cat, alt, env, base, nasc}} para os cartões do comparador (campos ausentes ficam de fora).

    cat = categoria da luta mais recente, ignorando peso casado (não é divisão); só se o lutador
    nunca lutou fora dele fica "Catch Weight". alt/env em cm inteiros, nasc em 'AAAA-MM-DD'.
    """
    lutas = df.merge(datas_eventos[["Event_URL", "Event_Date"]], on="Event_URL")
    lutas["peso_casado"] = lutas["Weight_Class"] == "Catch Weight"
    # Mais recente primeiro, com as lutas de peso casado depois de todas as outras
    lutas = lutas.sort_values(["peso_casado", "Event_Date"], ascending=[True, False])
    base = lutas.drop_duplicates("Fighter")[["Fighter", "Weight_Class", "Fighter_URL"]]
    base = base.merge(lutadores, on="Fighter_URL", how="left")

    fisico = {}
    for linha in base.itertuples(index=False):
        campos = {"cat": linha.Weight_Class, "alt": linha.Height_cm, "env": linha.Reach_cm,
                  "base": linha.Stance, "nasc": linha.DOB}
        campos = {k: v for k, v in campos.items() if pd.notna(v)}
        for k in ("alt", "env"):
            if k in campos:
                campos[k] = int(round(campos[k]))
        fisico[linha.Fighter] = campos
    return fisico


# Faixas de diferença do gráfico idade_vs_envergadura.png: limite superior de cada faixa
# (anos de idade / polegadas de envergadura); None = sem limite (última faixa).
FAIXAS_VANTAGEM = {"idade": [2, 5, 8, None], "env": [1, 2, 3, None]}


def historico_vantagens(df, lutadores, datas_eventos):
    """Em lutas com vencedor, % de vitórias de quem era mais novo / tinha mais envergadura, por faixa.

    Mesma conta do gráfico idade_vs_envergadura.png (e da consulta SQL idade_envergadura).
    Devolve {"idade": [[limite, pct, lutas], ...], "env": [...]} para o comparador do site.
    """
    fisico = df.merge(lutadores, on="Fighter_URL").merge(datas_eventos[["Event_URL", "Event_Date"]], on="Event_URL")
    fisico["idade"] = (pd.to_datetime(fisico["Event_Date"]) - pd.to_datetime(fisico["DOB"])).dt.days / 365.25
    fisico["env"] = (fisico["Reach_cm"] / 2.54).round(1)
    vencedor = fisico[fisico["Resultado"] == "W"].set_index("Fight_URL")[["idade", "env"]]
    perdedor = fisico[fisico["Resultado"] == "L"].set_index("Fight_URL")[["idade", "env"]]
    duelos = vencedor.join(perdedor, lsuffix="_v", rsuffix="_p", how="inner")

    # Vantagem = mais novo (diferença de idade negativa) / mais envergadura (positiva)
    diferencas = {"idade": -(duelos["idade_v"] - duelos["idade_p"]), "env": (duelos["env_v"] - duelos["env_p"]).round(1)}
    historico = {}
    for chave, dif in diferencas.items():
        dif = dif[dif != 0]
        limites = FAIXAS_VANTAGEM[chave]
        faixas = pd.cut(dif.abs(), [0] + [l if l is not None else 999 for l in limites], labels=False)
        venceu = (dif > 0).groupby(faixas).agg(["mean", "size"])
        historico[chave] = [[limite, round(float(venceu.loc[i, "mean"]) * 100, 1), int(venceu.loc[i, "size"])]
                            for i, limite in enumerate(limites)]
    return historico


def exportar_lutadores(caminho_csv=ARQUIVO_RESUMO, caminho_round=ARQUIVO_ROUND, caminho_saida=ARQUIVO_SAIDA):
    """Lê os datasets limpos (resumo e por round) e grava o JSON consumido pela página interativa."""
    df = pd.read_csv(caminho_csv)
    agregado = agregar_lutadores(df)
    rounds = agregar_rounds(pd.read_csv(caminho_round))

    datas_eventos = pd.read_csv(ARQUIVO_EVENTOS)
    datas = datas_eventos["Event_Date"]
    lutadores = pd.read_csv(ARQUIVO_LUTADORES)
    fisico = dados_fisicos(df, lutadores, datas_eventos)
    saida = {
        "gerado_em": date.today().isoformat(),
        "periodo": {"inicio": datas.min(), "fim": datas.max()},
        "eventos": int(df["Event_URL"].nunique()),
        "lutas": int(df["Fight_URL"].nunique()),
        "vantagens": historico_vantagens(df, lutadores, datas_eventos),
        "lutadores": [
            {**{k: (int(v) if isinstance(v, (int, float)) and k != "nome" else v) for k, v in linha.items()},
             **fisico.get(linha["nome"], {}), "r": rounds.get(linha["nome"], [])}
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
