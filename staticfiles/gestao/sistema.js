/* ArtSkala · Gestão — campos com máscara, dinheiro em R$, atalhos e busca rápida.
 *
 * Campos (detectados pelo nome ou por data-campo="..."):
 *   dinheiro   preço, custo, valor...      como maquininha: 1 -> 0,01 · 10 -> 0,10 · 15000 -> 150,00
 *   pct        desconto, percentual        "12,5"           (sufixo %)
 *   medida     largura/altura em metros    "1,20"           (sufixo m)
 *   inteiro    estoque, quantidade         só números, com botões − e +
 *   telefone   (11) 96082-7853 / (11) 2235-3589
 *   documento  CPF 000.000.000-00 ou CNPJ 00.000.000/0000-00 (confere os dígitos)
 *   cep        00000-000 e preenche endereço, cidade e UF (ViaCEP)
 *   uf         2 letras maiúsculas
 *   email      sem espaços, minúsculo
 * O servidor entende "R$ 1.500,50" (core/dinheiro.py).
 *
 * window.Gestao: lerNumero, formatarBRL, formatarNumero, definirValor, aplicar.
 */
(function () {
    "use strict";

    const $ = (sel, raiz = document) => raiz.querySelector(sel);
    const $$ = (sel, raiz = document) => Array.from(raiz.querySelectorAll(sel));
    const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

    function lerNumero(valor) {
        if (typeof valor === "number") return Number.isFinite(valor) ? valor : 0;
        let t = String(valor == null ? "" : valor).replace(/[^\d,.\-]/g, "");
        if (!t) return 0;
        const negativo = t.startsWith("-");
        t = t.replace(/-/g, "");
        if (t.includes(",") && t.includes(".")) {
            t = t.lastIndexOf(",") > t.lastIndexOf(".") ? t.replace(/\./g, "").replace(",", ".") : t.replace(/,/g, "");
        } else if (t.includes(",")) {
            t = t.replace(/\./g, "").replace(",", ".");
        } else if ((t.match(/\./g) || []).length > 1) {
            t = t.replace(/\./g, "");
        }
        const n = parseFloat(t) || 0;
        return negativo ? -n : n;
    }

    function formatarNumero(n, casas = 2) {
        return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas }).format(lerNumero(n));
    }
    const formatarBRL = n => BRL.format(lerNumero(n));

    /* ------------------------------------------------------------ tipos */
    const REGRAS = [
        ["inteiro", /(^|_)(estoque|quantidade)(\[\])?$/],
        ["pct", /percentual|porcentagem/],
        ["medida", /(^|_)(largura|altura|comprimento)(_m)?$/],
        ["dinheiro", /(^|_)(preco|custo|valor|minimo|frete|preco_m2)(_\w+)?(\[\])?$/],
        ["telefone", /telefone|celular|whats/],
        ["documento", /(^|_)(cpf|cnpj|documento)$/],
        ["cep", /(^|_)cep$/],
        ["uf", /(^|_)(uf|estado)$/],
    ];

    function tipoDoCampo(input) {
        if (input.dataset.campo) return input.dataset.campo;
        if (input.type === "email") return "email";
        if (["hidden", "file", "checkbox", "radio", "date", "submit", "button", "search"].includes(input.type)) return "";
        const nome = (input.name || input.id || "").toLowerCase();
        if (nome === "avaliacao") return "";
        for (const [tipo, regra] of REGRAS) if (regra.test(nome)) return tipo;
        return "";
    }

    /* ------------------------------------------- dinheiro, % e medidas */
    // Digita do jeito natural: "1500" -> 1.500 | "1500,5" -> 1.500,5 | ao sair: 1.500,50.
    function formatarDigitando(texto, casas) {
        let limpo = String(texto).replace(/[^\d,]/g, "");
        const virgula = limpo.indexOf(",");
        let inteiro = virgula >= 0 ? limpo.slice(0, virgula) : limpo;
        let fracao = virgula >= 0 ? limpo.slice(virgula + 1).replace(/,/g, "").slice(0, casas) : null;
        inteiro = inteiro.replace(/^0+(?=\d)/, "");
        const agrupado = inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        if (fracao === null) return agrupado;
        return (agrupado || "0") + "," + fracao;
    }

    function manterCursor(input, novo) {
        // recoloca o cursor depois do mesmo número de dígitos/vírgula
        const pos = input.selectionStart == null ? input.value.length : input.selectionStart;
        const contar = s => s.replace(/[^\d,]/g, "").length;
        const alvo = contar(input.value.slice(0, pos));
        input.value = novo;
        let i = 0, vistos = 0;
        while (i < novo.length && vistos < alvo) { if (/[\d,]/.test(novo[i])) vistos++; i++; }
        try { input.setSelectionRange(i, i); } catch (erro) { /* tipo sem seleção */ }
    }

    function campoDecimal(input, tipo) {
        const casas = Number(input.dataset.casas || (tipo === "pct" ? 2 : 2));
        const maximo = input.max !== "" && input.max != null ? lerNumero(input.max) : (tipo === "pct" ? 100 : null);
        const inicial = input.value;
        if (input.type === "number") input.type = "text";
        input.setAttribute("inputmode", "decimal");
        input.autocomplete = "off";
        input.removeAttribute("step");
        input.removeAttribute("min");
        input.removeAttribute("max");
        input.classList.add("campo-num");

        const embrulho = document.createElement("span");
        embrulho.className = "campo-afixo campo-afixo--" + tipo;
        input.parentNode.insertBefore(embrulho, input);
        embrulho.appendChild(input);
        const afixo = document.createElement("span");
        afixo.className = "afixo";
        afixo.setAttribute("aria-hidden", "true");
        afixo.textContent = tipo === "dinheiro" ? "R$" : tipo === "pct" ? "%" : "m";
        embrulho.appendChild(afixo);

        const finalizar = () => {
            if (input.value.trim() === "" && input.dataset.vazio === "sim") return;
            let n = lerNumero(input.value);
            if (n < 0) n = 0;
            if (maximo != null && n > maximo) n = maximo;
            input.value = formatarNumero(n, casas);
        };

        if (tipo === "dinheiro") {
            // Dinheiro como maquininha: os números entram pela direita (centavos).
            const centavos = () => String(input.value).replace(/\D/g, "").replace(/^0+/, "").slice(0, 13);
            const mostrar = digitos => {
                const n = (parseInt(digitos || "0", 10) || 0) / 100;
                input.value = formatarNumero(maximo != null ? Math.min(n, maximo) : n, 2);
                try { input.setSelectionRange(input.value.length, input.value.length); } catch (erro) { /* */ }
            };
            input.addEventListener("keydown", e => {
                if (e.ctrlKey || e.metaKey || e.altKey) return;
                if (/^\d$/.test(e.key)) {
                    e.preventDefault();
                    const tudo = input.selectionStart === 0 && input.selectionEnd === input.value.length && input.value !== "";
                    mostrar((tudo ? "" : centavos()) + e.key);
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                } else if (e.key === "Backspace" || e.key === "Delete") {
                    e.preventDefault();
                    const tudo = input.selectionStart === 0 && input.selectionEnd === input.value.length;
                    mostrar(tudo ? "" : centavos().slice(0, -1));
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                } else if (e.key.length === 1) {
                    e.preventDefault();          // letras, vírgula e ponto: o valor já tem vírgula
                }
            });
            // colar "R$ 1.234,56" / "1234.5" ou digitar no celular (sem keydown confiável)
            input.addEventListener("input", e => {
                if (!e.isTrusted) return;
                const colou = /^insertFrom(Paste|Drop)/.test(e.inputType || "");
                if (colou) mostrar(String(Math.round(Math.abs(lerNumero(input.value)) * 100)));
                else if (!/^[\d.]*,\d{2}$/.test(input.value) || /^delete/.test(e.inputType || "")) mostrar(centavos());
            });
            input.addEventListener("focus", () => setTimeout(() => { try { input.setSelectionRange(input.value.length, input.value.length); } catch (erro) { /* */ } }, 0));
            input.addEventListener("blur", () => { finalizar(); input.dispatchEvent(new Event("change", { bubbles: true })); });
            input.value = inicial === "" && input.dataset.vazio === "sim" ? "" : formatarNumero(lerNumero(inicial), casas);
            input._finalizar = finalizar;
            return;
        }

        input.addEventListener("keydown", e => {
            // ponto do teclado numérico vira vírgula
            if ((e.key === "." || e.key === "Decimal") && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                if (!input.value.includes(",")) {
                    const ini = input.selectionStart, fim = input.selectionEnd;
                    input.setRangeText(",", ini, fim, "end");
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                }
            }
        });
        input.addEventListener("input", () => manterCursor(input, formatarDigitando(input.value, casas)));
        input.addEventListener("focus", () => { if (lerNumero(input.value) === 0) setTimeout(() => input.select(), 0); });
        input.addEventListener("blur", () => { finalizar(); input.dispatchEvent(new Event("change", { bubbles: true })); });

        input.value = inicial === "" && input.dataset.vazio === "sim" ? "" : formatarNumero(lerNumero(inicial), casas);
        input._finalizar = finalizar;
    }

    /* ------------------------------------------------------- inteiros */
    function campoInteiro(input) {
        const minimo = input.min !== "" ? Number(input.min) : 0;
        if (input.type === "number") input.type = "text";
        input.setAttribute("inputmode", "numeric");
        input.removeAttribute("step");
        input.classList.add("campo-num");
        const embrulho = document.createElement("span");
        embrulho.className = "campo-passos";
        input.parentNode.insertBefore(embrulho, input);
        const menos = Object.assign(document.createElement("button"), { type: "button", className: "passo", textContent: "−" });
        const mais = Object.assign(document.createElement("button"), { type: "button", className: "passo", textContent: "+" });
        menos.setAttribute("aria-label", "Diminuir");
        mais.setAttribute("aria-label", "Aumentar");
        embrulho.append(menos, input, mais);
        const valor = () => parseInt(String(input.value).replace(/\D/g, ""), 10) || 0;
        const definir = n => {
            input.value = String(Math.max(minimo, n));
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
        };
        menos.addEventListener("click", () => definir(valor() - 1));
        mais.addEventListener("click", () => definir(valor() + 1));
        input.addEventListener("input", () => {
            const limpo = String(input.value).replace(/\D/g, "");
            if (limpo !== input.value) input.value = limpo;
        });
        input.addEventListener("blur", () => { if (valor() < minimo) input.value = String(minimo); });
        input.addEventListener("keydown", e => {
            if (e.key === "ArrowUp") { e.preventDefault(); definir(valor() + 1); }
            if (e.key === "ArrowDown") { e.preventDefault(); definir(valor() - 1); }
        });
    }

    /* --------------------------------------- telefone, documento, CEP */
    function mascara(digitos, modelo) {
        let i = 0, saida = "";
        for (const c of modelo) {
            if (i >= digitos.length) break;
            if (c === "0") saida += digitos[i++]; else saida += c;
        }
        return saida;
    }

    const telefone = d => d.length > 10 ? mascara(d, "(00) 00000-0000") : mascara(d, "(00) 0000-0000");
    const documento = d => d.length > 11 ? mascara(d, "00.000.000/0000-00") : mascara(d, "000.000.000-00");

    function cpfValido(d) {
        if (d.length !== 11 || /^(\d)\1+$/.test(d)) return false;
        for (let t = 9; t < 11; t++) {
            let soma = 0;
            for (let i = 0; i < t; i++) soma += Number(d[i]) * (t + 1 - i);
            if (((soma * 10) % 11) % 10 !== Number(d[t])) return false;
        }
        return true;
    }
    function cnpjValido(d) {
        if (d.length !== 14 || /^(\d)\1+$/.test(d)) return false;
        const calc = n => {
            const pesos = n === 12 ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
            const soma = pesos.reduce((s, p, i) => s + Number(d[i]) * p, 0);
            const r = soma % 11;
            return r < 2 ? 0 : 11 - r;
        };
        return calc(12) === Number(d[12]) && calc(13) === Number(d[13]);
    }

    function dica(input, texto) {
        let el = input._dica;
        if (!el) {
            el = document.createElement("small");
            el.className = "dica-campo";
            el.setAttribute("role", "status");
            (input.closest(".campo") || input.parentNode).appendChild(el);
            input._dica = el;
        }
        el.textContent = texto || "";
        el.hidden = !texto;
    }

    function campoMascara(input, formatar, maxDigitos, aoCompletar) {
        input.setAttribute("inputmode", "numeric");
        input.autocomplete = input.autocomplete || "off";
        const aplicarMascara = () => {
            const d = input.value.replace(/\D/g, "").slice(0, maxDigitos);
            const novo = formatar(d);
            if (novo !== input.value) {
                const noFim = input.selectionStart >= input.value.length;
                input.value = novo;
                if (noFim) try { input.setSelectionRange(novo.length, novo.length); } catch (erro) { /* */ }
            }
            return d;
        };
        input.addEventListener("input", () => { const d = aplicarMascara(); if (aoCompletar) aoCompletar(d, false); });
        input.addEventListener("blur", () => { const d = aplicarMascara(); if (aoCompletar) aoCompletar(d, true); });
        aplicarMascara();
    }

    function preencherPorCep(input, cep) {
        const form = input.form;
        if (!form || input._cepBuscado === cep) return;
        input._cepBuscado = cep;
        dica(input, "Buscando endereço…");
        fetch(`https://viacep.com.br/ws/${cep}/json/`)
            .then(r => (r.ok ? r.json() : Promise.reject()))
            .then(dados => {
                if (dados.erro) { dica(input, "CEP não encontrado. Confira os números."); return; }
                const pegar = nomes => nomes.map(n => form.elements[n]).find(Boolean);
                const colocar = (campo, valor) => {
                    if (campo && valor && !campo.value.trim()) {
                        campo.value = valor;
                        campo.dispatchEvent(new Event("input", { bubbles: true }));
                    }
                };
                colocar(pegar(["endereco", "logradouro", "rua"]), [dados.logradouro, dados.bairro].filter(Boolean).join(", "));
                colocar(pegar(["bairro"]), dados.bairro);
                colocar(pegar(["cidade", "municipio"]), dados.localidade);
                colocar(pegar(["estado", "uf"]), dados.uf);
                dica(input, `${dados.localidade || ""}${dados.uf ? " / " + dados.uf : ""}`);
            })
            .catch(() => dica(input, ""));
    }

    /* ------------------------------------------------------- aplicar */
    function prepararCampo(input) {
        if (input.dataset.mascara === "ok" || input.readOnly) return;
        const tipo = tipoDoCampo(input);
        if (!tipo) return;
        input.dataset.mascara = "ok";
        switch (tipo) {
            case "dinheiro": case "pct": case "medida": campoDecimal(input, tipo); break;
            case "inteiro": campoInteiro(input); break;
            case "telefone":
                input.type = "tel";
                campoMascara(input, telefone, 11, (d, saiu) => dica(input, saiu && d && d.length < 10 ? "Telefone incompleto: DDD + número." : ""));
                break;
            case "documento":
                campoMascara(input, documento, 14, (d, saiu) => {
                    let erro = "";
                    if (saiu && d) {
                        if (d.length === 11) erro = cpfValido(d) ? "" : "CPF inválido: confira os números.";
                        else if (d.length === 14) erro = cnpjValido(d) ? "" : "CNPJ inválido: confira os números.";
                        else erro = "Digite os 11 números do CPF ou os 14 do CNPJ.";
                    }
                    input.setCustomValidity(erro);
                    input.setAttribute("aria-invalid", erro ? "true" : "false");
                    dica(input, erro);
                });
                break;
            case "cep":
                campoMascara(input, d => mascara(d, "00000-000"), 8, d => {
                    if (d.length === 8 && input.dataset.semAutopreencher === undefined) preencherPorCep(input, d);
                });
                break;
            case "uf":
                input.maxLength = 2;
                input.addEventListener("input", () => { input.value = input.value.replace(/[^a-z]/gi, "").toUpperCase().slice(0, 2); });
                break;
            case "email":
                input.addEventListener("blur", () => { input.value = input.value.trim().toLowerCase(); });
                break;
        }
    }

    function aplicar(raiz = document) {
        $$("input", raiz).forEach(prepararCampo);
        $$("[data-brl]", raiz).forEach(el => { el.textContent = formatarBRL(el.dataset.brl); });
    }

    function definirValor(input, numero) {
        const tipo = tipoDoCampo(input);
        if (tipo === "dinheiro" || tipo === "pct" || tipo === "medida") input.value = formatarNumero(numero, Number(input.dataset.casas || 2));
        else input.value = numero;
        input.dispatchEvent(new Event("input", { bubbles: true }));
    }

    window.Gestao = { lerNumero, formatarBRL, formatarNumero, definirValor, aplicar };

    /* ------------------------- alterações não salvas e Ctrl+S salva */
    function prepararFormularios() {
        $$(".conteudo form[method=post], .conteudo form[method=POST]").forEach(form => {
            if (form.dataset.semAviso !== undefined || form.dataset.vigiado) return;
            form.dataset.vigiado = "1";
            form.addEventListener("input", e => { if (e.isTrusted) form.dataset.alterado = "1"; });
            form.addEventListener("submit", () => {
                $$("input", form).forEach(i => i._finalizar && i._finalizar());
                delete form.dataset.alterado;
                form.dataset.enviando = "1";
                const botao = $("button[type=submit], .btn-primario[type=submit]", form);
                if (botao && !botao.dataset.textoOriginal) {
                    botao.dataset.textoOriginal = botao.textContent;
                    setTimeout(() => { botao.disabled = true; botao.textContent = "Salvando…"; }, 0);
                    setTimeout(() => { botao.disabled = false; botao.textContent = botao.dataset.textoOriginal; delete botao.dataset.textoOriginal; }, 8000);
                }
            });
        });
    }
    window.addEventListener("beforeunload", e => {
        if ($$("form[data-alterado]").some(f => !f.dataset.enviando)) { e.preventDefault(); e.returnValue = ""; }
    });

    document.addEventListener("keydown", e => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
            const form = $$(".conteudo form[method=post], .conteudo form[method=POST]").find(f => f.offsetParent !== null && $(".btn-primario", f));
            if (form) { e.preventDefault(); form.requestSubmit ? form.requestSubmit() : form.submit(); }
        }
    });

    /* --------------------------------------------------- busca rápida */
    function buscaRapida() {
        const dialogo = $("#busca-rapida");
        if (!dialogo || typeof dialogo.showModal !== "function") return;
        const campo = $("input", dialogo);
        const lista = $("[data-resultados]", dialogo);
        const url = dialogo.dataset.url;
        let itens = [], atual = 0, relogio = null, controle = null;

        const desenhar = () => {
            lista.innerHTML = "";
            if (!itens.length) {
                const vazio = document.createElement("li");
                vazio.className = "busca-vazio";
                vazio.textContent = campo.value.trim() ? "Nada encontrado. Tente o nome, o cliente ou o código da etiqueta (ex.: PRD-000012)." : "Digite o nome, o cliente ou bipe o código da etiqueta.";
                lista.appendChild(vazio);
                return;
            }
            itens.forEach((item, i) => {
                const li = document.createElement("li");
                const a = document.createElement("a");
                a.href = item.url;
                a.className = "busca-item" + (i === atual ? " ativo" : "");
                a.setAttribute("role", "option");
                a.setAttribute("aria-selected", String(i === atual));
                const tipo = document.createElement("span");
                tipo.className = "busca-tipo";
                tipo.textContent = item.tipo;
                const texto = document.createElement("span");
                texto.className = "busca-texto";
                const forte = document.createElement("strong");
                forte.textContent = item.titulo;
                const sub = document.createElement("small");
                sub.textContent = item.detalhe || "";
                texto.append(forte, sub);
                a.append(tipo, texto);
                if (item.codigo) {
                    const cod = document.createElement("code");
                    cod.textContent = item.codigo;
                    a.appendChild(cod);
                }
                li.appendChild(a);
                lista.appendChild(li);
            });
            const ativo = $(".busca-item.ativo", lista);
            if (ativo) ativo.scrollIntoView({ block: "nearest" });
        };

        const buscar = (imediato) => {
            clearTimeout(relogio);
            relogio = setTimeout(() => {
                if (controle) controle.abort();
                controle = new AbortController();
                fetch(`${url}?q=${encodeURIComponent(campo.value.trim())}`, { signal: controle.signal, headers: { Accept: "application/json" } })
                    .then(r => r.json())
                    .then(dados => {
                        itens = dados.resultados || [];
                        atual = 0;
                        desenhar();
                        if (imediato && dados.exato && itens[0]) window.location.href = itens[0].url;
                    })
                    .catch(() => {});
            }, imediato ? 0 : 160);
        };

        const abrir = () => {
            if (dialogo.open) return;
            dialogo.showModal();
            campo.value = "";
            itens = [];
            buscar(false);
            setTimeout(() => campo.focus(), 0);
        };
        campo.addEventListener("input", () => buscar(false));
        campo.addEventListener("keydown", e => {
            if (e.key === "ArrowDown") { e.preventDefault(); atual = Math.min(itens.length - 1, atual + 1); desenhar(); }
            else if (e.key === "ArrowUp") { e.preventDefault(); atual = Math.max(0, atual - 1); desenhar(); }
            else if (e.key === "Enter") {
                e.preventDefault();
                // leitor de código de barras/QR manda o código e Enter de uma vez
                if (/^(PRD|PED|ORC|PRJ)/i.test(campo.value.trim())) buscar(true);
                else if (itens[atual]) window.location.href = itens[atual].url;
            }
        });
        dialogo.addEventListener("click", e => { if (e.target === dialogo) dialogo.close(); });
        $$("[data-abrir-busca]").forEach(b => b.addEventListener("click", abrir));
        document.addEventListener("keydown", e => {
            const digitando = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName) || document.activeElement.isContentEditable;
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); abrir(); }
            else if (e.key === "/" && !digitando) { e.preventDefault(); abrir(); }
        });
    }

    /* ------------------------------------------------------- início */
    function iniciar() {
        aplicar(document);
        prepararFormularios();
        buscaRapida();
        // linhas criadas depois (itens do orçamento) também ganham máscara
        new MutationObserver(registros => {
            registros.forEach(r => r.addedNodes.forEach(no => { if (no.nodeType === 1) aplicar(no); }));
            prepararFormularios();
        }).observe(document.body, { childList: true, subtree: true });
        // avisos somem sozinhos
        $$(".mensagem").forEach((aviso, i) => setTimeout(() => aviso.classList.add("saindo"), 6000 + i * 500));
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar); else iniciar();
})();
