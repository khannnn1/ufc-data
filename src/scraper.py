"""Funções de coleta (web scraping) de dados do ufcstats.com via Selenium + BeautifulSoup."""

import time
import os
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def criar_driver(headless=False):
    """Cria e configura uma instância do Chrome controlada pelo Selenium.

    Com janela por padrão: desde 2026-11 a verificação do ufcstats não termina no Chrome sem janela
    (headless): a página fica em branco para sempre. Com janela ela passa em ~50 s. Por isso a coleta
    (manual ou a rotina agendada, que roda com o usuário logado) abre uma janela do Chrome.
    """
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
PAUSA = 0.5  # segundos entre páginas, para não sobrecarregar o site


def esperar(driver, seletor, espera_max=20):
    """Espera um elemento da página aparecer (em vez de um sleep fixo) e faz uma pausa curta de cortesia.

    Só o primeiro acesso da sessão passa pela verificação anti-bot (alguns segundos); depois cada página
    carrega em menos de 1 s, então esperar pelo conteúdo é bem mais rápido que os antigos 5 s fixos.
    """
    WebDriverWait(driver, espera_max).until(EC.presence_of_element_located((By.CSS_SELECTOR, seletor)))
    time.sleep(PAUSA)


def _tabelas_da_luta(tabelas_html):
    """Separa as tabelas da página da luta: (totais, totais por round, golpes sig., golpes sig. por round).

    Lutas recentes têm as 4. Lutas antigas podem não ter as tabelas por round ("Round-by-round stats not
    currently available") ou nenhuma estatística; o que faltar volta como None.
    """
    if len(tabelas_html) == 4:
        return tuple(tabelas_html)
    if len(tabelas_html) == 2:
        return tabelas_html[0], None, tabelas_html[1], None
    if len(tabelas_html) == 1:
        return tabelas_html[0], None, None, None
    if not tabelas_html:
        return None, None, None, None
    raise ValueError(f"Página de luta com {len(tabelas_html)} tabelas, formato desconhecido")


def _linhas(tabela):
    """Linhas dos dois lutadores de uma tabela (ou listas vazias se a tabela não existe)."""
    if tabela is None:
        return [], []
    _, l1, l2 = extrair_tabela_por_lutador(tabela)
    return l1, l2


def extrair_dados_luta_html(html, url):
    """Nome, resultado, método, formato de tempo e estatísticas (resumo + por round) a partir do HTML da luta."""
    soup = BeautifulSoup(html, "html.parser")

    pessoas = soup.find_all("div", class_="b-fight-details__person")
    nomes, resultados = [], []
    for pessoa in pessoas[:2]:
        nomes.append(pessoa.find("a", class_="b-link b-fight-details__person-link").text.strip())
        resultados.append(pessoa.find("i", class_="b-fight-details__person-status").text.strip())

    info_bloco = soup.find("p", class_="b-fight-details__text")
    itens = info_bloco.find_all("i", class_=["b-fight-details__text-item_first", "b-fight-details__text-item"])
    info = {}
    for item in itens:
        label = item.find("i", class_="b-fight-details__label").text.strip()
        valor = item.get_text().replace(label, "").strip()
        info[label] = valor

    totais, totais_round, sig, sig_round = _tabelas_da_luta(soup.find_all("table"))
    linhas = [_linhas(t) for t in (totais, totais_round, sig, sig_round)]
    vazio_totais = [None] * len(HEADERS_TOTAIS)
    vazio_sig = [None] * len(HEADERS_SIG)

    resumos, rounds = [], []
    for i, (nome, resultado) in enumerate(zip(nomes, resultados)):
        l_totais, l_totais_round, l_sig, l_sig_round = (par[i] for par in linhas)

        resumo = pd.concat([pd.DataFrame([l_totais[0] if l_totais else vazio_totais], columns=HEADERS_TOTAIS),
                            pd.DataFrame([l_sig[0] if l_sig else vazio_sig], columns=HEADERS_SIG)], axis=1)
        resumo["Fighter"] = nome
        resumo["Resultado"] = resultado
        resumos.append(resumo.drop(columns=["Fighter_sig", "Sig. str_sig", "Sig. str. %_sig"]))

        if l_totais_round:
            sig_por_round = l_sig_round if len(l_sig_round) == len(l_totais_round) else [vazio_sig] * len(l_totais_round)
            por_round = pd.concat([pd.DataFrame(l_totais_round, columns=HEADERS_TOTAIS),
                                   pd.DataFrame(sig_por_round, columns=HEADERS_SIG)], axis=1)
            por_round["Fighter"] = nome
            por_round["Round"] = range(1, len(por_round) + 1)
            rounds.append(por_round.drop(columns=["Fighter_sig", "Sig. str_sig", "Sig. str. %_sig"]))

    df_resumo_luta = pd.concat(resumos, ignore_index=True)
    df_resumo_luta["Method"] = info.get("Method:")
    df_resumo_luta["Final_Round"] = info.get("Round:")
    df_resumo_luta["Time"] = info.get("Time:")
    df_resumo_luta["Time_Format"] = info.get("Time format:")  # ex.: "3 Rnd (5-5-5)", "No Time Limit"
    df_resumo_luta["Referee"] = info.get("Referee:")
    df_resumo_luta["Fight_URL"] = url

    colunas_round = [c for c in HEADERS_TOTAIS + HEADERS_SIG if c not in {"Fighter_sig", "Sig. str_sig", "Sig. str. %_sig"}]
    df_por_round = pd.concat(rounds, ignore_index=True) if rounds else pd.DataFrame(columns=colunas_round + ["Round"])
    df_por_round["Fight_URL"] = url

    return df_resumo_luta, df_por_round


def extrair_dados_luta(url, driver):
    """Abre a página da luta e extrai os dados (ver extrair_dados_luta_html)."""
    driver.get(url)
    esperar(driver, "div.b-fight-details__person")
    return extrair_dados_luta_html(driver.page_source, url)


def extrair_urls_evento(url_evento, driver):
    """Extrai as URLs de todas as lutas de um evento."""
    driver.get(url_evento)
    esperar(driver, "tr.b-fight-details__table-row")
    html_evento = driver.page_source
    soup_evento = BeautifulSoup(html_evento, "html.parser")

    linhas_luta = soup_evento.find_all("tr", class_="b-fight-details__table-row")
    return [linha["data-link"] for linha in linhas_luta if linha.has_attr("data-link")]


ICONES_PERFORMANCE = {"perf.png", "sub.png", "ko.png"}  # sub/ko: nomes antigos do bônus de performance


def extrair_lutas_da_pagina_evento(html_evento):
    """Lutadores, categoria de peso, disputa de cinturão e bônus de cada luta, lidos da página do evento.

    A célula "Fighter" tem os dois lutadores (nome e link da página de cada um). Categoria, cinturão
    e bônus ficam na célula "Weight class": o texto é a categoria e os ícones marcam cinturão
    (belt.png), Luta da Noite (fight.png) e Performance da Noite (perf.png).
    """
    soup = BeautifulSoup(html_evento, "html.parser")
    cabecalho = [th.get_text(strip=True) for th in soup.select("thead th")]
    coluna = cabecalho.index("Weight class")
    coluna_lutadores = cabecalho.index("Fighter")

    lutas = []
    for linha in soup.find_all("tr", class_="b-fight-details__table-row"):
        if not linha.has_attr("data-link"):
            continue
        celula = linha.find_all("td")[coluna]
        icones = {img["src"].rsplit("/", 1)[-1] for img in celula.find_all("img")}
        lutador_1, lutador_2 = linha.find_all("td")[coluna_lutadores].find_all("a")
        lutas.append({
            "Fight_URL": linha["data-link"],
            "Fighter_1": lutador_1.get_text(strip=True), "Fighter_1_URL": lutador_1["href"],
            "Fighter_2": lutador_2.get_text(strip=True), "Fighter_2_URL": lutador_2["href"],
            "Weight_Class": celula.get_text(strip=True),
            "Title_Bout": int("belt.png" in icones),
            "Fight_Bonus": int("fight.png" in icones),
            "Perf_Bonus": int(bool(icones & ICONES_PERFORMANCE)),
        })
    return lutas


def extrair_lutas_evento(url_evento, driver):
    """DataFrame com categoria, cinturão e bônus das lutas de um evento (uma linha por luta)."""
    driver.get(url_evento)
    esperar(driver, "tr.b-fight-details__table-row")
    df = pd.DataFrame(extrair_lutas_da_pagina_evento(driver.page_source))
    df.insert(0, "Event_URL", url_evento)
    return df


def extrair_lutador(url_lutador, driver, espera_max=20):
    """Altura, envergadura, base e data de nascimento da página de um lutador (textos como no site).

    Espera o bloco de dados aparecer em vez de um sleep fixo: só o primeiro acesso da sessão
    passa pela verificação anti-bot; depois a página carrega em menos de 1 s.
    """
    driver.get(url_lutador)
    WebDriverWait(driver, espera_max).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "ul.b-list__box-list li")))
    soup = BeautifulSoup(driver.page_source, "html.parser")

    campos = {}
    for item in soup.select("ul.b-list__box-list li"):
        rotulo = item.find("i", class_="b-list__box-item-title")
        if rotulo:
            texto_rotulo = rotulo.get_text(strip=True)
            valor = item.get_text(" ", strip=True).replace(texto_rotulo, "", 1).strip()
            campos[texto_rotulo.rstrip(":").upper()] = valor
    return {
        "Fighter_URL": url_lutador,
        "Name": soup.select_one("span.b-content__title-highlight").get_text(strip=True),
        "Height": campos.get("HEIGHT"),  # ex.: 5' 5"
        "Reach": campos.get("REACH"),    # ex.: 65"
        "Stance": campos.get("STANCE"),  # ex.: Orthodox
        "DOB": campos.get("DOB"),        # ex.: Oct 10, 2001
    }


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


def anexar_csv(df, arquivo):
    """Acrescenta linhas a um CSV, alinhando as colunas às do cabeçalho que já existe.

    Se o df traz uma coluna nova (ex.: Time_Format, que os CSVs antigos não têm), o arquivo é
    reescrito uma vez com a coluna a mais (vazia nas linhas antigas); depois volta a ser só append.
    """
    if not os.path.exists(arquivo):
        df.to_csv(arquivo, index=False)
        return
    cabecalho = list(pd.read_csv(arquivo, nrows=0).columns)
    novas = [c for c in df.columns if c not in cabecalho]
    if novas:
        antigo = pd.read_csv(arquivo, dtype=str, keep_default_na=False)  # texto como está, sem converter
        pd.concat([antigo, df], ignore_index=True).to_csv(arquivo, index=False)
    else:
        df.reindex(columns=cabecalho).to_csv(arquivo, mode="a", header=False, index=False)


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

                anexar_csv(df_resumo, arquivo_resumo)
                anexar_csv(df_round, arquivo_round)

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