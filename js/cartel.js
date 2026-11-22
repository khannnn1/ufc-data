// Seção "Qualidade do cartel" (#cartel) da página interativa: lê dados/cartel.json (src/cartel.py).
// Mede QUEM cada lutador venceu e para quem perdeu (força do adversário no dia, com 25% de retrospecto e
// ajuste de época), não COMO lutou (isso é a nota). Vale a carreira inteira no UFC: não muda com o período.
// Carregado depois de interativo.js, que chama iniciarCartel() e parametrosCartel(p) (link compartilhável).

const VISOES_CARTEL = {
  geral: {
    rotulo: "Geral", campo: "geral", formato: (v) => fmt2.format(v), minimo: "auge",
    intro: "Quem é forte nas três visões ao mesmo tempo: a média de Qualidade, Longevidade e Auge, cada uma medida em desvios-padrão em relação à média (0 = lutador médio do índice; 2 = dois desvios acima). Só entra quem tem as três, ou seja, 10 lutas ou mais.",
  },
  qual: {
    rotulo: "Qualidade", campo: "qual", formato: (v) => fmt2.format(v),
    intro: "O cartel mais forte por luta: a soma dos pontos dividida pelo número de lutas (mais 2, para que poucas lutas boas não passem à frente de carreiras longas).",
  },
  long: {
    rotulo: "Longevidade", campo: "long", formato: (v) => fmt1.format(v),
    intro: "Quem acumulou mais: a soma dos pontos de todas as lutas. Favorece carreiras longas contra adversários fortes.",
  },
  auge: {
    rotulo: "Auge", campo: "auge", formato: (v) => fmt2.format(v), minimo: "auge",
    intro: "O melhor período: a média das 10 lutas seguidas que mais valeram, sem o começo e o fim da carreira.",
  },
};
const GENEROS_CARTEL = { M: "Masculino", F: "Feminino" };
const ATIVIDADE_DIAS = 730; // "em atividade" = lutou nos últimos 2 anos (o mesmo corte do top 15 pelo Elo)
const TAMANHOS_CARTEL = [10, 20, 50];
const PADROES_CARTEL = { cv: "geral", cg: "M", cc: "", ca: "", ct: 20 };

let dadosCartel = null; // dados/cartel.json
let lutadoresCartel = []; // um por lutador de cartel.json, juntado com foto/categoria de lutadores.json

function estadoCartelDaUrl() {
  const p = new URLSearchParams(location.search);
  const ct = parseInt(p.get("ct"), 10);
  return {
    cv: p.get("cv") in VISOES_CARTEL ? p.get("cv") : PADROES_CARTEL.cv,
    cg: p.get("cg") in GENEROS_CARTEL ? p.get("cg") : PADROES_CARTEL.cg,
    cc: CATEGORIAS_RANKING.includes(p.get("cc")) ? p.get("cc") : PADROES_CARTEL.cc,
    ca: p.get("ca") === "sim" ? "sim" : PADROES_CARTEL.ca,
    ct: TAMANHOS_CARTEL.includes(ct) ? ct : PADROES_CARTEL.ct,
  };
}

// Lido ao carregar o script: a página reescreve a URL antes de cartel.json chegar
const ESTADO_INICIAL_CARTEL = estadoCartelDaUrl();

// Escreve na URL só o que difere do padrão (chamado por atualizarUrl em interativo.js); enquanto
// cartel.json não chega, mantém o que veio no link
function parametrosCartel(p) {
  const valores = !dadosCartel ? ESTADO_INICIAL_CARTEL : {
    cv: document.getElementById("visao-cartel").value, cg: document.getElementById("genero-cartel").value,
    cc: document.getElementById("categoria-cartel").value, ca: document.getElementById("ativos-cartel").value,
    ct: parseInt(document.getElementById("tamanho-cartel").value, 10),
  };
  for (const [chave, valor] of Object.entries(valores)) if (valor !== PADROES_CARTEL[chave]) p.set(chave, valor);
}

// Categorias do seletor conforme a divisão: masculinas ou femininas (sem peso casado nem peso aberto)
function categoriasDoGenero(genero) {
  return CATEGORIAS_RANKING.filter((c) => (genero === "F") === c.startsWith("Women"));
}

function preencherCategoriasCartel(genero, valor) {
  const select = document.getElementById("categoria-cartel");
  select.length = 1; // mantém "Todas"
  for (const c of categoriasDoGenero(genero)) select.add(new Option(CATEGORIAS[c], c));
  select.value = categoriasDoGenero(genero).includes(valor) ? valor : "";
}

async function iniciarCartel() {
  const secao = document.getElementById("cartel");
  try {
    const [cartelJson, tudo] = await Promise.all([
      fetch("dados/cartel.json", { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
      carregarLutadoresTudo(),
    ]);
    dadosCartel = cartelJson;
    const base = new Map(tudo.lutadores.map((l) => [l.nome, l]));
    // categoria (lutas em cada uma) e melhor posição na carreira, de lutas.json (já carregado pela página)
    const porCat = new Map();
    for (const luta of dadosLutas?.lutas || []) {
      if (!luta[1]) continue;
      for (const lado of [luta[8], luta[9]]) {
        const m = porCat.get(lado[0]) || new Map();
        m.set(luta[1], (m.get(luta[1]) || 0) + 1);
        porCat.set(lado[0], m);
      }
    }
    const melhor = melhoresPosicoes(dadosLutas);
    lutadoresCartel = dadosCartel.lutadores.map((c) => ({
      ...(base.get(c.nome) || { nome: c.nome }), porCat: porCat.get(c.nome), melhor: melhor.get(c.nome), c,
    }));
  } catch (erro) {
    console.error(erro);
    document.getElementById("tabela-cartel").innerHTML = '<tbody><tr><td class="vazio">Não foi possível carregar o índice de cartel.</td></tr></tbody>';
    return;
  }

  const preencher = (id, opcoes) => {
    const select = document.getElementById(id);
    for (const [valor, rotulo] of opcoes) select.add(new Option(rotulo, valor));
  };
  preencher("visao-cartel", Object.entries(VISOES_CARTEL).map(([k, v]) => [k, v.rotulo]));
  preencher("genero-cartel", Object.entries(GENEROS_CARTEL));
  const estado = ESTADO_INICIAL_CARTEL;
  document.getElementById("visao-cartel").value = estado.cv;
  document.getElementById("genero-cartel").value = estado.cg;
  preencherCategoriasCartel(estado.cg, estado.cc);
  document.getElementById("ativos-cartel").value = estado.ca;
  document.getElementById("tamanho-cartel").value = String(estado.ct);

  document.getElementById("genero-cartel").addEventListener("change", (e) => {
    preencherCategoriasCartel(e.target.value, document.getElementById("categoria-cartel").value);
    desenharCartel();
  });
  ["visao-cartel", "categoria-cartel", "ativos-cartel", "tamanho-cartel"].forEach((id) =>
    document.getElementById(id).addEventListener("change", desenharCartel));
  desenharCartel();
  if (location.hash === "#cartel") secao.scrollIntoView();
}

function desenharCartel() {
  const visao = VISOES_CARTEL[document.getElementById("visao-cartel").value];
  const genero = document.getElementById("genero-cartel").value;
  const categoria = document.getElementById("categoria-cartel").value;
  const soAtivos = document.getElementById("ativos-cartel").value === "sim";
  const tamanho = parseInt(document.getElementById("tamanho-cartel").value, 10);
  const limite = new Date(Date.now() - ATIVIDADE_DIAS * 864e5).toISOString().slice(0, 10);

  const elegiveis = lutadoresCartel
    .filter((l) => l.c.g === genero && l.c[visao.campo] != null && naCategoria(l, categoria) && (!soAtivos || l.c.ultima >= limite))
    // empate: mais lutas (amostra maior), depois o nome
    .sort((x, y) => y.c[visao.campo] - x.c[visao.campo] || y.c.n - x.c.n || x.nome.localeCompare(y.nome));
  const top = elegiveis.slice(0, tamanho);

  document.getElementById("intro-visao-cartel").textContent = visao.intro;
  desenharTabelaCartel(visao, top);

  const p = dadosCartel.parametros;
  const minimo = visao.minimo === "auge" ? p.janela_auge : p.min_lutas;
  const doPeso = categoria ? ` do ${CATEGORIAS[categoria].toLowerCase()}` : "";
  document.getElementById("nota-cartel").textContent =
    `${fmt0.format(elegiveis.length)} ${genero === "F" ? "lutadoras" : "lutadores"}${doPeso} com pelo menos ${minimo} lutas no UFC`
    + `${soAtivos ? ", que lutaram nos últimos 2 anos" : ""}. Elite = adversário com força de ${fmt0.format(p.elite)} ou mais (cerca de 5% das lutas). `
    + "Desclassificações e lutas sem resultado não contam. Categoria: quem lutou por último nela ou tem pelo menos "
    + `${LUTAS_NA_CATEGORIA} lutas nela. Só lutas do UFC: o cartel de outros eventos não entra.`;
  atualizarUrl();
}

const anoDe = (iso) => iso.slice(0, 4);
const intervaloAnos = (de, ate) => (anoDe(de) === anoDe(ate) ? anoDe(de) : `${anoDe(de)}–${anoDe(ate)}`);

// Adversário com a força (Elo do dia, com 25% do pico depois e ajuste de época) e o ano
function celulaAdversario(info) {
  const td = document.createElement("td");
  td.className = "col-adversario";
  if (!info) {
    td.textContent = "—";
    td.classList.add("vazio");
    return td;
  }
  const [nome, forca, data] = info;
  const sub = document.createElement("span");
  sub.className = "sub-lutador";
  sub.textContent = `força ${fmt0.format(forca)} · ${anoDe(data)}`;
  td.append(linkNome(nome), sub);
  return td;
}

function desenharTabelaCartel(visao, top) {
  const auge = visao.campo === "auge";
  const tabela = document.getElementById("tabela-cartel");
  tabela.innerHTML = `<caption class="visualmente-oculto">Índice de cartel: ${visao.rotulo}</caption>
    <thead><tr><th class="num">#</th><th>Lutador</th><th class="col-barra">${visao.rotulo}</th>
    ${auge
      ? '<th class="col-extra">Trecho</th><th class="num col-extra" title="Vitórias sobre adversários de elite dentro do trecho">Elite</th>'
      : '<th class="num col-extra" title="Vitórias sobre adversários de elite">Elite</th><th class="num col-extra" title="Força média dos adversários de todas as lutas">Força média</th><th class="col-adversario">Melhor vitória</th><th class="col-adversario">Pior derrota</th>'}
    <th class="col-cartel">Cartel</th></tr></thead>`;
  const corpo = document.createElement("tbody");
  const maximo = top.length ? top[0].c[visao.campo] : 0;
  top.forEach((l, i) => {
    const c = l.c;
    const valor = c[visao.campo];
    const linha = document.createElement("tr");
    linha.innerHTML = `<td class="num posicao">${i + 1}</td><td><div class="lutador-linha"></div></td>
      <td class="col-barra"><div class="barra-valor"><div class="barra"><span></span></div><strong></strong></div></td>`;
    linha.querySelector(".lutador-linha").append(avatar(l), identificacao(l));
    linha.querySelector(".barra span").style.width = `${maximo > 0 ? Math.max((valor / maximo) * 100, 1) : 0}%`;
    linha.querySelector(".barra-valor strong").textContent = visao.formato(valor);
    const celula = (texto, classe, titulo) => {
      const td = document.createElement("td");
      td.className = classe;
      td.textContent = texto;
      if (titulo) td.title = titulo;
      linha.appendChild(td);
    };
    if (auge) {
      const [de, ate, cartelTrecho, elite] = c.trecho;
      const td = document.createElement("td");
      td.className = "col-extra";
      const sub = document.createElement("span");
      sub.className = "sub-lutador";
      sub.textContent = cartelTrecho;
      td.append(intervaloAnos(de, ate), sub);
      linha.appendChild(td);
      celula(fmt0.format(elite), "num col-extra");
    } else {
      celula(fmt0.format(c.elite), "num col-extra");
      celula(fmt0.format(c.forca), "num col-extra");
      linha.append(celulaAdversario(c.melhor), celulaAdversario(c.pior));
    }
    // cartel oficial (lutadores.json, inclui DQ e NC) e, se diferente, o que conta no índice
    const oficial = l.w != null ? cartel(l) : c.cartel;
    celula(oficial, "col-cartel", oficial !== c.cartel ? `No índice: ${c.cartel} (sem desclassificações e lutas sem resultado)` : "");
    corpo.appendChild(linha);
  });
  if (!top.length) corpo.innerHTML = `<tr><td colspan="${auge ? 6 : 8}" class="vazio">Ninguém com esses filtros.</td></tr>`;
  tabela.appendChild(corpo);
}
