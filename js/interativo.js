// Página interativa: lê dados/lutadores.json (gerado por src/exportar.py) e monta os gráficos
// com Chart.js. O JSON traz TOTAIS por lutador; médias e percentuais são calculados aqui.

const CORES = {
  vermelho: "#e63946",
  azul: "#457b9d",
  texto: "#f5f5f5",
  suave: "#9a9a9a",
  grade: "#2a2a2a",
};

Chart.defaults.color = CORES.suave;
Chart.defaults.font.family = '-apple-system, "Segoe UI", Roboto, sans-serif';
Chart.defaults.animation.duration = 300;

// ---------- Formatação ----------

const fmt1 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const fmt0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

const formatos = {
  inteiro: (v) => fmt0.format(v),
  decimal: (v) => (Math.abs(v) < 1 ? fmt2.format(v) : fmt1.format(v)),
  pct: (v) => fmt0.format(v) + "%",
  minutos: (v) => fmt1.format(v) + " min",
};

// ---------- Métricas ----------
// valor(l): calcula a métrica a partir dos totais do lutador l.
// requisito(l): amostra mínima além do mínimo de lutas (ex.: precisão só com tentativas suficientes).

const lutasComResultado = (l) => l.w + l.l + l.d;

const METRICAS = {
  vitorias: { rotulo: "Vitórias (total)", valor: (l) => l.w, formato: "inteiro" },
  taxa_vitoria: {
    rotulo: "Taxa de vitória (%)", valor: (l) => (l.w / lutasComResultado(l)) * 100, formato: "pct",
    requisito: (l) => lutasComResultado(l) > 0,
  },
  ko: { rotulo: "Vitórias por nocaute (total)", valor: (l) => l.ko, formato: "inteiro" },
  subw: { rotulo: "Vitórias por finalização (total)", valor: (l) => l.subw, formato: "inteiro" },
  kd: { rotulo: "Knockdowns (total)", valor: (l) => l.kd, formato: "inteiro" },
  sig_luta: { rotulo: "Golpes significativos acertados por luta", valor: (l) => l.sl / l.n, formato: "decimal" },
  volume_min: {
    rotulo: "Golpes significativos tentados por minuto", valor: (l) => l.sa / (l.dur / 60), formato: "decimal",
    requisito: (l) => l.dur > 0,
  },
  precisao: {
    rotulo: "Precisão de golpes significativos (%)", valor: (l) => (l.sl / l.sa) * 100, formato: "pct",
    requisito: (l) => l.sa >= 50, nota: "Só lutadores com pelo menos 50 golpes significativos tentados.",
  },
  td_luta: { rotulo: "Quedas por luta", valor: (l) => l.tdl / l.n, formato: "decimal" },
  precisao_td: {
    rotulo: "Precisão de quedas (%)", valor: (l) => (l.tdl / l.tda) * 100, formato: "pct",
    requisito: (l) => l.tda >= 10, nota: "Só lutadores com pelo menos 10 quedas tentadas.",
  },
  ctrl_luta: { rotulo: "Tempo de controle por luta", valor: (l) => l.ctrl / l.n / 60, formato: "minutos" },
  sub_luta: { rotulo: "Tentativas de finalização por luta", valor: (l) => l.sub / l.n, formato: "decimal" },
  chao_pct: {
    rotulo: "Golpes acertados no chão (%)", valor: (l) => (l.ground / l.sl) * 100, formato: "pct",
    requisito: (l) => l.sl >= 100, nota: "Só lutadores com pelo menos 100 golpes significativos acertados.",
  },
};

// Painéis do comparador: médias por luta ou percentuais, cada um na sua escala.
const METRICAS_COMPARADOR = ["sig_luta", "precisao", "volume_min", "td_luta", "precisao_td", "ctrl_luta", "sub_luta", "kd_luta"];
METRICAS.kd_luta = { rotulo: "Knockdowns por luta", valor: (l) => l.kd / l.n, formato: "decimal" };

// Valor de uma métrica ou null se não der para calcular (ex.: nenhuma queda tentada).
function calcular(metrica, lutador) {
  const v = metrica.valor(lutador);
  return Number.isFinite(v) ? v : null;
}

// ---------- Plugin: valor escrito na ponta da barra (padrão visual do projeto) ----------

const valoresNaPonta = {
  id: "valoresNaPonta",
  afterDatasetsDraw(chart, _args, opcoes) {
    const { ctx } = chart;
    ctx.save();
    ctx.font = `${opcoes.tamanho || 12}px ${Chart.defaults.font.family}`;
    ctx.fillStyle = CORES.texto;
    ctx.textBaseline = "middle";
    chart.data.datasets.forEach((dataset, i) => {
      chart.getDatasetMeta(i).data.forEach((barra, j) => {
        const valor = dataset.data[j];
        if (valor === null || valor === undefined) return;
        ctx.fillText(opcoes.formatar(valor, j, i), barra.x + 6, barra.y);
      });
    });
    ctx.restore();
  },
};

// ---------- Estado ----------

let lutadores = [];
let porNome = new Map();
const graficos = { paineis: [], ranking: null, dispersao: null, rounds: null };

// ---------- Comparador ----------

function cartel(l) {
  return `${l.w}-${l.l}` + (l.d ? `-${l.d}` : "") + (l.nc ? ` (${l.nc} NC)` : "");
}

function preencherCartao(elemento, l) {
  if (!l) {
    elemento.innerHTML = '<div class="detalhe">Escolha um lutador</div>';
    return;
  }
  elemento.innerHTML = `
    <div class="nome"></div>
    <div class="cartel">${cartel(l)}</div>
    <div class="detalhe">${l.n} ${l.n === 1 ? "luta" : "lutas"} no período ·
      ${l.ko} por nocaute · ${l.subw} por finalização</div>`;
  elemento.querySelector(".nome").textContent = l.nome; // nome via textContent: nunca como HTML
}

function desenharComparador() {
  const nomeA = document.getElementById("lutador-a").value.trim();
  const nomeB = document.getElementById("lutador-b").value.trim();
  const a = porNome.get(nomeA.toLowerCase());
  const b = porNome.get(nomeB.toLowerCase());

  const faltando = [[nomeA, a], [nomeB, b]].filter(([nome, l]) => nome && !l).map(([nome]) => `"${nome}"`);
  document.getElementById("aviso-comparador").textContent =
    faltando.length ? `Não encontrei ${faltando.join(" nem ")} no período. Escolha um nome da lista.` : "";

  preencherCartao(document.getElementById("cartao-a"), a);
  preencherCartao(document.getElementById("cartao-b"), b);

  graficos.paineis.forEach((g) => g.destroy());
  graficos.paineis = [];
  const container = document.getElementById("paineis");
  container.innerHTML = "";

  // Round a round e dispersão mostram os lutadores do comparador, então acompanham cada mudança
  desenharRounds();
  desenharDispersao();

  const selecionados = [a, b].filter(Boolean);
  if (!selecionados.length) {
    atualizarUrl();
    return;
  }

  for (const chave of METRICAS_COMPARADOR) {
    const metrica = METRICAS[chave];
    const painel = document.createElement("div");
    painel.className = "painel";
    painel.innerHTML = `<h3>${metrica.rotulo}</h3><div class="area"><canvas role="img"></canvas></div>`;
    container.appendChild(painel);

    const valores = selecionados.map((l) => calcular(metrica, l));
    const canvas = painel.querySelector("canvas");
    canvas.setAttribute("aria-label",
      `${metrica.rotulo}: ` + selecionados.map((l, i) => `${l.nome} ${valores[i] === null ? "sem dados" : formatos[metrica.formato](valores[i])}`).join(", "));

    const maximo = Math.max(...valores.filter((v) => v !== null), 0);
    graficos.paineis.push(new Chart(canvas, {
      type: "bar",
      data: {
        labels: selecionados.map((l) => l.nome),
        datasets: [{
          data: valores,
          backgroundColor: selecionados.map((l) => (l === a ? CORES.azul : CORES.vermelho)),
          borderRadius: 4,
          barPercentage: 0.8,
          categoryPercentage: 0.9,
        }],
      },
      options: {
        indexAxis: "y",
        maintainAspectRatio: false,
        layout: { padding: { right: 70 } },
        scales: {
          x: { display: false, min: 0, max: maximo > 0 ? maximo * 1.05 : 1 },
          y: { grid: { display: false }, ticks: { color: CORES.texto } },
        },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => (c.raw === null ? "sem dados" : formatos[metrica.formato](c.raw)) } },
          valoresNaPonta: { formatar: (v) => formatos[metrica.formato](v) },
        },
      },
      plugins: [valoresNaPonta],
    }));
  }
  atualizarUrl();
}

// ---------- Ranking ----------

function desenharRanking() {
  const chave = document.getElementById("metrica").value;
  const metrica = METRICAS[chave];
  const campoMin = document.getElementById("min-lutas");
  const minLutas = Math.min(12, Math.max(1, parseInt(campoMin.value, 10) || 1));
  campoMin.value = minLutas; // corrige no campo o que foi digitado fora do intervalo
  const tamanho = parseInt(document.getElementById("tamanho").value, 10);

  const elegiveis = lutadores
    .filter((l) => l.n >= minLutas && (!metrica.requisito || metrica.requisito(l)))
    .map((l) => ({ l, v: calcular(metrica, l) }))
    .filter((x) => x.v !== null);

  // Desempate: mais lutas primeiro (amostra maior), depois nome
  elegiveis.sort((x, y) => y.v - x.v || y.l.n - x.l.n || x.l.nome.localeCompare(y.l.nome));
  const top = elegiveis.slice(0, tamanho);

  const nota = `${elegiveis.length} lutadores com pelo menos ${minLutas} ${minLutas === 1 ? "luta" : "lutas"} no período.`
    + (metrica.nota ? " " + metrica.nota : "");
  document.getElementById("nota-ranking").textContent = nota;

  document.getElementById("area-ranking").style.height = `${Math.max(top.length, 1) * 32 + 40}px`;
  const canvas = document.getElementById("canvas-ranking");
  canvas.setAttribute("aria-label", `Ranking: ${metrica.rotulo}. ` + top.map((x, i) => `${i + 1}º ${x.l.nome}, ${formatos[metrica.formato](x.v)}`).join("; "));

  if (graficos.ranking) graficos.ranking.destroy();
  const maximo = top.length ? top[0].v : 1;
  graficos.ranking = new Chart(canvas, {
    type: "bar",
    data: {
      labels: top.map((x) => x.l.nome),
      datasets: [{ data: top.map((x) => x.v), backgroundColor: CORES.vermelho, borderRadius: 4, barPercentage: 0.8 }],
    },
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      layout: { padding: { right: 110 } },
      scales: {
        x: { display: false, min: 0, max: maximo > 0 ? maximo * 1.02 : 1 },
        y: { grid: { display: false }, ticks: { color: CORES.texto, autoSkip: false } },
      },
      onHover: (evento, elementos) => { evento.native.target.style.cursor = elementos.length ? "pointer" : "default"; },
      onClick: (_evento, elementos) => {
        if (!elementos.length) return;
        document.getElementById("lutador-a").value = top[elementos[0].index].l.nome;
        desenharComparador();
        document.getElementById("comparador").scrollIntoView({ behavior: "smooth" });
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (c) => formatos[metrica.formato](c.raw),
            afterLabel: (c) => `Cartel ${cartel(top[c.dataIndex].l)} · ${top[c.dataIndex].l.n} lutas`,
          },
        },
        valoresNaPonta: {
          formatar: (v, j) => `${formatos[metrica.formato](v)}  (${top[j].l.n} lutas)`,
        },
      },
    },
    plugins: [valoresNaPonta],
  });

  desenharTabela(metrica, top);
  atualizarUrl();
}

function desenharTabela(metrica, top) {
  const tabela = document.getElementById("tabela-ranking");
  tabela.innerHTML = `<thead><tr><th class="num">#</th><th>Lutador</th><th class="num">${metrica.rotulo}</th>
    <th class="num">Lutas</th><th>Cartel</th></tr></thead>`;
  const corpo = document.createElement("tbody");
  top.forEach((x, i) => {
    const linha = document.createElement("tr");
    [[i + 1, "num"], [x.l.nome, ""], [formatos[metrica.formato](x.v), "num"], [x.l.n, "num"], [cartel(x.l), ""]]
      .forEach(([texto, classe]) => {
        const celula = document.createElement("td");
        celula.textContent = texto;
        if (classe) celula.className = classe;
        linha.appendChild(celula);
      });
    corpo.appendChild(linha);
  });
  tabela.appendChild(corpo);
}

// A sugestão do <datalist> filtra pelo texto do campo: com um nome já preenchido, a lista mostra só
// ele. Por isso, ao focar, o campo é esvaziado (o nome atual vira placeholder) e a lista completa
// aparece; ao sair sem escolher ninguém, o nome anterior volta.
function configurarCampoLutador(campo) {
  let anterior = "";

  campo.addEventListener("focus", () => {
    anterior = campo.value;
    campo.placeholder = anterior || "Digite um nome";
    campo.value = "";
  });

  campo.addEventListener("blur", () => {
    if (!campo.value.trim()) campo.value = anterior;
    campo.placeholder = "Digite um nome";
    desenharComparador();
  });

  // Atualiza assim que o texto bate com um nome (ao escolher da lista ou terminar de digitar),
  // sem esperar o usuário sair do campo
  campo.addEventListener("input", () => {
    if (porNome.has(campo.value.trim().toLowerCase())) {
      anterior = campo.value.trim();
      desenharComparador();
    }
  });

  campo.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter") campo.blur();
  });
}

// ---------- Round a round ----------
// Cada lutador traz "r": [[round, rounds disputados, sl, sa, tdl, tda, ctrl, kd], ...] (ordem
// definida em src/exportar.py). As métricas são médias por round disputado.

const ROUNDS = [1, 2, 3, 4, 5];

const METRICAS_ROUND = {
  sig: { rotulo: "Golpes significativos acertados por round", valor: (t) => t.sl / t.n, formato: "decimal" },
  precisao: { rotulo: "Precisão de golpes significativos (%)", valor: (t) => (t.sa ? (t.sl / t.sa) * 100 : null), formato: "pct" },
  quedas: { rotulo: "Quedas por round", valor: (t) => t.tdl / t.n, formato: "decimal" },
  controle: { rotulo: "Tempo de controle por round", valor: (t) => t.ctrl / t.n / 60, formato: "minutos" },
};

let mediaGeralRounds = new Map();

// {round: {n, sl, sa, tdl, tda, ctrl, kd}} a partir das listas compactas de um lutador
function roundsDe(l) {
  const mapa = new Map();
  for (const [round, n, sl, sa, tdl, tda, ctrl, kd] of l.r || []) mapa.set(round, { n, sl, sa, tdl, tda, ctrl, kd });
  return mapa;
}

function prepararRounds() {
  mediaGeralRounds = new Map();
  for (const l of lutadores) {
    for (const [round, t] of roundsDe(l)) {
      const soma = mediaGeralRounds.get(round) || { n: 0, sl: 0, sa: 0, tdl: 0, tda: 0, ctrl: 0, kd: 0 };
      for (const campo in soma) soma[campo] += t[campo];
      mediaGeralRounds.set(round, soma);
    }
  }
}

function desenharRounds() {
  const canvas = document.getElementById("canvas-rounds");
  if (!canvas || !mediaGeralRounds.size) return;
  const metrica = METRICAS_ROUND[document.getElementById("metrica-round").value];
  const formatar = formatos[metrica.formato];
  const formatarEixo = (v) => {
    if (v === 0) return "0";
    if (metrica.formato === "pct") return formatar(v);
    return fmt1.format(v) + (metrica.formato === "minutos" ? " min" : "");
  };

  const a = porNome.get(document.getElementById("lutador-a").value.trim().toLowerCase());
  const b = porNome.get(document.getElementById("lutador-b").value.trim().toLowerCase());

  // Cada ponto guarda também quantos rounds entram na média, para o tooltip
  const serie = (totais) => ROUNDS.map((round) => {
    const t = totais.get(round);
    const v = t ? metrica.valor(t) : null;
    return { y: Number.isFinite(v) ? v : null, n: t ? t.n : 0 };
  });

  const datasets = [];
  for (const [l, cor] of [[a, CORES.azul], [b, CORES.vermelho]]) {
    if (!l) continue;
    const pontos = serie(roundsDe(l));
    datasets.push({
      label: l.nome, data: pontos.map((p) => p.y), amostras: pontos.map((p) => p.n),
      borderColor: cor, backgroundColor: cor, borderWidth: 2.5, pointRadius: 5, pointHoverRadius: 7,
    });
  }
  const geral = serie(mediaGeralRounds);
  datasets.push({
    label: "Média de todos os lutadores", data: geral.map((p) => p.y), amostras: geral.map((p) => p.n),
    borderColor: CORES.suave, backgroundColor: CORES.suave, borderDash: [5, 4], borderWidth: 1.5, pointRadius: 3,
  });

  canvas.setAttribute("aria-label", `${metrica.rotulo}, do 1º ao 5º round. `
    + datasets.map((d) => `${d.label}: ` + d.data.map((v, i) => `${i + 1}º ${v === null ? "sem rounds" : formatar(v)}`).join(", ")).join(". "));

  if (graficos.rounds) graficos.rounds.destroy();
  graficos.rounds = new Chart(canvas, {
    type: "line",
    data: { labels: ROUNDS.map((r) => `${r}º round`), datasets },
    options: {
      maintainAspectRatio: false,
      spanGaps: false, // round não disputado fica em branco, sem ligar os vizinhos
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { grid: { display: false }, ticks: { color: CORES.texto } },
        // No eixo, casas decimais iguais em todos os rótulos (os valores dos pontos seguem `formatar`)
        y: { beginAtZero: true, grid: { color: CORES.grade }, ticks: { callback: (v) => formatarEixo(v) } },
      },
      plugins: {
        legend: { labels: { usePointStyle: true, boxWidth: 8, color: CORES.texto } },
        tooltip: {
          callbacks: {
            title: (itens) => `${itens[0].label} — ${metrica.rotulo.toLowerCase()}`,
            label: (c) => {
              const n = c.dataset.amostras[c.dataIndex];
              return `${c.dataset.label}: ${c.raw === null ? "sem rounds" : formatar(c.raw)} (${fmt0.format(n)} ${n === 1 ? "round" : "rounds"})`;
            },
          },
        },
      },
    },
  });
}

// ---------- Dispersão volume × precisão ----------
// Mesmo recorte do gráfico estático: lutadores com 4+ lutas; volume por minuto de luta.

const MIN_LUTAS_DISPERSAO = 4;
let baseDispersao = { pontos: [], medianaX: 0, medianaY: 0 };

function pontoDe(l) {
  if (!l || !l.sa || !l.dur) return null;
  return { x: l.sa / (l.dur / 60), y: (l.sl / l.sa) * 100, l };
}

function mediana(valores) {
  const v = [...valores].sort((p, q) => p - q);
  const meio = Math.floor(v.length / 2);
  return v.length % 2 ? v[meio] : (v[meio - 1] + v[meio]) / 2;
}

function prepararDispersao() {
  const pontos = lutadores.filter((l) => l.n >= MIN_LUTAS_DISPERSAO).map(pontoDe).filter(Boolean);
  baseDispersao = {
    pontos,
    medianaX: mediana(pontos.map((p) => p.x)),
    medianaY: mediana(pontos.map((p) => p.y)),
  };
}

// Linhas das medianas, nomes dos quadrantes e nomes dos lutadores destacados
const guiasDispersao = {
  id: "guiasDispersao",
  beforeDatasetsDraw(chart) {
    const { ctx, chartArea: area, scales: { x, y } } = chart;
    ctx.save();
    ctx.strokeStyle = "#555555";
    ctx.setLineDash([5, 4]);
    ctx.beginPath();
    ctx.moveTo(x.getPixelForValue(baseDispersao.medianaX), area.top);
    ctx.lineTo(x.getPixelForValue(baseDispersao.medianaX), area.bottom);
    ctx.moveTo(area.left, y.getPixelForValue(baseDispersao.medianaY));
    ctx.lineTo(area.right, y.getPixelForValue(baseDispersao.medianaY));
    ctx.stroke();

    ctx.setLineDash([]);
    ctx.fillStyle = CORES.suave;
    ctx.font = `11px ${Chart.defaults.font.family}`;
    const m = 6;
    ctx.textBaseline = "top";
    ctx.textAlign = "left";  ctx.fillText("Pouco volume, muita precisão", area.left + m, area.top + m);
    ctx.textAlign = "right"; ctx.fillText("Muito volume, muita precisão", area.right - m, area.top + m);
    ctx.textBaseline = "bottom";
    ctx.textAlign = "left";  ctx.fillText("Pouco volume, pouca precisão", area.left + m, area.bottom - m);
    ctx.textAlign = "right"; ctx.fillText("Muito volume, pouca precisão", area.right - m, area.bottom - m);
    ctx.restore();
  },
  afterDatasetsDraw(chart) {
    const { ctx, chartArea: area } = chart;
    ctx.save();
    ctx.font = `600 12px ${Chart.defaults.font.family}`;
    ctx.fillStyle = CORES.texto;
    ctx.textBaseline = "middle";
    chart.data.datasets.forEach((dataset, i) => {
      if (!dataset.destaque) return;
      chart.getDatasetMeta(i).data.forEach((ponto) => {
        // Nome à direita do ponto; à esquerda se não couber
        const largura = ctx.measureText(dataset.label).width;
        const cabe = ponto.x + 12 + largura < area.right;
        ctx.textAlign = cabe ? "left" : "right";
        ctx.fillText(dataset.label, ponto.x + (cabe ? 12 : -12), ponto.y);
      });
    });
    ctx.restore();
  },
};

function desenharDispersao() {
  const canvas = document.getElementById("canvas-dispersao");
  if (!canvas || !baseDispersao.pontos.length) return;

  const a = porNome.get(document.getElementById("lutador-a").value.trim().toLowerCase());
  const b = porNome.get(document.getElementById("lutador-b").value.trim().toLowerCase());
  const destacados = [[a, CORES.azul], [b, CORES.vermelho]].filter(([l]) => l && pontoDe(l));
  const nomesDestacados = new Set(destacados.map(([l]) => l.nome));

  const datasets = [{
    label: `Demais lutadores (${baseDispersao.pontos.length - nomesDestacados.size})`,
    data: baseDispersao.pontos.filter((p) => !nomesDestacados.has(p.l.nome)),
    backgroundColor: "rgba(154, 154, 154, 0.45)",
    pointRadius: 3.5,
    pointHoverRadius: 6,
    pointHitRadius: 6,
  }];
  for (const [l, cor] of destacados) {
    datasets.push({
      label: l.nome,
      destaque: true,
      data: [pontoDe(l)],
      backgroundColor: cor,
      borderColor: "#0d0d0d",
      borderWidth: 2,
      pointRadius: 7,
      pointHoverRadius: 9,
      pointHitRadius: 10,
    });
  }

  // Quem está destacado mas fica fora do recorte (menos de 4 lutas) ainda aparece, com aviso
  const poucasLutas = destacados.filter(([l]) => l.n < MIN_LUTAS_DISPERSAO).map(([l]) => `${l.nome} (${l.n} ${l.n === 1 ? "luta" : "lutas"})`);
  document.getElementById("nota-dispersao").textContent =
    `Linhas tracejadas = medianas (${fmt1.format(baseDispersao.medianaX)} golpes tentados por minuto, ${fmt0.format(baseDispersao.medianaY)}% de precisão).`
    + (poucasLutas.length ? ` Destacado com amostra pequena: ${poucasLutas.join(" e ")}.` : "");
  canvas.setAttribute("aria-label", `Dispersão de volume e precisão de ${baseDispersao.pontos.length} lutadores. `
    + destacados.map(([l]) => { const p = pontoDe(l); return `${l.nome}: ${fmt1.format(p.x)} golpes por minuto, ${fmt0.format(p.y)}% de precisão`; }).join("; "));

  if (graficos.dispersao) graficos.dispersao.destroy();
  graficos.dispersao = new Chart(canvas, {
    type: "scatter",
    data: { datasets },
    options: {
      maintainAspectRatio: false,
      layout: { padding: { right: 8 } },
      scales: {
        x: { title: { display: true, text: "Golpes significativos tentados por minuto" }, grid: { color: CORES.grade } },
        y: { title: { display: true, text: "Precisão (%)" }, grid: { color: CORES.grade } },
      },
      onHover: (evento, elementos) => { evento.native.target.style.cursor = elementos.length ? "pointer" : "default"; },
      onClick: (_evento, elementos) => {
        if (!elementos.length) return;
        const { datasetIndex, index } = elementos[0];
        const l = graficos.dispersao.data.datasets[datasetIndex].data[index].l;
        document.getElementById("lutador-a").value = l.nome;
        desenharComparador();
        document.getElementById("comparador").scrollIntoView({ behavior: "smooth" });
      },
      plugins: {
        legend: { labels: { usePointStyle: true, boxWidth: 8, color: CORES.texto } },
        tooltip: {
          callbacks: {
            label: (c) => {
              const { l, x, y } = c.raw;
              return `${l.nome}: ${fmt1.format(x)} golpes/min · ${fmt0.format(y)}% · ${l.n} ${l.n === 1 ? "luta" : "lutas"}`;
            },
          },
        },
      },
    },
    plugins: [guiasDispersao],
  });
}

// ---------- Link compartilhável ----------
// O estado da página fica na URL (?a=...&b=...&m=...&min=...&top=...): quem abre o link vê a mesma
// comparação e o mesmo ranking. Valores inválidos na URL são ignorados e ficam os padrões.

const PADROES = { a: "Islam Makhachev", b: "Merab Dvalishvili", m: "taxa_vitoria", min: 4, top: 10, rm: "sig" };
const TAMANHOS_TOP = [10, 15, 20];
let urlPronta = false; // só escreve na URL depois de aplicar o estado inicial

function lerEstadoDaUrl() {
  const p = new URLSearchParams(location.search);
  const nomeValido = (valor, padrao) => porNome.get((valor || "").trim().toLowerCase())?.nome || padrao;
  const inteiro = (valor, minimo, maximo, padrao) => {
    const n = parseInt(valor, 10);
    return Number.isInteger(n) && n >= minimo && n <= maximo ? n : padrao;
  };
  const m = p.get("m");
  const rm = p.get("rm");
  const top = parseInt(p.get("top"), 10);
  return {
    rm: rm in METRICAS_ROUND ? rm : PADROES.rm,
    a: nomeValido(p.get("a"), PADROES.a),
    b: nomeValido(p.get("b"), PADROES.b),
    m: m in METRICAS && m !== "kd_luta" ? m : PADROES.m,
    min: inteiro(p.get("min"), 1, 12, PADROES.min),
    top: TAMANHOS_TOP.includes(top) ? top : PADROES.top,
  };
}

function atualizarUrl() {
  if (!urlPronta) return;
  const nomeCanonico = (id) => porNome.get(document.getElementById(id).value.trim().toLowerCase())?.nome;
  const a = nomeCanonico("lutador-a");
  const b = nomeCanonico("lutador-b");

  const p = new URLSearchParams();
  if (a) p.set("a", a);
  if (b) p.set("b", b);
  p.set("m", document.getElementById("metrica").value);
  p.set("min", document.getElementById("min-lutas").value);
  p.set("top", document.getElementById("tamanho").value);
  p.set("rm", document.getElementById("metrica-round").value);
  // replaceState: atualiza o endereço sem criar uma entrada nova no histórico a cada mudança
  history.replaceState(null, "", `${location.pathname}?${p}${location.hash}`);

  document.title = a && b ? `${a} × ${b} — UFC Data` : "UFC Data — Explore os dados";
}

async function copiarLink(secao, aviso) {
  const url = new URL(location.href);
  url.hash = secao;
  try {
    await navigator.clipboard.writeText(url.href);
    aviso.textContent = "Link copiado!";
  } catch {
    // Sem permissão de área de transferência: mostra o link para copiar à mão
    aviso.textContent = url.href;
  }
  clearTimeout(aviso._timer);
  aviso._timer = setTimeout(() => { aviso.textContent = ""; }, 4000);
}

// ---------- Inicialização ----------

async function iniciar() {
  let dados;
  try {
    // no-cache: o navegador sempre confere com o servidor se o JSON mudou (resposta 304 rápida
    // quando não mudou). Sem isso, depois de regenerar o JSON, quem já visitou via o antigo.
    const resposta = await fetch("dados/lutadores.json", { cache: "no-cache" });
    if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
    dados = await resposta.json();
  } catch (erro) {
    document.getElementById("resumo-dados").textContent =
      "Não foi possível carregar os dados. Se abriu o arquivo direto do disco, rode um servidor local (python -m http.server).";
    console.error(erro);
    return;
  }

  lutadores = dados.lutadores;
  porNome = new Map(lutadores.map((l) => [l.nome.toLowerCase(), l]));
  // "2023-04-08" -> "abr/2023" (sem new Date(): evita mudar o dia por fuso horário)
  const mesAno = (iso) => {
    const [ano, mes] = iso.split("-");
    return `${["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"][mes - 1]}/${ano}`;
  };
  const periodo = dados.periodo ? ` (${mesAno(dados.periodo.inicio)} a ${mesAno(dados.periodo.fim)})` : "";
  document.getElementById("resumo-dados").textContent =
    `${fmt0.format(dados.lutas)} lutas de ${dados.eventos} eventos do UFC${periodo}, ${fmt0.format(lutadores.length)} lutadores. `
    + "Compare dois lutadores quaisquer ou monte o seu próprio ranking.";

  const lista = document.getElementById("lista-lutadores");
  [...lutadores].sort((x, y) => x.nome.localeCompare(y.nome)).forEach((l) => {
    const opcao = document.createElement("option");
    opcao.value = l.nome;
    lista.appendChild(opcao);
  });

  const seletor = document.getElementById("metrica");
  for (const [chave, metrica] of Object.entries(METRICAS)) {
    if (chave === "kd_luta") continue; // só no comparador
    const opcao = document.createElement("option");
    opcao.value = chave;
    opcao.textContent = metrica.rotulo;
    seletor.appendChild(opcao);
  }
  const seletorRound = document.getElementById("metrica-round");
  for (const [chave, metrica] of Object.entries(METRICAS_ROUND)) {
    const opcao = document.createElement("option");
    opcao.value = chave;
    opcao.textContent = metrica.rotulo;
    seletorRound.appendChild(opcao);
  }

  const estado = lerEstadoDaUrl();
  seletorRound.value = estado.rm;
  seletor.value = estado.m;
  document.getElementById("min-lutas").value = estado.min;
  document.getElementById("tamanho").value = estado.top;
  document.getElementById("lutador-a").value = estado.a;
  document.getElementById("lutador-b").value = estado.b;

  ["lutador-a", "lutador-b"].forEach((id) => configurarCampoLutador(document.getElementById(id)));
  ["metrica", "min-lutas", "tamanho"].forEach((id) => document.getElementById(id).addEventListener("change", desenharRanking));
  prepararDispersao();
  prepararRounds();
  seletorRound.addEventListener("change", () => { desenharRounds(); atualizarUrl(); });
  document.querySelectorAll("button.copiar").forEach((botao) => {
    botao.addEventListener("click", () => copiarLink(botao.dataset.secao, botao.nextElementSibling));
  });

  desenharComparador();
  desenharRanking();
  urlPronta = true;
  atualizarUrl();

  // Com o conteúdo desenhado, a âncora do link (#comparador ou #ranking) já cai no lugar certo
  if (location.hash) document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView();
}

iniciar();
