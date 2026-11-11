"""Rotina de publicação automática: conferências dos números e o caminho no git (repositórios temporários)."""

import json
import subprocess

import pytest

from src.publicar import (PUBLICAVEIS, conferir, enviar, eventos_depois_de, mensagem_do_commit, preparar_copia,
                          resumo_do_site)


def _lado(nome, res, sl=10):
    return [nome, res, 0, sl, 20, 0, 0, 0, 6.6, [0, 0, 0], None]


def _site(eventos, lutas_por_evento, sem_estat=()):
    """Resumo no formato de resumo_do_site; eventos = [(nome, data)], do mais novo ao mais antigo."""
    lista_eventos = [[nome, data, f"id{i}"] for i, (nome, data) in enumerate(eventos)]
    lutas = [[i, "Lightweight", "KO/TKO", 1, "1:00", 0, 0, 0,
              _lado(f"A{i}{j}", "W", None if (i, j) in sem_estat else 10), _lado(f"B{i}{j}", "L")]
             for i, n in enumerate(lutas_por_evento) for j in range(n)]
    return {"eventos": len(lista_eventos), "lutas": len(lutas), "ultimo": max(e[1] for e in lista_eventos),
            "lista_eventos": lista_eventos, "lista_lutas": lutas}


ANTES = _site([("UFC 331", "2026-10-31"), ("UFC 330", "2026-10-24")], [12, 13])


def test_resumo_do_site_le_lutas_json(tmp_path):
    (tmp_path / "lutas.json").write_text(json.dumps({"eventos": [["UFC 2", "1994-03-11", "x"], ["UFC 3", "1994-09-09", "y"]],
                                                     "lutas": [[0], [1], [1]]}), encoding="utf-8")
    r = resumo_do_site(tmp_path)
    assert (r["eventos"], r["lutas"], r["ultimo"]) == (2, 3, "1994-09-09")


def test_conferir_aceita_um_evento_novo_completo():
    depois = _site([("UFC 332", "2026-11-07"), ("UFC 331", "2026-10-31"), ("UFC 330", "2026-10-24")], [14, 12, 13])
    assert conferir(ANTES, depois) == []
    assert eventos_depois_de(depois, ANTES["ultimo"]) == [["UFC 332", "2026-11-07"]]


def test_conferir_barra_evento_sem_estatistica_e_base_que_encolheu():
    sem_estat = _site([("UFC 332", "2026-11-07"), ("UFC 331", "2026-10-31"), ("UFC 330", "2026-10-24")], [14, 12, 13],
                      sem_estat={(0, 3)})
    assert any("sem estatística" in p for p in conferir(ANTES, sem_estat))
    encolheu = _site([("UFC 332", "2026-11-07"), ("UFC 331", "2026-10-31")], [14, 12])
    assert any(p.startswith("eventos") for p in conferir(ANTES, encolheu))
    duplicado = _site([("UFC 332", "2026-11-07"), ("UFC 331", "2026-10-31"), ("UFC 330", "2026-10-24")], [40, 12, 13])
    assert any(p.startswith("lutas") for p in conferir(ANTES, duplicado))
    assert conferir(ANTES, ANTES) != []  # nada novo não se publica


def test_mensagem_do_commit_lista_os_eventos():
    assert mensagem_do_commit([["UFC 332", "2026-11-07"], ["UFC FN", "2026-11-14"]]) == \
        "Base atualizada: UFC 332 (2026-11-07) · UFC FN (2026-11-14)"


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repos(tmp_path):
    """origin (bare) com uma main; pasta principal clonada e uma cópia de publicação (worktree)."""
    origem, principal, copia = tmp_path / "origem.git", tmp_path / "principal", tmp_path / "publicacao"
    _git("init", "--bare", "-b", "main", str(origem), cwd=tmp_path)
    _git("clone", str(origem), str(principal), cwd=tmp_path)
    for chave, valor in [("user.name", "Teste"), ("user.email", "teste@exemplo.com")]:
        _git("config", chave, valor, cwd=principal)
    _git("checkout", "-b", "main", cwd=principal)
    for caminho in PUBLICAVEIS:
        arquivo = principal / caminho if caminho.endswith(".ipynb") else principal / caminho / "x.json"
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("{}", encoding="utf-8")
    (principal / "README.md").write_text("oi", encoding="utf-8")
    _git("add", ".", cwd=principal)
    _git("commit", "-m", "inicio", cwd=principal)
    _git("push", "origin", "main", cwd=principal)
    _git("worktree", "add", "-B", "publicacao", str(copia), "origin/main", cwd=principal)
    return origem, principal, copia


def test_preparar_copia_recusa_a_pasta_principal(repos):
    _, principal, _ = repos
    with pytest.raises(RuntimeError, match="pasta principal"):
        preparar_copia(principal)


def test_publica_so_os_arquivos_do_site_e_descarta_o_resto(repos):
    origem, principal, copia = repos
    (copia / "dados" / "x.json").write_text("velho", encoding="utf-8")  # sobra de uma execução que falhou
    preparar_copia(copia)
    assert (copia / "dados" / "x.json").read_text(encoding="utf-8") == "{}"

    (copia / "dados" / "x.json").write_text('{"novo": 1}', encoding="utf-8")
    (copia / "README.md").write_text("mexido", encoding="utf-8")  # fora de PUBLICAVEIS: não vai
    assert enviar("Base atualizada: UFC 332 (2026-11-07)", copia)
    assert _git("log", "-1", "--format=%s", "main", cwd=origem) == "Base atualizada: UFC 332 (2026-11-07)"
    assert _git("show", "main:dados/x.json", cwd=origem) == '{"novo": 1}'
    assert _git("show", "main:README.md", cwd=origem) == "oi"
    assert not enviar("de novo", copia)  # nada mudou desde o último envio


def test_enviar_reaplica_quando_a_main_andou(repos):
    origem, principal, copia = repos
    preparar_copia(copia)
    (principal / "README.md").write_text("mudou na main", encoding="utf-8")
    _git("commit", "-am", "outra mudança", cwd=principal)
    _git("push", "origin", "main", cwd=principal)
    (copia / "dados" / "x.json").write_text('{"novo": 2}', encoding="utf-8")
    assert enviar("Base atualizada", copia)
    assert _git("show", "main:README.md", cwd=origem) == "mudou na main"
    assert _git("show", "main:dados/x.json", cwd=origem) == '{"novo": 2}'
