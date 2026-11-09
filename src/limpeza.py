"""Funções de limpeza e transformação dos dados extraídos do ufcstats.com."""

import re

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


def medida_para_cm(valor):
    """Converte altura/envergadura do ufcstats para cm: 5' 11" (pés e polegadas) ou 72" (polegadas)."""
    if pd.isna(valor) or valor.strip() in ("--", ""):
        return None
    valor = valor.replace('"', "").strip()
    pes, _, polegadas = valor.rpartition("'")
    total = int(pes or 0) * 12 + float(polegadas or 0)
    return round(total * 2.54, 1)


def limpar_lutadores(df):
    """Dados brutos das páginas de lutador -> altura e envergadura em cm, base e nascimento 'AAAA-MM-DD'."""
    return pd.DataFrame({
        "Fighter_URL": df["Fighter_URL"],
        "Name": df["Name"],
        "Height_cm": df["Height"].apply(medida_para_cm),
        "Reach_cm": df["Reach"].apply(medida_para_cm),
        "Stance": df["Stance"].replace("--", None),
        "DOB": pd.to_datetime(df["DOB"].replace("--", None), format="%b %d, %Y").dt.strftime("%Y-%m-%d"),
    })


def duracoes_dos_rounds(formato):
    """Duração de cada round (min) a partir do "Time format" do ufcstats.

    "3 Rnd (5-5-5)" -> [5, 5, 5]; "1 Rnd + OT (15-3)" -> [15, 3]; "No Time Limit" -> [] (sem limite).
    Sem formato (CSVs coletados antes de existir a coluna, todos da era de rounds de 5 min) -> None.
    """
    if pd.isna(formato) or not str(formato).strip():
        return None
    dentro = re.search(r"\(([^)]*)\)", str(formato))
    if not dentro:
        return []
    return [int(n) for n in re.findall(r"\d+", dentro.group(1))]


def duracao_segundos(round_final, tempo_seg, formato=None):
    """Tempo total de luta: rounds completos anteriores (pelo formato) + o tempo do último round."""
    if pd.isna(round_final) or pd.isna(tempo_seg):
        return None
    rounds = duracoes_dos_rounds(formato)
    if rounds is None:
        rounds = [5]
    anteriores = int(round_final) - 1
    if not rounds:  # sem limite de tempo: só existe um "round"
        return tempo_seg
    completos = rounds[:anteriores] + [rounds[-1]] * max(0, anteriores - len(rounds))
    return sum(completos) * 60 + tempo_seg


def adicionar_duracao(df, coluna_saida="Duracao_seg"):
    """Coluna de duração da luta (s) a partir de Final_Round, Time ('M:SS') e Time_Format (se houver)."""
    df = df.copy()
    tempo = tempo_para_segundos(df[["Time"]].copy(), "Time")["Time_seconds"]
    formatos = df["Time_Format"] if "Time_Format" in df.columns else pd.Series(None, index=df.index, dtype=object)
    df[coluna_saida] = [duracao_segundos(r, t, f) for r, t, f in zip(df["Final_Round"], tempo, formatos)]
    df[coluna_saida] = pd.to_numeric(df[coluna_saida])
    return df


INICIO_TUF = "2005-01-01"  # 1ª final do The Ultimate Fighter: 2005-04-09


def tipo_de_disputa(titulo, formato, data):
    """0 = luta comum, 1 = disputa de cinturão do UFC, 2 = final de torneio (TUF e afins).

    O ufcstats marca as finais do TUF com o mesmo ícone de cinturão. Desde 2005, disputa de cinturão do UFC
    tem 5 rounds; as finais de torneio têm 3 ("3 Rnd (5-5-5)" ou "3 Rnd + OT", com round extra).
    Antes disso há disputas de 3 rounds de verdade (UFC 26), então a regra só vale a partir do TUF.
    """
    if not titulo or pd.isna(titulo):
        return 0
    if isinstance(formato, str) and formato.startswith("3 Rnd") and str(data) >= INICIO_TUF:
        return 2
    return 1


def separar_finais_de_torneio(df, datas_eventos):
    """Tira as finais do TUF de Title_Bout (vira 0) e marca em Final_TUF (0/1). Idempotente.

    Usado por quem conta disputas de cinturão (análises, banco/Power BI, notebooks); 65 lutas na base completa.
    """
    if "Final_TUF" in df.columns or "Title_Bout" not in df.columns:
        return df
    datas = df["Event_URL"].map(datas_eventos.set_index("Event_URL")["Event_Date"])
    formatos = df["Time_Format"] if "Time_Format" in df.columns else pd.Series(None, index=df.index, dtype=object)
    tipo = [tipo_de_disputa(t, f, d) for t, f, d in zip(df["Title_Bout"], formatos, datas)]
    final = pd.Series([int(t == 2) for t in tipo], index=df.index)
    return df.assign(Title_Bout=df["Title_Bout"].where(final == 0, 0), Final_TUF=final)
