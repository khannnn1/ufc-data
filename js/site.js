// Partes comuns a todas as páginas: barra do topo (menu + busca de lutador) e funções usadas pelo
// ranking, pelo comparador e pelo perfil (foto, cartel, categoria em PT, idade...).
// Carregado ANTES do script de cada página: as funções e constantes abaixo ficam globais.

const CATEGORIAS = {
  "Super Heavyweight": "Superpesado", "Heavyweight": "Peso-pesado", "Light Heavyweight": "Meio-pesado", "Middleweight": "Peso-médio",
  "Welterweight": "Meio-médio", "Lightweight": "Peso-leve", "Featherweight": "Peso-pena",
  "Bantamweight": "Peso-galo", "Flyweight": "Peso-mosca", "Catch Weight": "Peso casado",
  "Women's Featherweight": "Peso-pena feminino", "Women's Bantamweight": "Peso-galo feminino",
  "Women's Flyweight": "Peso-mosca feminino", "Women's Strawweight": "Peso-palha feminino",
  "Open Weight": "Peso aberto",  // torneios dos primeiros UFCs, sem divisão de peso
};
const BASES = { Orthodox: "ortodoxo", Southpaw: "canhoto", Switch: "troca de base", "Open Stance": "base aberta", Sideways: "base lateral" };

const METODOS = {
  "Decision - Unanimous": "Decisão unânime",
  "Decision - Split": "Decisão dividida",
  "Decision - Majority": "Decisão majoritária",
  "KO/TKO": "Nocaute",
  "TKO - Doctor's Stoppage": "Nocaute (interrupção médica)",
  "Submission": "Finalização",
  "Overturned": "Resultado anulado",
  "Could Not Continue": "Não pôde continuar",
  "DQ": "Desclassificação",
  "Other": "Outro",
};
const RESULTADOS = { W: "V", L: "D", D: "E", NC: "SR" };
const RESULTADOS_LONGOS = { W: "Vitória", L: "Derrota", D: "Empate", NC: "Sem resultado" };

// ---------- Nota por luta (src/rating.py) ----------
// Lado de uma luta em dados/lutas.json: [..., nota, [resultado, desempenho, adversário]] (índices 8 e 9).
const NOTA_BASE = 6.6;
const ESTILOS = {
  Striker: "no ataque, golpes e knockdowns pesam mais",
  Wrestler: "no ataque, quedas e controle pesam mais",
  Finalizador: "no ataque, tentativas de finalização pesam mais",
  Completo: "todas as estatísticas com o peso aprendido nas decisões",
};
const fmtNota = (n) => n.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
// Faixas de cor: abaixo de 6, de 6 a 6,9, de 7 a 7,9, 8 ou mais (o número está sempre escrito)
function classeNota(n) {
  return n >= 8 ? "otima" : n >= 7 ? "boa" : n >= 6 ? "media" : "baixa";
}
// Selo da nota; com as partes, vira botão que abre o detalhamento
function seloNota(nota, partes, contexto = {}) {
  const selo = document.createElement(partes ? "button" : "span");
  selo.className = `selo-nota ${classeNota(nota)}`;
  selo.textContent = fmtNota(nota);
  if (partes) {
    selo.type = "button";
    selo.title = "Ver como a nota foi calculada";
    selo.setAttribute("aria-label", `Nota ${fmtNota(nota)}${contexto.nome ? ` de ${contexto.nome}` : ""}: ver detalhamento`);
    selo.addEventListener("click", (e) => { e.stopPropagation(); e.preventDefault(); abrirDetalheNota(selo, nota, partes, contexto); });
  } else {
    selo.title = `Nota ${fmtNota(nota)}`;
  }
  return selo;
}
function mediaDasNotas(notas) {
  return notas.length ? Math.round((notas.reduce((s, n) => s + n, 0) / notas.length) * 10) / 10 : null;
}

let caixaNota = null;
function fecharDetalheNota() {
  if (caixaNota) { caixaNota.remove(); caixaNota = null; }
}
function abrirDetalheNota(botao, nota, [resultado, desempenho, adversario], { nome, estilo } = {}) {
  const mesmo = caixaNota && caixaNota.dono === botao;
  fecharDetalheNota();
  if (mesmo) return;
  const sinal = (v) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const linhas = [["Base", NOTA_BASE.toLocaleString("pt-BR", { minimumFractionDigits: 2 })], ["Resultado", sinal(resultado)],
    ["Desempenho", sinal(desempenho)], ["Adversário", sinal(adversario)]];
  const soma = NOTA_BASE + resultado + desempenho + adversario;
  caixaNota = document.createElement("div");
  caixaNota.className = "detalhe-nota";
  caixaNota.setAttribute("role", "dialog");
  caixaNota.dono = botao;
  caixaNota.innerHTML = `<div class="titulo-nota"></div><dl></dl><p class="estilo-nota"></p><a href="sobre.html#nota">Como a nota é calculada</a>`;
  caixaNota.querySelector(".titulo-nota").append(seloNota(nota), ` ${nome || ""}`);
  const dl = caixaNota.querySelector("dl");
  for (const [rotulo, valor] of linhas) {
    const dt = document.createElement("dt"); dt.textContent = rotulo;
    const dd = document.createElement("dd"); dd.textContent = valor;
    dl.append(dt, dd);
  }
  if (Math.abs(soma - nota) > 0.06) {
    const dt = document.createElement("dt"); dt.textContent = "Limite da escala";
    const dd = document.createElement("dd"); dd.textContent = `${fmtNota(soma)} → ${fmtNota(nota)}`;
    dl.append(dt, dd);
  }
  caixaNota.querySelector(".estilo-nota").textContent = estilo ? `Estilo: ${estilo} (${ESTILOS[estilo] || ""})` : "";
  document.body.appendChild(caixaNota);
  const r = botao.getBoundingClientRect();
  const largura = caixaNota.offsetWidth;
  caixaNota.style.left = `${Math.max(8, Math.min(window.scrollX + r.left + r.width / 2 - largura / 2, window.scrollX + document.documentElement.clientWidth - largura - 8))}px`;
  caixaNota.style.top = `${window.scrollY + r.bottom + 6}px`;
}
document.addEventListener("click", (e) => { if (caixaNota && !caixaNota.contains(e.target)) fecharDetalheNota(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") fecharDetalheNota(); });
window.addEventListener("resize", fecharDetalheNota);

const fmtData = (iso) => iso.split("-").reverse().join("/");

const normalizar = (texto) => texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function cartel(l) {
  return `${l.w}-${l.l}` + (l.d ? `-${l.d}` : "") + (l.nc ? ` (${l.nc} NC)` : "");
}

function idade(nasc, naData = new Date()) {
  const n = new Date(nasc + "T00:00:00");
  const fezAniversario = naData.getMonth() > n.getMonth() ||
    (naData.getMonth() === n.getMonth() && naData.getDate() >= n.getDate());
  return naData.getFullYear() - n.getFullYear() - (fezAniversario ? 0 : 1);
}

function metros(cm) {
  return (cm / 100).toFixed(2).replace(".", ",") + " m";
}

// Anos de UFC: "2019–2022", ou só "2024" se todas as lutas foram no mesmo ano (carreira inteira,
// não muda com o filtro de período)
function anosDeUfc(l) {
  if (!l.anos) return "";
  const [inicio, fim] = l.anos;
  return inicio === fim ? String(inicio) : `${inicio}–${fim}`;
}

function iniciais(nome) {
  const partes = nome.replace(/\(.*\)/, "").trim().split(/\s+/);
  return ((partes[0] || "")[0] + (partes.length > 1 ? partes[partes.length - 1][0] : "")).toUpperCase();
}

// Foto redonda do lutador; sem foto (ou se a imagem não carregar), as iniciais num círculo
function avatar(l, classe = "") {
  const caixa = document.createElement("div");
  caixa.className = `avatar ${classe}`.trim();
  caixa.setAttribute("aria-hidden", "true");
  caixa.textContent = iniciais(l.nome);
  if (l.foto) {
    const img = document.createElement("img");
    img.src = l.foto;
    img.alt = "";
    img.loading = "lazy";
    img.referrerPolicy = "no-referrer";
    img.addEventListener("error", () => img.remove());
    caixa.appendChild(img);
  }
  return caixa;
}

// Endereço do perfil de um lutador (o nome é único no JSON: homônimos têm o ano de nascimento)
function linkPerfil(nome) {
  return `lutador.html?n=${encodeURIComponent(nome)}`;
}

// Link para o perfil; o clique não sobe para a linha da tabela (que leva ao comparador)
function linkNome(nome, classe = "nome-lutador") {
  const a = document.createElement("a");
  a.className = classe;
  a.href = linkPerfil(nome);
  a.textContent = nome; // nome via textContent: nunca como HTML
  a.addEventListener("click", (e) => e.stopPropagation());
  return a;
}

// Nome em destaque (link para o perfil) e, embaixo, categoria e anos de UFC
// Melhor posição que cada lutador teve no top 15 pelo Elo, na carreira inteira (lado[10] de dados/lutas.json:
// posição na véspera de cada luta). Não muda com o filtro de período.
function melhoresPosicoes(dadosLutas) {
  const melhor = new Map();
  for (const luta of dadosLutas?.lutas || []) {
    for (const lado of [luta[8], luta[9]]) {
      if (lado[10] && !(melhor.get(lado[0]) <= lado[10])) melhor.set(lado[0], lado[10]);
    }
  }
  return melhor;
}
const TITULO_MELHOR_POSICAO = "Melhor posição no top 15 da categoria pelo Elo (não é o ranking oficial)";
const textoMelhorPosicao = (posicao) => (posicao ? `melhor #${posicao}` : "");

function identificacao(l) {
  const bloco = document.createElement("div");
  bloco.className = "identificacao";
  const sub = document.createElement("span");
  sub.className = "sub-lutador";
  sub.textContent = [l.cat ? (CATEGORIAS[l.cat] || l.cat) : "", anosDeUfc(l), textoMelhorPosicao(l.melhor)]
    .filter(Boolean).join(" · ");
  if (l.melhor) sub.title = TITULO_MELHOR_POSICAO;
  bloco.append(linkNome(l.nome), sub);
  return bloco;
}

// ---------- Dados ----------

// lutadores.json (histórico todo), buscado uma vez por página. no-cache: o navegador confere com o
// servidor se o arquivo mudou (304 rápido quando não mudou).
let promessaLutadores = null;
function carregarLutadoresTudo() {
  promessaLutadores ??= fetch("dados/lutadores.json", { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .catch((erro) => { promessaLutadores = null; throw erro; });
  return promessaLutadores;
}

// dados/lutas.json: histórico de todas as lutas (montar_lutas em src/exportar.py), ~1 MB
let promessaLutas = null;
function carregarLutas() {
  promessaLutas ??= fetch("dados/lutas.json", { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .catch((erro) => { promessaLutas = null; throw erro; });
  return promessaLutas;
}

// Análises da página inicial (dados/analises.json, ~5 KB): também dão a data da base para o rodapé
let promessaAnalises = null;
function carregarAnalises() {
  promessaAnalises ??= fetch("dados/analises.json", { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .catch((erro) => { promessaAnalises = null; throw erro; });
  return promessaAnalises;
}

function linkEventoUrl(id) {
  return `eventos.html?id=${encodeURIComponent(id)}`;
}

// ---------- Barra do topo ----------

const MENU = [
  { rotulo: "Análises", href: "index.html", pagina: "index" },
  { rotulo: "Eventos", href: "eventos.html", pagina: "eventos" },
  { rotulo: "Rankings", href: "interativo.html#ranking", pagina: "interativo" },
  { rotulo: "Comparar", href: "interativo.html#comparador", pagina: "interativo-comparador" },
];

function montarBarraTopo() {
  const pagina = document.body.dataset.pagina || "";
  const barra = document.createElement("nav");
  barra.className = "barra-topo";
  barra.setAttribute("aria-label", "Principal");
  barra.innerHTML = `
    <div class="barra-conteudo">
      <a class="logo" href="index.html">UFC <span>Data</span></a>
      <ul class="menu">${MENU.map((m) => `<li><a href="${m.href}"${pagina === m.pagina ? ' aria-current="page"' : ""}>${m.rotulo}</a></li>`).join("")}</ul>
      <div class="busca" role="search">
        <label class="visualmente-oculto" for="busca-lutador">Buscar lutador</label>
        <input id="busca-lutador" type="search" placeholder="Buscar lutador" autocomplete="off"
          role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="busca-sugestoes">
        <ul class="busca-sugestoes" id="busca-sugestoes" role="listbox" aria-label="Lutadores" hidden></ul>
      </div>
    </div>`;
  document.body.prepend(barra);
  configurarBusca(barra.querySelector("#busca-lutador"), barra.querySelector("#busca-sugestoes"));
}

// Busca global: ao digitar, até 8 lutadores (quem começa com o termo primeiro, depois mais lutas);
// Enter ou clique abre o perfil.
function configurarBusca(campo, lista) {
  let todos = null;
  let itens = [];
  let ativo = -1;

  const fechar = () => { lista.hidden = true; campo.setAttribute("aria-expanded", "false"); ativo = -1; };
  const abrir = (nome) => { window.location.href = linkPerfil(nome); };

  function mostrar() {
    const termo = normalizar(campo.value.trim());
    if (!todos || !termo) return fechar();
    const pontuados = [];
    for (const l of todos) {
      const chave = normalizar(l.nome);
      // Alguma palavra do nome começa com o termo (Silva acha Anderson Silva) vem antes de "contém";
      // dentro de cada grupo, quem tem mais lutas primeiro
      const nivel = chave.startsWith(termo) || chave.includes(" " + termo) ? 0 : chave.includes(termo) ? 1 : -1;
      if (nivel >= 0) pontuados.push([nivel, -l.n, l]);
    }
    pontuados.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2].nome.localeCompare(b[2].nome));
    itens = pontuados.slice(0, 8).map((p) => p[2]);
    lista.innerHTML = "";
    if (!itens.length) {
      lista.innerHTML = '<li class="vazio">Nenhum lutador com esse nome</li>';
    }
    itens.forEach((l, i) => {
      const item = document.createElement("li");
      item.id = `busca-op-${i}`;
      item.setAttribute("role", "option");
      const texto = document.createElement("div");
      texto.className = "identificacao";
      const nome = document.createElement("span");
      nome.className = "nome-lutador";
      nome.textContent = l.nome;
      const sub = document.createElement("span");
      sub.className = "sub-lutador";
      sub.textContent = [l.cat ? (CATEGORIAS[l.cat] || l.cat) : "", anosDeUfc(l), cartel(l)].filter(Boolean).join(" · ");
      texto.append(nome, sub);
      item.append(avatar(l, "pequeno"), texto);
      item.addEventListener("mousedown", (e) => e.preventDefault()); // não tira o foco do campo
      item.addEventListener("click", () => abrir(l.nome));
      lista.appendChild(item);
    });
    ativo = -1;
    lista.hidden = false;
    campo.setAttribute("aria-expanded", "true");
  }

  function marcar(i) {
    const opcoes = lista.querySelectorAll('[role="option"]');
    opcoes.forEach((o, j) => o.classList.toggle("ativo", j === i));
    ativo = i;
    if (opcoes[i]) campo.setAttribute("aria-activedescendant", opcoes[i].id);
  }

  campo.addEventListener("focus", () => {
    carregarLutadoresTudo().then((d) => { todos = d.lutadores; mostrar(); }).catch(console.error);
  });
  campo.addEventListener("input", mostrar);
  campo.addEventListener("blur", fechar);
  campo.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" && itens.length) { e.preventDefault(); marcar(Math.min(ativo + 1, itens.length - 1)); }
    else if (e.key === "ArrowUp" && itens.length) { e.preventDefault(); marcar(Math.max(ativo - 1, 0)); }
    else if (e.key === "Enter" && itens.length) { e.preventDefault(); abrir(itens[Math.max(ativo, 0)].nome); }
    else if (e.key === "Escape") { campo.value = ""; fechar(); }
  });
}

// Rodapé comum (substitui o do HTML, que fica só para quem está sem JavaScript): fontes, página
// Sobre e a data da última atualização da base
function montarRodape() {
  let rodape = document.querySelector("body > footer");
  if (!rodape) rodape = document.body.appendChild(document.createElement("footer"));
  rodape.innerHTML = `
    <div>Projeto de <a href="https://github.com/khannnn1/ufc-data">código aberto no GitHub</a> · Dados de <a href="http://ufcstats.com">ufcstats.com</a> · Fotos de <a href="https://www.ufc.com">ufc.com</a> · <a href="sobre.html">Sobre o projeto</a></div>
    <div class="atualizacao"></div>`;
  carregarAnalises().then((d) => {
    const fim = d.tudo?.periodo?.fim;
    rodape.querySelector(".atualizacao").textContent =
      `Base atualizada em ${fmtData(d.gerado_em)}${fim ? ` · último evento em ${fmtData(fim)}` : ""}`;
  }).catch(() => {});
}

montarBarraTopo();
montarRodape();
