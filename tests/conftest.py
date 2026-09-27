"""Mini-dataset sintético no formato dos CSVs limpos, para testar sem depender de data/ (não versionado)."""

import pandas as pd
import pytest

from src.banco import ESTATISTICAS

# 3 lutas em 2 eventos, 4 lutadores:
#   F1 (E1): A (canhoto) vence B (ortodoxo) por nocaute no 1º round — Performance da Noite
#   F2 (E1): C (ortodoxo) vence D (troca de base) na decisão; D derrubou C uma vez — Luta da Noite
#   F3 (E2): A vence C por finalização no 2º round — disputa de cinturão
LUTAS = [
    # Fight_URL, Event_URL, vencedor, perdedor, Method, Final_Round, Time, Weight_Class, Title, Fight_Bonus, Perf_Bonus
    ("F1", "E1", "A", "B", "KO/TKO", 1, "2:30", "Lightweight", 0, 0, 1),
    ("F2", "E1", "C", "D", "Decision - Unanimous", 3, "5:00", "Welterweight", 0, 1, 0),
    ("F3", "E2", "A", "C", "Submission", 2, "1:00", "Lightweight", 1, 0, 0),
]
KNOCKDOWNS = {("F1", "A"): 1, ("F2", "D"): 1}
GOLPES = {("F1", "A"): 20, ("F1", "B"): 5, ("F2", "C"): 60, ("F2", "D"): 50, ("F3", "A"): 15, ("F3", "C"): 10}


def _linha(fight, evento, lutador, resultado, metodo, round_final, tempo, categoria, titulo, bonus_luta, bonus_perf):
    golpes = GOLPES[(fight, lutador)]
    estatisticas = {coluna: 0 for coluna in ESTATISTICAS}
    estatisticas.update({"KD": KNOCKDOWNS.get((fight, lutador), 0), "Sig_str_landed": golpes,
                         "Sig_str_attempted": golpes * 2, "Head_landed": golpes, "Distance_landed": golpes,
                         "Ctrl_seconds": 30})
    return {"Fighter": lutador, "Fighter_URL": f"url/{lutador}", "Resultado": resultado,
            "Fight_URL": fight, "Event_URL": evento, "Event_Name": f"Evento {evento}",
            "Method": metodo, "Final_Round": round_final, "Time": tempo, "Referee": "Juiz",
            "Weight_Class": categoria, "Title_Bout": titulo, "Fight_Bonus": bonus_luta, "Perf_Bonus": bonus_perf,
            **estatisticas}


@pytest.fixture
def resumo():
    linhas = []
    for fight, evento, vencedor, perdedor, *dados in LUTAS:
        linhas.append(_linha(fight, evento, vencedor, "W", *dados))
        linhas.append(_linha(fight, evento, perdedor, "L", *dados))
    return pd.DataFrame(linhas)


@pytest.fixture
def por_round(resumo):
    """Uma linha por lutador-luta-round, com as estatísticas todas no 1º round."""
    colunas = ["Fight_URL", "Fighter", *ESTATISTICAS]
    return resumo[colunas].assign(Round=1)


@pytest.fixture
def datas_eventos():
    return pd.DataFrame({"Event_URL": ["E1", "E2"], "Event_Name": ["Evento E1", "Evento E2"],
                         "Event_Date": ["2024-03-01", "2024-02-01"]})


@pytest.fixture
def lutadores():
    return pd.DataFrame({
        "Fighter_URL": ["url/A", "url/B", "url/C", "url/D"],
        "Name": ["A", "B", "C", "D"],
        "Height_cm": [180.3, 177.8, 185.4, 175.3],
        "Reach_cm": [72 * 2.54, 70 * 2.54, 75 * 2.54, 71 * 2.54],
        "Stance": ["Southpaw", "Orthodox", "Orthodox", "Switch"],
        "DOB": ["1995-01-01", "1990-01-01", "1992-06-15", "1998-01-01"],
    })
