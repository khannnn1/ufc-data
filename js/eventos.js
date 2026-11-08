// Eventos (eventos.html): sem parâmetro, a lista de eventos por ano; com ?id=<código do evento no
// ufcstats>, o card do evento no formato de placar. Lê dados/lutas.json e dados/lutadores.json.

function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto !== undefined) e.textContent = texto;
  return e;
}

const fmtInt = new Intl.NumberFormat("pt-BR");

// Lutas agrupadas por evento (índice em dados.eventos), na ordem do card
function lutasPorEvento(dadosLutas) {
  const grupos = dadosLutas.eventos.map(() => []);
  for (const luta of dadosLutas.lutas) grupos[luta[0]].push(luta);
  return grupos;
}

// ---------- Lista ----------

function desenharLista(principal, dadosLutas, porNome) {
  const grupos = lutasPorEvento(dadosLutas);
  const anos = [...new Set(dadosLutas.eventos.map((e) => e[1].slice(0, 4)))];
  const params = new URLSearchParams(window.location.search);
  const anoInicial = anos.includes(params.get("ano")) ? params.get("ano") : anos[0];

  principal.innerHTML = "";
  principal.append(el("h1", "", "Eventos"),
    el("p", "intro", `${fmtInt.format(dadosLutas.eventos.length)} eventos do UFC, de ${dadosLutas.eventos.at(-1)[1].slice(0, 4)} a ${anos[0]}. Clique num evento para ver o card completo.`));

  const controles = el("div", "controles-eventos");
  const ano = el("select");
  ano.setAttribute("aria-label", "Ano");
  ano.innerHTML = '<option value="">Todos os anos</option>' + anos.map((a) => `<option value="${a}">${a}</option>`).join("");
  ano.value = anoInicial;
  const busca = el("input");
  busca.type = "search";
  busca.placeholder = "Filtrar por nome do evento ou lutador";
  busca.setAttribute("aria-label", "Filtrar eventos");
  controles.append(ano, busca);

  const lista = el("ul", "lista-eventos");
  principal.append(controles, lista);

  function desenhar() {
    const termo = normalizar(busca.value.trim());
    lista.innerHTML = "";
    let mostrados = 0;
    dadosLutas.eventos.forEach(([nome, data, id], i) => {
      if (ano.value && !data.startsWith(ano.value)) return;
      const lutas = grupos[i];
      if (termo) {
        const textos = [nome, ...lutas.flatMap((l) => [l[8][0], l[9][0]])].map(normalizar);
        if (!textos.some((t) => t.includes(termo))) return;
      }
      mostrados++;
      const item = el("li");
      const link = el("a", "evento");
      link.href = linkEventoUrl(id);
      const nomeEvento = el("span", "nome-evento", nome);
      // Melhor atuação da noite: maior nota entre todos os lados do card
      let melhor = null;
      for (const luta of lutas) for (const lado of [luta[8], luta[9]]) if (lado[8] != null && (!melhor || lado[8] > melhor[8])) melhor = lado;
      if (melhor) {
        const destaque = el("span", "melhor-nota", "Melhor atuação: ");
        destaque.append(el("span", "", melhor[0]), " ", seloNota(melhor[8]));
        nomeEvento.appendChild(destaque);
      }
      link.append(el("span", "data", fmtData(data)), nomeEvento);
      const principalLuta = el("span", "principal");
      if (lutas.length) {
        const [, , , , , , , , a, b] = lutas[0];
        for (const [i2, lado] of [a, b].entries()) {
          if (i2) principalLuta.appendChild(el("span", "x", "vs"));
          const caixa = el("span", `lado${lado[1] === "W" ? " venceu" : ""}`);
          caixa.append(avatar(porNome.get(lado[0]) || { nome: lado[0] }, "pequeno"), el("span", "", lado[0]));
          principalLuta.appendChild(caixa);
        }
      }
      link.append(principalLuta, el("span", "qtd", `${lutas.length} ${lutas.length === 1 ? "luta" : "lutas"}`));
      item.appendChild(link);
      lista.appendChild(item);
    });
    if (!mostrados) lista.innerHTML = '<li class="vazio">Nenhum evento com esse filtro.</li>';
    const url = new URL(window.location.href);
    if (ano.value) url.searchParams.set("ano", ano.value); else url.searchParams.delete("ano");
    history.replaceState(null, "", url);
  }
  ano.addEventListener("change", desenhar);
  busca.addEventListener("input", () => {
    if (busca.value.trim() && ano.value) ano.value = ""; // buscar procura em todos os anos
    desenhar();
  });
  desenhar();
}

// ---------- Card de um evento ----------

function ladoDoPlacar(lado, porNome, direita, temVencedor, estilos) {
  const [nome, resultado] = lado;
  const caixa = el("div", `lado${direita ? " direita" : ""}${temVencedor && resultado === "L" ? " perdeu" : ""}`);
  const id = el("div", "identificacao");
  const l = porNome.get(nome);
  const sub = el("span", "sub-lutador", l ? cartel(l) : "");
  id.append(linkNome(nome), sub);
  const selo = el("span", `resultado ${resultado}`, RESULTADOS[resultado] || resultado);
  selo.title = RESULTADOS_LONGOS[resultado] || resultado;
  const notaLado = lado[8];
  const extras = el("div", "selos");
  extras.appendChild(selo);
  if (notaLado !== null && notaLado !== undefined) extras.appendChild(seloNota(notaLado, lado[9], { nome, estilo: estilos[nome] }));
  caixa.append(avatar(l || { nome }, "grande"), id, extras);
  return caixa;
}

function desenharEvento(principal, dadosLutas, porNome, id) {
  const indice = dadosLutas.eventos.findIndex((e) => e[2] === id);
  principal.innerHTML = "";
  const voltar = el("a", "voltar", "← Todos os eventos");
  voltar.href = "eventos.html";
  principal.appendChild(voltar);
  if (indice < 0) {
    principal.appendChild(el("p", "erro", "Evento não encontrado."));
    return;
  }
  const [nome, data] = dadosLutas.eventos[indice];
  if (data) voltar.href = `eventos.html?ano=${data.slice(0, 4)}`;
  document.title = `${nome} — UFC Data`;
  const lutas = dadosLutas.lutas.filter((l) => l[0] === indice);
  const cabecalho = el("div", "cabecalho-evento");
  const bonus = lutas.filter((l) => l[6]).length + lutas.filter((l) => l[7]).length;
  cabecalho.append(el("h1", "", nome),
    el("div", "sub", [fmtData(data), `${lutas.length} ${lutas.length === 1 ? "luta" : "lutas"}`,
      ((n) => (n ? `${n} ${n === 1 ? "disputa" : "disputas"} de cinturão` : ""))(lutas.filter((l) => l[5]).length),
      bonus ? `${bonus} bônus` : ""].filter(Boolean).join(" · ")));
  principal.appendChild(cabecalho);

  const lista = el("div", "lutas");
  lutas.forEach((luta, i) => {
    const [, cat, metodo, round, tempo, titulo, lutaNoite, perf, a, b] = luta;
    const temVencedor = a[1] === "W";
    const cartao = el("article", "luta");
    const rotulo = el("div", "rotulo-luta");
    if (i === 0) rotulo.appendChild(el("strong", "", "Luta principal"));
    if (cat) rotulo.appendChild(el("span", "", CATEGORIAS[cat] || cat));
    if (titulo) rotulo.appendChild(el("span", "etiqueta cinturao", "Cinturão"));
    if (lutaNoite) rotulo.appendChild(el("span", "etiqueta bonus", "Luta da Noite"));
    if (perf && temVencedor) rotulo.appendChild(el("span", "etiqueta bonus", "Performance"));

    const placar = el("div", "placar");
    const centro = el("div", "centro");
    centro.append(el("div", "metodo", METODOS[metodo] || metodo),
      el("div", "detalhe", [round ? `${round}º round` : "", tempo || ""].filter(Boolean).join(" · ")));
    const estilos = dadosLutas.estilos || {};
    placar.append(ladoDoPlacar(a, porNome, false, temVencedor, estilos), centro, ladoDoPlacar(b, porNome, true, temVencedor, estilos));
    cartao.append(rotulo, placar);

    // Estatísticas dos dois lados (a = [nome, res, kd, sl, sa, tdl, tda, ctrl])
    if (a[3] !== null && b[3] !== null) {
      const estat = el("div", "estat-luta");
      const par = (rotuloEstat, va, vb) => {
        const s = el("span", "", `${rotuloEstat} `);
        s.append(el("strong", "", String(va)), ` × `, el("strong", "", String(vb)));
        estat.appendChild(s);
      };
      par("Golpes sig.", a[3], b[3]);
      par("Quedas", a[5], b[5]);
      if (a[2] || b[2]) par("Knockdowns", a[2], b[2]);
      const min = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
      par("Controle", min(a[7]), min(b[7]));
      cartao.appendChild(estat);
    }
    lista.appendChild(cartao);
  });
  principal.appendChild(lista);
}

async function iniciar() {
  const principal = document.getElementById("eventos");
  let dadosLutas, dados;
  try {
    [dadosLutas, dados] = await Promise.all([carregarLutas(), carregarLutadoresTudo()]);
  } catch (erro) {
    principal.innerHTML = '<p class="erro">Não foi possível carregar os dados. Se abriu o arquivo direto do disco, rode um servidor local (python -m http.server).</p>';
    console.error(erro);
    return;
  }
  const porNome = new Map(dados.lutadores.map((l) => [l.nome, l]));
  const id = new URLSearchParams(window.location.search).get("id");
  if (id) desenharEvento(principal, dadosLutas, porNome, id);
  else desenharLista(principal, dadosLutas, porNome);
}

iniciar();
