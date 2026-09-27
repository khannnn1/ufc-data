"""Parsing do HTML do ufcstats.com com páginas mínimas no mesmo formato (sem rede nem Selenium)."""

from bs4 import BeautifulSoup

from src.scraper import extrair_eventos_da_pagina, extrair_lutas_da_pagina_evento, extrair_tabela_por_lutador

PAGINA_EVENTO = """
<table>
  <thead><tr><th>W/L</th><th>Fighter</th><th>Kd</th><th>Weight class</th></tr></thead>
  <tbody>
    <tr class="b-fight-details__table-row">
      <td>linha sem data-link (estrutural)</td>
    </tr>
    <tr class="b-fight-details__table-row" data-link="http://ufc/luta-1">
      <td>win</td>
      <td><p><a href="http://ufc/lutador-a">Lutador A</a></p><p><a href="http://ufc/lutador-b">Lutador B</a></p></td>
      <td>1</td>
      <td><p>Lightweight <img src="http://ufc/img/belt.png"> <img src="/img/fight.png"></p></td>
    </tr>
    <tr class="b-fight-details__table-row" data-link="http://ufc/luta-2">
      <td>win</td>
      <td><p><a href="http://ufc/lutador-c">Lutadora C</a></p><p><a href="http://ufc/lutador-d">Lutadora D</a></p></td>
      <td>0</td>
      <td><p>Women's Flyweight <img src="http://ufc/img/ko.png"></p></td>
    </tr>
  </tbody>
</table>
"""


def test_extrair_lutas_da_pagina_evento_le_lutadores_categoria_e_icones():
    lutas = extrair_lutas_da_pagina_evento(PAGINA_EVENTO)
    assert len(lutas) == 2  # a linha sem data-link fica de fora
    primeira, segunda = lutas
    assert primeira == {
        "Fight_URL": "http://ufc/luta-1",
        "Fighter_1": "Lutador A", "Fighter_1_URL": "http://ufc/lutador-a",
        "Fighter_2": "Lutador B", "Fighter_2_URL": "http://ufc/lutador-b",
        "Weight_Class": "Lightweight", "Title_Bout": 1, "Fight_Bonus": 1, "Perf_Bonus": 0,
    }
    # ko.png é um nome antigo do bônus de Performance da Noite
    assert (segunda["Weight_Class"], segunda["Title_Bout"], segunda["Fight_Bonus"], segunda["Perf_Bonus"]) == \
        ("Women's Flyweight", 0, 0, 1)


def test_extrair_eventos_da_pagina_le_nome_url_e_data():
    html = """
    <table>
      <tr class="b-statistics__table-row"><td></td></tr>
      <tr class="b-statistics__table-row"><td>
        <a class="b-link b-link_style_black" href="http://ufc/evento-331"> UFC 331: A vs. B </a>
        <span class="b-statistics__date"> September 19, 2026 </span>
      </td></tr>
    </table>"""
    assert extrair_eventos_da_pagina(html) == [
        {"nome": "UFC 331: A vs. B", "url": "http://ufc/evento-331", "data": "2026-09-19"}]


def test_extrair_tabela_por_lutador_separa_os_dois_paragrafos_de_cada_celula():
    # O ufcstats põe os dois lutadores na mesma célula (um <p> cada): por isso não dá para usar pd.read_html
    html = """
    <table>
      <tr><th>Fighter</th><th>KD</th><th>Sig. str.</th></tr>
      <tr>
        <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">A</p><p class="b-fight-details__table-text">B</p></td>
        <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">1</p><p class="b-fight-details__table-text">0</p></td>
        <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">20 of 40</p><p class="b-fight-details__table-text">5 of 30</p></td>
      </tr>
    </table>"""
    headers, lutador_1, lutador_2 = extrair_tabela_por_lutador(BeautifulSoup(html, "html.parser").table)
    assert headers == ["Fighter", "KD", "Sig. str."]
    assert lutador_1 == [["A", "1", "20 of 40"]]
    assert lutador_2 == [["B", "0", "5 of 30"]]
