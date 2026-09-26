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
const graficos = { paineis: [], ranking: null };

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

  const selecionados = [a, b].filter(Boolean);
  if (!selecionados.length) return;

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
}

// ---------- Ranking ----------

function desenharRanking() {
  const chave = document.getElementById("metrica").value;
  const metrica = METRICAS[chave];
  const minLutas = Math.max(1, parseInt(document.getElementById("min-lutas").value, 10) || 1);
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

// ---------- Inicialização ----------

async function iniciar() {
  let dados;
  try {
    const resposta = await fetch("dados/lutadores.json");
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
  document.getElementById("resumo-dados").textContent =
    `${fmt0.format(dados.lutas)} lutas de ${dados.eventos} eventos do UFC, ${fmt0.format(lutadores.length)} lutadores. `
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
  seletor.value = "taxa_vitoria";

  document.getElementById("lutador-a").value = "Islam Makhachev";
  document.getElementById("lutador-b").value = "Merab Dvalishvili";

  // "change" dispara ao escolher da lista ou sair do campo; evita redesenhar a cada tecla
  ["lutador-a", "lutador-b"].forEach((id) => document.getElementById(id).addEventListener("change", desenharComparador));
  ["metrica", "min-lutas", "tamanho"].forEach((id) => document.getElementById(id).addEventListener("change", desenharRanking));

  desenharComparador();
  desenharRanking();
}

iniciar();
