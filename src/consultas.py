"""Lê as consultas nomeadas de sql/consultas.sql e as executa no banco data/ufc.db."""

import re
import sqlite3
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_CONSULTAS = RAIZ / "sql" / "consultas.sql"
ARQUIVO_BANCO = RAIZ / "data" / "ufc.db"


def carregar_consultas(caminho=ARQUIVO_CONSULTAS):
    """Devolve {nome: sql} a partir dos blocos que começam com '-- nome: <identificador>'."""
    texto = Path(caminho).read_text(encoding="utf-8")
    partes = re.split(r"^-- nome: (\w+)\s*$", texto, flags=re.MULTILINE)
    # partes = [cabeçalho, nome1, sql1, nome2, sql2, ...]
    return {nome: sql.strip() for nome, sql in zip(partes[1::2], partes[2::2])}


def consultar(nome, caminho_banco=ARQUIVO_BANCO):
    """Executa a consulta pelo nome e devolve um DataFrame."""
    sql = carregar_consultas()[nome]
    with sqlite3.connect(caminho_banco) as conexao:
        return pd.read_sql_query(sql, conexao)
