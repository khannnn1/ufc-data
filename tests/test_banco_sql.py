"""Banco SQLite em memória com o schema real e o mini-dataset: estrutura, chaves e consultas nomeadas."""

import sqlite3

import pandas as pd
import pytest

from src.banco import ARQUIVO_SCHEMA, montar_tabelas
from src.consultas import ARQUIVO_CONSULTAS, carregar_consultas


@pytest.fixture
def conexao(resumo, por_round, datas_eventos, lutadores):
    tabelas = montar_tabelas(resumo, por_round, datas_eventos, lutadores)
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")  # uma chave estrangeira quebrada faz o INSERT falhar
    con.executescript(ARQUIVO_SCHEMA.read_text(encoding="utf-8"))
    for nome in ["eventos", "lutas", "lutadores", "desempenho", "desempenho_round"]:
        tabelas[nome].to_sql(nome, con, if_exists="append", index=False)
    yield con
    con.close()


def consultar(con, nome):
    return pd.read_sql_query(carregar_consultas()[nome], con)


def test_montar_tabelas_separa_eventos_lutas_e_desempenho(conexao):
    contagem = {t: conexao.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ["eventos", "lutas", "lutadores", "desempenho", "desempenho_round"]}
    assert contagem == {"eventos": 2, "lutas": 3, "lutadores": 4, "desempenho": 6, "desempenho_round": 6}
    # evento_id em ordem de data decrescente: 1 = mais recente (E1, março)
    assert conexao.execute("SELECT url FROM eventos WHERE evento_id = 1").fetchone()[0] == "E1"
    # duração = (round final - 1) * 300 + tempo no round
    assert conexao.execute("SELECT duracao_seg FROM lutas WHERE url = 'F3'").fetchone()[0] == 360


def test_consultas_tem_nomes_unicos_e_nao_vazios():
    consultas = carregar_consultas()
    # Um nome repetido sobrescreveria a consulta anterior no dicionário sem aviso
    marcadores = ARQUIVO_CONSULTAS.read_text(encoding="utf-8").count("\n-- nome: ")
    assert len(consultas) == marcadores >= 15
    # Tirando os comentários, cada bloco é uma consulta (SELECT ou WITH)
    for nome, sql in consultas.items():
        codigo = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--")).strip().upper()
        assert codigo.startswith(("SELECT", "WITH")), nome


def test_todas_as_consultas_rodam_no_schema(conexao):
    # Pega erro de sintaxe e coluna inexistente; com o mini-dataset várias voltam vazias (amostras mínimas)
    for nome, sql in carregar_consultas().items():
        pd.read_sql_query(sql, conexao)


def test_confronto_bases(conexao):
    bases = consultar(conexao, "confronto_bases").set_index("confronto")
    # F1 e F3: canhoto (A) vence ortodoxos; F2: ortodoxo (C) vence quem troca de base
    assert bases.loc["Southpaw x Orthodox", ["lutas", "vitorias_lado_a"]].tolist() == [2, 2]
    assert bases.loc["Switch x Orthodox", ["lutas", "vitorias_lado_a"]].tolist() == [1, 0]
    assert "Switch x Southpaw" not in bases.index


def test_luta_da_noite(conexao):
    ln = consultar(conexao, "luta_da_noite").set_index("tipo")
    premiada = ln.loc["Luta da Noite"]
    assert premiada["lutas"] == 1
    assert premiada["ida_e_volta_pct"] == 100.0  # em F2 o perdedor (D) derrubou o vencedor
    assert premiada["decisao_pct"] == 100.0
    assert ln.loc["Demais lutas", "lutas"] == 2


def test_disputas_titulo(conexao):
    titulo = consultar(conexao, "disputas_titulo").set_index("tipo")
    assert titulo.loc["Disputa de cinturão", "lutas"] == 1
    assert titulo.loc["Disputa de cinturão", "finalizacao_pct"] == 100.0
    assert titulo.loc["Disputa de cinturão", "duracao_min"] == 6.0
