"""Exporta os dados em modelo estrela (CSV) para o painel do Power BI (pasta powerbi/).

Parte das mesmas tabelas do banco SQLite (src.banco.montar_tabelas) e acrescenta o que facilita
o painel: método agrupado, categoria e base em português, flags 0/1 de resultado, idade na data
da luta e uma tabela de calendário. CSV com ';' e vírgula decimal (padrão do Power BI em pt-BR)
e UTF-8 com BOM, para os acentos abrirem certos.

Uso (na raiz, com o venv): python -m src.powerbi
"""

from pathlib import Path

import pandas as pd

from src.banco import ARQUIVO_EVENTOS, ARQUIVO_LUTADORES, ARQUIVO_RESUMO, ARQUIVO_ROUND, montar_tabelas

RAIZ = Path(__file__).resolve().parent.parent
PASTA_SAIDA = RAIZ / "powerbi" / "dados"

CATEGORIAS_PT = {
    "Heavyweight": "Pesado", "Light Heavyweight": "Meio-pesado", "Middleweight": "Médio",
    "Welterweight": "Meio-médio", "Lightweight": "Leve", "Featherweight": "Pena",
    "Bantamweight": "Galo", "Flyweight": "Mosca", "Women's Featherweight": "Pena (fem.)",
    "Women's Bantamweight": "Galo (fem.)", "Women's Flyweight": "Mosca (fem.)",
    "Women's Strawweight": "Palha (fem.)", "Catch Weight": "Peso casado",
}
BASES_PT = {"Orthodox": "Ortodoxo", "Southpaw": "Canhoto", "Switch": "Troca de base"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def grupo_metodo(metodo):
    """Nocaute (inclui TKO médico), Finalização, Decisão ou Outro (DQ, luta anulada, sem condições)."""
    if pd.isna(metodo):
        return "Outro"
    if "KO/TKO" in metodo or metodo.startswith("TKO - Doctor"):
        return "Nocaute"
    if "Submission" in metodo:
        return "Finalização"
    if metodo.startswith("Decision"):
        return "Decisão"
    return "Outro"


def montar_modelo(tabelas):
    """{nome: DataFrame} do modelo estrela, a partir das tabelas de montar_tabelas()."""
    eventos, lutas, lutadores = tabelas["eventos"], tabelas["lutas"], tabelas["lutadores"]
    desempenho, por_round = tabelas["desempenho"], tabelas["desempenho_round"]

    # Lutador: o link da página é a chave; no modelo vira um id inteiro (relacionamentos mais leves)
    dim_lutador = lutadores.reset_index(drop=True)
    dim_lutador.insert(0, "lutador_id", range(1, len(dim_lutador) + 1))
    id_do_lutador = dim_lutador.set_index("url")["lutador_id"]
    dim_lutador["base"] = dim_lutador["base"].map(BASES_PT)
    dim_lutador = dim_lutador.drop(columns="url")

    dim_luta = lutas.merge(eventos[["evento_id", "nome", "data"]], on="evento_id").rename(columns={"nome": "evento"})
    dim_luta["metodo_grupo"] = dim_luta["metodo"].map(grupo_metodo)
    dim_luta["categoria"] = dim_luta["categoria"].map(CATEGORIAS_PT).fillna(dim_luta["categoria"])
    dim_luta["duracao_min"] = (dim_luta["duracao_seg"] / 60).round(2)
    dim_luta = dim_luta[["luta_id", "evento_id", "evento", "data", "categoria", "metodo", "metodo_grupo",
                         "round_final", "tempo_final", "duracao_min", "arbitro",
                         "disputa_titulo", "bonus_luta", "bonus_performance"]]

    # Fato: uma linha por lutador em cada luta, com a duração e a data da luta repetidas (para
    # medidas por minuto e filtro de calendário direto na fato) e o adversário
    fato = desempenho.copy()
    fato["lutador_id"] = fato["lutador_url"].map(id_do_lutador)
    fato = fato.merge(dim_luta[["luta_id", "data"]], on="luta_id").merge(lutas[["luta_id", "duracao_seg"]], on="luta_id")
    adversario = fato[["luta_id", "lutador_id"]].rename(columns={"lutador_id": "adversario_id"})
    fato = fato.merge(adversario, on="luta_id")
    fato = fato[fato["lutador_id"] != fato["adversario_id"]]
    for resultado, coluna in [("W", "vitoria"), ("L", "derrota"), ("D", "empate"), ("NC", "sem_resultado")]:
        fato[coluna] = (fato["resultado"] == resultado).astype(int)
    nascimento = fato["lutador_id"].map(dim_lutador.set_index("lutador_id")["nascimento"])
    fato["idade_na_luta"] = ((pd.to_datetime(fato["data"]) - pd.to_datetime(nascimento)).dt.days / 365.25).round(1)
    fato = fato.drop(columns=["lutador", "lutador_url"])
    fato = fato[["luta_id", "lutador_id", "adversario_id", "data", "resultado", "vitoria", "derrota", "empate",
                 "sem_resultado", "duracao_seg", "idade_na_luta",
                 *[c for c in fato.columns if c not in {"luta_id", "lutador_id", "adversario_id", "data", "resultado",
                                                         "vitoria", "derrota", "empate", "sem_resultado",
                                                         "duracao_seg", "idade_na_luta"}]]]
    fato = fato.sort_values(["luta_id", "lutador_id"]).reset_index(drop=True)

    # Round: o dataset por round não tem o link; o par (luta, nome) identifica o lutador
    id_por_nome = desempenho.assign(lutador_id=desempenho["lutador_url"].map(id_do_lutador)).set_index(
        ["luta_id", "lutador"])["lutador_id"]
    fato_round = por_round.copy()
    fato_round["lutador_id"] = [id_por_nome.get((l, n)) for l, n in zip(fato_round["luta_id"], fato_round["lutador"])]
    fato_round = fato_round.drop(columns="lutador")[["luta_id", "lutador_id", "round",
                                                      *[c for c in por_round.columns if c not in {"luta_id", "lutador", "round"}]]]

    # Calendário contínuo do 1º ao último dia dos anos do período (tabela de datas do Power BI)
    datas = pd.to_datetime(eventos["data"])
    dias = pd.date_range(f"{datas.min().year}-01-01", f"{datas.max().year}-12-31", freq="D")
    dim_calendario = pd.DataFrame({
        "data": dias.strftime("%Y-%m-%d"),
        "ano": dias.year,
        "trimestre": "T" + dias.quarter.astype(str),
        "mes_num": dias.month,
        "mes": [MESES[m - 1] for m in dias.month],
        "ano_mes": [f"{MESES[m - 1]}/{a}" for a, m in zip(dias.year, dias.month)],
        "ano_mes_ordem": dias.year * 100 + dias.month,  # para ordenar ano_mes (Classificar por coluna)
    })

    return {"fato_desempenho": fato, "fato_round": fato_round, "dim_luta": dim_luta,
            "dim_lutador": dim_lutador, "dim_calendario": dim_calendario}


def exportar_powerbi(pasta_saida=PASTA_SAIDA):
    """Lê os CSVs limpos, monta o modelo e grava um CSV por tabela em powerbi/dados/."""
    tabelas = montar_tabelas(pd.read_csv(ARQUIVO_RESUMO), pd.read_csv(ARQUIVO_ROUND), pd.read_csv(ARQUIVO_EVENTOS),
                             pd.read_csv(ARQUIVO_LUTADORES))
    modelo = montar_modelo(tabelas)
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    for nome, tabela in modelo.items():
        tabela.to_csv(pasta_saida / f"{nome}.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")
    return {nome: len(tabela) for nome, tabela in modelo.items()}


if __name__ == "__main__":
    for tabela, linhas in exportar_powerbi().items():
        print(f"{tabela}: {linhas} linhas")
    print(f"-> {PASTA_SAIDA}")
