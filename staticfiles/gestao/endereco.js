/* Endereço do orçamento: CEP -> endereço (ViaCEP), rua -> CEP (ViaCEP),
   endereço -> ponto no mapa (OpenStreetMap/Nominatim) e distância de carro
   até a ArtSkala (OSRM). Tudo direto do navegador, sem chave de API.
   Se a rota falhar, mostra a distância em linha reta (aproximada). */
(function () {
    "use strict";
    const caixa = document.querySelector("[data-endereco]");
    if (!caixa) return;
    const form = caixa.closest("form");
    const $ = s => caixa.querySelector(s);
    const campo = nome => form.elements[nome];
    const G = window.Gestao;
    const esc = t => String(t == null ? "" : t).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const km = n => (Math.round(n * 10) / 10).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    const memoria = {
        ler(k, p) { try { const v = localStorage.getItem(k); return v == null ? p : JSON.parse(v); } catch (e) { return p; } },
        gravar(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* */ } },
    };
    const caixaDistancia = $("[data-distancia]");
    const linkRota = $("[data-link-rota]");

    function definir(nome, valor, sobrescrever = true) {
        const el = campo(nome);
        if (!el || valor == null || valor === "") return;
        if (!sobrescrever && el.value.trim()) return;
        el.value = valor;
        el.dispatchEvent(new Event("input", { bubbles: true }));
    }
    function aviso(html, classe = "distancia-vazia") { caixaDistancia.innerHTML = `<div class="${classe}">${html}</div>`; }

    /* ------------------------------------------------- CEP -> endereço */
    let ultimoCep = (campo("cep").value || "").replace(/\D/g, "");
    function buscarCep() {
        const cep = campo("cep").value.replace(/\D/g, "");
        if (cep.length !== 8 || cep === ultimoCep) return;
        ultimoCep = cep;
        aviso("Buscando o endereço do CEP…");
        fetch(`https://viacep.com.br/ws/${cep}/json/`)
            .then(r => r.json())
            .then(d => {
                if (d.erro) { aviso("CEP não encontrado. Confira os números ou procure pela rua."); return; }
                definir("endereco", d.logradouro);
                definir("bairro", d.bairro);
                definir("cidade", d.localidade);
                definir("uf", d.uf);
                if (d.complemento && !campo("complemento").value) campo("complemento").placeholder = d.complemento;
                const numero = campo("numero");
                if (!numero.value) { aviso("Endereço encontrado. Coloque o <b>número</b> para calcular a distância exata."); numero.focus(); }
                else calcular();
            })
            .catch(() => aviso("Não deu para consultar o CEP agora (sem internet?). Preencha à mão."));
    }
    campo("cep").addEventListener("input", buscarCep);
    campo("numero").addEventListener("change", () => calcular());

    /* --------------------------------------------------- rua -> CEP */
    const resultadoRuas = $("[data-resultado-ruas]");
    $("[data-procurar-rua]").addEventListener("click", () => {
        const rua = campo("endereco").value.trim().replace(/^(rua|r\.|avenida|av\.?)\s+/i, "");
        const cidade = campo("cidade").value.trim() || "São Paulo";
        const uf = (campo("uf").value.trim() || "SP").toUpperCase();
        resultadoRuas.hidden = false;
        if (rua.length < 3) {
            resultadoRuas.innerHTML = '<p class="dica-campo">Escreva pelo menos 3 letras do nome da rua no campo "Rua / avenida" e a cidade.</p>';
            campo("endereco").focus();
            return;
        }
        resultadoRuas.innerHTML = '<p class="dica-campo">Procurando…</p>';
        fetch(`https://viacep.com.br/ws/${encodeURIComponent(uf)}/${encodeURIComponent(cidade)}/${encodeURIComponent(rua)}/json/`)
            .then(r => r.json())
            .then(lista => {
                if (!Array.isArray(lista) || !lista.length) {
                    resultadoRuas.innerHTML = `<p class="dica-campo">Nenhuma rua "${esc(rua)}" em ${esc(cidade)}/${esc(uf)}. Confira o nome e a cidade.</p>`;
                    return;
                }
                resultadoRuas.innerHTML = `<p class="dica-campo">${lista.length} resultado${lista.length > 1 ? "s" : ""}: escolha o certo (a faixa de números aparece ao lado).</p>` +
                    '<ul class="ruas">' + lista.slice(0, 30).map((d, i) =>
                        `<li><button type="button" data-rua="${i}"><strong>${esc(d.logradouro)}</strong><span>${esc([d.complemento, d.bairro, d.localidade + "/" + d.uf].filter(Boolean).join(" · "))}</span><code>${esc(d.cep)}</code></button></li>`
                    ).join("") + "</ul>";
                resultadoRuas.querySelectorAll("[data-rua]").forEach(b => b.addEventListener("click", () => {
                    const d = lista[Number(b.dataset.rua)];
                    ultimoCep = d.cep.replace(/\D/g, "");
                    definir("cep", d.cep);
                    definir("endereco", d.logradouro);
                    definir("bairro", d.bairro);
                    definir("cidade", d.localidade);
                    definir("uf", d.uf);
                    resultadoRuas.hidden = true;
                    if (!campo("numero").value) { aviso("Rua escolhida. Coloque o <b>número</b> para calcular a distância."); campo("numero").focus(); }
                    else calcular();
                }));
            })
            .catch(() => { resultadoRuas.innerHTML = '<p class="dica-campo">Não deu para procurar agora. Tente de novo em instantes.</p>'; });
    });

    /* ------------------------------------------- endereço -> mapa */
    const textoEndereco = () => [
        [campo("endereco").value, campo("numero").value].filter(Boolean).join(", "),
        campo("bairro").value, [campo("cidade").value, campo("uf").value].filter(Boolean).join(" - "), "Brasil",
    ].filter(Boolean).join(", ");

    function geocodificar(parametros) {
        const url = "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=br&accept-language=pt-BR&" + new URLSearchParams(parametros);
        return fetch(url, { headers: { Accept: "application/json" } })
            .then(r => r.json())
            .then(l => (l && l[0] ? { lat: parseFloat(l[0].lat), lng: parseFloat(l[0].lon), nome: l[0].display_name } : null));
    }
    function pontoDoCliente() {
        const rua = [campo("numero").value, campo("endereco").value].filter(Boolean).join(" ");
        const cidade = campo("cidade").value, uf = campo("uf").value, cep = campo("cep").value;
        const tentativas = [];
        if (campo("endereco").value) tentativas.push({ street: rua, city: cidade, state: uf, country: "Brasil" });
        if (campo("endereco").value) tentativas.push({ q: textoEndereco() });
        if (cep.replace(/\D/g, "").length === 8) tentativas.push({ postalcode: cep, country: "Brasil" });
        if (campo("bairro").value) tentativas.push({ q: [campo("bairro").value, cidade, uf, "Brasil"].join(", ") });
        const proxima = i => (i >= tentativas.length ? Promise.resolve(null)
            : geocodificar(tentativas[i]).then(p => p || proxima(i + 1)).catch(() => proxima(i + 1)));
        return proxima(0);
    }
    function pontoDaLoja() {
        const lat = parseFloat(caixa.dataset.origemLat), lng = parseFloat(caixa.dataset.origemLng);
        if (Number.isFinite(lat) && Number.isFinite(lng)) return Promise.resolve({ lat, lng });
        const guardado = memoria.ler("ak-origem", null);
        if (guardado && guardado.endereco === caixa.dataset.origemEndereco) return Promise.resolve(guardado);
        return geocodificar({ q: caixa.dataset.origemEndereco + ", Brasil" }).then(p => {
            if (p) memoria.gravar("ak-origem", { ...p, endereco: caixa.dataset.origemEndereco });
            return p;
        });
    }
    function linhaReta(a, b) {
        const R = 6371, rad = x => x * Math.PI / 180;
        const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
        const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
        return 2 * R * Math.asin(Math.sqrt(h));
    }
    function rota(a, b) {
        return fetch(`https://router.project-osrm.org/route/v1/driving/${a.lng},${a.lat};${b.lng},${b.lat}?overview=false`)
            .then(r => r.json())
            .then(d => (d.code === "Ok" && d.routes && d.routes[0] ? { km: d.routes[0].distance / 1000, min: Math.round(d.routes[0].duration / 60) } : null));
    }

    let calculando = false;
    function calcular() {
        if (calculando) return;
        if (!campo("endereco").value && campo("cep").value.replace(/\D/g, "").length !== 8) {
            aviso("Preencha o CEP ou a rua para calcular a distância.");
            return;
        }
        calculando = true;
        aviso("Calculando a distância até a ArtSkala…");
        Promise.all([pontoDaLoja(), pontoDoCliente()])
            .then(([loja, cliente]) => {
                if (!loja || !cliente) { aviso("Não achei esse endereço no mapa. Confira rua, número e cidade."); return; }
                const reta = linhaReta(loja, cliente);
                return rota(loja, cliente).catch(() => null).then(r => {
                    const distancia = r ? r.km : reta * 1.3;
                    salvar(cliente, distancia, r ? r.min : null);
                    caixaDistancia.innerHTML = `<div class="distancia-numero"><strong>${km(distancia)} km</strong>
                        <span>${r ? `de carro até a ArtSkala · ~${r.min} min` : "aproximado (rota indisponível agora)"} · em linha reta ${km(reta)} km</span></div>`;
                });
            })
            .catch(() => aviso("Não deu para calcular agora (sem internet?). Tente de novo."))
            .finally(() => { calculando = false; atualizarLink(); atualizarDeslocamento(); });
    }
    function salvar(ponto, distancia, minutos) {
        $("[data-lat]").value = ponto.lat.toFixed(6);
        $("[data-lng]").value = ponto.lng.toFixed(6);
        $("[data-km]").value = (Math.round(distancia * 10) / 10).toFixed(1);
        $("[data-min]").value = minutos == null ? "" : String(minutos);
        form.dataset.alterado = "1";
    }
    function atualizarLink() {
        const destino = textoEndereco();
        const tem = campo("endereco").value || campo("cep").value;
        linkRota.hidden = !tem;
        if (tem) linkRota.href = "https://www.google.com/maps/dir/?api=1&travelmode=driving&origin=" + encodeURIComponent(caixa.dataset.origemEndereco) + "&destination=" + encodeURIComponent(destino);
    }
    $("[data-calcular-distancia]").addEventListener("click", calcular);
    ["endereco", "numero", "bairro", "cidade", "uf"].forEach(n => campo(n).addEventListener("input", atualizarLink));
    atualizarLink();

    /* --------------------------------------------- deslocamento */
    const valorKm = $("[data-valor-km]"), viagens = $("[data-viagens]"), totalEl = $("[data-total-deslocamento]"), botaoAdd = $("[data-add-deslocamento]");
    const guardadoKm = memoria.ler("ak-valor-km", null);
    if (guardadoKm != null) valorKm.value = String(guardadoKm);
    function contaDeslocamento() {
        const distancia = parseFloat($("[data-km]").value) || 0;
        const idas = Math.max(1, parseInt(String(viagens.value).replace(/\D/g, ""), 10) || 1);
        const preco = G ? G.lerNumero(valorKm.value) : parseFloat(valorKm.value) || 0;
        return { distancia, idas, preco, rodado: distancia * 2 * idas, total: distancia * 2 * idas * preco };
    }
    function atualizarDeslocamento() {
        const c = contaDeslocamento();
        totalEl.textContent = G ? G.formatarBRL(c.total) : "R$ " + c.total.toFixed(2);
        botaoAdd.disabled = !(c.distancia > 0 && c.preco > 0);
        botaoAdd.title = c.distancia ? `${km(c.rodado)} km rodados (${c.idas}× ida e volta)` : "Calcule a distância primeiro";
    }
    [valorKm, viagens].forEach(el => el.addEventListener("input", () => {
        if (el === valorKm && G) memoria.gravar("ak-valor-km", G.lerNumero(valorKm.value));
        atualizarDeslocamento();
    }));
    botaoAdd.addEventListener("click", () => {
        const c = contaDeslocamento();
        if (typeof window.adicionarItemOrcamento !== "function" || !(c.total > 0)) return;
        window.adicionarItemOrcamento({
            origem: "AVULSO",
            descricao: `Deslocamento — ${km(c.rodado)} km (${c.idas}× ida e volta)`.slice(0, 200),
            quantidade: 1,
            valor_unitario: Math.round(c.total * 100) / 100,
            custo_unitario: 0,
        });
        botaoAdd.textContent = "✓ Colocado nos itens";
        setTimeout(() => { botaoAdd.textContent = "+ Pôr no orçamento como item"; }, 2500);
    });
    setTimeout(atualizarDeslocamento, 0);
})();
