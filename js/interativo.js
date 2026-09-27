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
// total: soma no período (não média nem taxa); muda o desempate do ranking.

const lutasComResultado = (l) => l.w + l.l + l.d;

const METRICAS = {
  vitorias: { rotulo: "Vitórias (total)", valor: (l) => l.w, formato: "inteiro", total: true },
  taxa_vitoria: {
    rotulo: "Taxa de vitória (%)", valor: (l) => (l.w / lutasComResultado(l)) * 100, formato: "pct",
    requisito: (l) => lutasComResultado(l) > 0,
  },
  ko: { rotulo: "Vitórias por nocaute (total)", valor: (l) => l.ko, formato: "inteiro", total: true },
  subw: { rotulo: "Vitórias por finalização (total)", valor: (l) => l.subw, formato: "inteiro", total: true },
  kd: { rotulo: "Knockdowns (total)", valor: (l) => l.kd, formato: "inteiro", total: true },
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
let vantagens = null; // % histórico de vitórias de quem é mais novo / tem mais envergadura, por faixa (JSON)
const graficos = { paineis: [], ranking: null, dispersao: null, rounds: null };

// ---------- Comparador ----------

function cartel(l) {
  return `${l.w}-${l.l}` + (l.d ? `-${l.d}` : "") + (l.nc ? ` (${l.nc} NC)` : "");
}

const CATEGORIAS = {
  "Heavyweight": "Peso-pesado", "Light Heavyweight": "Meio-pesado", "Middleweight": "Peso-médio",
  "Welterweight": "Meio-médio", "Lightweight": "Peso-leve", "Featherweight": "Peso-pena",
  "Bantamweight": "Peso-galo", "Flyweight": "Peso-mosca", "Catch Weight": "Peso casado",
  "Women's Featherweight": "Peso-pena feminino", "Women's Bantamweight": "Peso-galo feminino",
  "Women's Flyweight": "Peso-mosca feminino", "Women's Strawweight": "Peso-palha feminino",
};
// Filtro do ranking: divisões do mais pesado ao mais leve, masculinas e depois femininas (sem peso casado)
const CATEGORIAS_RANKING = Object.keys(CATEGORIAS).filter((c) => c !== "Catch Weight");
const BASES = { Orthodox: "ortodoxo", Southpaw: "canhoto", Switch: "troca de base" };
// Filtros do ranking por base e por faixa de idade (idade de hoje, como nos cartões)
const BASES_RANKING = { Orthodox: "Ortodoxo", Southpaw: "Canhoto", Switch: "Troca de base" };
const FAIXAS_IDADE = {
  ate25: { rotulo: "Até 25 anos", min: 0, max: 25 },
  "26a30": { rotulo: "26 a 30 anos", min: 26, max: 30 },
  "31a35": { rotulo: "31 a 35 anos", min: 31, max: 35 },
  "36mais": { rotulo: "36 anos ou mais", min: 36, max: 200 },
};

function idade(nasc) {
  const n = new Date(nasc + "T00:00:00");
  const hoje = new Date();
  const fezAniversario = hoje.getMonth() > n.getMonth() ||
    (hoje.getMonth() === n.getMonth() && hoje.getDate() >= n.getDate());
  return hoje.getFullYear() - n.getFullYear() - (fezAniversario ? 0 : 1);
}

function metros(cm) {
  return (cm / 100).toFixed(2).replace(".", ",") + " m";
}

// Categoria da luta mais recente, idade, altura, envergadura e base (o que houver no JSON)
function linhaFisico(l) {
  const partes = [];
  if (l.nasc) partes.push(`${idade(l.nasc)} anos`);
  if (l.alt) partes.push(metros(l.alt));
  if (l.env) partes.push(`envergadura ${metros(l.env)}`);
  if (l.base) partes.push(BASES[l.base] || l.base.toLowerCase());
  return partes.join(" · ");
}

function preencherCartao(elemento, l) {
  if (!l) {
    elemento.innerHTML = '<div class="detalhe">Escolha um lutador</div>';
    return;
  }
  elemento.innerHTML = `
    <div class="nome"></div>
    <div class="categoria"></div>
    <div class="cartel">${cartel(l)}</div>
    <div class="detalhe">${l.n} ${l.n === 1 ? "luta" : "lutas"} no período ·
      ${l.ko} por nocaute · ${l.subw} por finalização</div>
    <div class="detalhe fisico"></div>`;
  elemento.querySelector(".nome").textContent = l.nome; // nome via textContent: nunca como HTML
  elemento.querySelector(".categoria").textContent = l.cat ? (CATEGORIAS[l.cat] || l.cat) : "";
  elemento.querySelector(".fisico").textContent = linhaFisico(l);
}

// "No papel": diferença de idade e de envergadura entre os dois, com a taxa histórica de vitória de
// quem tem essa vantagem na mesma faixa de diferença (as faixas do gráfico idade_vs_envergadura.png).
function faixaDe(tabela, diferenca) {
  return tabela.find(([limite]) => limite === null || diferenca <= limite);
}

function textoFaixa(limite, anterior, unidade) {
  if (limite === null) return `mais de ${anterior} ${unidade}`;
  return anterior === 0 ? `até ${limite} ${unidade}` : `${anterior} a ${limite} ${unidade}`;
}

function linhasNoPapel(a, b) {
  const linhas = [];
  if (!vantagens) return linhas;

  if (a.nasc && b.nasc) {
    // Diferença de idade = diferença entre as datas de nascimento
    const anos = (new Date(b.nasc) - new Date(a.nasc)) / (365.25 * 24 * 3600 * 1000);
    if (Math.abs(anos) < 0.5) {
      linhas.push({ texto: "Os dois têm praticamente a mesma idade." });
    } else {
      const novo = anos > 0 ? b : a;
      const tabela = vantagens.idade;
      const i = tabela.indexOf(faixaDe(tabela, Math.abs(anos)));
      const [limite, pct, n] = tabela[i];
      const faixa = textoFaixa(limite, i ? tabela[i - 1][0] : 0, "anos");
      const inteiro = Math.round(Math.abs(anos));
      linhas.push({
        nome: novo.nome,
        texto: ` tem ${inteiro} ${inteiro === 1 ? "ano" : "anos"} a menos. Com ${faixa} de diferença, quem é mais novo venceu ${fmt0.format(pct)}% das lutas do período (${fmt0.format(n)} lutas).`,
      });
    }
  }

  if (a.env && b.env) {
    const polegadas = Math.round((a.env - b.env) / 2.54 * 10) / 10;
    if (Math.abs(polegadas) < 0.5) {
      linhas.push({ texto: "Os dois têm a mesma envergadura." });
    } else {
      const maior = polegadas > 0 ? a : b;
      const tabela = vantagens.env;
      const i = tabela.indexOf(faixaDe(tabela, Math.abs(polegadas)));
      const [limite, pct, n] = tabela[i];
      const anterior = i ? tabela[i - 1][0] : 0;
      const faixa = limite === null ? `mais de ${anterior}"` : anterior ? `${anterior}" a ${limite}"` : `até ${limite}"`;
      linhas.push({
        nome: maior.nome,
        texto: ` tem ${Math.abs(a.env - b.env)} cm (${fmt0.format(Math.round(Math.abs(polegadas)))}") a mais de envergadura. Com ${faixa} de diferença, quem alcança mais venceu ${fmt0.format(pct)}% (${fmt0.format(n)} lutas).`,
      });
    }
  }
  if (a.base && b.base && vantagens.bases) {
    if (a.base === b.base) {
      linhas.push({ texto: `Os dois lutam na mesma base (${BASES[a.base] || a.base.toLowerCase()}).` });
    } else {
      const confronto = vantagens.bases.find(([x, y]) => (x === a.base && y === b.base) || (x === b.base && y === a.base));
      if (confronto) {
        // Conta sempre pelo lado do 1º lutador do comparador
        const [x, , vitoriasX, n] = confronto;
        const vitorias = x === a.base ? vitoriasX : n - vitoriasX;
        const [inf, sup] = intervaloWilson(vitorias, n);
        const acaso = inf <= 0.5 && sup >= 0.5 ? " Diferença dentro da margem do acaso (intervalo de 95%)." : "";
        const baseA = BASES[a.base] || a.base.toLowerCase();
        const baseB = BASES[b.base] || b.base.toLowerCase();
        linhas.push({
          nome: a.nome,
          texto: ` (${baseA}) contra ${baseB}: nesse confronto, o lado ${a.base === "Switch" ? "que troca de base" : baseA} venceu ${fmt0.format(vitorias / n * 100)}% das lutas do período (${fmt0.format(n)} lutas).${acaso}`,
        });
      }
    }
  }
  return linhas;
}

// Intervalo de confiança de 95% (Wilson) para uma proporção, como no gráfico de bases
function intervaloWilson(acertos, n, z = 1.96) {
  const p = acertos / n;
  const centro = (p + z * z / (2 * n)) / (1 + z * z / n);
  const margem = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n);
  return [centro - margem, centro + margem];
}

function desenharNoPapel(a, b) {
  const caixa = document.getElementById("no-papel");
  caixa.innerHTML = "";
  const linhas = a && b && a !== b ? linhasNoPapel(a, b) : [];
  caixa.hidden = !linhas.length;
  if (!linhas.length) return;

  const titulo = document.createElement("h3");
  titulo.textContent = "No papel";
  caixa.appendChild(titulo);
  for (const linha of linhas) {
    const p = document.createElement("p");
    if (linha.nome) {
      const nome = document.createElement("strong");
      nome.textContent = linha.nome; // via textContent: nunca como HTML
      nome.className = linha.nome === a.nome ? "lado-a" : "lado-b";
      p.appendChild(nome);
    }
    p.appendChild(document.createTextNode(linha.texto));
    caixa.appendChild(p);
  }
  const nota = document.createElement("p");
  nota.className = "rodape";
  nota.textContent = "Taxas históricas de todas as lutas com vencedor no período, não uma previsão: idade pesa bem mais que envergadura e base.";
  caixa.appendChild(nota);
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
  desenharNoPapel(a, b);

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
  const categoria = document.getElementById("categoria").value;
  const base = document.getElementById("base").value;
  const faixa = FAIXAS_IDADE[document.getElementById("idade").value];
  const naFaixa = (l) => {
    if (!faixa) return true;
    if (!l.nasc) return false;
    const anos = idade(l.nasc);
    return anos >= faixa.min && anos <= faixa.max;
  };

  const elegiveis = lutadores
    .filter((l) => l.n >= minLutas && (!categoria || l.cat === categoria) && (!base || l.base === base) && naFaixa(l))
    .filter((l) => !metrica.requisito || metrica.requisito(l))
    .map((l) => ({ l, v: calcular(metrica, l) }))
    .filter((x) => x.v !== null);

  // Desempate, depois do valor: em totais, quem chegou nele com MENOS lutas (como nos PNGs do index);
  // em médias e taxas, quem tem MAIS lutas (amostra maior). Por último, o nome.
  const sinal = metrica.total ? 1 : -1;
  elegiveis.sort((x, y) => y.v - x.v || sinal * (x.l.n - y.l.n) || x.l.nome.localeCompare(y.l.nome));
  const top = elegiveis.slice(0, tamanho);

  const doPeso = categoria ? ` do ${CATEGORIAS[categoria].toLowerCase()}` : "";
  const daBase = base ? ` ${{ Orthodox: "ortodoxos", Southpaw: "canhotos", Switch: "que trocam de base" }[base]}` : "";
  const daIdade = faixa ? ` (${faixa.rotulo.toLowerCase()} hoje)` : "";
  const nota = `${elegiveis.length} lutadores${daBase}${doPeso}${daIdade} com pelo menos ${minLutas} ${minLutas === 1 ? "luta" : "lutas"} no período.`
    + (categoria ? " Categoria = a da luta mais recente de cada um; quem mudou de divisão entra com todas as lutas." : "")
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

// Lista de sugestões própria (o <datalist> nativo abre com todos os 964 nomes e não aceita limite
// de altura). Ao focar, o campo é esvaziado (o nome atual vira placeholder) e a lista aparece com
// rolagem; digitar filtra sem diferenciar acentos e maiúsculas. Ao sair sem escolher, o nome volta.
let nomesOrdenados = [];

const normalizar = (texto) => texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function filtrarNomes(texto) {
  const termo = normalizar(texto.trim());
  if (!termo) return nomesOrdenados.map((n) => n.nome);
  // Prioridade: nome que começa com o termo, depois alguma palavra que começa com ele, depois contém
  const grupos = [[], [], []];
  for (const { nome, chave } of nomesOrdenados) {
    if (chave.startsWith(termo)) grupos[0].push(nome);
    else if (chave.includes(" " + termo)) grupos[1].push(nome);
    else if (chave.includes(termo)) grupos[2].push(nome);
  }
  return grupos.flat();
}

function configurarCampoLutador(campo) {
  const lista = document.getElementById(campo.getAttribute("aria-controls"));
  let anterior = "";
  let itens = [];
  let ativo = -1;

  const fechar = () => {
    lista.hidden = true;
    campo.setAttribute("aria-expanded", "false");
    campo.removeAttribute("aria-activedescendant");
    ativo = -1;
  };

  const marcar = (indice) => {
    const opcoes = lista.querySelectorAll('[role="option"]');
    if (!opcoes.length) return;
    ativo = (indice + opcoes.length) % opcoes.length;
    opcoes.forEach((opcao, i) => opcao.classList.toggle("ativo", i === ativo));
    campo.setAttribute("aria-activedescendant", opcoes[ativo].id);
    opcoes[ativo].scrollIntoView({ block: "nearest" });
  };

  const mostrar = () => {
    itens = filtrarNomes(campo.value);
    ativo = -1;
    campo.removeAttribute("aria-activedescendant");
    lista.innerHTML = "";
    if (!itens.length) {
      const vazio = document.createElement("li");
      vazio.className = "vazio";
      vazio.textContent = "Nenhum lutador com esse nome no período";
      lista.appendChild(vazio);
    }
    itens.forEach((nome, i) => {
      const opcao = document.createElement("li");
      opcao.id = `${lista.id}-${i}`;
      opcao.setAttribute("role", "option");
      opcao.textContent = nome; // via textContent: nunca como HTML
      lista.appendChild(opcao);
    });
    lista.scrollTop = 0;
    lista.hidden = false;
    campo.setAttribute("aria-expanded", "true");
  };

  const escolher = (nome) => {
    campo.value = nome;
    anterior = nome;
    campo.blur(); // o blur fecha a lista e redesenha
  };

  // mousedown com preventDefault: clicar num nome ou na barra de rolagem não tira o foco do campo
  lista.addEventListener("mousedown", (evento) => evento.preventDefault());
  lista.addEventListener("click", (evento) => {
    const opcao = evento.target.closest('[role="option"]');
    if (opcao) escolher(opcao.textContent);
  });

  campo.addEventListener("focus", () => {
    anterior = campo.value;
    campo.placeholder = anterior || "Digite um nome";
    campo.value = "";
    mostrar();
  });

  campo.addEventListener("blur", () => {
    fechar();
    if (!campo.value.trim()) campo.value = anterior;
    campo.placeholder = "Digite um nome";
    desenharComparador();
  });

  campo.addEventListener("input", () => {
    mostrar();
    // Atualiza assim que o texto bate com um nome, sem esperar o usuário sair do campo
    if (porNome.has(campo.value.trim().toLowerCase())) {
      anterior = campo.value.trim();
      desenharComparador();
    }
  });

  campo.addEventListener("keydown", (evento) => {
    if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
      evento.preventDefault();
      if (lista.hidden) mostrar();
      marcar(ativo + (evento.key === "ArrowDown" ? 1 : -1));
    } else if (evento.key === "Enter") {
      evento.preventDefault();
      if (ativo >= 0) escolher(itens[ativo]);
      else if (itens.length === 1) escolher(itens[0]);
      else campo.blur();
    } else if (evento.key === "Escape") {
      campo.value = "";
      campo.blur(); // volta o nome anterior
    }
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
// O estado da página fica na URL (?a=...&b=...&m=...&min=...&top=...&cat=...&base=...&idade=...): quem abre o link vê a mesma
// comparação e o mesmo ranking. Valores inválidos na URL são ignorados e ficam os padrões.

const PADROES = { a: "Islam Makhachev", b: "Merab Dvalishvili", m: "taxa_vitoria", min: 4, top: 10, rm: "sig", cat: "", base: "", idade: "" };
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
    cat: CATEGORIAS_RANKING.includes(p.get("cat")) ? p.get("cat") : PADROES.cat,
    base: p.get("base") in BASES_RANKING ? p.get("base") : PADROES.base,
    idade: p.get("idade") in FAIXAS_IDADE ? p.get("idade") : PADROES.idade,
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
  const cat = document.getElementById("categoria").value;
  if (cat) p.set("cat", cat);
  // base e idade, como a categoria, só entram na URL quando filtradas
  for (const id of ["base", "idade"]) {
    const valor = document.getElementById(id).value;
    if (valor) p.set(id, valor);
  }
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
  vantagens = dados.vantagens || null;
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

  nomesOrdenados = lutadores.map((l) => ({ nome: l.nome, chave: normalizar(l.nome) }))
    .sort((x, y) => x.nome.localeCompare(y.nome));

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

  const seletorCategoria = document.getElementById("categoria");
  CATEGORIAS_RANKING.forEach((cat) => {
    const opcao = document.createElement("option");
    opcao.value = cat;
    opcao.textContent = CATEGORIAS[cat];
    seletorCategoria.appendChild(opcao);
  });

  const preencher = (id, opcoes) => {
    const select = document.getElementById(id);
    for (const [valor, rotulo] of opcoes) select.add(new Option(rotulo, valor));
    return select;
  };
  preencher("base", Object.entries(BASES_RANKING));
  preencher("idade", Object.entries(FAIXAS_IDADE).map(([k, f]) => [k, f.rotulo]));

  const estado = lerEstadoDaUrl();
  seletorCategoria.value = estado.cat;
  document.getElementById("base").value = estado.base;
  document.getElementById("idade").value = estado.idade;
  seletorRound.value = estado.rm;
  seletor.value = estado.m;
  document.getElementById("min-lutas").value = estado.min;
  document.getElementById("tamanho").value = estado.top;
  document.getElementById("lutador-a").value = estado.a;
  document.getElementById("lutador-b").value = estado.b;

  ["lutador-a", "lutador-b"].forEach((id) => configurarCampoLutador(document.getElementById(id)));
  ["metrica", "min-lutas", "tamanho", "categoria", "base", "idade"].forEach((id) => document.getElementById(id).addEventListener("change", desenharRanking));
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
