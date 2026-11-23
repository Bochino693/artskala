/* ArtSkala — Gestão > Restaurar fotos.

   O dono escolhe o ZIP baixado do Cloudinary (ou as fotos soltas, ou a pasta
   extraída). O ZIP é aberto aqui mesmo, no navegador (DecompressionStream,
   sem biblioteca de fora), e cada foto vai num pedido separado: a Vercel
   aceita no máximo ~4,5 MB por pedido. Fotos maiores são reduzidas antes
   (envio-fotos.js). O servidor acha, pelo nome, a foto do site que usa cada
   arquivo e responde o que aconteceu. */
(function () {
    "use strict";

    const zona = document.getElementById("rf-zona");
    if (!zona) return;
    const ENDERECO = zona.dataset.endereco;
    const LIMITE = Number(zona.dataset.limite) || 4.5 * 1024 * 1024;
    const csrf = (zona.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";
    const progresso = document.getElementById("rf-progresso");
    const barra = progresso.querySelector(".rf-barra span");
    const status = document.getElementById("rf-status");
    const lista = document.getElementById("rf-lista");
    const fim = document.getElementById("rf-fim");
    const FOTO = /\.(jpe?g|png|webp|gif|avif|bmp|tiff?)$/i;
    const TIPOS = { jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", webp: "image/webp", gif: "image/gif",
                    avif: "image/avif", bmp: "image/bmp", tif: "image/tiff", tiff: "image/tiff" };
    const contas = { restaurada: 0, ja_restaurada: 0, sem_referencia: 0, ambigua: 0, erro: 0 };
    let total = 0, feitos = 0, ocupado = false;

    function ehFoto(caminho) {
        const partes = caminho.split("/");
        if (partes.some(function (p) { return p.toLowerCase() === "__macosx" || p.indexOf("._") === 0; })) return false;
        return FOTO.test(caminho);
    }

    function tipoPeloNome(nome) {
        const ext = (nome.split(".").pop() || "").toLowerCase();
        return TIPOS[ext] || "application/octet-stream";
    }

    /* ---------------------------------------------- ZIP (leitura no navegador) */
    async function bytes(arquivo, inicio, fimByte) {
        return new DataView(await arquivo.slice(inicio, fimByte).arrayBuffer());
    }

    async function entradasDoZip(arquivo) {
        const tamanho = arquivo.size;
        const cauda = Math.min(tamanho, 65535 + 22 + 20);
        const fimDados = await bytes(arquivo, tamanho - cauda, tamanho);
        let eocd = -1;
        for (let i = fimDados.byteLength - 22; i >= 0; i--) {
            if (fimDados.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
        }
        if (eocd < 0) throw new Error("não parece um ZIP");
        let quantas = fimDados.getUint16(eocd + 10, true);
        let tamCentral = fimDados.getUint32(eocd + 12, true);
        let iniCentral = fimDados.getUint32(eocd + 16, true);
        if (quantas === 0xffff || tamCentral === 0xffffffff || iniCentral === 0xffffffff) {   // ZIP64
            const loc = eocd - 20;
            if (loc >= 0 && fimDados.getUint32(loc, true) === 0x07064b50) {
                const pos = Number(fimDados.getBigUint64(loc + 8, true));
                const z = await bytes(arquivo, pos, pos + 56);
                if (z.getUint32(0, true) === 0x06064b50) {
                    quantas = Number(z.getBigUint64(32, true));
                    tamCentral = Number(z.getBigUint64(40, true));
                    iniCentral = Number(z.getBigUint64(48, true));
                }
            }
        }
        const central = await bytes(arquivo, iniCentral, iniCentral + tamCentral);
        const utf8 = new TextDecoder("utf-8");
        const entradas = [];
        let p = 0;
        for (let n = 0; n < quantas && p + 46 <= central.byteLength; n++) {
            if (central.getUint32(p, true) !== 0x02014b50) break;
            const flags = central.getUint16(p + 8, true);
            const metodo = central.getUint16(p + 10, true);
            let comprimido = central.getUint32(p + 20, true);
            let original = central.getUint32(p + 24, true);
            const tamNome = central.getUint16(p + 28, true);
            const tamExtra = central.getUint16(p + 30, true);
            const tamComentario = central.getUint16(p + 32, true);
            let local = central.getUint32(p + 42, true);
            const nome = utf8.decode(new Uint8Array(central.buffer, central.byteOffset + p + 46, tamNome));
            let e = p + 46 + tamNome;
            const fimExtra = e + tamExtra;
            while (e + 4 <= fimExtra) {
                const id = central.getUint16(e, true), tam = central.getUint16(e + 2, true);
                if (id === 0x0001) {                           // tamanhos de ZIP64
                    let q = e + 4;
                    if (original === 0xffffffff) { original = Number(central.getBigUint64(q, true)); q += 8; }
                    if (comprimido === 0xffffffff) { comprimido = Number(central.getBigUint64(q, true)); q += 8; }
                    if (local === 0xffffffff) { local = Number(central.getBigUint64(q, true)); }
                }
                e += 4 + tam;
            }
            if (!nome.endsWith("/")) entradas.push({ nome: nome, metodo: metodo, comprimido: comprimido, original: original, local: local, cifrado: !!(flags & 1) });
            p = fimExtra + tamComentario;
        }
        return entradas;
    }

    async function extrair(arquivo, entrada) {
        if (entrada.cifrado) throw new Error("ZIP com senha");
        const cab = await bytes(arquivo, entrada.local, entrada.local + 30);
        if (cab.getUint32(0, true) !== 0x04034b50) throw new Error("entrada corrompida no ZIP");
        const inicio = entrada.local + 30 + cab.getUint16(26, true) + cab.getUint16(28, true);
        const dados = arquivo.slice(inicio, inicio + entrada.comprimido);
        const tipo = tipoPeloNome(entrada.nome);
        if (entrada.metodo === 0) return new Blob([dados], { type: tipo });
        if (entrada.metodo === 8) {
            if (typeof DecompressionStream === "undefined") throw new Error("este navegador não abre ZIP: extraia e escolha as fotos");
            const aberto = await new Response(dados.stream().pipeThrough(new DecompressionStream("deflate-raw"))).blob();
            return new Blob([aberto], { type: tipo });
        }
        throw new Error("compressão do ZIP não suportada (extraia e escolha as fotos)");
    }

    /* ------------------------------------------------------------- envio */
    function linha(caminho, texto, classe) {
        const li = document.createElement("li");
        const nome = document.createElement("code");
        nome.textContent = caminho;
        const res = document.createElement("span");
        res.className = classe;
        res.textContent = texto;
        li.append(nome, res);
        lista.prepend(li);
    }

    function atualizar() {
        barra.style.width = (total ? Math.round(feitos * 100 / total) : 0) + "%";
        status.textContent = feitos < total ? "Enviando " + feitos + " de " + total + "…" : "Pronto: " + total + " arquivo(s) conferidos.";
        Object.keys(contas).forEach(function (chave) {
            const alvo = progresso.querySelector('[data-conta="' + chave + '"]');
            if (alvo) alvo.textContent = contas[chave];
        });
    }

    async function enviar(caminho, blob) {
        let arquivo = blob instanceof File ? blob : new File([blob], caminho.split("/").pop(), { type: blob.type });
        if (arquivo.size > LIMITE * 0.95 && window.akReduzirFoto) arquivo = await window.akReduzirFoto(arquivo, LIMITE * 0.9);
        if (arquivo.size > LIMITE) throw new Error("grande demais para enviar (" + (arquivo.size / 1048576).toFixed(1) + " MB)");
        const dados = new FormData();
        dados.append("acao", "arquivo");
        dados.append("caminho", caminho);
        dados.append("arquivo", arquivo, arquivo.name);
        let tentativa = 0;
        for (;;) {
            try {
                const resposta = await fetch(ENDERECO, {
                    method: "POST", body: dados, credentials: "same-origin",
                    headers: { "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" },
                });
                let json = {};
                try { json = await resposta.json(); } catch (e) { /* resposta sem JSON */ }
                if (resposta.status === 413) throw new Error("grande demais para a Vercel");
                if (!resposta.ok && resposta.status >= 500 && tentativa < 2) throw Object.assign(new Error(json.erro || "o site não respondeu"), { repetir: true });
                if (!resposta.ok && !json.situacao) throw new Error(json.erro || ("o site respondeu " + resposta.status));
                return json;
            } catch (erro) {
                if (!erro.repetir && !(erro instanceof TypeError) || tentativa >= 2) throw erro;
                tentativa += 1;
                await new Promise(function (ok) { setTimeout(ok, 1500 * tentativa); });
            }
        }
    }

    async function processar(tarefa) {
        try {
            const blob = await tarefa.obter();
            const json = await enviar(tarefa.caminho, blob);
            const situacao = json.situacao || "erro";
            contas[situacao] = (contas[situacao] || 0) + 1;
            linha(tarefa.caminho, json.texto || json.erro || situacao,
                  situacao === "restaurada" ? "ok" : situacao === "erro" ? "erro" : "alerta");
            if (typeof json.faltando === "number") {
                const cartao = document.querySelector("[data-faltando]");
                if (cartao) cartao.textContent = json.faltando;
            }
        } catch (erro) {
            contas.erro += 1;
            linha(tarefa.caminho, "erro: " + (erro.message || erro), "erro");
        }
        feitos += 1;
        atualizar();
    }

    async function executar(tarefas) {
        if (ocupado) { window.Gestao && Gestao.aviso("Espere terminar o envio atual.", "info"); return; }
        ocupado = true;
        total += tarefas.length;
        progresso.hidden = false;
        fim.hidden = true;
        atualizar();
        const fila = tarefas.slice();
        async function trabalhador() { while (fila.length) await processar(fila.shift()); }
        await Promise.all([trabalhador(), trabalhador(), trabalhador()]);
        ocupado = false;
        fim.hidden = false;
        if (window.Gestao) Gestao.aviso(contas.restaurada + " foto(s) restaurada(s).", contas.restaurada ? "ok" : "info");
    }

    async function tarefasDe(arquivos) {
        const tarefas = [];
        for (const arquivo of arquivos) {
            const caminho = (arquivo.webkitRelativePath || arquivo.name).replace(/\\/g, "/");
            if (/\.zip$/i.test(arquivo.name)) {
                try {
                    const entradas = await entradasDoZip(arquivo);
                    entradas.filter(function (e) { return ehFoto(e.nome); }).forEach(function (entrada) {
                        tarefas.push({ caminho: entrada.nome, obter: function () { return extrair(arquivo, entrada); } });
                    });
                } catch (erro) {
                    progresso.hidden = false;
                    contas.erro += 1;
                    linha(caminho, "não consegui abrir o ZIP: " + (erro.message || erro), "erro");
                }
            } else if (ehFoto(caminho)) {
                tarefas.push({ caminho: caminho, obter: function () { return Promise.resolve(arquivo); } });
            }
        }
        return tarefas;
    }

    async function receber(arquivos) {
        const tarefas = await tarefasDe(Array.from(arquivos || []));
        if (!tarefas.length) {
            if (window.Gestao) Gestao.aviso("Nenhuma foto encontrada (JPG, PNG, WebP ou GIF, soltas ou num ZIP).", "erro");
            return;
        }
        executar(tarefas);
    }

    ["rf-arquivos", "rf-pasta"].forEach(function (id) {
        const campo = document.getElementById(id);
        campo.addEventListener("change", function () { receber(campo.files); campo.value = ""; });
    });
    ["dragenter", "dragover"].forEach(function (tipo) {
        zona.addEventListener(tipo, function (e) { e.preventDefault(); zona.classList.add("arrastando"); });
    });
    ["dragleave", "drop"].forEach(function (tipo) {
        zona.addEventListener(tipo, function (e) { e.preventDefault(); zona.classList.remove("arrastando"); });
    });
    zona.addEventListener("drop", function (e) { receber(e.dataTransfer && e.dataTransfer.files); });

    window.akRestaurarFotos = { entradasDoZip: entradasDoZip, extrair: extrair };
})();
