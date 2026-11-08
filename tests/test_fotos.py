import pandas as pd

from src.fotos import extrair_foto, lutadores_para_coletar, slug_ufc

ESTILO = "https://ufc.com/images/styles/event_results_athlete_headshot/s3"


def _pagina(og=None, imagens=()):
    meta = f'<meta property="og:image" content="{og}">' if og else ""
    imgs = "".join(f'<img src="{src}">' for src in imagens)
    return f"<html><head>{meta}</head><body>{imgs}</body></html>"


def test_slug_ufc():
    assert slug_ufc("Jon Jones") == "jon-jones"
    assert slug_ufc("Sean O'Malley") == "sean-omalley"
    assert slug_ufc("José Aldo") == "jose-aldo"
    assert slug_ufc("B.J. Penn") == "bj-penn"


def test_extrair_foto_prefere_a_versao_reduzida_do_og_image():
    # Em Royce Gracie, a 1ª imagem de headshot da página é de outro lutador (Matt Hughes)
    html = _pagina("https://ufc.com/images/2022-10/GRACIE_ROYCE.png", [
        f"{ESTILO}/image/fighter_images/Matt_Hughes/matt_hughes_500x325_ufc.png?itok=x",
        f"{ESTILO}/2022-10/GRACIE_ROYCE.png?itok=IWrsEPFw",
    ])
    assert extrair_foto(html) == f"{ESTILO}/2022-10/GRACIE_ROYCE.png?itok=IWrsEPFw"


def test_extrair_foto_sem_versao_reduzida_usa_o_og_image():
    assert extrair_foto(_pagina("https://ufc.com/images/2025-10/JONES_JON.png")) == "https://ufc.com/images/2025-10/JONES_JON.png"


def test_extrair_foto_sem_foto_ou_pagina_de_busca():
    assert extrair_foto(_pagina()) is None
    assert extrair_foto(_pagina("https://www.ufc.com/themes/custom/ufc/assets/img/no-profile-image.png")) is None
    html = _pagina("https://ufc.com/images/2025-10/JONES_JON.png")
    assert extrair_foto(html, "https://www.ufc.com.br/search?query=athlete%20xyz") is None


def test_lutadores_para_coletar_ordena_por_luta_mais_recente_e_pula_homonimos():
    lutadores = pd.DataFrame({"Fighter_URL": ["u1", "u2", "u3", "u4"],
                              "Name": ["Antigo", "Recente", "Bruno Silva", "Bruno Silva"]})
    resumo = pd.DataFrame({"Fighter_URL": ["u1", "u2", "u3", "u4"], "Event_URL": ["E1", "E2", "E2", "E2"]})
    datas = pd.DataFrame({"Event_URL": ["E1", "E2"], "Event_Date": ["1995-01-01", "2026-01-01"]})
    fila = lutadores_para_coletar(lutadores, resumo, datas)
    assert fila["Slug"].tolist() == ["recente", "antigo"]
    assert lutadores_para_coletar(lutadores, resumo, datas, ["u2"])["Slug"].tolist() == ["antigo"]
