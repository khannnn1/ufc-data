"""`atualizar(historico=True)` de ponta a ponta com um navegador falso (páginas fixas, sem rede nem Selenium)."""

import pandas as pd
import pytest
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException

import src.atualizar as atualizar_mod
import src.scraper as scraper_mod
from src.atualizar import atualizar, caminhos
from src.scraper import extrair_varios_eventos

from tests.test_historico import LINHA_SIG, LINHA_TOTAIS, SIG, TOTAIS, _pagina_luta, _tabela

LISTAGEM = "http://ufcstats.com/statistics/events/completed?page={}"
EVENTOS = [  # do mais recente ao mais antigo, como na listagem do site
    ("E3", "UFC Novo", "October 01, 2026", ["F31"]),
    ("E2", "UFC Base", "April 08, 2023", ["F21", "F22"]),
    ("E1", "UFC 1", "November 12, 1993", ["F11"]),
]


def _html_listagem():
    linhas = "".join(
        f'<tr class="b-statistics__table-row"><td><a class="b-link b-link_style_black" href="{url}">{nome}</a>'
        f'<span class="b-statistics__date">{data}</span></td></tr>' for url, nome, data, _ in EVENTOS)
    return f"<table>{linhas}</table>"


def _html_evento(lutas):
    linhas = "".join(
        f'<tr class="b-fight-details__table-row" data-link="{luta}"><td>win</td>'
        f'<td><p><a href="L-A">A</a></p><p><a href="L-B">B</a></p></td><td><p>Open Weight</p></td></tr>' for luta in lutas)
    return f'<table><thead><tr><th>W/L</th><th>Fighter</th><th>Weight class</th></tr></thead><tbody>{linhas}</tbody></table>'


def _html_lutador(nome):
    campos = [("Height:", "6' 0\""), ("Reach:", '72"'), ("STANCE:", "Orthodox"), ("DOB:", "Jan 01, 1990")]
    itens = "".join(f'<li><i class="b-list__box-item-title">{r}</i> {v}</li>' for r, v in campos)
    return f'<span class="b-content__title-highlight">{nome}</span><ul class="b-list__box-list">{itens}</ul>'


class NavegadorFalso:
    def __init__(self, falhar=()):
        self.paginas = {LISTAGEM.format("all"): _html_listagem(), LISTAGEM.format(1): _html_listagem(),
                        "L-A": _html_lutador("A"), "L-B": _html_lutador("B")}
        completa = _pagina_luta([_tabela(TOTAIS, [LINHA_TOTAIS]), _tabela(TOTAIS, [LINHA_TOTAIS]),
                                 _tabela(SIG, [LINHA_SIG]), _tabela(SIG, [LINHA_SIG])])
        for url, _, _, lutas in EVENTOS:
            self.paginas[url] = _html_evento(lutas)
            for luta in lutas:
                # UFC 1: sem nenhuma estatística, como as lutas mais antigas do ufcstats
                self.paginas[luta] = _pagina_luta([], "No Time Limit") if url == "E1" else completa
        self.falhar = set(falhar)
        self.page_source = ""

    def get(self, url):
        if url in self.falhar:
            self.falhar.discard(url)  # falha só na primeira tentativa
            self.page_source = "<p>erro</p>"
            return
        self.page_source = self.paginas.get(url, "<html></html>")

    def find_element(self, by, seletor):
        if BeautifulSoup(self.page_source, "html.parser").select_one(seletor) is None:
            raise NoSuchElementException(seletor)
        return object()


@pytest.fixture
def sem_espera(monkeypatch):
    monkeypatch.setattr(scraper_mod, "PAUSA", 0)
    monkeypatch.setattr(scraper_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(atualizar_mod.time, "sleep", lambda s: None)
    # A falha de uma luta espera o tempo máximo do WebDriverWait: encurta para o teste
    espera_original = scraper_mod.esperar
    monkeypatch.setattr(scraper_mod, "esperar", lambda d, s, espera_max=20: espera_original(d, s, 0.01))
    monkeypatch.setattr(atualizar_mod, "esperar", lambda d, s, espera_max=20: espera_original(d, s, 0.01))


def test_historico_coleta_antigos_novos_e_retoma_lutas_que_falharam(tmp_path, sem_espera):
    arq = caminhos(tmp_path)
    (tmp_path / "raw").mkdir()
    (tmp_path / "processed").mkdir()
    # Base de partida: só o evento E2, e a luta F22 falhou nessa coleta
    navegador = NavegadorFalso(falhar={"F22"})
    extrair_varios_eventos([{"nome": "UFC Base", "url": "E2"}], navegador,
                           arquivo_resumo=arq["bruto_resumo"], arquivo_round=arq["bruto_round"])
    assert set(pd.read_csv(arq["bruto_resumo"])["Fight_URL"]) == {"F21"}

    novos = atualizar(tmp_path, exportar_site=False, driver=navegador, historico=True)

    assert [e["url"] for e in novos] == ["E3", "E1"]
    resumo = pd.read_csv(arq["resumo"])
    assert sorted(resumo["Fight_URL"].unique()) == ["F11", "F21", "F22", "F31"]  # F22 recoletada
    assert resumo.groupby("Fight_URL").size().eq(2).all()
    antiga = resumo[resumo["Fight_URL"] == "F11"]
    assert antiga["Sig_str_landed"].isna().all() and antiga["Time_Format"].eq("No Time Limit").all()
    assert set(resumo["Weight_Class"]) == {"Open Weight"}
    eventos = pd.read_csv(arq["eventos"])
    assert eventos["Event_Date"].tolist() == ["2026-10-01", "2023-04-08", "1993-11-12"]

    # Rodar de novo não coleta nada (retomável e idempotente)
    assert atualizar(tmp_path, exportar_site=False, driver=navegador, historico=True) == []
    assert len(pd.read_csv(arq["resumo"])) == len(resumo)


def test_listagem_vazia_falha_em_vez_de_dizer_que_nao_ha_eventos(tmp_path, sem_espera):
    arq = caminhos(tmp_path)
    (tmp_path / "raw").mkdir()
    (tmp_path / "processed").mkdir()
    navegador = NavegadorFalso()
    extrair_varios_eventos([{"nome": "UFC Base", "url": "E2"}], navegador,
                           arquivo_resumo=arq["bruto_resumo"], arquivo_round=arq["bruto_round"])
    navegador.paginas[LISTAGEM.format(1)] = "<p>verificando que você não é um robô...</p>"
    with pytest.raises(RuntimeError, match="não carregou"):
        atualizar(tmp_path, exportar_site=False, driver=navegador)


def test_modo_normal_traz_so_os_eventos_novos(tmp_path, sem_espera):
    arq = caminhos(tmp_path)
    (tmp_path / "raw").mkdir()
    (tmp_path / "processed").mkdir()
    navegador = NavegadorFalso()
    extrair_varios_eventos([{"nome": "UFC Base", "url": "E2"}], navegador,
                           arquivo_resumo=arq["bruto_resumo"], arquivo_round=arq["bruto_round"])
    novos = atualizar(tmp_path, exportar_site=False, driver=navegador)
    assert [e["url"] for e in novos] == ["E3"]
