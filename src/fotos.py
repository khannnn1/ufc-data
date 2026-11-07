"""Coleta a foto (rosto) de cada lutador na página de atleta do ufc.com, para as tabelas do site.

Uso, na raiz e com o venv: `python -m src.fotos` (ou `--limite N` para só N lutadores nesta execução).
Grava data/raw/fotos.csv (Fighter_URL, Slug, Photo_URL; Photo_URL vazio = sem foto encontrada) e
depois basta `python -m src.exportar` para a foto entrar no JSON do site.

- O ufcstats não tem fotos; o ufc.com tem uma página por atleta em /athlete/<slug>, com o slug
  montado a partir do nome ("Sean O'Malley" -> sean-omalley). Basta `requests` (sem anti-bot).
- O robots.txt do ufc.com pede `crawl-delay: 15` e proíbe paginar /athletes/all, então a coleta
  visita só as páginas de atleta, uma a cada 15 s (~240 por hora; a base toda leva ~11 h).
  Começa por quem lutou mais recentemente e é retomável: salva a cada 10 e pula quem já está no CSV.
- A foto do rosto é a meta og:image (a 1ª imagem de "headshot" da página pode ser de OUTRO lutador,
  de um card de luta). Usamos a versão reduzida dela (estilo event_results_athlete_headshot) quando
  a página a tem. O site só aponta para a URL: as imagens não são copiadas para o repositório.
- Nome que não existe no ufc.com cai numa página de busca (status 200): detectada pela URL final.
- Homônimos (mesmo nome, pessoas diferentes) ficam sem foto: o slug não diz qual dos dois é.
"""

import argparse
import re
import time
import unicodedata
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_LUTADORES = RAIZ / "data" / "processed" / "lutadores.csv"
ARQUIVO_RESUMO = RAIZ / "data" / "processed" / "dataset_final_resumo_limpo.csv"
ARQUIVO_EVENTOS = RAIZ / "data" / "processed" / "eventos.csv"
ARQUIVO_FOTOS = RAIZ / "data" / "raw" / "fotos.csv"

URL_ATLETA = "https://www.ufc.com/athlete/{}"
PAUSA = 15  # segundos entre páginas (crawl-delay do robots.txt do ufc.com)
SALVAR_A_CADA = 10
CABECALHOS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}


def slug_ufc(nome):
    """Slug da página do atleta no ufc.com: sem acento, minúsculo, sem apóstrofo/ponto, hífens."""
    texto = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    texto = re.sub(r"['’.]", "", texto.lower())
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")


def extrair_foto(html, url_final=""):
    """URL da foto do rosto numa página de atleta do ufc.com, ou None (sem foto / não é atleta)."""
    if "/search" in url_final:
        return None
    sopa = BeautifulSoup(html, "html.parser")
    meta = sopa.find("meta", attrs={"property": "og:image"})
    if not meta or not meta.get("content"):
        return None
    original = meta["content"]
    if "no-profile-image" in original or "silhouette" in original.lower():
        return None
    # og:image = .../images/2025-10/JONES_JON.png; a mesma foto reduzida, se estiver na página:
    # .../images/styles/event_results_athlete_headshot/s3/2025-10/JONES_JON.png?itok=...
    caminho = original.split("/images/", 1)[-1]
    for img in sopa.find_all("img", src=True):
        if f"event_results_athlete_headshot/s3/{caminho}" in img["src"]:
            return img["src"] if img["src"].startswith("http") else "https://www.ufc.com" + img["src"]
    return original


def lutadores_para_coletar(lutadores, resumo, datas_eventos, ja_coletados=()):
    """Fighter_URL, Name e slug de quem falta, do que lutou mais recentemente para o mais antigo.

    Fica de fora quem já está em fotos.csv e quem tem homônimo (mesmo slug que outro lutador).
    """
    ultima = (resumo.merge(datas_eventos[["Event_URL", "Event_Date"]], on="Event_URL")
              .groupby("Fighter_URL")["Event_Date"].max().rename("ultima"))
    tabela = lutadores[["Fighter_URL", "Name"]].join(ultima, on="Fighter_URL")
    tabela["Slug"] = tabela["Name"].map(slug_ufc)
    tabela = tabela[~tabela["Slug"].duplicated(keep=False) & (tabela["Slug"] != "")]
    tabela = tabela[~tabela["Fighter_URL"].isin(set(ja_coletados))]
    return tabela.sort_values(["ultima", "Name"], ascending=[False, True], na_position="last")[["Fighter_URL", "Name", "Slug"]]


def _salvar(linhas, caminho):
    novo = pd.DataFrame(linhas, columns=["Fighter_URL", "Slug", "Photo_URL"])
    if caminho.exists():
        novo = pd.concat([pd.read_csv(caminho), novo], ignore_index=True)
    novo.drop_duplicates("Fighter_URL", keep="last").to_csv(caminho, index=False)


def coletar_fotos(limite=None, caminho=ARQUIVO_FOTOS, pausa=PAUSA):
    """Visita a página de cada lutador que falta e grava a foto em data/raw/fotos.csv."""
    import requests

    caminho = Path(caminho)
    ja = pd.read_csv(caminho)["Fighter_URL"] if caminho.exists() else []
    fila = lutadores_para_coletar(pd.read_csv(ARQUIVO_LUTADORES),
                                  pd.read_csv(ARQUIVO_RESUMO, usecols=["Fighter_URL", "Event_URL"], low_memory=False),
                                  pd.read_csv(ARQUIVO_EVENTOS), ja)
    if limite:
        fila = fila.head(limite)
    print(f"{len(fila)} lutadores a visitar (~{len(fila) * pausa / 3600:.1f} h com {pausa} s entre páginas)")

    sessao = requests.Session()
    sessao.headers.update(CABECALHOS)
    linhas, achadas = [], 0
    try:
        for i, linha in enumerate(fila.itertuples(index=False), 1):
            try:
                resposta = sessao.get(URL_ATLETA.format(linha.Slug), timeout=30)
                if not resposta.ok:  # 403/429/5xx: não grava, para tentar de novo na próxima execução
                    print(f"  {linha.Name}: HTTP {resposta.status_code}")
                    time.sleep(pausa)
                    continue
                foto = extrair_foto(resposta.text, resposta.url)
                linhas.append((linha.Fighter_URL, linha.Slug, foto))
                achadas += foto is not None
            except Exception as erro:  # falha isolada (rede): tenta de novo na próxima execução
                print(f"  erro em {linha.Name}: {erro}")
            if len(linhas) >= SALVAR_A_CADA:
                _salvar(linhas, caminho)
                linhas = []
                print(f"  {i}/{len(fila)} visitados, {achadas} fotos")
            time.sleep(pausa)
    finally:
        if linhas:
            _salvar(linhas, caminho)
    print(f"Pronto: {achadas} fotos encontradas. Rode `python -m src.exportar` para levá-las ao site.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limite", type=int, help="no máximo N lutadores nesta execução")
    coletar_fotos(parser.parse_args().limite)
