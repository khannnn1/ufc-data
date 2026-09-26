"""Configuração visual (dark mode) e funções auxiliares de plotagem do projeto."""

import matplotlib.pyplot as plt
import pandas as pd

COR_VERMELHO = "#e63946"
COR_AZUL = "#457b9d"
COR_AMARELO = "#c08a1e"  # terceira cor categórica, para gráficos com 3 grupos


def aplicar_estilo_dark():
    """Configura o estilo visual global (dark mode/editorial) usado em todos os gráficos do projeto."""
    plt.rcParams["figure.facecolor"] = "#0d0d0d"
    plt.rcParams["axes.facecolor"] = "#0d0d0d"
    plt.rcParams["axes.edgecolor"] = "#444444"
    plt.rcParams["axes.labelcolor"] = "#f5f5f5"
    plt.rcParams["text.color"] = "#f5f5f5"
    plt.rcParams["xtick.color"] = "#f5f5f5"
    plt.rcParams["ytick.color"] = "#f5f5f5"
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.size"] = 11
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["axes.spines.left"] = False
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.color"] = "#2a2a2a"
    plt.rcParams["grid.linewidth"] = 0.5
    plt.rcParams["axes.axisbelow"] = True


def estilizar_grafico(ax, titulo, mostrar_eixo_x=False):
    """Aplica título e remove o eixo numérico (padrão editorial) de um gráfico de barras horizontais."""
    ax.set_title(titulo, fontsize=13, fontweight="bold")
    ax.set_xlabel("")
    if not mostrar_eixo_x:
        ax.set_xticks([])


def adicionar_valores_barras(ax, barras, cor_texto="#f5f5f5"):
    """Escreve o valor numérico na ponta de cada barra horizontal."""
    for barra in barras:
        largura = barra.get_width()
        ax.text(largura + (largura * 0.02), barra.get_y() + barra.get_height() / 2,
                 f"{largura:.0f}" if largura == int(largura) else f"{largura:.1f}",
                 va="center", fontsize=10, color=cor_texto)

def top_com_desempate(valores, lutas, n=10):
    """Top n de um total por lutador (Series indexada pelo nome), com desempate estável.

    Empate no valor: fica na frente quem precisou de menos lutas para chegar nele; persistindo,
    ordem alfabética. Sem isso, quem entra no corte entre empatados muda a cada atualização da base.
    """
    tabela = pd.DataFrame({"valor": valores, "lutas": lutas.reindex(valores.index)})
    tabela["nome"] = tabela.index
    tabela = tabela.sort_values(["valor", "lutas", "nome"], ascending=[False, True, True]).head(n)
    return tabela["valor"].rename(valores.name)
