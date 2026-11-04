/* Gráficos do painel em SVG puro (sem biblioteca), no padrão do Lazer & Sport:
   números vêm prontos do servidor (core/painel.py); aqui só se desenha.
   Redesenha ao mudar o tamanho da tela para o texto ficar sempre legível. */
(function () {
    "use strict";
    const fonte = document.getElementById("dados-graficos");
    if (!fonte) return;
    const D = JSON.parse(fonte.textContent);
    const NS = "http://www.w3.org/2000/svg";
    const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
    const brl = v => BRL.format(v || 0);
    const curto = v => {
        const a = Math.abs(v);
        if (a >= 1e6) return "R$ " + (v / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mi";
        if (a >= 1e3) return "R$ " + (v / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mil";
        return "R$ " + Math.round(v).toLocaleString("pt-BR");
    };
    const COR = { receita: "#c9233c", custo: "#c7cfdc", lucro: "#167c5b", azul: "#286caf", verde: "#167c5b", ambar: "#b7791f", grade: "#e6e9f0", texto: "#667389" };

    function el(nome, attrs = {}, pai) {
        const n = document.createElementNS(NS, nome);
        for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
        if (pai) pai.appendChild(n);
        return n;
    }
    function texto(pai, x, y, conteudo, attrs = {}) {
        const t = el("text", { x, y, fill: COR.texto, "font-size": 11.5, "font-family": "Inter, system-ui, sans-serif", ...attrs }, pai);
        t.textContent = conteudo;
        return t;
    }
    function teto(max) {
        if (max <= 0) return 1;
        const bruto = max * 1.1;
        const pot = Math.pow(10, Math.floor(Math.log10(bruto)));
        const passo = [1, 2, 2.5, 5, 10].map(m => m * pot).find(p => bruto / p <= 4) || pot * 10;
        return Math.ceil(bruto / passo) * passo;
    }
    function vazio(caixa, mensagem) {
        caixa.innerHTML = `<div class="graf-vazio">${mensagem}</div>`;
    }

    /* ----------------------------------------------------- dica (tooltip) */
    const dica = document.createElement("div");
    dica.className = "graf-dica";
    dica.hidden = true;
    document.body.appendChild(dica);
    function mostrarDica(evento, html) {
        dica.innerHTML = html;
        dica.hidden = false;
        const largura = dica.offsetWidth, altura = dica.offsetHeight;
        let x = evento.clientX + 14, y = evento.clientY - altura - 10;
        if (x + largura > window.innerWidth - 8) x = evento.clientX - largura - 14;
        if (y < 8) y = evento.clientY + 16;
        dica.style.left = x + "px";
        dica.style.top = y + "px";
    }
    const esconderDica = () => { dica.hidden = true; };

    /* ------------------------------- barras duplas + linha (mensal) */
    function mensal(caixa) {
        const n = D.meses.length;
        const temDados = D.receita.some(v => v) || D.custo.some(v => v);
        if (!temDados) return vazio(caixa, "Ainda não há vendas no período. Aprove orçamentos ou receba pedidos e o gráfico aparece aqui.");
        const W = Math.max(320, caixa.clientWidth), H = parseInt(getComputedStyle(caixa).getPropertyValue("--altura")) || 300;
        const m = { e: W < 560 ? 46 : 64, d: 12, t: 14, b: 30 };
        const max = teto(Math.max(...D.receita, ...D.custo, ...D.lucro));
        const min = Math.min(0, ...D.lucro);
        const piso = min < 0 ? -teto(-min) : 0;
        const y = v => m.t + (H - m.t - m.b) * (1 - (v - piso) / (max - piso));
        const passo = (W - m.e - m.d) / n;
        const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": "Receita, custo e lucro por mês" });
        const defs = el("defs", {}, svg);
        const g = el("linearGradient", { id: "grad-receita", x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
        el("stop", { offset: "0%", "stop-color": "#e2384f" }, g);
        el("stop", { offset: "100%", "stop-color": "#a91830" }, g);
        const ga = el("linearGradient", { id: "grad-lucro", x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
        el("stop", { offset: "0%", "stop-color": COR.lucro, "stop-opacity": .22 }, ga);
        el("stop", { offset: "100%", "stop-color": COR.lucro, "stop-opacity": 0 }, ga);

        for (let i = 0; i <= 4; i++) {
            const v = piso + (max - piso) * i / 4;
            el("line", { x1: m.e, x2: W - m.d, y1: y(v), y2: y(v), stroke: COR.grade, "stroke-dasharray": v === 0 ? "" : "3 4" }, svg);
            texto(svg, m.e - 8, y(v) + 4, curto(v), { "text-anchor": "end" });
        }
        const largura = Math.min(26, passo * 0.32);
        const pulo = Math.ceil(n / Math.max(4, Math.floor((W - m.e) / 58)));
        D.meses.forEach((rotulo, i) => {
            const cx = m.e + passo * i + passo / 2;
            const zero = y(0);
            const hr = Math.max(D.receita[i] ? 2 : 0, zero - y(D.receita[i]));
            const hc = Math.max(D.custo[i] ? 2 : 0, zero - y(D.custo[i]));
            el("rect", { x: cx - largura - 1, y: zero - hr, width: largura, height: hr, rx: 4, fill: "url(#grad-receita)", class: "graf-barra" }, svg);
            el("rect", { x: cx + 1, y: zero - hc, width: largura, height: hc, rx: 4, fill: COR.custo, class: "graf-barra" }, svg);
            if (i % pulo === 0 || (i === n - 1 && (n - 1) % pulo >= Math.ceil(pulo / 2))) texto(svg, cx, H - 9, rotulo, { "text-anchor": "middle" });
        });
        const pontos = D.lucro.map((v, i) => [m.e + passo * i + passo / 2, y(v)]);
        el("path", { d: `M${pontos[0][0]},${y(0)} L` + pontos.map(p => p.join(",")).join(" L") + ` L${pontos[n - 1][0]},${y(0)} Z`, fill: "url(#grad-lucro)" }, svg);
        el("polyline", { points: pontos.map(p => p.join(",")).join(" "), fill: "none", stroke: COR.lucro, "stroke-width": 2.6, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
        pontos.forEach(([px, py]) => el("circle", { cx: px, cy: py, r: 3.6, fill: "#fff", stroke: COR.lucro, "stroke-width": 2 }, svg));

        // áreas invisíveis para a dica de cada mês
        const marca = el("line", { y1: m.t, y2: H - m.b, stroke: "#202b3e", "stroke-opacity": .12, "stroke-width": passo, visibility: "hidden" }, svg);
        D.meses.forEach((rotulo, i) => {
            const alvo = el("rect", { x: m.e + passo * i, y: m.t, width: passo, height: H - m.t - m.b, fill: "transparent" }, svg);
            alvo.addEventListener("mousemove", e => {
                marca.setAttribute("x1", m.e + passo * i + passo / 2);
                marca.setAttribute("x2", m.e + passo * i + passo / 2);
                marca.setAttribute("visibility", "visible");
                const margem = D.receita[i] ? Math.round(D.lucro[i] / D.receita[i] * 100) : 0;
                mostrarDica(e, `<strong>${rotulo}</strong><span><i style="background:${COR.receita}"></i>Receita <b>${brl(D.receita[i])}</b></span>
                    <span><i style="background:${COR.custo}"></i>Custo <b>${brl(D.custo[i])}</b></span>
                    <span><i style="background:${COR.lucro}"></i>Lucro <b>${brl(D.lucro[i])}</b></span>
                    <small>Margem ${margem}% · ${D.aprovados[i]} orçamento${D.aprovados[i] === 1 ? "" : "s"} aprovado${D.aprovados[i] === 1 ? "" : "s"}</small>`);
            });
            alvo.addEventListener("mouseleave", () => { marca.setAttribute("visibility", "hidden"); esconderDica(); });
        });
        caixa.replaceChildren(svg);
    }

    /* ------------------------------------------- barras horizontais */
    function horizontais(caixa, linhas, cores) {
        if (!linhas.length || !linhas.some(l => l.base > 0)) return false;
        const lista = document.createElement("div");
        lista.className = "graf-barras";
        const max = Math.max(...linhas.map(l => l.base), 1);
        linhas.forEach((l, i) => {
            const linha = document.createElement("div");
            linha.className = "graf-barras-linha";
            linha.innerHTML = `<div class="graf-barras-topo"><span>${l.nome}</span><b>${l.direita}</b></div>
                <div class="graf-barras-trilho"><span style="width:${Math.max(l.base ? 2 : 0, l.base / max * 100)}%;background:${cores[i % cores.length]}"></span></div>
                ${l.baixo ? `<small>${l.baixo}</small>` : ""}`;
            lista.appendChild(linha);
        });
        caixa.replaceChildren(lista);
        return true;
    }
    const CORES_FUNIL = { RASCUNHO: "#8a94a6", ENVIADO: "#286caf", APROVADO: "#167c5b", RECUSADO: "#c9233c", EXPIRADO: "#b7791f" };
    function funil(caixa) {
        const linhas = D.funil.map(f => ({ nome: f.nome, base: f.qtd, direita: `${f.qtd} · ${brl(f.valor)}` }));
        if (!horizontais(caixa, linhas, D.funil.map(f => CORES_FUNIL[f.chave] || "#8a94a6")))
            vazio(caixa, "Nenhum orçamento cadastrado ainda.");
    }
    function top(caixa) {
        const linhas = D.top.map(t => ({ nome: t.nome, base: t.valor, direita: brl(t.valor), baixo: `${t.qtd} unidade${t.qtd === 1 ? "" : "s"}` }));
        if (!horizontais(caixa, linhas, ["#c9233c", "#d8495d", "#e06a7b", "#e88a97", "#efa9b2", "#f4c4cb"]))
            vazio(caixa, "Os campeões aparecem quando houver vendas no período.");
    }

    /* --------------------------------------------------------- donut */
    function categorias(caixa) {
        const fatias = D.categorias;
        const total = fatias.reduce((s, f) => s + f.valor, 0);
        if (!total) return vazio(caixa, "Sem vendas por categoria no período.");
        const box = document.createElement("div");
        box.className = "graf-donut";
        const svg = el("svg", { viewBox: "0 0 42 42", width: 190, height: 190, role: "img", "aria-label": "Receita por categoria" });
        el("circle", { cx: 21, cy: 21, r: 15.915, fill: "none", stroke: "#eef1f6", "stroke-width": 6.5 }, svg);
        let acumulado = 0;
        fatias.forEach(f => {
            const pct = f.valor / total * 100;
            const arco = el("circle", { cx: 21, cy: 21, r: 15.915, fill: "none", stroke: f.cor, "stroke-width": 6.5,
                "stroke-dasharray": `${Math.max(0, pct - 0.6)} ${100 - Math.max(0, pct - 0.6)}`, "stroke-dashoffset": 25 - acumulado, class: "graf-fatia" }, svg);
            arco.addEventListener("mousemove", e => mostrarDica(e, `<strong>${f.nome}</strong><span><b>${brl(f.valor)}</b> · ${pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%</span>`));
            arco.addEventListener("mouseleave", esconderDica);
            acumulado += pct;
        });
        const centro = el("text", { x: 21, y: 20.2, "text-anchor": "middle", "font-size": 3.6, "font-weight": 800, fill: "#202b3e", "font-family": "Inter, system-ui, sans-serif" }, svg);
        centro.textContent = curto(total);
        const sub = el("text", { x: 21, y: 24.6, "text-anchor": "middle", "font-size": 2.4, fill: COR.texto, "font-family": "Inter, system-ui, sans-serif" }, svg);
        sub.textContent = "no período";
        box.appendChild(svg);
        const legenda = document.createElement("ul");
        legenda.className = "graf-donut-legenda";
        legenda.innerHTML = fatias.map(f => `<li><i style="background:${f.cor}"></i><span>${f.nome}</span><b>${(f.valor / total * 100).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%</b><small>${brl(f.valor)}</small></li>`).join("");
        box.appendChild(legenda);
        caixa.replaceChildren(box);
    }

    /* ---------------------------- comercial: colunas + linha de clientes */
    function comercial(caixa) {
        const n = D.meses.length;
        if (!D.criados.some(v => v) && !D.clientes.some(v => v)) return vazio(caixa, "Sem orçamentos ou cadastros no período.");
        const W = Math.max(300, caixa.clientWidth), H = parseInt(getComputedStyle(caixa).getPropertyValue("--altura")) || 230;
        const m = { e: 34, d: 34, t: 12, b: 28 };
        const max = teto(Math.max(...D.criados, ...D.aprovados, 1));
        const maxC = teto(Math.max(...D.clientes, 1));
        const passo = (W - m.e - m.d) / n;
        const y = v => m.t + (H - m.t - m.b) * (1 - v / max);
        const yc = v => m.t + (H - m.t - m.b) * (1 - v / maxC);
        const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": "Orçamentos criados e aprovados e novos clientes por mês" });
        for (let i = 0; i <= 3; i++) {
            const v = max * i / 3;
            el("line", { x1: m.e, x2: W - m.d, y1: y(v), y2: y(v), stroke: COR.grade, "stroke-dasharray": i ? "3 4" : "" }, svg);
            texto(svg, m.e - 6, y(v) + 4, Math.round(v), { "text-anchor": "end" });
            texto(svg, W - m.d + 6, y(v) + 4, Math.round(maxC * i / 3), { fill: COR.ambar });
        }
        const largura = Math.min(18, passo * 0.3);
        const pulo = Math.ceil(n / Math.max(4, Math.floor((W - m.e) / 58)));
        D.meses.forEach((rotulo, i) => {
            const cx = m.e + passo * i + passo / 2;
            el("rect", { x: cx - largura - 1, y: y(D.criados[i]), width: largura, height: y(0) - y(D.criados[i]), rx: 3, fill: COR.azul, opacity: .85 }, svg);
            el("rect", { x: cx + 1, y: y(D.aprovados[i]), width: largura, height: y(0) - y(D.aprovados[i]), rx: 3, fill: COR.verde }, svg);
            if (i % pulo === 0 || (i === n - 1 && (n - 1) % pulo >= Math.ceil(pulo / 2))) texto(svg, cx, H - 8, rotulo, { "text-anchor": "middle" });
        });
        const pontos = D.clientes.map((v, i) => [m.e + passo * i + passo / 2, yc(v)]);
        el("polyline", { points: pontos.map(p => p.join(",")).join(" "), fill: "none", stroke: COR.ambar, "stroke-width": 2.2, "stroke-dasharray": "0", "stroke-linejoin": "round" }, svg);
        pontos.forEach(([px, py]) => el("circle", { cx: px, cy: py, r: 3, fill: "#fff", stroke: COR.ambar, "stroke-width": 1.8 }, svg));
        D.meses.forEach((rotulo, i) => {
            const alvo = el("rect", { x: m.e + passo * i, y: m.t, width: passo, height: H - m.t - m.b, fill: "transparent" }, svg);
            alvo.addEventListener("mousemove", e => {
                const taxa = D.criados[i] ? Math.round(D.aprovados[i] / D.criados[i] * 100) : 0;
                mostrarDica(e, `<strong>${rotulo}</strong><span><i style="background:${COR.azul}"></i>Criados <b>${D.criados[i]}</b></span>
                <span><i style="background:${COR.verde}"></i>Aprovados <b>${D.aprovados[i]}</b></span>
                <span><i style="background:${COR.ambar}"></i>Novos clientes <b>${D.clientes[i]}</b></span><small>Aprovação ${taxa}%</small>`);
            });
            alvo.addEventListener("mouseleave", esconderDica);
        });
        caixa.replaceChildren(svg);
    }

    const DESENHOS = { mensal, funil, top, categorias, comercial };
    function desenharTudo() {
        document.querySelectorAll("[data-grafico]").forEach(caixa => {
            const f = DESENHOS[caixa.dataset.grafico];
            if (f) f(caixa);
        });
    }
    let relogio = null, larguraAnterior = window.innerWidth;
    window.addEventListener("resize", () => {
        if (window.innerWidth === larguraAnterior) return;
        larguraAnterior = window.innerWidth;
        clearTimeout(relogio);
        relogio = setTimeout(desenharTudo, 120);
    });
    window.addEventListener("scroll", esconderDica, { passive: true });
    desenharTudo();
})();
