"""Atualiza a base com os eventos mais recentes do ufcstats.com e regenera tudo o que depende dela.

Uso (na raiz do projeto, com o venv):
    python -m src.atualizar              # coleta eventos novos, limpa, gera JSON do site e banco SQL
    python -m src.atualizar --graficos   # idem + roda os notebooks 02 e 03 (PNGs e SQL)
    python -m src.atualizar --historico  # coleta TODOS os eventos que faltam, até os primeiros UFCs (horas)
    python -m src.atualizar --historico --limite 5   # só 5 eventos que faltam (para testar)

Sem --historico, só entram eventos MAIS NOVOS que o último da base. Com --historico entram também
os mais antigos. A coleta é retomável: cada evento é salvo ao terminar, então dá para interromper
(Ctrl+C) e rodar de novo, que continua de onde parou. Lutas que falharam dentro de um evento já
salvo são recoletadas na execução seguinte.
Também mantém data/processed/eventos.csv com a data de cada evento, data/raw/lutas_evento.csv com
lutadores (nome e link), categoria de peso, cinturão e bônus de cada luta (lidos da página do evento)
e data/raw/lutadores.csv com altura, envergadura, base e nascimento (página de cada lutador). Os dois
são completados com o que faltar da base, então a primeira execução depois de criá-los é mais longa.
"""

import argparse
import time
from datetime import date
from pathlib import Path

import pandas as pd
from selenium.common.exceptions import TimeoutException

from src.limpeza import limpar_dataset, limpar_lutadores
from src.scraper import (anexar_csv, criar_driver, esperar, extrair_dados_luta, extrair_eventos_da_pagina,
                         extrair_lutador, extrair_lutas_evento, extrair_varios_eventos)

RAIZ = Path(__file__).resolve().parent.parent
URL_LISTAGEM = "http://ufcstats.com/statistics/events/completed?page={}"
SELETOR_LISTAGEM = "tr.b-statistics__table-row a.b-link_style_black"


def caminhos(pasta_dados):
    """Arquivos da base dentro de uma pasta de dados (a real é data/; o teste usa uma pasta temporária)."""
    pasta = Path(pasta_dados)
    return {
        "bruto_resumo": pasta / "raw" / "eventos_resumo.csv",
        "bruto_round": pasta / "raw" / "eventos_round.csv",
        "lutas_evento": pasta / "raw" / "lutas_evento.csv",
        "bruto_lutadores": pasta / "raw" / "lutadores.csv",
        "lutadores": pasta / "processed" / "lutadores.csv",
        "resumo": pasta / "processed" / "dataset_final_resumo_limpo.csv",
        "round": pasta / "processed" / "dataset_final_round_limpo.csv",
        "eventos": pasta / "processed" / "eventos.csv",
    }


def listar_eventos(driver, urls_base, datas_conhecidas, max_paginas=10):
    """Percorre a listagem (mais recente primeiro) até ter visto a base e as datas que faltam.

    Para quando: já apareceu algum evento da base (logo, os novos ficaram para trás) E todos os
    eventos da base ainda sem data foram vistos.

    Espera a tabela aparecer (a 1ª página da sessão passa pelo anti-bot, que às vezes leva mais
    que alguns segundos). Se nenhum evento da base aparecer, a listagem não carregou direito:
    falha em vez de concluir, em silêncio, que não há eventos novos.
    """
    faltam_datas = set(urls_base) - set(datas_conhecidas)
    vistos, eventos = set(), []
    for pagina in range(1, max_paginas + 1):
        print(f"Lendo a página {pagina} da listagem de eventos...")
        driver.get(URL_LISTAGEM.format(pagina))
        try:
            esperar(driver, SELETOR_LISTAGEM, espera_max=60)
        except TimeoutException:
            if pagina == 1:
                raise RuntimeError("A listagem de eventos não carregou (anti-bot?); rode de novo.")
            break  # passou da última página
        da_pagina = extrair_eventos_da_pagina(driver.page_source)
        if not da_pagina:
            break
        eventos.extend(da_pagina)
        vistos.update(e["url"] for e in da_pagina)
        if vistos & set(urls_base) and faltam_datas <= vistos:
            break
        time.sleep(2)
    if urls_base and not vistos & set(urls_base):
        raise RuntimeError(f"Nenhum evento da base apareceu em {max_paginas} páginas da listagem; "
                           "ela não carregou direito ou max_paginas é pequeno.")
    return eventos


def listar_todos_eventos(driver):
    """Todos os eventos já realizados, numa página só (?page=all), do mais recente ao mais antigo da listagem."""
    print("Lendo a listagem completa de eventos...")
    driver.get(URL_LISTAGEM.format("all"))
    esperar(driver, SELETOR_LISTAGEM, espera_max=60)
    return extrair_eventos_da_pagina(driver.page_source)


def eventos_a_coletar(listagem, urls_base, datas, hoje, historico=False):
    """Eventos da listagem que ainda não estão na base.

    Sem histórico: só os mais novos que o último da base. Com histórico: todos os que faltam.
    Eventos sem data ou com data futura ficam de fora.
    """
    base = set(urls_base)
    mais_recente = max((datas[u] for u in base if u in datas), default="")
    vistos, novos = set(), []
    for e in listagem:
        if e["url"] in base or e["url"] in vistos or not e["data"] or e["data"] > hoje:
            continue
        if historico or e["data"] > mais_recente:
            novos.append(e)
            vistos.add(e["url"])
    return novos


def lutas_faltantes(lutas_evento, bruto_resumo):
    """Lutas listadas na página do evento que não estão no resumo bruto (falharam na coleta)."""
    ja_tem = set(bruto_resumo["Fight_URL"])
    eventos_na_base = set(bruto_resumo["Event_URL"])
    faltam = lutas_evento[~lutas_evento["Fight_URL"].isin(ja_tem) & lutas_evento["Event_URL"].isin(eventos_na_base)]
    return faltam[["Event_URL", "Fight_URL"]].drop_duplicates("Fight_URL")


def completar_lutas_faltantes(faltam, nomes_eventos, driver, arquivo_resumo, arquivo_round):
    """Coleta de novo as lutas que falharam, acrescentando-as aos CSVs brutos (uma a uma)."""
    if faltam.empty:
        return
    print(f"Lutas que faltam em eventos já coletados: {len(faltam)}.")
    for i, (evento, luta) in enumerate(faltam.itertuples(index=False), start=1):
        try:
            resumo, por_round = extrair_dados_luta(luta, driver)
            for df in (resumo, por_round):
                df["Event_URL"] = evento
                df["Event_Name"] = nomes_eventos.get(evento)
            anexar_csv(resumo, arquivo_resumo)
            anexar_csv(por_round, arquivo_round)
            print(f"  ({i}/{len(faltam)}) ok  {luta}")
        except Exception as e:
            print(f"  ({i}/{len(faltam)}) Erro em {luta}: {e}")


def completar_lutas_evento(urls_eventos, driver, arquivo):
    """Coleta categoria/cinturão/bônus dos eventos que ainda não estão no arquivo (append a cada evento)."""
    arquivo = Path(arquivo)
    ja_tem = set(pd.read_csv(arquivo)["Event_URL"]) if arquivo.exists() else set()
    faltam = [u for u in urls_eventos if u not in ja_tem]
    if faltam:
        print(f"Categoria de peso e bônus: {len(faltam)} eventos a ler.")
    for i, url in enumerate(faltam, start=1):
        try:
            df = extrair_lutas_evento(url, driver)
            df.to_csv(arquivo, mode="a", header=not arquivo.exists(), index=False)
            print(f"  ({i}/{len(faltam)}) {len(df)} lutas  {url}")
        except Exception as e:
            print(f"  ({i}/{len(faltam)}) Erro nesse evento: {e}")
        time.sleep(2)


def completar_lutadores(urls_lutadores, driver, arquivo):
    """Coleta as páginas dos lutadores que ainda não estão no arquivo (append a cada 25 lutadores)."""
    arquivo = Path(arquivo)
    ja_tem = set(pd.read_csv(arquivo)["Fighter_URL"]) if arquivo.exists() else set()
    faltam = [u for u in urls_lutadores if u not in ja_tem]
    if faltam:
        print(f"Páginas de lutador: {len(faltam)} a ler.")
    lote = []
    for i, url in enumerate(faltam, start=1):
        try:
            lote.append(extrair_lutador(url, driver))
        except Exception as e:
            print(f"  ({i}/{len(faltam)}) Erro em {url}: {e}")
        if lote and (len(lote) == 25 or i == len(faltam)):
            pd.DataFrame(lote).to_csv(arquivo, mode="a", header=not arquivo.exists(), index=False)
            print(f"  ({i}/{len(faltam)}) salvos")
            lote = []
        time.sleep(1)


def adicionar_dados_das_lutas(resumo, lutas_evento):
    """Junta categoria, cinturão, bônus (uma linha por luta) e o link do lutador ao dataset resumo.

    O link vem da página do evento, casado pelo par (luta, nome): é o identificador único do
    lutador (nomes se repetem entre pessoas diferentes).
    """
    colunas = ["Fight_URL", "Weight_Class", "Title_Bout", "Fight_Bonus", "Perf_Bonus"]
    resultado = resumo.merge(lutas_evento[colunas].drop_duplicates("Fight_URL"), on="Fight_URL", how="left")
    sem_dados = resultado.loc[resultado["Weight_Class"].isna(), "Fight_URL"].nunique()
    if sem_dados:
        print(f"Atenção: {sem_dados} lutas sem categoria de peso (rode de novo para tentar coletar).")

    links = pd.concat([
        lutas_evento[["Fight_URL", f"Fighter_{n}", f"Fighter_{n}_URL"]].set_axis(["Fight_URL", "Fighter", "Fighter_URL"], axis=1)
        for n in (1, 2)
    ]).drop_duplicates(["Fight_URL", "Fighter"])
    resultado = resultado.merge(links, on=["Fight_URL", "Fighter"], how="left")
    sem_link = resultado["Fighter_URL"].isna().sum()
    if sem_link:
        print(f"Atenção: {sem_link} linhas sem link do lutador (nome diferente entre página da luta e do evento).")
    return resultado


def desambiguar_homonimos(resumo, por_round, lutadores):
    """Nomes iguais de pessoas diferentes ganham o ano de nascimento: "Bruno Silva (1989)".

    Tudo o que agrupa por Fighter (gráficos, JSON do site, consultas SQL) passa a separá-los.
    O ano não muda com o tempo, então links do site com o nome continuam valendo. Se o ano não
    basta (mesmo ano, ou nascimento desconhecido), entra também o início do código do link do
    lutador no ufcstats, que também não muda: "Fulano (?, 1a2b)".
    """
    pessoas = resumo[["Fighter_URL", "Fighter"]].drop_duplicates("Fighter_URL")
    repetidos = pessoas[pessoas["Fighter"].duplicated(keep=False)]
    if repetidos.empty:
        return resumo, por_round
    ano = repetidos["Fighter_URL"].map(lutadores.set_index("Fighter_URL")["DOB"]).str[:4]
    rotulo = repetidos["Fighter"] + " (" + ano.fillna("?") + ")"
    empatados = rotulo.duplicated(keep=False)
    codigo = repetidos["Fighter_URL"].str.rstrip("/").str.rsplit("/", n=1).str[-1].str[:4]
    rotulo[empatados] = repetidos["Fighter"] + " (" + ano.fillna("?") + ", " + codigo + ")"
    novo_nome = dict(zip(repetidos["Fighter_URL"], rotulo))
    if len(set(novo_nome.values())) < len(novo_nome):
        raise ValueError(f"Homônimos que não deu para separar: {novo_nome}")
    print("Homônimos separados:", ", ".join(sorted(novo_nome.values())))

    resumo = resumo.copy()
    trocar = resumo["Fighter_URL"].isin(novo_nome)
    # O dataset por round não tem o link: o par (luta, nome antigo) identifica a pessoa
    por_luta = {(f, n): novo_nome[u] for f, n, u in resumo.loc[trocar, ["Fight_URL", "Fighter", "Fighter_URL"]].itertuples(index=False)}
    resumo.loc[trocar, "Fighter"] = resumo.loc[trocar, "Fighter_URL"].map(novo_nome)
    por_round = por_round.copy()
    por_round["Fighter"] = [por_luta.get((f, n), n) for f, n in zip(por_round["Fight_URL"], por_round["Fighter"])]
    return resumo, por_round


def urls_de_lutadores(lutas_evento):
    """Links únicos dos lutadores da base, na ordem em que aparecem (mais recentes primeiro)."""
    return list(dict.fromkeys(pd.concat([lutas_evento["Fighter_1_URL"], lutas_evento["Fighter_2_URL"]])))


def atualizar(pasta_dados=RAIZ / "data", exportar_site=True, max_paginas=10, driver=None, historico=False,
              limite=None, hoje=None):
    """Coleta eventos novos (ou, com historico, todos os que faltam), atualiza CSVs brutos/limpos e eventos.csv;
    opcionalmente JSON e banco. limite = no máximo N eventos nesta execução. hoje = data limite ('AAAA-MM-DD',
    padrão: hoje); a rotina automática (src.publicar) passa ontem, para não pegar um evento ainda em andamento."""
    arq = caminhos(pasta_dados)
    bruto_resumo = pd.read_csv(arq["bruto_resumo"])
    urls_base = list(dict.fromkeys(bruto_resumo["Event_URL"]))
    eventos_csv = pd.read_csv(arq["eventos"]) if arq["eventos"].exists() else pd.DataFrame(
        columns=["Event_URL", "Event_Name", "Event_Date"])
    datas = dict(zip(eventos_csv["Event_URL"], eventos_csv["Event_Date"]))

    driver_proprio = driver is None
    driver = driver or criar_driver()
    try:
        listagem = listar_todos_eventos(driver) if historico else listar_eventos(driver, urls_base, datas, max_paginas)
        for e in listagem:
            if e["data"]:
                datas[e["url"]] = e["data"]

        faltando = [u for u in urls_base if u not in datas]
        if faltando:
            raise RuntimeError(f"{len(faltando)} eventos da base não apareceram na listagem; aumente max_paginas.")

        mais_recente = max(datas[u] for u in urls_base)
        novos = eventos_a_coletar(listagem, urls_base, datas, hoje or date.today().isoformat(), historico)
        total = len(novos)
        novos = novos[:limite] if limite else novos

        print(f"Último evento na base: {mais_recente}. Eventos a coletar: {total}"
              + (f" (nesta execução: {len(novos)})" if len(novos) < total else ""))
        for e in novos[:20]:
            print(f"  + {e['data']}  {e['nome']}")
        if len(novos) > 20:
            print(f"  ... e mais {len(novos) - 20}")
        if novos:
            extrair_varios_eventos(novos, driver, arquivo_resumo=arq["bruto_resumo"], arquivo_round=arq["bruto_round"])
        urls_atuais = list(dict.fromkeys(pd.read_csv(arq["bruto_resumo"], low_memory=False)["Event_URL"]))
        completar_lutas_evento(urls_atuais, driver, arq["lutas_evento"])
        bruto_atual = pd.read_csv(arq["bruto_resumo"], low_memory=False)
        nomes = dict(zip(bruto_atual["Event_URL"], bruto_atual["Event_Name"]))
        completar_lutas_faltantes(lutas_faltantes(pd.read_csv(arq["lutas_evento"]), bruto_atual),
                                  nomes, driver, arq["bruto_resumo"], arq["bruto_round"])
        completar_lutadores(urls_de_lutadores(pd.read_csv(arq["lutas_evento"])), driver, arq["bruto_lutadores"])
    finally:
        if driver_proprio:
            driver.quit()

    # Limpeza completa a partir dos brutos (mesmo resultado dos notebooks, conferido em limpar_dataset)
    bruto_resumo = pd.read_csv(arq["bruto_resumo"], low_memory=False)
    resumo = limpar_dataset(bruto_resumo)
    por_round = limpar_dataset(pd.read_csv(arq["bruto_round"], low_memory=False))
    if arq["lutas_evento"].exists():
        resumo = adicionar_dados_das_lutas(resumo, pd.read_csv(arq["lutas_evento"]))
    if arq["bruto_lutadores"].exists():
        lutadores = limpar_lutadores(pd.read_csv(arq["bruto_lutadores"]).drop_duplicates("Fighter_URL"))
        lutadores.to_csv(arq["lutadores"], index=False)
        resumo, por_round = desambiguar_homonimos(resumo, por_round, lutadores)
    resumo.to_csv(arq["resumo"], index=False)
    por_round.to_csv(arq["round"], index=False)

    eventos = bruto_resumo[["Event_URL", "Event_Name"]].drop_duplicates("Event_URL")
    eventos["Event_Date"] = eventos["Event_URL"].map(datas)
    eventos.sort_values("Event_Date", ascending=False).to_csv(arq["eventos"], index=False)

    if exportar_site:
        from src.banco import criar_banco
        from src.exportar import exportar_lutadores
        from src.powerbi import exportar_powerbi

        exportar_lutadores()
        print("Banco SQL:", criar_banco())
        print("CSVs do Power BI:", exportar_powerbi())

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
    parser.add_argument("--historico", action="store_true",
                        help="coleta todos os eventos que faltam, inclusive os mais antigos que a base (demora horas)")
    parser.add_argument("--limite", type=int, help="no máximo N eventos nesta execução")
    args = parser.parse_args()

    novos = atualizar(historico=args.historico, limite=args.limite)
    if args.graficos:
        rodar_notebooks()
    if novos:
        print("\nAtenção: os textos com números fixos no index.html (badges e legendas) e no README"
              " não se atualizam sozinhos; revise-os.")
