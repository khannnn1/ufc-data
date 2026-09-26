"""Monta o banco SQLite (data/ufc.db) a partir dos CSVs limpos, seguindo sql/schema.sql."""

import sqlite3
from pathlib import Path

import pandas as pd

from src.limpeza import tempo_para_segundos

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_RESUMO = RAIZ / "data" / "processed" / "dataset_final_resumo_limpo.csv"
ARQUIVO_ROUND = RAIZ / "data" / "processed" / "dataset_final_round_limpo.csv"
ARQUIVO_EVENTOS = RAIZ / "data" / "processed" / "eventos.csv"  # datas; gerado por src/atualizar.py
ARQUIVO_SCHEMA = RAIZ / "sql" / "schema.sql"
ARQUIVO_BANCO = RAIZ / "data" / "ufc.db"

# Colunas do CSV -> colunas das tabelas desempenho e desempenho_round
ESTATISTICAS = {
    "KD": "kd",
    "Sig_str_landed": "sig_acertados", "Sig_str_attempted": "sig_tentados",
    "Total_str_landed": "total_acertados", "Total_str_attempted": "total_tentados",
    "Td_landed": "quedas", "Td_attempted": "quedas_tentadas",
    "Sub. att": "tent_finalizacao", "Rev.": "reversoes",
    "Ctrl_seconds": "controle_seg",
    "Head_landed": "cabeca", "Body_landed": "corpo", "Leg_landed": "perna",
    "Distance_landed": "distancia", "Clinch_landed": "clinch", "Ground_landed": "chao",
}

# Colunas vindas da página do evento (data/raw/lutas_evento.csv, juntadas por src/atualizar.py) -> tabela lutas
DADOS_DA_LUTA = {
    "Weight_Class": "categoria", "Title_Bout": "disputa_titulo",
    "Fight_Bonus": "bonus_luta", "Perf_Bonus": "bonus_performance",
}


def montar_tabelas(resumo, por_round, datas_eventos):
    """Separa os CSVs (uma linha por lutador-luta) em eventos, lutas, desempenho e desempenho_round."""
    eventos = resumo[["Event_URL", "Event_Name"]].drop_duplicates("Event_URL")
    eventos["data"] = eventos["Event_URL"].map(datas_eventos.set_index("Event_URL")["Event_Date"])
    if eventos["data"].isna().any():
        raise ValueError("Há eventos sem data em eventos.csv; rode `python -m src.atualizar`.")
    eventos = eventos.sort_values("data", ascending=False).reset_index(drop=True)
    eventos.insert(0, "evento_id", range(1, len(eventos) + 1))
    eventos = eventos.rename(columns={"Event_URL": "url", "Event_Name": "nome"})

    lutas = resumo.drop_duplicates("Fight_URL")[["Fight_URL", "Event_URL", "Method", "Final_Round", "Time", "Referee",
                                                 *DADOS_DA_LUTA]]
    lutas = tempo_para_segundos(lutas.assign(Tempo=lutas["Time"]), "Tempo").reset_index(drop=True)
    lutas["duracao_seg"] = (lutas["Final_Round"] - 1) * 300 + lutas["Tempo_seconds"]
    lutas.insert(0, "luta_id", range(1, len(lutas) + 1))
    lutas["evento_id"] = lutas["Event_URL"].map(eventos.set_index("url")["evento_id"])
    lutas = lutas.rename(columns={"Fight_URL": "url", "Method": "metodo", "Final_Round": "round_final",
                                  "Time": "tempo_final", "Referee": "arbitro", **DADOS_DA_LUTA})
    lutas = lutas[["luta_id", "url", "evento_id", "metodo", "round_final", "tempo_final", "duracao_seg", "arbitro",
                   *DADOS_DA_LUTA.values()]]

    id_da_luta = lutas.set_index("url")["luta_id"]

    desempenho = resumo.rename(columns={"Fighter": "lutador", "Resultado": "resultado", **ESTATISTICAS})
    desempenho["luta_id"] = desempenho["Fight_URL"].map(id_da_luta)
    desempenho = desempenho[["luta_id", "lutador", "resultado", *ESTATISTICAS.values()]]

    desempenho_round = por_round.rename(columns={"Fighter": "lutador", "Round": "round", **ESTATISTICAS})
    desempenho_round["luta_id"] = desempenho_round["Fight_URL"].map(id_da_luta)
    desempenho_round = desempenho_round[["luta_id", "lutador", "round", *ESTATISTICAS.values()]]

    return {"eventos": eventos, "lutas": lutas, "desempenho": desempenho, "desempenho_round": desempenho_round}


def criar_banco(caminho_banco=ARQUIVO_BANCO):
    """Recria o banco do zero: executa o schema e insere as quatro tabelas."""
    tabelas = montar_tabelas(pd.read_csv(ARQUIVO_RESUMO), pd.read_csv(ARQUIVO_ROUND), pd.read_csv(ARQUIVO_EVENTOS))

    with sqlite3.connect(caminho_banco) as conexao:
        conexao.execute("PRAGMA foreign_keys = ON")
        conexao.executescript(ARQUIVO_SCHEMA.read_text(encoding="utf-8"))
        # Ordem importa por causa das chaves estrangeiras
        for nome in ["eventos", "lutas", "desempenho", "desempenho_round"]:
            tabelas[nome].to_sql(nome, conexao, if_exists="append", index=False)

    return {nome: len(tabela) for nome, tabela in tabelas.items()}


if __name__ == "__main__":
    for tabela, linhas in criar_banco().items():
        print(f"{tabela}: {linhas} linhas")
    print(f"-> {ARQUIVO_BANCO}")
