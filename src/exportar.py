"""Exporta os dados agregados por lutador em JSON, para a página interativa (interativo.html)."""

import json
from datetime import date
from pathlib import Path

import pandas as pd

from src.analises import montar_analises
from src.limpeza import adicionar_duracao
from src.rating import calcular_notas, posicoes_no_ranking

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_RESUMO = RAIZ / "data" / "processed" / "dataset_final_resumo_limpo.csv"
ARQUIVO_ROUND = RAIZ / "data" / "processed" / "dataset_final_round_limpo.csv"
ARQUIVO_EVENTOS = RAIZ / "data" / "processed" / "eventos.csv"
ARQUIVO_LUTADORES = RAIZ / "data" / "processed" / "lutadores.csv"
ARQUIVO_FOTOS = RAIZ / "data" / "raw" / "fotos.csv"  # gerado por `python -m src.fotos` (opcional)
ARQUIVO_SAIDA = RAIZ / "dados" / "lutadores.json"
PASTA_SAIDA = RAIZ / "dados"

# Filtro de período do site: um JSON por período (o site troca de arquivo ao mudar o filtro).
# Lutas antigas tinham outras regras (sem limite de tempo, rounds longos) e às vezes não têm
# estatísticas, então médias do histórico todo misturam eras diferentes.
# inicio = data mínima do evento ('AAAA-MM-DD'), None = sem corte; "anos" = relativo a hoje.
PERIODOS = {
    "tudo": {"rotulo": "Todo o histórico", "inicio": None},
    "moderno": {"rotulo": "Desde 2001 (regras unificadas)", "inicio": "2001-01-01"},
    "recente": {"rotulo": "Últimos 3 anos", "anos": 3},
}


def arquivo_do_periodo(chave, pasta=PASTA_SAIDA):
    """dados/lutadores.json para o histórico todo; dados/lutadores_<chave>.json para os demais."""
    return Path(pasta) / ("lutadores.json" if chave == "tudo" else f"lutadores_{chave}.json")


def inicio_do_periodo(periodo, hoje=None):
    """Data mínima ('AAAA-MM-DD') de um período de PERIODOS, ou None se não há corte."""
    if periodo.get("anos"):
        hoje = hoje or date.today()
        return hoje.replace(year=hoje.year - periodo["anos"]).isoformat()
    return periodo.get("inicio")

# Totais somados por lutador. Nomes curtos para o JSON ficar pequeno; o navegador calcula
# médias por luta e percentuais a partir deles.
SOMAS = {
    "kd": "KD",
    "sl": "Sig_str_landed", "sa": "Sig_str_attempted",
    "tl": "Total_str_landed", "ta": "Total_str_attempted",
    "tdl": "Td_landed", "tda": "Td_attempted",
    "sub": "Sub. att",
    "ctrl": "Ctrl_seconds",
    "head": "Head_landed", "body": "Body_landed", "leg": "Leg_landed",
    "dist": "Distance_landed", "clinch": "Clinch_landed", "ground": "Ground_landed",
    "dur": "Duracao_seg",
}


def agregar_lutadores(df):
    """Uma linha por lutador: cartel, vitórias por método e totais das estatísticas no período."""
    df = adicionar_duracao(df)

    vitoria = df["Resultado"] == "W"
    df["ko"] = (vitoria & df["Method"].str.contains("KO/TKO|TKO - Doctor", na=False)).astype(int)
    df["subw"] = (vitoria & df["Method"].str.contains("Submission", na=False)).astype(int)
    for resultado in ["W", "L", "D", "NC"]:
        df[resultado] = (df["Resultado"] == resultado).astype(int)

    # Lutas antigas sem estatísticas contam no cartel (n), mas não nas médias por luta/minuto:
    # ne = lutas com estatísticas, de = duração delas (s)
    com_estatisticas = df["Sig_str_landed"].notna()
    df["ne"] = com_estatisticas.astype(int)
    df["de"] = df["Duracao_seg"].where(com_estatisticas, 0)

    colunas = {"n": ("Fight_URL", "nunique"), "w": ("W", "sum"), "l": ("L", "sum"),
               "d": ("D", "sum"), "nc": ("NC", "sum"), "ko": ("ko", "sum"), "subw": ("subw", "sum"),
               "ne": ("ne", "sum"), "de": ("de", "sum")}
    colunas.update({curto: (original, "sum") for curto, original in SOMAS.items()})

    agregado = df.groupby("Fighter").agg(**colunas).reset_index()
    return agregado.rename(columns={"Fighter": "nome"})


# Ordem das colunas de cada round no JSON: [round, rounds disputados, sl, sa, tdl, tda, ctrl, kd].
# Lista em vez de objeto para o arquivo ficar pequeno; o JS lê com essa mesma ordem.
COLUNAS_ROUND = ["Sig_str_landed", "Sig_str_attempted", "Td_landed", "Td_attempted", "Ctrl_seconds", "KD"]


def agregar_rounds(df_round):
    """{lutador: [[round, rounds, sl, sa, tdl, tda, ctrl, kd], ...]} com os totais de cada round."""
    totais = df_round.groupby(["Fighter", "Round"]).agg(
        rounds=("Fight_URL", "size"), **{col: (col, "sum") for col in COLUNAS_ROUND}
    ).reset_index()
    por_lutador = {}
    for linha in totais.itertuples(index=False):
        valores = [int(linha.Round), int(linha.rounds)] + [int(getattr(linha, col)) for col in COLUNAS_ROUND]
        por_lutador.setdefault(linha.Fighter, []).append(valores)
    return por_lutador


def periodo_de_atividade(df, datas_eventos):
    """{lutador: [ano da 1ª luta, ano da última]} no UFC, pelas datas dos eventos.

    Calculado sobre a base inteira (não sobre o recorte do filtro de período do site): é a carreira
    no UFC, mostrada ao lado do nome nas tabelas (ex.: 2019–2022).
    """
    anos = df.merge(datas_eventos[["Event_URL", "Event_Date"]], on="Event_URL")
    anos = anos.assign(ano=anos["Event_Date"].str[:4].astype(int)).groupby("Fighter")["ano"].agg(["min", "max"])
    return {nome: [int(linha["min"]), int(linha["max"])] for nome, linha in anos.iterrows()}


def dados_fisicos(df, lutadores, datas_eventos):
    """{nome: {cat, alt, env, base, nasc, foto}} para os cartões e tabelas (campos ausentes ficam de fora).

    cat = categoria da luta mais recente, ignorando peso casado (não é divisão); só se o lutador
    nunca lutou fora dele fica "Catch Weight". alt/env em cm inteiros, nasc em 'AAAA-MM-DD'.
    foto = URL da foto (coluna Photo_URL de lutadores, se houver; ver src/fotos.py).
    """
    lutas = df.merge(datas_eventos[["Event_URL", "Event_Date"]], on="Event_URL")
    lutas["peso_casado"] = lutas["Weight_Class"] == "Catch Weight"
    # Mais recente primeiro, com as lutas de peso casado depois de todas as outras
    lutas = lutas.sort_values(["peso_casado", "Event_Date"], ascending=[True, False])
    base = lutas.drop_duplicates("Fighter")[["Fighter", "Weight_Class", "Fighter_URL"]]
    base = base.merge(lutadores, on="Fighter_URL", how="left")

    fisico = {}
    for linha in base.itertuples(index=False):
        campos = {"cat": linha.Weight_Class, "alt": linha.Height_cm, "env": linha.Reach_cm,
                  "base": linha.Stance, "nasc": linha.DOB, "foto": getattr(linha, "Photo_URL", None)}
        campos = {k: v for k, v in campos.items() if pd.notna(v)}
        for k in ("alt", "env"):
            if k in campos:
                campos[k] = int(round(campos[k]))
        fisico[linha.Fighter] = campos
    return fisico


# Faixas de diferença do gráfico idade_vs_envergadura.png: limite superior de cada faixa
# (anos de idade / polegadas de envergadura); None = sem limite (última faixa).
FAIXAS_VANTAGEM = {"idade": [2, 5, 8, None], "env": [1, 2, 3, None]}


def historico_vantagens(df, lutadores, datas_eventos):
    """Em lutas com vencedor, % de vitórias de quem era mais novo / tinha mais envergadura, por faixa,
    e de cada lado nos confrontos de bases diferentes.

    Mesma conta do gráfico idade_vs_envergadura.png (e da consulta SQL idade_envergadura).
    Devolve {"idade": [[limite, pct, lutas], ...], "env": [...], "bases": [[a, b, vitorias_a, lutas], ...]}
    para o comparador do site.
    """
    fisico = df.merge(lutadores, on="Fighter_URL").merge(datas_eventos[["Event_URL", "Event_Date"]], on="Event_URL")
    fisico["idade"] = (pd.to_datetime(fisico["Event_Date"]) - pd.to_datetime(fisico["DOB"])).dt.days / 365.25
    fisico["env"] = (fisico["Reach_cm"] / 2.54).round(1)
    vencedor = fisico[fisico["Resultado"] == "W"].set_index("Fight_URL")[["idade", "env"]]
    perdedor = fisico[fisico["Resultado"] == "L"].set_index("Fight_URL")[["idade", "env"]]
    duelos = vencedor.join(perdedor, lsuffix="_v", rsuffix="_p", how="inner")

    # Vantagem = mais novo (diferença de idade negativa) / mais envergadura (positiva)
    diferencas = {"idade": -(duelos["idade_v"] - duelos["idade_p"]), "env": (duelos["env_v"] - duelos["env_p"]).round(1)}
    historico = {}
    for chave, dif in diferencas.items():
        dif = dif[dif != 0]
        limites = FAIXAS_VANTAGEM[chave]
        faixas = pd.cut(dif.abs(), [0] + [l if l is not None else 999 for l in limites], labels=False)
        venceu = (dif > 0).groupby(faixas).agg(["mean", "size"]).reindex(range(len(limites)))
        # Faixa sem nenhuma luta (recortes pequenos): pct None, 0 lutas
        historico[chave] = [[limite, None if pd.isna(venceu.loc[i, "mean"]) else round(float(venceu.loc[i, "mean"]) * 100, 1),
                             0 if pd.isna(venceu.loc[i, "size"]) else int(venceu.loc[i, "size"])]
                            for i, limite in enumerate(limites)]

    # Confrontos de bases diferentes (gráfico base_canhoto_vs_ortodoxo.png / SQL confronto_bases):
    # [base_a, base_b, vitórias de base_a, lutas]
    base_v = df.merge(lutadores[["Fighter_URL", "Stance"]], on="Fighter_URL")
    bases = pd.concat([
        base_v[base_v["Resultado"] == "W"].set_index("Fight_URL")["Stance"].rename("v"),
        base_v[base_v["Resultado"] == "L"].set_index("Fight_URL")["Stance"].rename("p"),
    ], axis=1, join="inner").dropna()
    historico["bases"] = []
    for a, b in [("Southpaw", "Orthodox"), ("Switch", "Orthodox"), ("Switch", "Southpaw")]:
        no_confronto = ((bases["v"] == a) & (bases["p"] == b)) | ((bases["v"] == b) & (bases["p"] == a))
        historico["bases"].append([a, b, int((no_confronto & (bases["v"] == a)).sum()), int(no_confronto.sum())])
    return historico


def montar_json(df, df_round, datas_eventos, lutadores, periodo=None, carreira=None):
    """Conteúdo do JSON do site para um recorte já filtrado (resumo, por round e datas dos eventos).

    carreira = periodo_de_atividade da base inteira; sem ele, é calculado sobre o próprio recorte.
    """
    carreira = carreira if carreira is not None else periodo_de_atividade(df, datas_eventos)
    agregado = agregar_lutadores(df)
    rounds = agregar_rounds(df_round)
    datas = datas_eventos.loc[datas_eventos["Event_URL"].isin(df["Event_URL"]), "Event_Date"]
    fisico = dados_fisicos(df, lutadores, datas_eventos)
    return {
        "gerado_em": date.today().isoformat(),
        "filtro": periodo,
        "periodos": {chave: p["rotulo"] for chave, p in PERIODOS.items()},
        "periodo": {"inicio": datas.min(), "fim": datas.max()},
        "eventos": int(df["Event_URL"].nunique()),
        "lutas": int(df["Fight_URL"].nunique()),
        "vantagens": historico_vantagens(df, lutadores, datas_eventos),
        "lutadores": [
            {**{k: (int(v) if isinstance(v, (int, float)) and k != "nome" else v) for k, v in linha.items()},
             **fisico.get(linha["nome"], {}), "anos": carreira.get(linha["nome"]), "r": rounds.get(linha["nome"], [])}
            for linha in agregado.to_dict(orient="records")
        ],
    }


# Estatísticas de cada lado no histórico de lutas (perfil do lutador), nesta ordem:
# [nome, resultado, kd, golpes sig. acertados, tentados, quedas, quedas tentadas, controle (s)]
COLUNAS_LADO = ["KD", "Sig_str_landed", "Sig_str_attempted", "Td_landed", "Td_attempted", "Ctrl_seconds"]


def montar_lutas(df, datas_eventos, notas=None, estilos=None, posicoes=None):
    """Histórico de todas as lutas para a página de perfil (dados/lutas.json), da mais recente à mais antiga.

    {"eventos": [[nome, data, id], ...]  (id = código do evento no link do ufcstats, estável),
     "lutas": [[evento (índice em eventos), categoria, método, round, tempo, cinturão, luta da noite,
                performance da noite, lado_1, lado_2], ...]}
    lado = [nome, resultado W/L/D/NC, kd, sig acertados, sig tentados, quedas, quedas tentadas, controle_s,
            nota, [resultado, desempenho, adversário], posição no top 15 da categoria pelo Elo na véspera]
           (nota e partes de src/rating.py, se `notas` vier; posição de `posicoes_no_ranking`, se vier);
    estatísticas ausentes (lutas antigas) e lutas sem nota viram null. `estilos` ({nome: estilo}) vai
    junto como "estilos". O vencedor vem primeiro quando houver.
    Dentro de cada evento, as lutas seguem a ordem do card (luta principal primeiro), que é a ordem
    em que aparecem no CSV (o scraper lê a página do evento de cima para baixo).
    Listas em vez de objetos para o arquivo ficar pequeno; o JS lê nesta mesma ordem.
    """
    df = df.reset_index(drop=True)
    df["_pos"] = df.index.to_series().groupby(df["Fight_URL"]).transform("min")  # ordem no card
    df = df.merge(datas_eventos[["Event_URL", "Event_Date"]], on="Event_URL")
    eventos = (df[["Event_URL", "Event_Name", "Event_Date"]].drop_duplicates("Event_URL")
               .sort_values(["Event_Date", "Event_Name"], ascending=False).reset_index(drop=True))
    indice = {url: i for i, url in enumerate(eventos["Event_URL"])}
    ordem_resultado = {"W": 0, "D": 1, "NC": 1, "L": 2}
    df = df.assign(_ordem=df["Resultado"].map(ordem_resultado).fillna(1))
    df = df.sort_values(["Event_Date", "Event_Name", "_pos", "_ordem", "Fighter"], ascending=[False, False, True, True, True])

    def inteiro(v):
        return None if pd.isna(v) else int(v)

    nota_de = {}
    if notas is not None:
        for linha in notas.itertuples(index=False):
            nota_de[(linha.Fight_URL, linha.Fighter)] = [float(linha.Nota), [round(float(linha.resultado), 2),
                                                          round(float(linha.desempenho), 2), round(float(linha.adversario), 2)]]

    lutas = []
    for _, luta in df.groupby("Fight_URL", sort=False):
        primeira = luta.iloc[0]
        lados = [[l["Fighter"], l["Resultado"], *[inteiro(l[c]) for c in COLUNAS_LADO],
                  *nota_de.get((l["Fight_URL"], l["Fighter"]), [None, None]),
                  *([] if posicoes is None else [posicoes.get((l["Fight_URL"], l["Fighter"]))])] for _, l in luta.iterrows()]
        lutas.append([indice[primeira["Event_URL"]], primeira.get("Weight_Class") if pd.notna(primeira.get("Weight_Class")) else None,
                      primeira["Method"], inteiro(primeira["Final_Round"]), primeira["Time"],
                      inteiro(primeira.get("Title_Bout", 0)) or 0, inteiro(primeira.get("Fight_Bonus", 0)) or 0,
                      inteiro(primeira.get("Perf_Bonus", 0)) or 0, *lados])
    lutas.sort(key=lambda l: l[0])  # estável: mantém a ordem dentro do evento
    saida = {"gerado_em": date.today().isoformat(),
            "eventos": [[nome, data, url.rstrip("/").rsplit("/", 1)[-1]]
                        for url, nome, data in eventos[["Event_URL", "Event_Name", "Event_Date"]].values],
            "lutas": lutas}
    if estilos is not None:
        nomes = set(df["Fighter"])
        saida["estilos"] = {nome: estilo for nome, estilo in sorted(estilos.items()) if nome in nomes}
    return saida


def filtrar_periodo(df, df_round, datas_eventos, inicio):
    """Só as lutas de eventos a partir de `inicio` (None = tudo), no resumo e no por round."""
    if inicio is None:
        return df, df_round
    eventos = set(datas_eventos.loc[datas_eventos["Event_Date"] >= inicio, "Event_URL"])
    df = df[df["Event_URL"].isin(eventos)]
    return df, df_round[df_round["Fight_URL"].isin(set(df["Fight_URL"]))]


def juntar_fotos(lutadores, caminho_fotos=None):
    """Acrescenta Photo_URL (de data/raw/fotos.csv, se existir) ao cadastro de lutadores."""
    caminho_fotos = Path(caminho_fotos or ARQUIVO_FOTOS)
    if not caminho_fotos.exists():
        return lutadores
    fotos = pd.read_csv(caminho_fotos)[["Fighter_URL", "Photo_URL"]].drop_duplicates("Fighter_URL")
    return lutadores.merge(fotos, on="Fighter_URL", how="left")


def exportar_lutadores(caminho_csv=ARQUIVO_RESUMO, caminho_round=ARQUIVO_ROUND, pasta_saida=PASTA_SAIDA):
    """Lê os datasets limpos e grava um JSON por período de PERIODOS (o do histórico todo é lutadores.json)."""
    df = pd.read_csv(caminho_csv, low_memory=False)
    df_round = pd.read_csv(caminho_round, low_memory=False)
    datas_eventos = pd.read_csv(ARQUIVO_EVENTOS)
    lutadores = juntar_fotos(pd.read_csv(ARQUIVO_LUTADORES))
    carreira = periodo_de_atividade(df, datas_eventos)  # base inteira, igual em todos os períodos

    notas, info = calcular_notas(df, datas_eventos)  # nota de cada lutador em cada luta (src/rating.py)
    Path(pasta_saida).mkdir(parents=True, exist_ok=True)
    saidas, analises = {}, {}
    for chave, periodo in PERIODOS.items():
        recorte, recorte_round = filtrar_periodo(df, df_round, datas_eventos, inicio_do_periodo(periodo))
        saida = montar_json(recorte, recorte_round, datas_eventos, lutadores, chave, carreira)
        with open(arquivo_do_periodo(chave, pasta_saida), "w", encoding="utf-8") as f:
            json.dump(saida, f, ensure_ascii=False, separators=(",", ":"))
        saidas[chave] = saida
        analises[chave] = {**montar_analises(recorte, recorte_round, notas, datas_eventos), "periodo": saida["periodo"]}
    with open(Path(pasta_saida) / "analises.json", "w", encoding="utf-8") as f:
        json.dump({"gerado_em": date.today().isoformat(), "periodos": {c: p["rotulo"] for c, p in PERIODOS.items()},
                   **analises}, f, ensure_ascii=False, separators=(",", ":"))
    with open(Path(pasta_saida) / "lutas.json", "w", encoding="utf-8") as f:
        json.dump(montar_lutas(df, datas_eventos, notas, info["estilos"], posicoes_no_ranking(df, datas_eventos)), f, ensure_ascii=False, separators=(",", ":"))
    return saidas


if __name__ == "__main__":
    for chave, resultado in exportar_lutadores().items():
        print(f"{PERIODOS[chave]['rotulo']}: {len(resultado['lutadores'])} lutadores, {resultado['lutas']} lutas, "
              f"{resultado['eventos']} eventos -> {arquivo_do_periodo(chave)}")
