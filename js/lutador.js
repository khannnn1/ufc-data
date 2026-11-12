// Perfil do lutador (lutador.html?n=Nome): lê dados/lutadores.json (totais, foto, físico) e
// dados/lutas.json (histórico de todas as lutas, gerado por montar_lutas em src/exportar.py).

const fmt1 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2, minimumFractionDigits: 2 });

// Estatísticas comparadas com a média da categoria. A média é "agrupada": soma dos numeradores de
// todos os lutadores da categoria dividida pela soma dos denominadores (quem lutou mais pesa mais).
const ESTATISTICAS = [
  { rotulo: "Golpes significativos acertados por minuto", num: (l) => l.sl, den: (l) => l.de / 60, fmt: fmt2 },
  { rotulo: "Precisão de golpes significativos", num: (l) => l.sl, den: (l) => l.sa, pct: true },
  { rotulo: "Quedas a cada 15 minutos", num: (l) => l.tdl, den: (l) => l.de / 900, fmt: fmt2 },
  { rotulo: "Precisão de quedas", num: (l) => l.tdl, den: (l) => l.tda, pct: true },
  { rotulo: "Tentativas de finalização a cada 15 minutos", num: (l) => l.sub, den: (l) => l.de / 900, fmt: fmt2 },
  { rotulo: "Tempo de controle por luta (min)", num: (l) => l.ctrl / 60, den: (l) => l.ne, fmt: fmt1 },
  { rotulo: "Knockdowns a cada 15 minutos", num: (l) => l.kd, den: (l) => l.de / 900, fmt: fmt2 },
];
const MIN_LUTAS_MEDIA = 3; // lutadores com menos lutas com estatística não entram na média da categoria

function formatarEstat(e, v) {
  return e.pct ? `${Math.round(v * 100)}%` : e.fmt.format(v);
}

function elemento(tag, classe, texto) {
  const el = document.createElement(tag);
  if (classe) el.className = classe;
  if (texto !== undefined) el.textContent = texto;
  return el;
}

// ---------- Blocos da página ----------

function topo(l, historico, estilo) {
  const secao = elemento("section", "perfil-topo");
  secao.appendChild(avatar(l, "enorme"));
  const titulo = elemento("div", "titulo");
  titulo.appendChild(elemento("h1", "", l.nome));
  const posicoes = historico.map((h) => h.eu[10]).filter(Boolean);
  const campeao = historico.some((h) => h.titulo === 1 && h.eu[1] === "W");
  const melhor = campeao ? "campeao" : posicoes.length ? Math.min(...posicoes) : null;
  const sub = elemento("div", "sub",
    [l.cat ? (CATEGORIAS[l.cat] || l.cat) : "", l.anos ? `UFC ${anosDeUfc(l)}` : "", estilo ? `Estilo: ${estilo}` : "",
      campeao ? `${textoCampeao(l.cat).replace("c", "C")} do UFC` : melhor ? `Melhor posição: #${melhor}` : ""].filter(Boolean).join(" · "));
  if (melhor) sub.title = tituloMelhorPosicao(melhor);
  titulo.appendChild(sub);
  const c = elemento("div", "cartel-grande", cartel(l));
  c.appendChild(elemento("small", "", "cartel no UFC"));
  titulo.appendChild(c);
  const acoes = elemento("div", "acoes");
  const notas = historico.filter((h) => h.eu[8] != null).map((h) => h.eu[8]);
  if (notas.length) {
    const media = mediaDasNotas(notas);
    const ultimas = mediaDasNotas(notas.slice(0, 5));
    const bloco = elemento("div", "nota-media");
    const grande = seloNota(media);
    grande.classList.add("grande");
    const texto = elemento("div", "texto-nota");
    texto.append(elemento("strong", "", "Nota média"), elemento("span", "", `${notas.length} ${notas.length === 1 ? "luta" : "lutas"}`));
    if (notas.length > 5) texto.append(elemento("span", "", `Últimas 5: ${fmtNota(ultimas)}`));
    bloco.append(grande, texto);
    acoes.appendChild(bloco);
  }
  const comparar = elemento("a", "botao", "Comparar com outro lutador");
  comparar.href = `interativo.html?a=${encodeURIComponent(l.nome)}#comparador`;
  acoes.appendChild(comparar);
  secao.append(titulo, acoes);
  return secao;
}

// Nota de cada luta, da mais antiga à mais recente, em barras (altura = nota, de 3 a 10)
function notasPorLuta(historico, estilos) {
  const lutas = historico.filter((h) => h.eu[8] != null).reverse();
  if (lutas.length < 2) return null;
  const cartao = elemento("section", "cartao-p notas-luta");
  cartao.appendChild(elemento("h2", "", "Nota em cada luta"));
  const grafico = elemento("div", "barras-notas");
  grafico.setAttribute("role", "list");
  const altura = (n) => `${((n - 3) / 7) * 100}%`;
  const base = elemento("div", "linha-base");
  base.style.bottom = altura(NOTA_BASE);
  base.title = "Nota base 6,6";
  grafico.appendChild(base);
  for (const h of lutas) {
    const barra = elemento("a", `barra-nota ${classeNota(h.eu[8])}`);
    barra.href = linkEventoUrl(h.idEvento);
    barra.setAttribute("role", "listitem");
    barra.style.height = altura(h.eu[8]);
    const texto = `${fmtNota(h.eu[8])} · ${RESULTADOS_LONGOS[h.eu[1]] || h.eu[1]} contra ${h.adv[0]} · ${h.evento}, ${fmtData(h.data)}`;
    barra.title = texto;
    barra.setAttribute("aria-label", texto);
    if (lutas.length <= 24) barra.appendChild(elemento("span", "valor-barra", fmtNota(h.eu[8])));
    grafico.appendChild(barra);
  }
  const eixo = elemento("div", "eixo-notas");
  eixo.append(elemento("span", "", lutas[0].data.slice(0, 4)), elemento("span", "", "linha tracejada: nota base 6,6"), elemento("span", "", lutas.at(-1).data.slice(0, 4)));
  cartao.append(grafico, eixo);
  return cartao;
}

// Sequência atual: vitórias ou derrotas seguidas a partir da luta mais recente (empate/NC interrompe)
function sequencia(historico) {
  if (!historico.length) return null;
  const primeiro = historico[0].eu[1];
  if (primeiro !== "W" && primeiro !== "L") return null;
  let n = 0;
  while (n < historico.length && historico[n].eu[1] === primeiro) n++;
  return { tipo: primeiro, n };
}

function fatos(l, historico) {
  const grade = elemento("section", "fatos");
  const seq = sequencia(historico);
  const itens = [
    ["Idade", l.nasc ? `${idade(l.nasc)} anos` : "—"],
    ["Altura", l.alt ? metros(l.alt) : "—"],
    ["Envergadura", l.env ? metros(l.env) : "—"],
    ["Base", l.base ? (BASES[l.base] || l.base).replace(/^./, (x) => x.toUpperCase()) : "—"],
    ["Lutas no UFC", String(l.n)],
    ["Sequência atual", seq ? `${seq.n} ${seq.tipo === "W" ? (seq.n > 1 ? "vitórias" : "vitória") : (seq.n > 1 ? "derrotas" : "derrota")}` : "—",
      seq ? (seq.tipo === "W" ? "vitoria" : "derrota") : ""],
  ];
  for (const [rotulo, valor, classe] of itens) {
    const f = elemento("div", "fato");
    f.append(elemento("div", "rotulo", rotulo), elemento("div", `valor ${classe || ""}`.trim(), valor));
    grade.appendChild(f);
  }
  return grade;
}

function metodos(historico) {
  const cartao = elemento("section", "cartao-p metodos");
  cartao.appendChild(elemento("h2", "", "Como vence e como perde"));
  for (const [resultado, rotulo] of [["W", "Vitórias"], ["L", "Derrotas"]]) {
    const lutas = historico.filter((h) => h.eu[1] === resultado);
    const contagem = Object.fromEntries(GRUPOS.map(([g]) => [g, 0]));
    lutas.forEach((h) => contagem[grupoMetodo(h.metodo)]++);
    const linha = elemento("div", "linha-metodo");
    const cab = elemento("div", "cabecalho");
    cab.append(elemento("span", "", `${rotulo}: ${lutas.length}`),
      elemento("span", "", GRUPOS.filter(([g]) => contagem[g]).map(([g, r]) => `${r} ${contagem[g]}`).join(" · ") || "—"));
    const barra = elemento("div", "empilhada");
    barra.setAttribute("role", "img");
    barra.setAttribute("aria-label", `${rotulo}: ` + GRUPOS.map(([g, r]) => `${r} ${contagem[g]}`).join(", "));
    for (const [g, r] of GRUPOS) {
      if (!contagem[g]) continue;
      const parte = elemento("span", `cor-${g}`);
      parte.style.width = `${(contagem[g] / lutas.length) * 100}%`;
      parte.title = `${r}: ${contagem[g]}`;
      barra.appendChild(parte);
    }
    linha.append(cab, barra);
    cartao.appendChild(linha);
  }
  const legenda = elemento("div", "legenda");
  for (const [g, r] of GRUPOS) {
    const item = elemento("span", "", r);
    item.prepend(elemento("i", `cor-${g}`));
    legenda.appendChild(item);
  }
  cartao.appendChild(legenda);
  return cartao;
}

function estatisticas(l, todos) {
  const cartao = elemento("section", "cartao-p");
  const nomeCat = l.cat ? (CATEGORIAS[l.cat] || l.cat).toLowerCase() : "";
  cartao.appendChild(elemento("h2", "", l.cat ? `Estatísticas × média do ${nomeCat}` : "Estatísticas"));
  const ne = l.ne ?? l.n;
  if (!ne) {
    cartao.appendChild(elemento("p", "nota", "As lutas deste lutador são de antes do registro de estatísticas detalhadas."));
    return cartao;
  }
  const pares = todos.filter((x) => x.cat === l.cat && (x.ne ?? x.n) >= MIN_LUTAS_MEDIA);
  for (const e of ESTATISTICAS) {
    const den = e.den(l);
    if (!(den > 0)) continue;
    const valor = e.num(l) / den;
    const somaDen = pares.reduce((s, x) => s + (e.den(x) || 0), 0);
    const media = somaDen > 0 ? pares.reduce((s, x) => s + (e.den(x) > 0 ? e.num(x) : 0), 0) / somaDen : null;

    const linha = elemento("div", "estat");
    linha.append(elemento("span", "rotulo", e.rotulo), elemento("span", "valor", formatarEstat(e, valor)));
    const trilho = elemento("div", "trilho");
    const escala = Math.max(valor, media || 0) * 1.25 || 1;
    const preenchido = elemento("div", `preenchido${media !== null && valor > media ? " acima" : ""}`);
    preenchido.style.width = `${Math.min((valor / escala) * 100, 100)}%`;
    trilho.appendChild(preenchido);
    if (media !== null) {
      const marca = elemento("div", "media");
      marca.style.left = `${(media / escala) * 100}%`;
      marca.title = `Média: ${formatarEstat(e, media)}`;
      trilho.appendChild(marca);
    }
    linha.appendChild(trilho);
    if (media !== null) linha.appendChild(elemento("span", "comparacao", `Média da categoria: ${formatarEstat(e, media)}`));
    cartao.appendChild(linha);
  }
  const notas = [`Totais das ${ne} ${ne === 1 ? "luta" : "lutas"} com estatísticas no UFC.`];
  if (ne < l.n) notas.push(`As ${l.n - ne} mais antigas não têm estatísticas detalhadas.`);
  if (ne < MIN_LUTAS_MEDIA) notas.push("Amostra pequena: os valores oscilam muito.");
  notas.push(`Média: lutadores da categoria com ${MIN_LUTAS_MEDIA}+ lutas (traço branco); verde = acima da média.`);
  cartao.appendChild(elemento("p", "nota", notas.join(" ")));
  return cartao;
}

function historicoDeLutas(historico, porNome, estilos, nomeLutador) {
  const cartao = elemento("section", "cartao-p");
  cartao.appendChild(elemento("h2", "", `Histórico de lutas (${historico.length})`));

  const filtros = elemento("div", "filtros-historico");
  const opcoes = [["todas", "Todas"], ["W", "Vitórias"], ["L", "Derrotas"], ["titulo", "Disputas de cinturão"]];
  const tabelaWrap = elemento("div", "tabela-wrap");
  const tabela = elemento("table", "historico");
  tabela.innerHTML = `<caption class="visualmente-oculto">Histórico de lutas, da mais recente à mais antiga</caption>
    <thead><tr><th>Res.</th><th title="Nota da luta, de 0 a 10">Nota</th><th>Adversário</th><th>Método</th><th class="num col-golpes" title="Golpes significativos acertados: lutador × adversário">Golpes sig.</th></tr></thead>`;
  const corpo = elemento("tbody");
  tabela.appendChild(corpo);
  tabelaWrap.appendChild(tabela);

  function desenhar(filtro) {
    corpo.innerHTML = "";
    const lista = historico.filter((h) => filtro === "todas" || (filtro === "titulo" ? h.titulo === 1 : h.eu[1] === filtro));
    for (const h of lista) {
      const tr = elemento("tr");
      const res = elemento("td");
      const selo = elemento("span", `resultado ${h.eu[1]}`, RESULTADOS[h.eu[1]] || h.eu[1]);
      selo.title = RESULTADOS_LONGOS[h.eu[1]] || h.eu[1];
      res.appendChild(selo);
      const nota = elemento("td");
      if (h.eu[8] != null) nota.appendChild(seloNota(h.eu[8], h.eu[9], { nome: nomeLutador, estilo: estilos[nomeLutador] }));
      else nota.textContent = "—";

      const adv = elemento("td");
      const caixa = elemento("div", "adversario");
      const dadosAdv = porNome.get(h.adv[0]) || { nome: h.adv[0] };
      const id = elemento("div", "identificacao");
      const sub = elemento("span", "sub-lutador");
      const linkEvento = elemento("a", "link-evento", h.evento);
      linkEvento.href = linkEventoUrl(h.idEvento);
      sub.append(linkEvento, ` · ${fmtData(h.data)}`);
      id.append(linkNome(h.adv[0]), sub);
      caixa.append(avatar(dadosAdv, "pequeno"), id);
      adv.appendChild(caixa);

      const met = elemento("td", "metodo");
      met.appendChild(elemento("div", "principal", METODOS[h.metodo] || h.metodo));
      const detalhe = [h.round ? `${h.round}º round` : "", h.tempo || ""].filter(Boolean).join(" · ");
      if (detalhe) met.appendChild(elemento("div", "sub-lutador", detalhe));
      if (h.titulo) met.appendChild(elemento("span", "etiqueta cinturao", h.titulo === 2 ? "Final do TUF" : "Cinturão"));
      if (h.lutaNoite) met.appendChild(elemento("span", "etiqueta bonus", "Luta da Noite"));
      if (h.perf && h.eu[1] === "W") met.appendChild(elemento("span", "etiqueta bonus", "Performance"));

      const golpes = elemento("td", "num golpes col-golpes");
      if (h.eu[3] !== null && h.adv[3] !== null) {
        golpes.appendChild(elemento("strong", "", String(h.eu[3])));
        golpes.append(` × ${h.adv[3]}`);
      } else {
        golpes.textContent = "—";
      }
      tr.append(res, nota, adv, met, golpes);
      corpo.appendChild(tr);
    }
    if (!lista.length) corpo.innerHTML = '<tr><td colspan="5" class="sub-lutador">Nenhuma luta neste filtro.</td></tr>';
  }

  for (const [chave, rotulo] of opcoes) {
    const botao = elemento("button", "", rotulo);
    botao.type = "button";
    botao.setAttribute("aria-pressed", String(chave === "todas"));
    botao.addEventListener("click", () => {
      filtros.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === botao)));
      desenhar(chave);
    });
    filtros.appendChild(botao);
  }
  if (!historico.some((h) => h.titulo === 1)) filtros.lastChild.remove();
  cartao.append(filtros, tabelaWrap);
  desenhar("todas");
  return cartao;
}

// Lutas do lutador, da mais recente à mais antiga, já "do ponto de vista" dele
function montarHistorico(nome, dadosLutas) {
  const historico = [];
  for (const luta of dadosLutas.lutas) {
    const [evento, cat, metodo, round, tempo, titulo, lutaNoite, perf, a, b] = luta;
    const eu = a[0] === nome ? a : b[0] === nome ? b : null;
    if (!eu) continue;
    const [nomeEvento, data, idEvento] = dadosLutas.eventos[evento];
    historico.push({ evento: nomeEvento, idEvento, data, cat, metodo, round, tempo, titulo, lutaNoite, perf, eu, adv: eu === a ? b : a });
  }
  return historico;
}

async function iniciar() {
  const principal = document.getElementById("perfil");
  const nome = new URLSearchParams(window.location.search).get("n");
  if (!nome) {
    principal.innerHTML = '<p class="erro">Escolha um lutador na busca do topo.</p>';
    return;
  }
  let dados, dadosLutas;
  try {
    [dados, dadosLutas] = await Promise.all([
      carregarLutadoresTudo(),
      carregarLutas(),
    ]);
  } catch (erro) {
    principal.innerHTML = '<p class="erro">Não foi possível carregar os dados. Se abriu o arquivo direto do disco, rode um servidor local (python -m http.server).</p>';
    console.error(erro);
    return;
  }
  const porNome = new Map(dados.lutadores.map((l) => [l.nome, l]));
  const l = porNome.get(nome) || dados.lutadores.find((x) => normalizar(x.nome) === normalizar(nome));
  if (!l) {
    principal.innerHTML = "";
    principal.appendChild(elemento("p", "erro", `Não encontrei "${nome}". Use a busca do topo.`));
    return;
  }
  document.title = `${l.nome} — UFC Data`;
  const historico = montarHistorico(l.nome, dadosLutas);

  principal.innerHTML = "";
  const grade = elemento("div", "grade");
  grade.append(metodos(historico), estatisticas(l, dados.lutadores));
  const estilos = dadosLutas.estilos || {};
  principal.append(topo(l, historico, estilos[l.nome]), fatos(l, historico));
  const notas = notasPorLuta(historico, estilos);
  if (notas) principal.appendChild(notas);
  principal.append(grade, historicoDeLutas(historico, porNome, estilos, l.nome));
}

iniciar();
