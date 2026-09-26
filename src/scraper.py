"""Funções de coleta (web scraping) de dados do ufcstats.com via Selenium + BeautifulSoup."""

import time
import os
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def criar_driver(headless=True):
    """Cria e configura uma instância do Chrome controlada pelo Selenium."""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)


def extrair_tabela_por_lutador(tabela_html):
    """Extrai os valores de uma tabela de estatísticas, separando por lutador (1º e 2º <p> de cada célula)."""
    linhas = tabela_html.find_all("tr")
    headers = [th.get_text(strip=True) for th in linhas[0].find_all("th")]

    dados_lutador_1 = []
    dados_lutador_2 = []

    for linha in linhas[1:]:
        celulas = linha.find_all("td", class_="b-fight-details__table-col")
        if not celulas:
            continue
        valores_1 = []
        valores_2 = []
        for celula in celulas:
            ps = celula.find_all("p", class_="b-fight-details__table-text")
            valores_1.append(ps[0].get_text(strip=True) if len(ps) > 0 else None)
            valores_2.append(ps[1].get_text(strip=True) if len(ps) > 1 else None)
        dados_lutador_1.append(valores_1)
        dados_lutador_2.append(valores_2)

    return headers, dados_lutador_1, dados_lutador_2


HEADERS_TOTAIS = ['Fighter', 'KD', 'Sig. str.', 'Sig. str. %', 'Total str.', 'Td', 'Td %', 'Sub. att', 'Rev.', 'Ctrl']
HEADERS_SIG = ['Fighter_sig', 'Sig. str_sig', 'Sig. str. %_sig', 'Head', 'Body', 'Leg', 'Distance', 'Clinch', 'Ground']


def extrair_dados_luta(url, driver):
    """Extrai nome, resultado, método e estatísticas (resumo + por round) de uma luta."""
    driver.get(url)
    time.sleep(5)
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    pessoas = soup.find_all("div", class_="b-fight-details__person")
    nome_1 = pessoas[0].find("a", class_="b-link b-fight-details__person-link").text.strip()
    resultado_1 = pessoas[0].find("i", class_="b-fight-details__person-status").text.strip()
    nome_2 = pessoas[1].find("a", class_="b-link b-fight-details__person-link").text.strip()
    resultado_2 = pessoas[1].find("i", class_="b-fight-details__person-status").text.strip()

    info_bloco = soup.find("p", class_="b-fight-details__text")
    itens = info_bloco.find_all("i", class_=["b-fight-details__text-item_first", "b-fight-details__text-item"])
    info = {}
    for item in itens:
        label = item.find("i", class_="b-fight-details__label").text.strip()
        valor = item.get_text().replace(label, "").strip()
        info[label] = valor

    metodo = info.get("Method:", None)
    round_final = info.get("Round:", None)
    tempo = info.get("Time:", None)
    referee = info.get("Referee:", None)

    tabelas_html = soup.find_all("table")
    _, l1_0, l2_0 = extrair_tabela_por_lutador(tabelas_html[0])
    _, l1_1, l2_1 = extrair_tabela_por_lutador(tabelas_html[1])
    _, l1_2, l2_2 = extrair_tabela_por_lutador(tabelas_html[2])
    _, l1_3, l2_3 = extrair_tabela_por_lutador(tabelas_html[3])

    df_resumo_l1 = pd.DataFrame([l1_0[0]], columns=HEADERS_TOTAIS)
    df_resumo_l1 = pd.concat([df_resumo_l1, pd.DataFrame([l1_2[0]], columns=HEADERS_SIG)], axis=1)
    df_resumo_l1["Fighter"] = nome_1
    df_resumo_l1["Resultado"] = resultado_1
    df_resumo_l1 = df_resumo_l1.drop(columns=["Fighter_sig", "Sig. str_sig", "Sig. str. %_sig"])

    df_resumo_l2 = pd.DataFrame([l2_0[0]], columns=HEADERS_TOTAIS)
    df_resumo_l2 = pd.concat([df_resumo_l2, pd.DataFrame([l2_2[0]], columns=HEADERS_SIG)], axis=1)
    df_resumo_l2["Fighter"] = nome_2
    df_resumo_l2["Resultado"] = resultado_2
    df_resumo_l2 = df_resumo_l2.drop(columns=["Fighter_sig", "Sig. str_sig", "Sig. str. %_sig"])

    df_resumo_luta = pd.concat([df_resumo_l1, df_resumo_l2], ignore_index=True)
    df_resumo_luta["Method"] = metodo
    df_resumo_luta["Final_Round"] = round_final
    df_resumo_luta["Time"] = tempo
    df_resumo_luta["Referee"] = referee
    df_resumo_luta["Fight_URL"] = url

    df_round_l1 = pd.DataFrame(l1_1, columns=HEADERS_TOTAIS)
    df_round_l1 = pd.concat([df_round_l1, pd.DataFrame(l1_3, columns=HEADERS_SIG)], axis=1)
    df_round_l1["Fighter"] = nome_1
    df_round_l1["Round"] = range(1, len(df_round_l1) + 1)
    df_round_l1 = df_round_l1.drop(columns=["Fighter_sig", "Sig. str_sig", "Sig. str. %_sig"])

    df_round_l2 = pd.DataFrame(l2_1, columns=HEADERS_TOTAIS)
    df_round_l2 = pd.concat([df_round_l2, pd.DataFrame(l2_3, columns=HEADERS_SIG)], axis=1)
    df_round_l2["Fighter"] = nome_2
    df_round_l2["Round"] = range(1, len(df_round_l2) + 1)
    df_round_l2 = df_round_l2.drop(columns=["Fighter_sig", "Sig. str_sig", "Sig. str. %_sig"])

    df_por_round = pd.concat([df_round_l1, df_round_l2], ignore_index=True)
    df_por_round["Fight_URL"] = url

    return df_resumo_luta, df_por_round


def extrair_urls_evento(url_evento, driver):
    """Extrai as URLs de todas as lutas de um evento."""
    driver.get(url_evento)
    time.sleep(5)
    html_evento = driver.page_source
    soup_evento = BeautifulSoup(html_evento, "html.parser")

    linhas_luta = soup_evento.find_all("tr", class_="b-fight-details__table-row")
    return [linha["data-link"] for linha in linhas_luta if linha.has_attr("data-link")]


ICONES_PERFORMANCE = {"perf.png", "sub.png", "ko.png"}  # sub/ko: nomes antigos do bônus de performance


def extrair_lutas_da_pagina_evento(html_evento):
    """Categoria de peso, disputa de cinturão e bônus de cada luta, lidos da tabela da página do evento.

    Os três ficam na célula "Weight class": o texto é a categoria e os ícones marcam cinturão
    (belt.png), Luta da Noite (fight.png) e Performance da Noite (perf.png).
    """
    soup = BeautifulSoup(html_evento, "html.parser")
    cabecalho = [th.get_text(strip=True) for th in soup.select("thead th")]
    coluna = cabecalho.index("Weight class")

    lutas = []
    for linha in soup.find_all("tr", class_="b-fight-details__table-row"):
        if not linha.has_attr("data-link"):
            continue
        celula = linha.find_all("td")[coluna]
        icones = {img["src"].rsplit("/", 1)[-1] for img in celula.find_all("img")}
        lutas.append({
            "Fight_URL": linha["data-link"],
            "Weight_Class": celula.get_text(strip=True),
            "Title_Bout": int("belt.png" in icones),
            "Fight_Bonus": int("fight.png" in icones),
            "Perf_Bonus": int(bool(icones & ICONES_PERFORMANCE)),
        })
    return lutas


def extrair_lutas_evento(url_evento, driver):
    """DataFrame com categoria, cinturão e bônus das lutas de um evento (uma linha por luta)."""
    driver.get(url_evento)
    time.sleep(5)
    df = pd.DataFrame(extrair_lutas_da_pagina_evento(driver.page_source))
    df.insert(0, "Event_URL", url_evento)
    return df


def extrair_evento(url_evento, driver):
    """Extrai os dados de todas as lutas de um evento."""
    urls_lutas = extrair_urls_evento(url_evento, driver)

    todos_resumos = []
    todos_rounds = []

    for i, url_luta in enumerate(urls_lutas):
        print(f"  Luta {i + 1}/{len(urls_lutas)}: {url_luta}")
        try:
            df_resumo, df_round = extrair_dados_luta(url_luta, driver)
            todos_resumos.append(df_resumo)
            todos_rounds.append(df_round)
        except Exception as e:
            print(f"    Erro nessa luta: {e}")

    if not todos_resumos:
        return None, None

    df_evento_resumo = pd.concat(todos_resumos, ignore_index=True)
    df_evento_round = pd.concat(todos_rounds, ignore_index=True)

    df_evento_resumo["Event_URL"] = url_evento
    df_evento_round["Event_URL"] = url_evento

    return df_evento_resumo, df_evento_round


def extrair_varios_eventos(eventos, driver, limite=None,
                           arquivo_resumo="../data/raw/eventos_resumo.csv",
                           arquivo_round="../data/raw/eventos_round.csv"):
    """Processa uma lista de eventos, salvando incrementalmente em CSV a cada evento concluído."""
    lista_eventos = eventos[:limite] if limite else eventos

    for i, evento in enumerate(lista_eventos):
        print(f"=== Evento {i + 1}/{len(lista_eventos)}: {evento['nome']} ===")
        try:
            df_resumo, df_round = extrair_evento(evento["url"], driver)
            if df_resumo is not None:
                df_resumo["Event_Name"] = evento["nome"]
                df_round["Event_Name"] = evento["nome"]

                escrever_cabecalho_resumo = not os.path.exists(arquivo_resumo)
                escrever_cabecalho_round = not os.path.exists(arquivo_round)

                df_resumo.to_csv(arquivo_resumo, mode="a", header=escrever_cabecalho_resumo, index=False)
                df_round.to_csv(arquivo_round, mode="a", header=escrever_cabecalho_round, index=False)

                print(f"  Salvo com sucesso ({len(df_resumo)} linhas de resumo, {len(df_round)} de round)")
        except Exception as e:
            print(f"  Erro nesse evento: {e}")
        time.sleep(2)

    print("Concluído! Recarregando dataset final do disco...")
    return pd.read_csv(arquivo_resumo), pd.read_csv(arquivo_round)


def extrair_eventos_da_pagina(html_pagina):
    """Eventos (nome, URL e data 'AAAA-MM-DD') de uma página da listagem, na ordem do site (mais recente primeiro)."""
    soup_pagina = BeautifulSoup(html_pagina, "html.parser")
    eventos = []
    for linha in soup_pagina.find_all("tr", class_="b-statistics__table-row"):
        link = linha.find("a", class_="b-link b-link_style_black")
        if not link:
            continue  # linhas vazias/estruturais da tabela
        span_data = linha.find("span", class_="b-statistics__date")
        data = None
        if span_data:
            # ex.: "September 19, 2026"
            data = datetime.strptime(span_data.get_text(strip=True), "%B %d, %Y").date().isoformat()
        eventos.append({"nome": link.text.strip(), "url": link["href"], "data": data})
    return eventos


def extrair_eventos_multiplas_paginas(driver, num_paginas):
    """Coleta a lista de eventos (nome, URL e data) percorrendo múltiplas páginas da listagem."""
    todos_eventos = []

    for pagina in range(1, num_paginas + 1):
        url_pagina = f"http://ufcstats.com/statistics/events/completed?page={pagina}"
        print(f"Coletando página {pagina}...")

        driver.get(url_pagina)
        time.sleep(5)
        todos_eventos.extend(extrair_eventos_da_pagina(driver.page_source))
        time.sleep(2)

    return todos_eventos