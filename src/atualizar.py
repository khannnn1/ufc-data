"""Atualiza a base com os eventos mais recentes do ufcstats.com e regenera tudo o que depende dela.

Uso (na raiz do projeto, com o venv):
    python -m src.atualizar              # coleta eventos novos, limpa, gera JSON do site e banco SQL
    python -m src.atualizar --graficos   # idem + roda os notebooks 02 e 03 (PNGs e SQL)

Só entram eventos MAIS NOVOS que o último da base (o recorte continua sendo "os mais recentes").
Também mantém data/processed/eventos.csv com a data de cada evento.
"""

import argparse
import time
from datetime import date
from pathlib import Path

import pandas as pd

from src.limpeza import limpar_dataset
from src.scraper import criar_driver, extrair_eventos_da_pagina, extrair_varios_eventos

RAIZ = Path(__file__).resolve().parent.parent
URL_LISTAGEM = "http://ufcstats.com/statistics/events/completed?page={}"


def caminhos(pasta_dados):
    """Arquivos da base dentro de uma pasta de dados (a real é data/; o teste usa uma pasta temporária)."""
    pasta = Path(pasta_dados)
    return {
        "bruto_resumo": pasta / "raw" / "eventos_resumo.csv",
        "bruto_round": pasta / "raw" / "eventos_round.csv",
        "resumo": pasta / "processed" / "dataset_final_resumo_limpo.csv",
        "round": pasta / "processed" / "dataset_final_round_limpo.csv",
        "eventos": pasta / "processed" / "eventos.csv",
    }


def listar_eventos(driver, urls_base, datas_conhecidas, max_paginas=10):
    """Percorre a listagem (mais recente primeiro) até ter visto a base e as datas que faltam.

    Para quando: já apareceu algum evento da base (logo, os novos ficaram para trás) E todos os
    eventos da base ainda sem data foram vistos.
    """
    faltam_datas = set(urls_base) - set(datas_conhecidas)
    vistos, eventos = set(), []
    for pagina in range(1, max_paginas + 1):
        print(f"Lendo a página {pagina} da listagem de eventos...")
        driver.get(URL_LISTAGEM.format(pagina))
        time.sleep(5)
        da_pagina = extrair_eventos_da_pagina(driver.page_source)
        if not da_pagina:
            break
        eventos.extend(da_pagina)
        vistos.update(e["url"] for e in da_pagina)
        if vistos & set(urls_base) and faltam_datas <= vistos:
            break
        time.sleep(2)
    return eventos


def atualizar(pasta_dados=RAIZ / "data", exportar_site=True, max_paginas=10, driver=None):
    """Coleta eventos novos, atualiza CSVs brutos/limpos e eventos.csv; opcionalmente JSON e banco."""
    arq = caminhos(pasta_dados)
    bruto_resumo = pd.read_csv(arq["bruto_resumo"])
    urls_base = list(dict.fromkeys(bruto_resumo["Event_URL"]))
    eventos_csv = pd.read_csv(arq["eventos"]) if arq["eventos"].exists() else pd.DataFrame(
        columns=["Event_URL", "Event_Name", "Event_Date"])
    datas = dict(zip(eventos_csv["Event_URL"], eventos_csv["Event_Date"]))

    driver_proprio = driver is None
    driver = driver or criar_driver()
    try:
        listagem = listar_eventos(driver, urls_base, datas, max_paginas)
        for e in listagem:
            if e["data"]:
                datas[e["url"]] = e["data"]

        faltando = [u for u in urls_base if u not in datas]
        if faltando:
            raise RuntimeError(f"{len(faltando)} eventos da base não apareceram na listagem; aumente max_paginas.")

        mais_recente = max(datas[u] for u in urls_base)
        hoje = date.today().isoformat()
        novos = [e for e in listagem
                 if e["url"] not in set(urls_base) and e["data"] and mais_recente < e["data"] <= hoje]

        print(f"Último evento na base: {mais_recente}. Eventos novos: {len(novos)}")
        for e in novos:
            print(f"  + {e['data']}  {e['nome']}")
        if novos:
            extrair_varios_eventos(novos, driver, arquivo_resumo=arq["bruto_resumo"], arquivo_round=arq["bruto_round"])
    finally:
        if driver_proprio:
            driver.quit()

    # Limpeza completa a partir dos brutos (mesmo resultado dos notebooks, conferido em limpar_dataset)
    bruto_resumo = pd.read_csv(arq["bruto_resumo"])
    limpar_dataset(bruto_resumo).to_csv(arq["resumo"], index=False)
    limpar_dataset(pd.read_csv(arq["bruto_round"])).to_csv(arq["round"], index=False)

    eventos = bruto_resumo[["Event_URL", "Event_Name"]].drop_duplicates("Event_URL")
    eventos["Event_Date"] = eventos["Event_URL"].map(datas)
    eventos.sort_values("Event_Date", ascending=False).to_csv(arq["eventos"], index=False)

    if exportar_site:
        from src.banco import criar_banco
        from src.exportar import exportar_lutadores

        exportar_lutadores()
        print("Banco SQL:", criar_banco())

    return novos


def rodar_notebooks():
    """Reexecuta os notebooks de gráficos e SQL, regravando PNGs e saídas."""
    import asyncio
    import sys

    import nbformat
    from nbclient import NotebookClient

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    for nome in ["02_visualizacao.ipynb", "03_sql.ipynb"]:
        caminho = RAIZ / "notebooks" / nome
        print(f"Executando {nome}...")
        nb = nbformat.read(caminho, as_version=4)
        NotebookClient(nb, timeout=600, kernel_name="python3",
                       resources={"metadata": {"path": str(caminho.parent)}}).execute()
        nbformat.write(nb, caminho)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graficos", action="store_true", help="também reexecuta os notebooks 02 e 03")
    args = parser.parse_args()

    novos = atualizar()
    if args.graficos:
        rodar_notebooks()
    if novos:
        print("\nAtenção: os textos com números fixos no index.html (badges e legendas) e no README"
              " não se atualizam sozinhos; revise-os.")
