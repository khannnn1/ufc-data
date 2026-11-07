"""Exporta os dados agregados por lutador em JSON, para a página interativa (interativo.html)."""

import json
from datetime import date
from pathlib import Path

import pandas as pd

from src.limpeza import adicionar_duracao

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_RESUMO = RAIZ / "data" / "processed" / "dataset_final_resumo_limpo.csv"
ARQUIVO_ROUND = RAIZ / "data" / "processed" / "dataset_final_round_limpo.csv"
ARQUIVO_EVENTOS = RAIZ / "data" / "processed" / "eventos.csv"
ARQUIVO_LUTADORES = RAIZ / "data" / "processed" / "lutadores.csv"
ARQUIVO_SAIDA = RAIZ / "dados" / "lutadores.json"
PASTA_SAIDA = RAIZ / "dados"

# Filtro de período do site: um JSON por período (o site troca de arquivo ao mudar o filtro).
# Lutas antigas tinham outras regras (sem limite de tempo, rounds longos) e às vezes não têm
# estatísticas, então médias do histórico todo misturam eras diferentes.
# inicio = data mínima do evento ('AAAA-MM-DD'), None = sem corte; "anos" = relativo a hoje.
PERIODOS = {
    "tudo": {"rotulo": "Todo o histórico", "inicio": None},
    "moderno": {"rotulo": "Desde 2001 (regras unificadas)", "inicio": "2001-01-01"},
    "recente": {"rotulo": "Últimos 3 anos", "anos": 3},
}


def arquivo_do_periodo(chave, pasta=PASTA_SAIDA):
    """dados/lutadores.json para o histórico todo; dados/lutadores_<chave>.json para os demais."""
    return Path(pasta) / ("lutadores.json" if chave == "tudo" else f"lutadores_{chave}.json")


def inicio_do_periodo(periodo, hoje=None):
    """Data mínima ('AAAA-MM-DD') de um período de PERIODOS, ou None se não há corte."""
    if periodo.get("anos"):
        hoje = hoje or date.today()
        return hoje.replace(year=hoje.year - periodo["anos"]).isoformat()
    return periodo.get("inicio")

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
    df = adicionar_duracao(df)

    vitoria = df["Resultado"] == "W"
    df["ko"] = (vitoria & df["Method"].str.contains("KO/TKO|TKO - Doctor", na=False)).astype(int)
    df["subw"] = (vitoria & df["Method"].str.contains("Submission", na=False)).astype(int)
    for resultado in ["W", "L", "D", "NC"]:
        df[resultado] = (df["Resultado"] == resultado).astype(int)

    # Lutas antigas sem estatísticas contam no cartel (n), mas não nas médias por luta/minuto:
    # ne = lutas com estatísticas, de = duração delas (s)
    com_estatisticas = df["Sig_str_landed"].notna()
    df["ne"] = com_estatisticas.astype(int)
    df["de"] = df["Duracao_seg"].where(com_estatisticas, 0)

    colunas = {"n": ("Fight_URL", "nunique"), "w": ("W", "sum"), "l": ("L", "sum"),
               "d": ("D", "sum"), "nc": ("NC", "sum"), "ko": ("ko", "sum"), "subw": ("subw", "sum"),
               "ne": ("ne", "sum"), "de": ("de", "sum")}
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
    """Em lutas com vencedor, % de vitórias de quem era mais novo / tinha mais envergadura, por faixa,
    e de cada lado nos confrontos de bases diferentes.

    Mesma conta do gráfico idade_vs_envergadura.png (e da consulta SQL idade_envergadura).
    Devolve {"idade": [[limite, pct, lutas], ...], "env": [...], "bases": [[a, b, vitorias_a, lutas], ...]}
    para o comparador do site.
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
        venceu = (dif > 0).groupby(faixas).agg(["mean", "size"]).reindex(range(len(limites)))
        # Faixa sem nenhuma luta (recortes pequenos): pct None, 0 lutas
        historico[chave] = [[limite, None if pd.isna(venceu.loc[i, "mean"]) else round(float(venceu.loc[i, "mean"]) * 100, 1),
                             0 if pd.isna(venceu.loc[i, "size"]) else int(venceu.loc[i, "size"])]
                            for i, limite in enumerate(limites)]

    # Confrontos de bases diferentes (gráfico base_canhoto_vs_ortodoxo.png / SQL confronto_bases):
    # [base_a, base_b, vitórias de base_a, lutas]
    base_v = df.merge(lutadores[["Fighter_URL", "Stance"]], on="Fighter_URL")
    bases = pd.concat([
        base_v[base_v["Resultado"] == "W"].set_index("Fight_URL")["Stance"].rename("v"),
        base_v[base_v["Resultado"] == "L"].set_index("Fight_URL")["Stance"].rename("p"),
    ], axis=1, join="inner").dropna()
    historico["bases"] = []
    for a, b in [("Southpaw", "Orthodox"), ("Switch", "Orthodox"), ("Switch", "Southpaw")]:
        no_confronto = ((bases["v"] == a) & (bases["p"] == b)) | ((bases["v"] == b) & (bases["p"] == a))
        historico["bases"].append([a, b, int((no_confronto & (bases["v"] == a)).sum()), int(no_confronto.sum())])
    return historico


def montar_json(df, df_round, datas_eventos, lutadores, periodo=None):
    """Conteúdo do JSON do site para um recorte já filtrado (resumo, por round e datas dos eventos)."""
    agregado = agregar_lutadores(df)
    rounds = agregar_rounds(df_round)
    datas = datas_eventos.loc[datas_eventos["Event_URL"].isin(df["Event_URL"]), "Event_Date"]
    fisico = dados_fisicos(df, lutadores, datas_eventos)
    return {
        "gerado_em": date.today().isoformat(),
        "filtro": periodo,
        "periodos": {chave: p["rotulo"] for chave, p in PERIODOS.items()},
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


def filtrar_periodo(df, df_round, datas_eventos, inicio):
    """Só as lutas de eventos a partir de `inicio` (None = tudo), no resumo e no por round."""
    if inicio is None:
        return df, df_round
    eventos = set(datas_eventos.loc[datas_eventos["Event_Date"] >= inicio, "Event_URL"])
    df = df[df["Event_URL"].isin(eventos)]
    return df, df_round[df_round["Fight_URL"].isin(set(df["Fight_URL"]))]


def exportar_lutadores(caminho_csv=ARQUIVO_RESUMO, caminho_round=ARQUIVO_ROUND, pasta_saida=PASTA_SAIDA):
    """Lê os datasets limpos e grava um JSON por período de PERIODOS (o do histórico todo é lutadores.json)."""
    df = pd.read_csv(caminho_csv, low_memory=False)
    df_round = pd.read_csv(caminho_round, low_memory=False)
    datas_eventos = pd.read_csv(ARQUIVO_EVENTOS)
    lutadores = pd.read_csv(ARQUIVO_LUTADORES)

    Path(pasta_saida).mkdir(parents=True, exist_ok=True)
    saidas = {}
    for chave, periodo in PERIODOS.items():
        recorte, recorte_round = filtrar_periodo(df, df_round, datas_eventos, inicio_do_periodo(periodo))
        saida = montar_json(recorte, recorte_round, datas_eventos, lutadores, chave)
        with open(arquivo_do_periodo(chave, pasta_saida), "w", encoding="utf-8") as f:
            json.dump(saida, f, ensure_ascii=False, separators=(",", ":"))
        saidas[chave] = saida
    return saidas


if __name__ == "__main__":
    for chave, resultado in exportar_lutadores().items():
        print(f"{PERIODOS[chave]['rotulo']}: {len(resultado['lutadores'])} lutadores, {resultado['lutas']} lutas, "
              f"{resultado['eventos']} eventos -> {arquivo_do_periodo(chave)}")
