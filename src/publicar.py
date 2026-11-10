"""Rotina automática: traz para a base os eventos já encerrados e publica o site sozinha.

Roda numa cópia de trabalho SÓ DELA (git worktree que acompanha a origin/main), com data/ apontando para a
base do PC; o Agendador de Tarefas do Windows a chama todo dia (ver scripts/agendar_publicacao.ps1).
Uso manual, nessa cópia:  python -m src.publicar            (atualiza e publica)
                          python -m src.publicar --sem-enviar (atualiza e confere, mas não faz commit/push)

Passos:
1. Descarta qualquer mudança na cópia e a alinha com a origin/main (por isso não se edita nada nela).
2. `atualizar` só com eventos de ANTES de hoje: um evento do dia pode estar em andamento e entraria pela metade.
3. Se a base tem evento mais novo que o último do site (dados/lutas.json): fotos dos lutadores novos,
   JSONs do site, banco SQL, Power BI e notebooks 02/03. Sem nada novo, para aqui (não publica nada).
   A comparação é com o site, não com a coleta do dia: se o PC ficou desligado ou uma publicação falhou,
   a execução seguinte publica o que estiver pendente.
4. Confere os números (eventos e lutas só crescem, evento novo com estatísticas) e roda os testes.
5. Commit só dos arquivos do site (PUBLICAVEIS) e push para a main; o GitHub Pages publica em ~1 min.
Qualquer falha: nada é publicado, o motivo vai para data/publicacao.log e a saída tem código 1.
"""

import argparse
import json
import subprocess
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PUBLICAVEIS = ["dados", "powerbi/dados", "figures", "notebooks/02_visualizacao.ipynb", "notebooks/03_sql.ipynb"]
ARQUIVO_LOG = RAIZ / "data" / "publicacao.log"
MAX_LUTAS_POR_EVENTO = 20  # nenhum card do UFC passa disso; mais é sinal de coleta duplicada
FOTOS_POR_EXECUCAO = 40  # ~10 min com a pausa de 15 s do ufc.com; cobre os estreantes de um card


def git(*args, cwd=RAIZ):
    """Roda um comando git e devolve a saída; erro vira exceção com a mensagem do git."""
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def preparar_copia(cwd=RAIZ):
    """Alinha a cópia de publicação com a origin/main, descartando o que houver nela.

    Recusa rodar na pasta principal do projeto (onde se trabalha): ali o reset apagaria trabalho.
    """
    git_dir = (Path(cwd) / git("rev-parse", "--git-dir", cwd=cwd)).resolve()
    comum = (Path(cwd) / git("rev-parse", "--git-common-dir", cwd=cwd)).resolve()
    if git_dir == comum:
        raise RuntimeError("Esta é a pasta principal do projeto. A publicação automática só roda na cópia própria "
                           "(git worktree), criada por scripts/agendar_publicacao.ps1.")
    git("fetch", "origin", "main", cwd=cwd)
    git("reset", "--hard", "origin/main", cwd=cwd)


def enviar(mensagem, cwd=RAIZ):
    """Commit só dos arquivos do site e push para a main. Devolve False se não havia nada a enviar."""
    git("add", "--", *PUBLICAVEIS, cwd=cwd)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=cwd).returncode == 0:
        return False
    git("commit", "-m", mensagem, cwd=cwd)
    try:
        git("push", "origin", "HEAD:main", cwd=cwd)
    except RuntimeError:  # a main andou enquanto a rotina rodava: reaplica o commit em cima e tenta uma vez mais
        git("pull", "--rebase", "origin", "main", cwd=cwd)
        git("push", "origin", "HEAD:main", cwd=cwd)
    return True


def descartar(cwd=RAIZ):
    """Volta os arquivos do site ao que está publicado (depois de uma falha)."""
    git("checkout", "HEAD", "--", *PUBLICAVEIS, cwd=cwd)


def resumo_do_site(pasta=RAIZ / "dados"):
    """Eventos, lutas e data do último evento em dados/lutas.json, mais as lutas de cada evento."""
    dados = json.loads((Path(pasta) / "lutas.json").read_text(encoding="utf-8"))
    eventos = dados["eventos"]  # [nome, data, id]
    return {"eventos": len(eventos), "lutas": len(dados["lutas"]),
            "ultimo": max((e[1] for e in eventos), default=""),
            "lista_eventos": eventos, "lista_lutas": dados["lutas"]}


def eventos_depois_de(resumo, data):
    """[nome, data] dos eventos do site posteriores a `data`, do mais antigo ao mais novo."""
    return sorted(([e[0], e[1]] for e in resumo["lista_eventos"] if e[1] > data), key=lambda e: e[1])


def conferir(antes, depois):
    """Motivos para NÃO publicar (lista vazia = pode publicar)."""
    novos = eventos_depois_de(depois, antes["ultimo"])
    problemas = []
    if not novos:
        problemas.append("nenhum evento mais novo que o último do site")
    if depois["eventos"] != antes["eventos"] + len(novos):
        problemas.append(f"eventos: {antes['eventos']} -> {depois['eventos']}, mas {len(novos)} são novos")
    novas_lutas = depois["lutas"] - antes["lutas"]
    if not len(novos) <= novas_lutas <= MAX_LUTAS_POR_EVENTO * max(len(novos), 1):
        problemas.append(f"lutas: {antes['lutas']} -> {depois['lutas']} para {len(novos)} evento(s) novo(s)")
    novos_idx = {i for i, e in enumerate(depois["lista_eventos"]) if e[1] > antes["ultimo"]}
    sem_estat = sum(1 for luta in depois["lista_lutas"] if luta[0] in novos_idx
                    for lado in luta[8:10] if lado[3] is None)
    if sem_estat:
        problemas.append(f"{sem_estat} lado(s) de luta sem estatística nos eventos novos (ufcstats incompleto?)")
    return problemas


def mensagem_do_commit(novos):
    """'Base atualizada: UFC 332 (2026-11-07)' (vários eventos separados por ' · ')."""
    return "Base atualizada: " + " · ".join(f"{nome} ({data})" for nome, data in novos)


class Log:
    """Escreve em data/publicacao.log e, se houver, na tela (com pythonw, o da tarefa agendada, não há tela)."""

    def __init__(self, caminho, tela):
        self.arquivo = open(caminho, "a", encoding="utf-8")
        self.tela = tela

    def write(self, texto):
        if self.tela:
            self.tela.write(texto)
        self.arquivo.write(texto)
        self.arquivo.flush()

    def flush(self):
        if self.tela:
            self.tela.flush()


def publicar(enviar_ao_github=True, hoje=None):
    """Executa a rotina inteira. Devolve True se publicou."""
    from src.atualizar import atualizar, rodar_notebooks
    from src.banco import criar_banco
    from src.exportar import exportar_lutadores
    from src.fotos import coletar_fotos
    from src.powerbi import exportar_powerbi

    hoje = hoje or date.today()
    if enviar_ao_github:
        preparar_copia()
    antes = resumo_do_site()
    print(f"Último evento no site: {antes['ultimo']} ({antes['eventos']} eventos, {antes['lutas']} lutas).")

    atualizar(exportar_site=False, hoje=(hoje - timedelta(days=1)).isoformat())

    import pandas as pd
    datas = pd.read_csv(RAIZ / "data" / "processed" / "eventos.csv")["Event_Date"]
    if datas.max() <= antes["ultimo"]:
        print("Nenhum evento novo para publicar.")
        return False

    try:
        coletar_fotos(limite=FOTOS_POR_EXECUCAO)
    except Exception:  # foto é enfeite: sem ela o lutador aparece com as iniciais
        print("Fotos: falhou, segue sem as novas.\n" + traceback.format_exc())
    exportar_lutadores()
    print("Banco SQL:", criar_banco())
    print("CSVs do Power BI:", exportar_powerbi())
    try:
        rodar_notebooks()
    except Exception:  # gráficos em PNG ficam como estavam; o resto segue
        print("Notebooks: falharam, os PNGs ficam como estavam.\n" + traceback.format_exc())
        git("checkout", "HEAD", "--", "figures", "notebooks")

    depois = resumo_do_site()
    novos = eventos_depois_de(depois, antes["ultimo"])
    problemas = conferir(antes, depois)
    testes = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=RAIZ, capture_output=True, text=True)
    if testes.returncode:
        problemas.append("testes falharam:\n" + testes.stdout[-3000:])
    if problemas:
        descartar()
        raise RuntimeError("Não publicado:\n- " + "\n- ".join(problemas))

    print(f"Novos no site: {len(novos)} evento(s), {depois['lutas'] - antes['lutas']} lutas.")
    for nome, data in novos:
        print(f"  + {data}  {nome}")
    if not enviar_ao_github:
        print("--sem-enviar: arquivos gerados, nada enviado.")
        return False
    enviou = enviar(mensagem_do_commit(novos))
    print("Publicado na main." if enviou else "Nada mudou nos arquivos do site.")
    return enviou


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sem-enviar", action="store_true", help="atualiza e confere, mas não faz commit nem push")
    args = parser.parse_args()

    ARQUIVO_LOG.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout = sys.stderr = Log(ARQUIVO_LOG, sys.__stdout__)
    print(f"\n===== {datetime.now():%Y-%m-%d %H:%M} =====")
    try:
        publicar(enviar_ao_github=not args.sem_enviar)
    except Exception:
        print(traceback.format_exc())
        sys.exit(1)
