/* Etiquetas — monta as folhas em milímetros a partir dos itens marcados.
   A mesma montagem é a prévia na tela e o que sai na impressora. */
(function () {
    "use strict";
    const raiz = document.querySelector("[data-etiquetas]");
    if (!raiz) return;
    const $ = (s, r = raiz) => r.querySelector(s);
    const $$ = (s, r = raiz) => Array.from(r.querySelectorAll(s));
    const DADOS = JSON.parse(document.getElementById("dados-etiquetas").textContent);
    const PAPEL = { a4: [210, 297], carta: [215.9, 279.4] };
    const num = (v, padrao = 0) => {
        const n = parseFloat(String(v == null ? "" : v).replace(",", "."));
        return Number.isFinite(n) ? n : padrao;
    };
    const esc = t => String(t == null ? "" : t).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const fmt = n => String(Math.round(n * 10) / 10).replace(".", ",");

    const memoria = {
        ler(chave, padrao) { try { const v = localStorage.getItem("etq-" + chave); return v == null ? padrao : JSON.parse(v); } catch (e) { return padrao; } },
        gravar(chave, valor) { try { localStorage.setItem("etq-" + chave, JSON.stringify(valor)); } catch (e) { /* sem armazenamento */ } },
    };

    let tipo = DADOS.tipo;
    const marcados = { produto: new Map(), pedido: new Map(), orcamento: new Map(), projeto: new Map() };
    DADOS.selecionados.forEach(id => marcados[tipo] && marcados[tipo].set(id, 1));

    /* --------------------------------------------------------- modelos */
    const selModelo = $("[data-modelo]");
    DADOS.modelos.forEach(m => selModelo.add(new Option(m.nome, m.id)));
    const personalizado = memoria.ler("personalizado", { w: 63.5, h: 38.1, colunas: 3, linhas: 7, gx: 2.5, gy: 0, papel: "a4" });

    function modeloAtual() {
        const base = DADOS.modelos.find(m => m.id === selModelo.value) || DADOS.modelos[0];
        if (base.id !== "personalizado") return { ...base, papel: base.rolo ? "rolo" : "a4" };
        const m = { ...base, ...personalizado };
        m.w = Math.max(10, num(m.w, 63.5)); m.h = Math.max(8, num(m.h, 38.1));
        m.colunas = Math.max(1, Math.round(num(m.colunas, 1))); m.linhas = Math.max(1, Math.round(num(m.linhas, 1)));
        m.gx = Math.max(0, num(m.gx)); m.gy = Math.max(0, num(m.gy));
        if (m.papel === "rolo") { m.folha = [m.w, m.h]; m.colunas = 1; m.linhas = 1; m.rolo = true; }
        else m.folha = PAPEL[m.papel] || PAPEL.a4;
        return m;
    }

    /* ----------------------------------------------------------- lista */
    const lista = $("[data-lista]");
    function desenharLista() {
        const itens = DADOS.itens[tipo] || [];
        lista.innerHTML = "";
        if (!itens.length) {
            lista.innerHTML = '<li class="etq-vazio">Nada cadastrado deste tipo ainda.</li>';
            return;
        }
        const frag = document.createDocumentFragment();
        itens.forEach(item => {
            const li = document.createElement("li");
            const copias = marcados[tipo].get(item.id);
            li.dataset.id = item.id;
            li.dataset.busca = item.busca;
            li.className = copias ? "marcado" : "";
            const rotuloCopias = tipo === "pedido" ? "Volumes" : "Cópias";
            li.innerHTML = `<input type="checkbox" ${copias ? "checked" : ""} aria-label="Imprimir ${esc(item.titulo)}">
                <span class="etq-item-texto"><strong>${esc(item.titulo)}</strong><small>${esc(item.codigo)} · ${esc(item.lista || "")}</small></span>
                <input type="text" inputmode="numeric" class="etq-copias" value="${copias || 1}" ${copias ? "" : "disabled"} title="${rotuloCopias}" aria-label="${rotuloCopias}">`;
            frag.appendChild(li);
        });
        lista.appendChild(frag);
        filtrar();
    }
    lista.addEventListener("change", e => {
        const li = e.target.closest("li[data-id]");
        if (!li) return;
        const id = Number(li.dataset.id);
        const caixa = $("input[type=checkbox]", li), copias = $(".etq-copias", li);
        if (e.target === caixa) {
            if (caixa.checked) marcados[tipo].set(id, Math.max(1, Math.round(num(copias.value, 1))));
            else marcados[tipo].delete(id);
            li.classList.toggle("marcado", caixa.checked);
            copias.disabled = !caixa.checked;
        }
        if (e.target === copias && caixa.checked) {
            const n = Math.min(500, Math.max(1, Math.round(num(copias.value, 1))));
            copias.value = n;
            marcados[tipo].set(id, n);
        }
        montar();
    });
    lista.addEventListener("input", e => { if (e.target.classList.contains("etq-copias")) e.target.dispatchEvent(new Event("change", { bubbles: true })); });
    lista.addEventListener("click", e => {
        const texto = e.target.closest(".etq-item-texto");
        if (texto) { const caixa = $("input[type=checkbox]", texto.parentNode); caixa.checked = !caixa.checked; caixa.dispatchEvent(new Event("change", { bubbles: true })); }
    });

    const filtro = $("[data-filtro]");
    function filtrar() {
        const termo = filtro.value.trim().toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
        $$("li[data-id]", lista).forEach(li => {
            const busca = li.dataset.busca.normalize("NFD").replace(/[̀-ͯ]/g, "");
            li.hidden = termo && !busca.includes(termo);
        });
    }
    filtro.addEventListener("input", filtrar);
    $$("[data-marcar]").forEach(b => b.addEventListener("click", () => {
        const todos = b.dataset.marcar === "todos";
        $$("li[data-id]", lista).forEach(li => {
            if (li.hidden && todos) return;
            const caixa = $("input[type=checkbox]", li);
            if (caixa.checked !== todos) { caixa.checked = todos; caixa.dispatchEvent(new Event("change", { bubbles: true })); }
        });
    }));

    /* ------------------------------------------------------- conteúdo */
    const opcao = nome => { const el = $(`[data-opcao="${nome}"]`); return el ? el.checked : false; };
    const qr = (texto, legenda) => opcao("qr") && texto
        ? `<span class="etq-qr-bloco"><img class="etq-qr" alt="" src="${DADOS.qr}?d=${encodeURIComponent(texto)}">${legenda ? `<small>${esc(legenda)}</small>` : ""}</span>` : "";
    const marca = () => opcao("marca") ? '<span class="etq-marca">ArtSkala</span>' : "<span></span>";

    const DESENHOS = {
        produto(i) {
            const preco = opcao("preco")
                ? `<div class="etq-preco ${i.preco === "Sob consulta" ? "consulta" : ""}">${i.preco_de ? `<s>de ${esc(i.preco_de)}</s>` : ""}${esc(i.preco)}</div>` : "";
            return `<div class="etq-corpo"><div class="etq-topo">${marca()}<span class="etq-cod">${esc(i.codigo)}</span></div>
                <div class="etq-titulo">${esc(i.titulo)}</div><div class="etq-sub">${esc(i.linha)}</div>${preco}</div>${qr(i.qr, "ver no site")}`;
        },
        pedido(i, volume, total) {
            const r = DADOS.remetente;
            return `<div class="etq-corpo"><div class="etq-faixa"><span>Destinatário</span><span>${esc(i.codigo)}</span></div>
                <div class="etq-nome">${esc(i.titulo)}</div>
                <div class="etq-end">${esc(i.endereco || "Endereço não informado")}</div>
                ${i.cidade || i.cep ? `<div class="etq-linha">${esc([i.cidade, i.cep && "CEP " + i.cep].filter(Boolean).join(" · "))}</div>` : ""}
                ${i.telefone ? `<div class="etq-linha"><b>Tel.</b> ${esc(i.telefone)}</div>` : ""}
                <div class="etq-rodape"><span>Pedido #${i.id} · ${esc(i.itens)} · ${esc(i.data)}</span>${total > 1 ? `<span class="etq-volume">Volume ${volume}/${total}</span>` : ""}</div>
                ${opcao("remetente") ? `<div class="etq-remetente"><b>Remetente:</b> ${esc(r.nome)} · ${esc(r.endereco)} · ${esc(r.cidade)} · ${esc(r.telefone)}</div>` : ""}
                </div>${qr(i.qr, "")}`;
        },
        orcamento(i) {
            const itens = (i.itens || []).map(t => `<li>${esc(t)}</li>`).join("");
            return `<div class="etq-corpo"><div class="etq-faixa"><span>Ordem de produção</span><span>${esc(i.codigo)}</span></div>
                <div class="etq-titulo">${esc(i.titulo)}</div>
                <div class="etq-linha"><b>Cliente:</b> ${esc(i.cliente || "—")}${i.telefone ? " · " + esc(i.telefone) : ""}</div>
                ${i.entrega ? `<div class="etq-linha"><b>Entrega:</b> ${esc(i.entrega)}</div>` : ""}
                ${itens ? `<ul class="etq-itens">${itens}</ul>` : ""}
                <div class="etq-rodape"><span>${esc(i.status)}</span>${opcao("marca") ? "<span>ArtSkala</span>" : ""}</div></div>${qr(i.qr, "")}`;
        },
        projeto(i) {
            return `<div class="etq-corpo"><div class="etq-topo">${marca()}<span class="etq-cod">${esc(i.codigo)}</span></div>
                <div class="etq-titulo">${esc(i.titulo)}</div><div class="etq-sub">${esc(i.cliente || "")}</div>
                ${i.data ? `<div class="etq-linha">Execução: ${esc(i.data)}</div>` : ""}</div>${qr(i.qr, "ver no site")}`;
        },
        livre(i) {
            const [primeira, ...resto] = i.linhas;
            return `<div class="etq-corpo" style="justify-content:center">${opcao("marca") ? '<div class="etq-topo"><span class="etq-marca">ArtSkala</span></div>' : ""}
                <div class="etq-livre-1">${esc(primeira || "")}</div>${resto.map(l => `<div class="etq-livre-n">${esc(l)}</div>`).join("")}</div>${qr(i.qr, "")}`;
        },
    };

    function etiquetasPedidas() {
        const saida = [];
        if (tipo === "livre") {
            const blocos = $("[data-livre-texto]").value.split(/\n\s*\n/).map(b => b.split("\n").map(l => l.trim()).filter(Boolean)).filter(b => b.length);
            const copias = Math.min(500, Math.max(1, Math.round(num($("[data-livre-copias]").value, 1))));
            const link = $("[data-livre-qr]").value.trim();
            blocos.forEach(linhas => { for (let c = 0; c < copias; c++) saida.push(DESENHOS.livre({ linhas, qr: link })); });
            return saida;
        }
        (DADOS.itens[tipo] || []).forEach(item => {
            const copias = marcados[tipo].get(item.id);
            for (let c = 1; c <= (copias || 0); c++) saida.push(DESENHOS[tipo](item, c, copias));
        });
        return saida;
    }

    /* ---------------------------------------------------------- montar */
    const folhas = $("[data-folhas]");
    const estiloPagina = document.getElementById("etq-pagina-print");

    function montar() {
        const m = modeloAtual();
        const [W, H] = m.folha;
        const porFolha = m.colunas * m.linhas;
        const inicio = Math.min(porFolha, Math.max(1, Math.round(num($("[data-inicio]").value, 1)))) - 1;
        const ax = num($('[data-ajuste="x"]').value), ay = num($('[data-ajuste="y"]').value);
        const ml = (W - m.colunas * m.w - (m.colunas - 1) * m.gx) / 2 + ax;
        const mt = (H - m.linhas * m.h - (m.linhas - 1) * m.gy) / 2 + ay;
        const etiquetas = etiquetasPedidas();
        const total = etiquetas.length;

        // mini (preço pequeno) · larga (QR ao lado) · alta (QR embaixo) · + grande (letras maiores)
        const base = m.h <= 26 || m.w <= 42 ? "mini" : (m.h / m.w >= 1.15 ? "alta" : "larga");
        const grande = m.w >= 90 && m.h >= 55;
        const formato = base + (grande ? " etq--grande" : "");
        const qrTam = Math.max(8, Math.min(m.h - 6, m.w * (base === "alta" ? 0.38 : 0.3), grande ? 34 : 24));

        estiloPagina.textContent = `@media print { @page { size: ${W}mm ${H}mm; margin: 0; } }`;
        folhas.classList.toggle("com-corte", opcao("corte"));
        folhas.innerHTML = "";
        if (!total) { atualizarResumo(0, 0, m); return; }

        const ocupadas = inicio + total;
        const nFolhas = m.rolo ? total : Math.ceil(ocupadas / porFolha);
        const frag = document.createDocumentFragment();
        for (let f = 0; f < nFolhas; f++) {
            const folha = document.createElement("div");
            folha.className = "etq-folha";
            folha.style.width = W + "mm";
            folha.style.height = H + "mm";
            let html = "";
            for (let p = 0; p < porFolha; p++) {
                const indice = m.rolo ? f - inicio : f * porFolha + p - inicio;
                const col = p % m.colunas, lin = Math.floor(p / m.colunas);
                const pos = `left:${ml + col * (m.w + m.gx)}mm;top:${mt + lin * (m.h + m.gy)}mm;width:${m.w}mm;height:${m.h}mm;`;
                if (m.rolo && f < inicio) continue;
                if (indice >= 0 && indice < total) html += `<div class="etq etq--${formato}" style="${pos}--qr:${qrTam}mm">${etiquetas[indice]}</div>`;
                else if (!m.rolo) html += `<div class="etq-pos-vazia" style="${pos}"></div>`;
            }
            if (m.rolo && f < inicio) continue;
            folha.innerHTML = html;
            frag.appendChild(folha);
        }
        folhas.appendChild(frag);
        ajustarZoom();
        atualizarResumo(total, folhas.children.length, m);
    }

    function atualizarResumo(total, nFolhas, m) {
        const botao = $("[data-imprimir]");
        botao.disabled = !total;
        const unidade = m.rolo ? (nFolhas === 1 ? "etiqueta no rolo" : "etiquetas no rolo") : (nFolhas === 1 ? "folha" : "folhas");
        $("[data-resumo]").textContent = total
            ? `${total} etiqueta${total > 1 ? "s" : ""} · ${m.rolo ? total + " " + unidade : nFolhas + " " + unidade}`
            : "Nenhuma etiqueta marcada.";
        $("[data-previa-info]").textContent = `${fmt(m.w)} × ${fmt(m.h)} mm · ${m.rolo ? "rolo" : m.colunas * m.linhas + " por folha"}`;
    }

    function ajustarZoom() {
        const m = modeloAtual();
        const larguraPx = m.folha[0] * 96 / 25.4;
        const disponivel = folhas.clientWidth - 36;
        const zoom = Math.max(0.3, Math.min(m.rolo ? 2.2 : 1, disponivel / larguraPx));
        folhas.style.setProperty("--zoom", zoom.toFixed(3));
    }
    window.addEventListener("resize", ajustarZoom);

    /* ------------------------------------------------------- controles */
    function trocarTipo(novo) {
        tipo = novo;
        $$(".etq-tipo").forEach(b => { const ativo = b.dataset.tipo === tipo; b.classList.toggle("ativo", ativo); b.setAttribute("aria-selected", String(ativo)); });
        $("[data-bloco-itens]").hidden = tipo === "livre";
        $("[data-bloco-livre]").hidden = tipo !== "livre";
        $$("[data-so-tipo]").forEach(el => { el.hidden = el.dataset.soTipo !== tipo; });
        selModelo.value = memoria.ler("modelo-" + tipo, DADOS.padrao[tipo]);
        if (!selModelo.value) selModelo.value = DADOS.padrao[tipo];
        mostrarPersonalizado();
        filtro.value = "";
        desenharLista();
        montar();
        const url = new URL(window.location.href);
        url.searchParams.set("tipo", tipo);
        url.searchParams.delete("ids");
        history.replaceState(null, "", url);
    }
    $$(".etq-tipo").forEach(b => b.addEventListener("click", () => trocarTipo(b.dataset.tipo)));

    function mostrarPersonalizado() {
        const eh = selModelo.value === "personalizado";
        $("[data-personalizado]").hidden = !eh;
        if (eh) $$("[data-medida]").forEach(c => { c.value = String(personalizado[c.dataset.medida]).replace(".", ","); });
    }
    selModelo.addEventListener("change", () => { memoria.gravar("modelo-" + tipo, selModelo.value); mostrarPersonalizado(); montar(); });
    $$("[data-medida]").forEach(c => c.addEventListener("input", () => {
        personalizado[c.dataset.medida] = c.tagName === "SELECT" ? c.value : num(c.value, personalizado[c.dataset.medida]);
        memoria.gravar("personalizado", personalizado);
        montar();
    }));
    $$("[data-inicio], [data-ajuste], [data-livre-texto], [data-livre-copias], [data-livre-qr]").forEach(c => c.addEventListener("input", montar));
    $$("[data-opcao]").forEach(c => {
        c.checked = memoria.ler("opcao-" + c.dataset.opcao, c.checked);
        c.addEventListener("change", () => { memoria.gravar("opcao-" + c.dataset.opcao, c.checked); montar(); });
    });

    $("[data-imprimir]").addEventListener("click", () => {
        const imagens = $$("img", folhas);
        const prontas = imagens.map(img => img.complete ? Promise.resolve() : new Promise(ok => { img.onload = img.onerror = ok; }));
        const botao = $("[data-imprimir]");
        botao.disabled = true;
        botao.textContent = "Preparando…";
        Promise.race([Promise.all(prontas), new Promise(ok => setTimeout(ok, 6000))]).then(() => {
            botao.disabled = false;
            botao.textContent = "Imprimir etiquetas";
            window.print();
        });
    });

    trocarTipo(tipo);
})();
