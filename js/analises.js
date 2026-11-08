// Página inicial (index.html): números-chave e análises do histórico em gráficos interativos, com
// filtro de período. Lê dados/analises.json, gerado por src/analises.py via `python -m src.exportar`
// (um bloco por período, mesmas chaves de PERIODOS em src/exportar.py e em js/interativo.js).

const CORES = { vermelho: "#e63946", azul: "#457b9d", amarelo: "#c08a1e", cinza: "#555555", texto: "#f5f5f5", suave: "#9a9a9a", grade: "#2a2a2a" };
Chart.defaults.color = CORES.suave;
Chart.defaults.font.family = '-apple-system, "Segoe UI", Roboto, sans-serif';
Chart.defaults.animation.duration = 300;

const PERIODO_PADRAO = "tudo";
// Rótulos curtos nos botões (cabem numa linha no celular); o rótulo longo vai no title
const ROTULOS_CURTOS = { tudo: "Todo o histórico", moderno: "Desde 2001", recente: "Últimos 3 anos" };
const fmtInt = new Intl.NumberFormat("pt-BR");
const fmt1 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const pct = (v) => (v === null || v === undefined ? "—" : `${fmt1.format(v)}%`);
const pct0 = (v) => `${Math.round(v)}%`;
const vezes = (a, b) => (b ? `${fmt1.format(a / b)}×` : "—");

function el(tag, classe, conteudo) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (typeof conteudo === "string") e.textContent = conteudo;
  else if (conteudo) e.append(...[].concat(conteudo));
  return e;
}
// Texto com trechos em negrito: frase("A ", ["54%"], " dos nocautes")
function frase(...partes) {
  const p = el("p", "destaque");
  for (const parte of partes) p.append(Array.isArray(parte) ? el("strong", "", parte[0]) : parte);
  return p;
}

// ---------- Plugins do Chart.js ----------

// Valor escrito na ponta da barra (mesmo padrão dos PNGs); em barras empilhadas, só o total na última
const valoresNaPonta = {
  id: "valoresNaPonta",
  afterDatasetsDraw(chart, _args, opcoes) {
    if (!opcoes.formatar) return;
    const { ctx } = chart;
    const horizontal = chart.options.indexAxis === "y";
    const empilhado = chart.options.scales?.x?.stacked;
    ctx.save();
    ctx.font = `12px ${Chart.defaults.font.family}`;
    ctx.fillStyle = CORES.texto;
    ctx.textBaseline = horizontal ? "middle" : "bottom";
    ctx.textAlign = horizontal ? "left" : "center";
    chart.data.datasets.forEach((dataset, i) => {
      if (empilhado && i !== chart.data.datasets.length - 1) return;
      if (!chart.isDatasetVisible(i)) return;
      chart.getDatasetMeta(i).data.forEach((barra, j) => {
        const valor = empilhado ? chart.data.datasets.reduce((s, d, k) => s + (chart.isDatasetVisible(k) ? d.data[j] || 0 : 0), 0) : dataset.data[j];
        if (valor === null || valor === undefined) return;
        if (horizontal) ctx.fillText(opcoes.formatar(valor, j), barra.x + 6, barra.y);
        else ctx.fillText(opcoes.formatar(valor, j), barra.x, barra.y - 4);
      });
    });
    ctx.restore();
  },
};

// Linha tracejada de referência (média geral) no eixo dos valores
const linhaReferencia = {
  id: "linhaReferencia",
  afterDatasetsDraw(chart, _args, opcoes) {
    if (opcoes.valor === undefined || opcoes.valor === null) return;
    const { ctx, chartArea } = chart;
    const x = chart.scales.x.getPixelForValue(opcoes.valor);
    ctx.save();
    ctx.strokeStyle = CORES.texto;
    ctx.globalAlpha = 0.6;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(x, chartArea.top);
    ctx.lineTo(x, chartArea.bottom);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 0.9;
    ctx.fillStyle = CORES.suave;
    ctx.font = `11px ${Chart.defaults.font.family}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(opcoes.rotulo, x, chartArea.top - 2);
    ctx.restore();
  },
};

// Os cartões são montados fora da página; os gráficos só são criados depois que entram nela
// (um Chart.js criado num canvas solto fica com tamanho 0 e não desenha)
const graficos = [];
const pendentes = [];
function novoGrafico(canvas, config) {
  pendentes.push(() => graficos.push(new Chart(canvas, config)));
}

// Eixos discretos: sem eixo numérico nas barras (valor já está na ponta), grade sutil
const eixoOculto = { display: false, grid: { display: false } };
const eixoCategorias = { grid: { display: false }, border: { display: false }, ticks: { color: CORES.texto } };

function cartao(titulo, { larga = false } = {}) {
  const c = el("section", `cartao-p analise${larga ? " larga" : ""}`);
  c.appendChild(el("h2", "", titulo));
  return c;
}
function areaDoGrafico(altura) {
  const area = el("div", "area");
  area.style.minHeight = `${altura}px`;
  const canvas = el("canvas");
  area.appendChild(canvas);
  return { area, canvas };
}
function legenda(itens) {
  const l = el("div", "legenda");
  for (const [rotulo, cor] of itens) {
    const s = el("span");
    s.append(el("i", `cor-${cor}`), rotulo);
    l.appendChild(s);
  }
  return l;
}
// Tabela com os mesmos números do gráfico (acessibilidade e conferência)
function tabela(cabecalho, linhas) {
  const d = el("details", "tabela");
  d.appendChild(el("summary", "", "Ver tabela"));
  const t = el("table");
  const thead = el("thead");
  thead.appendChild(el("tr", "", cabecalho.map((c) => el("th", "", c))));
  const tbody = el("tbody");
  for (const linha of linhas) tbody.appendChild(el("tr", "", linha.map((c) => el("td", "", String(c)))));
  t.append(thead, tbody);
  d.appendChild(t);
  return d;
}
function tooltipPct(contexto) {
  return `${contexto.dataset.label ? `${contexto.dataset.label}: ` : ""}${pct(contexto.parsed[contexto.chart.options.indexAxis === "y" ? "x" : "y"])}`;
}

// ---------- Análises ----------

// Métodos agrupados como no perfil: nocaute (com interrupção médica), finalização, decisões, outros
const GRUPOS_METODO = [
  { rotulo: "Nocaute", cor: "azul", metodos: ["KO/TKO", "TKO - Doctor's Stoppage"] },
  { rotulo: "Finalização", cor: "vermelho", metodos: ["Submission"] },
  { rotulo: "Decisão unânime", cor: "amarelo", metodos: ["Decision - Unanimous"] },
  { rotulo: "Decisão dividida", cor: "amarelo", metodos: ["Decision - Split", "Decision - Majority"] },
  { rotulo: "Outros", cor: "cinza", metodos: null, nota: "desclassificação, resultado anulado, não pôde continuar" },
];

function analiseMetodos(d) {
  const total = d.metodos.reduce((s, [, n]) => s + n, 0);
  const conhecidos = new Set(GRUPOS_METODO.flatMap((g) => g.metodos || []));
  const grupos = GRUPOS_METODO.map((g) => {
    const n = d.metodos.filter(([m]) => (g.metodos ? g.metodos.includes(m) : !conhecidos.has(m))).reduce((s, [, x]) => s + x, 0);
    return { ...g, n, pct: (n / total) * 100 };
  });
  const c = cartao("Como as lutas terminam");
  c.appendChild(frase([pct0(d.numeros.pct_antes_decisao)], " das lutas acabam antes da decisão: ", [pct0(grupos[0].pct)],
    " por nocaute e ", [pct0(grupos[1].pct)], " por finalização."));
  const { area, canvas } = areaDoGrafico(230);
  c.append(area, el("p", "nota", `Uma linha por luta, ${fmtInt.format(total)} lutas. Nocaute inclui a interrupção médica; decisão dividida inclui a majoritária; outros: ${GRUPOS_METODO[4].nota}.`),
    tabela(["Método", "Lutas", "%"], grupos.map((g) => [g.rotulo, fmtInt.format(g.n), pct(g.pct)])));
  novoGrafico(canvas, {
    type: "bar",
    data: { labels: grupos.map((g) => g.rotulo), datasets: [{ data: grupos.map((g) => g.pct), backgroundColor: grupos.map((g) => CORES[g.cor]), borderRadius: 4, barPercentage: 0.7 }] },
    options: {
      indexAxis: "y", maintainAspectRatio: false, layout: { padding: { right: 48 } },
      scales: { x: { ...eixoOculto, max: Math.max(...grupos.map((g) => g.pct)) }, y: eixoCategorias },
      plugins: { legend: { display: false }, valoresNaPonta: { formatar: (v) => pct(v) },
        tooltip: { callbacks: { label: (x) => `${pct(x.parsed.x)} · ${fmtInt.format(grupos[x.dataIndex].n)} lutas` } } },
    },
    plugins: [valoresNaPonta],
  });
  return c;
}

function analiseRoundFinal(d) {
  const r = d.round_final;
  const c = cartao("Em que round as lutas terminam");
  c.appendChild(frase("O 1º round concentra ", [pct0(r.ko[0])], " dos nocautes e ", [pct0(r.sub[0])],
    " das finalizações; cada round seguinte encerra cerca de metade do anterior."));
  c.appendChild(legenda([["Nocaute", "azul"], ["Finalização", "vermelho"]]));
  const { area, canvas } = areaDoGrafico(230);
  const rotulos = r.rounds.map((x) => `${x}º`.replace("4-5º", "4º e 5º"));
  c.append(area, el("p", "nota", `Percentual dentro de cada método: ${fmtInt.format(r.n_ko)} nocautes e ${fmtInt.format(r.n_sub)} finalizações.`),
    tabela(["Round", "Nocautes", "Finalizações"], rotulos.map((x, i) => [x, pct(r.ko[i]), pct(r.sub[i])])));
  novoGrafico(canvas, {
    type: "bar",
    data: { labels: rotulos, datasets: [
      { label: "Nocaute", data: r.ko, backgroundColor: CORES.azul, borderRadius: 4, barPercentage: 0.8, categoryPercentage: 0.7 },
      { label: "Finalização", data: r.sub, backgroundColor: CORES.vermelho, borderRadius: 4, barPercentage: 0.8, categoryPercentage: 0.7 },
    ] },
    options: {
      maintainAspectRatio: false, layout: { padding: { top: 18 } },
      scales: { y: { ...eixoOculto, beginAtZero: true }, x: eixoCategorias },
      plugins: { legend: { display: false }, valoresNaPonta: { formatar: pct0 }, tooltip: { callbacks: { label: tooltipPct } } },
    },
    plugins: [valoresNaPonta],
  });
  return c;
}

function analiseCategorias(d) {
  const cats = d.categorias;
  const c = cartao("Lutas encerradas antes da decisão, por categoria", { larga: true });
  if (!cats.length) {
    c.appendChild(el("p", "destaque", "Nenhuma categoria com lutas suficientes neste período."));
    return c;
  }
  const [primeira, ultima] = [cats[0], cats.at(-1)];
  const nome = (cat) => CATEGORIAS[cat] || cat;
  c.appendChild(frase("O ", [nome(primeira[0]).toLowerCase()], " lidera com ", [pct0(primeira[2] + primeira[3])],
    ` das lutas encerradas antes da decisão (${pct0(primeira[2])} por nocaute); o `, [nome(ultima[0]).toLowerCase()], " fecha a lista com ",
    [pct0(ultima[2] + ultima[3])], ". Nas categorias leves e femininas, a finalização pesa quase tanto quanto o nocaute."));
  c.appendChild(legenda([["Nocaute", "azul"], ["Finalização", "vermelho"]]));
  const { area, canvas } = areaDoGrafico(cats.length * 30 + 20);
  c.append(area, el("p", "nota", "Uma linha por luta. Fora o peso casado, o peso aberto dos primeiros torneios e categorias com menos de 20 lutas no período. Linha tracejada: média de todas as lutas."),
    tabela(["Categoria", "Lutas", "Nocaute", "Finalização", "Total"], cats.map(([cat, n, ko, sub]) => [nome(cat), fmtInt.format(n), pct(ko), pct(sub), pct(ko + sub)])));
  novoGrafico(canvas, {
    type: "bar",
    data: { labels: cats.map(([cat]) => nome(cat)), datasets: [
      { label: "Nocaute", data: cats.map((x) => x[2]), backgroundColor: CORES.azul, borderRadius: { topLeft: 4, bottomLeft: 4 }, borderSkipped: false, barPercentage: 0.7 },
      { label: "Finalização", data: cats.map((x) => x[3]), backgroundColor: CORES.vermelho, borderRadius: { topRight: 4, bottomRight: 4 }, borderSkipped: false, barPercentage: 0.7 },
    ] },
    options: {
      indexAxis: "y", maintainAspectRatio: false, layout: { padding: { right: 48, top: 14 } },
      scales: { x: { ...eixoOculto, stacked: true, max: Math.max(...cats.map((x) => x[2] + x[3])) }, y: { ...eixoCategorias, stacked: true } },
      plugins: { legend: { display: false }, valoresNaPonta: { formatar: pct0 },
        linhaReferencia: { valor: d.numeros.pct_antes_decisao, rotulo: `média ${pct0(d.numeros.pct_antes_decisao)}` },
        tooltip: { callbacks: { label: tooltipPct, footer: (itens) => `${fmtInt.format(cats[itens[0].dataIndex][1])} lutas` } } },
    },
    plugins: [valoresNaPonta, linhaReferencia],
  });
  return c;
}

// Pares de barras HTML (escalas diferentes por métrica, sem eixo comum)
function pares(linhas, [rotuloA, corA], [rotuloB, corB]) {
  const caixa = el("div", "pares");
  for (const { rotulo, a, b, formatar, razao } of linhas) {
    const par = el("div", "par");
    const cab = el("div", "cabecalho", [el("span", "", rotulo), el("span", "razao", razao ?? (a !== null && b ? vezes(a, b) : ""))]);
    par.appendChild(cab);
    const maximo = Math.max(a || 0, b || 0) || 1;
    for (const [valor, cor, nome] of [[a, corA, rotuloA], [b, corB, rotuloB]]) {
      const trilho = el("div", "trilho");
      const preenchido = el("span", `cor-${cor}`);
      preenchido.style.width = `${((valor || 0) / maximo) * 100}%`;
      trilho.appendChild(preenchido);
      const linha = el("div", "barra", [trilho, el("span", "valor", valor === null ? "—" : formatar(valor))]);
      linha.title = `${nome}: ${valor === null ? "sem dados" : formatar(valor)}`;
      par.appendChild(linha);
    }
    caixa.appendChild(par);
  }
  return caixa;
}

const METRICAS_VP = {
  golpes: { rotulo: "Golpes significativos acertados", formatar: (v) => fmt1.format(v) },
  quedas: { rotulo: "Quedas", formatar: (v) => fmt1.format(v) },
  controle: { rotulo: "Tempo de controle", formatar: (v) => `${fmt1.format(v)} min` },
  finalizacoes: { rotulo: "Tentativas de finalização", formatar: (v) => fmt1.format(v) },
  kd: { rotulo: "Knockdowns", formatar: (v) => new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(v) },
};

function analiseVencedores(d) {
  const linhas = d.vencedores_perdedores.map(([m, w, l]) => ({ ...METRICAS_VP[m], chave: m, a: w, b: l }));
  const c = cartao("O que separa vencedores de perdedores");
  // maior e menor razão vencedor/perdedor, calculadas no período escolhido
  const comRazao = linhas.filter((x) => x.b).sort((x, y) => y.a / y.b - x.a / x.b);
  if (comRazao.length > 1) {
    const [maior, menor] = [comRazao[0], comRazao.at(-1)];
    c.appendChild(frase(`A maior diferença está em ${maior.rotulo.toLowerCase()} (`, [vezes(maior.a, maior.b)], `); a menor, em ${menor.rotulo.toLowerCase()} (`,
      [vezes(menor.a, menor.b)], ")."));
  }
  c.append(legenda([["Vencedores", "vermelho"], ["Perdedores", "azul"]]), pares(linhas, ["Vencedores", "vermelho"], ["Perdedores", "azul"]),
    el("p", "nota", "Médias por lutador em cada luta, só lutas com vencedor e com estatísticas. É associação, não causa: um knockdown muitas vezes já é o começo do fim."));
  return c;
}

function analiseCinturao(d) {
  const { n, linhas } = d.cinturao;
  const valores = Object.fromEntries(linhas.map(([m, t, o]) => [m, [t, o]]));
  const c = cartao("Disputas de cinturão × demais lutas");
  if (!n) {
    c.appendChild(el("p", "destaque", "Nenhuma disputa de cinturão neste período."));
    return c;
  }
  const [ln, lnO] = valores.luta_noite;
  c.appendChild(frase("As ", [fmtInt.format(n)], " disputas duram mais (", [`${fmt1.format(valores.duracao[0])} min`], " contra ",
    `${fmt1.format(valores.duracao[1])})${valores.golpes_min[0] > valores.golpes_min[1] * 1.05 ? " e têm ritmo maior" : ", mas o ritmo por minuto não sobe"}. Nos bônus, Luta da Noite em `, [pct0(ln)],
    " delas, contra ", pct0(lnO), " das demais."));
  const rotulos = {
    duracao: ["Duração média", (v) => `${fmt1.format(v)} min`],
    golpes_min: ["Golpes sig. por minuto, por lutador", (v) => fmt1.format(v)],
    luta_noite: ["Levam Luta da Noite", pct],
    performance: ["Levam Performance da Noite", pct],
  };
  c.append(legenda([["Disputa de cinturão", "amarelo"], ["Demais lutas", "azul"]]),
    pares(linhas.map(([m, t, o]) => ({ rotulo: rotulos[m][0], formatar: rotulos[m][1], a: t, b: o })), ["Disputa de cinturão", "amarelo"], ["Demais lutas", "azul"]),
    el("p", "nota", "Uma linha por luta. Disputas são marcadas para 5 rounds e costumam fechar o card, a luta mais vista."));
  return c;
}

const PARTES = {
  alvo: { titulo: "Onde os golpes acertam", rotulos: ["Cabeça", "Corpo", "Perna"] },
  origem: { titulo: "De onde saem os golpes", rotulos: ["Distância", "Clinch", "Chão"] },
};
const CORES_PARTES = ["vermelho", "azul", "amarelo"];

function analiseDistribuicao(d, chave) {
  const { titulo, rotulos } = PARTES[chave];
  const dist = d[chave];
  const c = cartao(titulo);
  if (chave === "alvo") {
    c.appendChild(frase([pct0(dist.todos[0])], " dos golpes significativos acertam a cabeça; vencedores miram ainda mais nela (",
      pct0(dist.W[0]), " contra ", pct0(dist.L[0]), " dos perdedores)."));
  } else {
    c.appendChild(frase([pct0(dist.todos[0])], " dos golpes saem à distância. A diferença está no chão: vencedores acertam ",
      [pct0(dist.W[2])], " dos golpes por lá, perdedores só ", [pct0(dist.L[2])], "."));
  }
  c.appendChild(legenda(rotulos.map((r, i) => [r, CORES_PARTES[i]])));
  const caixa = el("div", "empilhadas");
  for (const [grupo, nome] of [["todos", "Todos"], ["W", "Vencedores"], ["L", "Perdedores"]]) {
    const faixa = el("div", "faixa");
    dist[grupo].forEach((v, i) => {
      const s = el("span", `cor-${CORES_PARTES[i]}`, v >= 9 ? pct0(v) : "");
      s.style.flex = `${v} 1 0`;
      s.title = `${nome}, ${rotulos[i].toLowerCase()}: ${pct(v)}`;
      faixa.appendChild(s);
    });
    caixa.appendChild(el("div", "linha", [el("span", "", nome), faixa]));
  }
  c.append(caixa, el("p", "nota", "Percentual dos golpes significativos acertados, somando todas as lutas com estatísticas."),
    tabela(["Grupo", ...rotulos], [["Todos", "todos"], ["Vencedores", "W"], ["Perdedores", "L"]].map(([n, g]) => [n, ...dist[g].map(pct)])));
  return c;
}

function analiseRounds(d) {
  const rounds = d.rounds;
  const c = cartao("Golpes significativos por round");
  const [primeiro, ultimo] = [rounds[0], rounds.at(-1)];
  c.appendChild(frase("A média sobe de ", [fmt1.format(primeiro[1])], " golpes por lutador no 1º round para ", [fmt1.format(ultimo[1])],
    ` no ${ultimo[0]}º. Em parte é viés de sobrevivência: só chegam lá as lutas que não acabaram cedo.`));
  const { area, canvas } = areaDoGrafico(220);
  c.append(area, el("p", "nota", "Média de golpes significativos acertados por lutador em cada round. 4º e 5º rounds só existem em lutas de 5 rounds (amostra menor)."),
    tabela(["Round", "Média", "Rounds na amostra"], rounds.map(([r, m, n]) => [`${r}º`, fmt1.format(m), fmtInt.format(n)])));
  novoGrafico(canvas, {
    type: "line",
    data: { labels: rounds.map(([r]) => `${r}º round`), datasets: [{ data: rounds.map(([, m]) => m), borderColor: CORES.vermelho, backgroundColor: CORES.vermelho, borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, tension: 0.2 }] },
    options: {
      maintainAspectRatio: false, layout: { padding: { top: 20, right: 12 } },
      interaction: { mode: "index", intersect: false },
      scales: { y: { ...eixoOculto, grace: "10%" }, x: { ...eixoCategorias, ticks: { color: CORES.suave } } },
      plugins: { legend: { display: false }, valoresNaPonta: { formatar: (v) => fmt1.format(v) },
        tooltip: { callbacks: { label: (x) => `${fmt1.format(x.parsed.y)} golpes por lutador`, footer: (i) => `${fmtInt.format(rounds[i[0].dataIndex][2])} rounds na amostra` } } },
    },
    plugins: [valoresNaPonta],
  });
  return c;
}

function analiseArbitros(d) {
  const arb = d.arbitros;
  const c = cartao("Lutas encerradas antes da decisão, por árbitro");
  const taxas = arb.map((a) => a[2]);
  c.appendChild(frase(`Entre os ${arb.length} árbitros com mais lutas, a taxa vai de `, [pct0(Math.min(...taxas))], " a ", [pct0(Math.max(...taxas))],
    `, em torno da média de ${pct0(d.numeros.pct_antes_decisao)}. O árbitro não decide como a luta termina: a diferença reflete as lutas que cada um recebe.`));
  const { area, canvas } = areaDoGrafico(arb.length * 30 + 20);
  c.append(area, tabela(["Árbitro", "Lutas", "Antes da decisão"], arb.map(([n, l, p]) => [n, fmtInt.format(l), pct(p)])));
  novoGrafico(canvas, {
    type: "bar",
    data: { labels: arb.map(([n, l]) => `${n} (${fmtInt.format(l)})`), datasets: [{ data: taxas, backgroundColor: CORES.azul, borderRadius: 4, barPercentage: 0.7 }] },
    options: {
      indexAxis: "y", maintainAspectRatio: false, layout: { padding: { right: 48, top: 14 } },
      scales: { x: { ...eixoOculto, min: 0, max: Math.max(...taxas) }, y: eixoCategorias },
      plugins: { legend: { display: false }, valoresNaPonta: { formatar: pct0 },
        linhaReferencia: { valor: d.numeros.pct_antes_decisao, rotulo: `média ${pct0(d.numeros.pct_antes_decisao)}` },
        tooltip: { callbacks: { label: (x) => `${pct(x.parsed.x)} antes da decisão`, footer: (i) => `${fmtInt.format(arb[i[0].dataIndex][1])} lutas apitadas` } } },
    },
    plugins: [valoresNaPonta, linhaReferencia],
  });
  return c;
}

// ---------- Nota por luta (src/rating.py) ----------

const ESTILOS_PLURAL = { Striker: "Strikers", Wrestler: "Wrestlers", Finalizador: "Finalizadores", Completo: "Completos" };
const fmt2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function analiseMelhores(d, periodo) {
  const { melhores } = d.notas;
  const c = cartao("Melhores atuações");
  c.appendChild(frase("As maiores notas do período, de 0 a 10 (base 6,6). Clique na nota para ver de onde ela veio."));
  const lista = el("ol", "atuacoes-lista");
  for (const [nome, nota, partes, adv, evento, data, idEvento, metodo, round, res, estilo] of melhores) {
    const link = el("a", "", evento);
    link.href = linkEventoUrl(idEvento);
    const detalhe = el("span", "sub", [`${RESULTADOS_LONGOS[res] || res} contra ${adv} · ${METODOS[metodo] || metodo}${round ? ` no ${round}º round` : ""} · `, link, ` · ${fmtData(data)}`]);
    const texto = el("div", "texto", [linkNome(nome), detalhe]);
    lista.appendChild(el("li", "", [seloNota(nota, partes, { nome, estilo }), texto]));
  }
  const mais = el("a", "", "Ver as 20 melhores, com filtro por categoria e estilo");
  const params = new URLSearchParams();
  if (periodo !== PERIODO_PADRAO) params.set("p", periodo);
  mais.href = `interativo.html${params.size ? `?${params}` : ""}#atuacoes`;
  c.append(lista, el("p", "nota", [mais]));
  return c;
}

function analiseEstilos(d) {
  const { estilos, media } = d.notas;
  const c = cartao("Nota média por estilo");
  const maior = estilos.reduce((a, b) => (b[3] > a[3] ? b : a));
  const vitorias = estilos.map((e) => e[4]);
  c.appendChild(frase([ESTILOS_PLURAL[maior[0]] || maior[0]], " têm a maior nota média (", [fmt2.format(maior[3])], ") e vencem ", [pct0(maior[4])],
    " das lutas. A nota acompanha o resultado: os pesos do estilo são ajustados para nenhum deles sair na frente só pelo jeito de lutar."));
  const { area, canvas } = areaDoGrafico(estilos.length * 40 + 20);
  c.append(area, el("p", "nota", `Barras: % de vitórias de cada estilo; entre parênteses, a nota média (média geral ${fmt2.format(media)}). O estilo vem dos números da carreira; quem tem menos de 3 lutas entra como completo.`),
    tabela(["Estilo", "Atuações", "Lutadores", "Nota média", "Vitórias"], estilos.map(([e, n, l, m, v]) => [e, fmtInt.format(n), fmtInt.format(l), fmt2.format(m), pct(v)])));
  novoGrafico(canvas, {
    type: "bar",
    data: { labels: estilos.map(([e, , , m]) => `${e} (${fmt2.format(m)})`), datasets: [{ data: vitorias, backgroundColor: CORES.azul, borderRadius: 4, barPercentage: 0.7 }] },
    options: {
      indexAxis: "y", maintainAspectRatio: false, layout: { padding: { right: 48, top: 14 } },
      scales: { x: { ...eixoOculto, min: 0, max: Math.max(...vitorias) }, y: eixoCategorias },
      plugins: { legend: { display: false }, valoresNaPonta: { formatar: pct0 }, linhaReferencia: { valor: 50, rotulo: "50%" },
        tooltip: { callbacks: { label: (x) => `${pct(x.parsed.x)} de vitórias`, footer: (i) => `${fmtInt.format(estilos[i[0].dataIndex][1])} atuações, ${fmtInt.format(estilos[i[0].dataIndex][2])} lutadores` } } },
    },
    plugins: [valoresNaPonta, linhaReferencia],
  });
  return c;
}

// ---------- Números-chave e atalhos ----------

function desenharNumeros(d) {
  const caixa = document.getElementById("numeros");
  caixa.innerHTML = "";
  const n = d.numeros;
  for (const [valor, rotulo] of [[fmtInt.format(n.eventos), "eventos"], [fmtInt.format(n.lutas), "lutas"],
    [fmtInt.format(n.lutadores), "lutadores"], [pct0(n.pct_antes_decisao), "das lutas acabam antes da decisão"]]) {
    caixa.appendChild(el("div", "numero", [el("div", "valor", valor), el("div", "rotulo", rotulo)]));
  }
}

const ATALHOS = [
  ["nota_media", "Nota média", "nota de 0 a 10 por luta"],
  ["vitorias", "Vitórias", "total no período"],
  ["taxa_vitoria", "Taxa de vitória", "com mínimo de lutas"],
  ["ko", "Nocautes", "vitórias por KO/TKO"],
  ["subw", "Finalizações", "vitórias por finalização"],
  ["kd", "Knockdowns", "total no período"],
  ["precisao", "Precisão de golpes", "mín. 50 tentativas"],
  ["precisao_td", "Precisão de quedas", "mín. 10 tentativas"],
  ["ctrl_luta", "Controle por luta", "minutos por luta"],
];

function desenharAtalhos(periodo) {
  const caixa = document.getElementById("atalhos");
  caixa.innerHTML = "";
  for (const [m, titulo, sub] of ATALHOS) {
    const a = el("a", "", [el("strong", "", titulo), el("span", "", sub)]);
    const params = new URLSearchParams({ m });
    if (periodo !== PERIODO_PADRAO) params.set("p", periodo);
    a.href = `interativo.html?${params}#ranking`;
    caixa.appendChild(a);
  }
}

// ---------- Período ----------

let dados = null;

function aplicarPeriodo(periodo) {
  const d = dados[periodo];
  document.querySelectorAll("#periodos button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.periodo === periodo)));
  document.getElementById("datas-periodo").textContent = d.periodo ? `${fmtData(d.periodo.inicio)} a ${fmtData(d.periodo.fim)}` : "";
  desenharNumeros(d);
  graficos.splice(0).forEach((g) => g.destroy());
  const caixa = document.getElementById("analises");
  caixa.innerHTML = "";
  caixa.append(analiseMetodos(d), analiseRoundFinal(d), analiseCategorias(d), analiseVencedores(d), analiseCinturao(d),
    analiseDistribuicao(d, "alvo"), analiseDistribuicao(d, "origem"), analiseRounds(d), analiseArbitros(d));
  if (d.notas?.melhores.length) caixa.append(analiseMelhores(d, periodo), analiseEstilos(d));
  pendentes.splice(0).forEach((criar) => criar());
  desenharAtalhos(periodo);

  const url = new URL(window.location.href);
  if (periodo === PERIODO_PADRAO) url.searchParams.delete("p"); else url.searchParams.set("p", periodo);
  history.replaceState(null, "", url);
}

async function iniciar() {
  try {
    dados = await carregarAnalises();
  } catch (erro) {
    document.getElementById("analises").innerHTML = '<p class="erro">Não foi possível carregar os dados. Se abriu o arquivo direto do disco, rode um servidor local (python -m http.server).</p>';
    console.error(erro);
    return;
  }
  const botoes = document.getElementById("periodos");
  for (const [chave, rotulo] of Object.entries(dados.periodos)) {
    const b = el("button", "", ROTULOS_CURTOS[chave] || rotulo);
    b.title = rotulo;
    b.type = "button";
    b.dataset.periodo = chave;
    b.addEventListener("click", () => aplicarPeriodo(chave));
    botoes.appendChild(b);
  }
  const p = new URLSearchParams(window.location.search).get("p");
  aplicarPeriodo(p in dados.periodos ? p : PERIODO_PADRAO);
}

iniciar();
