/* ArtSkala — gestão: fotos menores antes de enviar.

   A Vercel recusa qualquer envio acima de ~4,5 MB (o site nem chega a ver o
   pedido). Fotos de celular passam disso fácil. Aqui, ao escolher as fotos
   num campo de imagem da gestão, as grandes são reduzidas no próprio
   navegador para até 2000 px (o mesmo tamanho que o site guarda), sem perder
   a nitidez que aparece no site. Se mesmo assim o envio ficar grande, avisa
   antes de salvar. window.akReduzirFoto(arquivo, limite) é usado também pela
   tela Restaurar fotos. */
(function () {
    "use strict";

    const LADO = 2000;
    const LIMITE_ENVIO = 4.3 * 1024 * 1024;     // folga sob os ~4,5 MB da Vercel
    const REDUZIR_ACIMA = 1.2 * 1024 * 1024;

    function paraBlob(canvas, tipo, qualidade) {
        return new Promise(function (ok) { canvas.toBlob(ok, tipo, qualidade); });
    }

    function trocarExtensao(nome, tipo) {
        const ext = tipo === "image/webp" ? ".webp" : ".jpg";
        return (nome.replace(/\.[^./\\]+$/, "") || "foto") + ext;
    }

    async function reduzirFoto(arquivo, limite) {
        limite = limite || REDUZIR_ACIMA;
        if (!arquivo || arquivo.size <= limite || !/^image\/(jpeg|png|webp|bmp|tiff?)$/i.test(arquivo.type || "")) return arquivo;
        if (!window.createImageBitmap) return arquivo;
        let bitmap;
        try {
            bitmap = await createImageBitmap(arquivo, { imageOrientation: "from-image" });
        } catch (erro) {
            return arquivo;                                    // o navegador não abre: vai como está
        }
        const escala = Math.min(1, LADO / Math.max(bitmap.width, bitmap.height));
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(bitmap.width * escala));
        canvas.height = Math.max(1, Math.round(bitmap.height * escala));
        canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
        if (bitmap.close) bitmap.close();
        let melhor = null;
        for (const [tipo, qualidade] of [["image/webp", 0.88], ["image/webp", 0.8], ["image/jpeg", 0.86], ["image/jpeg", 0.75]]) {
            const blob = await paraBlob(canvas, tipo, qualidade);
            if (!blob || blob.type !== tipo) continue;          // Safari antigo não gera WebP
            if (!melhor || blob.size < melhor.size) melhor = blob;
            if (blob.size <= limite) break;
        }
        if (!melhor || melhor.size >= arquivo.size) return arquivo;
        return new File([melhor], trocarExtensao(arquivo.name, melhor.type), { type: melhor.type, lastModified: Date.now() });
    }
    window.akReduzirFoto = reduzirFoto;

    function megas(bytes) { return (bytes / 1048576).toFixed(1).replace(".", ","); }

    function aviso(texto, tipo) {
        if (window.Gestao && window.Gestao.aviso) window.Gestao.aviso(texto, tipo || "info", 7000);
    }

    async function prepararCampo(campo) {
        const form = campo.form;
        const arquivos = Array.from(campo.files || []);
        if (!arquivos.length || typeof DataTransfer === "undefined") return;
        const grandes = arquivos.filter(function (a) { return a.size > REDUZIR_ACIMA; });
        if (!grandes.length) return verificarTotal(form);
        if (form) form.dataset.preparandoFotos = "1";
        const botoes = form ? Array.from(form.querySelectorAll("button[type=submit], input[type=submit]")) : [];
        botoes.forEach(function (b) { b.disabled = true; });
        aviso(grandes.length === 1 ? "Preparando a foto para enviar…" : "Preparando " + grandes.length + " fotos para enviar…");
        try {
            const novos = new DataTransfer();
            for (const arquivo of arquivos) novos.items.add(await reduzirFoto(arquivo));
            campo.files = novos.files;
        } catch (erro) {
            /* fica com os arquivos originais */
        } finally {
            if (form) delete form.dataset.preparandoFotos;
            botoes.forEach(function (b) { b.disabled = false; });
        }
        verificarTotal(form);
    }

    function totalDoFormulario(form) {
        let total = 0;
        if (!form) return 0;
        form.querySelectorAll("input[type=file]").forEach(function (c) {
            Array.from(c.files || []).forEach(function (a) { total += a.size; });
        });
        return total;
    }

    function verificarTotal(form) {
        const total = totalDoFormulario(form);
        if (total > LIMITE_ENVIO) {
            aviso("As fotos somam " + megas(total) + " MB e cada envio aceita até 4,5 MB. Salve com menos fotos e adicione o resto depois.", "erro");
            return false;
        }
        return true;
    }

    document.addEventListener("change", function (evento) {
        const campo = evento.target;
        if (!campo || campo.type !== "file" || campo.hasAttribute("data-sem-reduzir")) return;
        if (!/image/.test(campo.accept || "") || !campo.closest(".conteudo form")) return;
        prepararCampo(campo);
    });

    // Antes de enviar: espera as fotos ficarem prontas e não deixa passar do limite.
    document.addEventListener("submit", function (evento) {
        const form = evento.target;
        if (!form || !form.querySelector || !form.querySelector("input[type=file]")) return;
        if (form.dataset.preparandoFotos) {
            evento.preventDefault();
            evento.stopImmediatePropagation();
            aviso("Espere as fotos ficarem prontas e salve de novo.");
        } else if (!verificarTotal(form)) {
            evento.preventDefault();
            evento.stopImmediatePropagation();
        }
    }, true);
})();
