/* ArtSkala — comportamento do site (cabeçalho, menu do celular, busca,
   vitrine da home, animação ao rolar, zoom das fotos e preços em R$). */
(function () {
    "use strict";

    document.documentElement.classList.add("ak-js");

    const $ = (sel, raiz = document) => raiz.querySelector(sel);
    const $$ = (sel, raiz = document) => Array.from(raiz.querySelectorAll(sel));

    /* ------------------------------------------------ cabeçalho */
    const topo = $(".ak-topo");
    const marcarRolagem = () => topo && topo.classList.toggle("rolou", window.scrollY > 8);
    window.addEventListener("scroll", marcarRolagem, { passive: true });
    marcarRolagem();

    // Painéis (Produtos, Conta): abrem no clique e no teclado.
    function fecharGrupos(exceto) {
        $$("[data-topo-grupo]").forEach(grupo => {
            if (grupo === exceto) return;
            grupo.classList.remove("aberto");
            const botao = $("button", grupo);
            if (botao) botao.setAttribute("aria-expanded", "false");
        });
    }

    $$("[data-topo-grupo]").forEach(grupo => {
        const botao = $("button", grupo);
        if (!botao) return;
        botao.addEventListener("click", evento => {
            evento.stopPropagation();
            const abrir = !grupo.classList.contains("aberto");
            fecharGrupos(grupo);
            grupo.classList.toggle("aberto", abrir);
            botao.setAttribute("aria-expanded", String(abrir));
        });
    });

    document.addEventListener("click", evento => {
        if (!evento.target.closest("[data-topo-grupo]")) fecharGrupos();
    });

    /* ---------------------------------------------------- busca */
    const busca = $("#ak-busca");
    $$("[data-abrir-busca]").forEach(botao => {
        botao.addEventListener("click", evento => {
            if (!busca) return;
            evento.preventDefault();
            busca.hidden = !busca.hidden;
            botao.setAttribute("aria-expanded", String(!busca.hidden));
            if (!busca.hidden) {
                fecharMenu();
                const campo = $("input", busca);
                if (campo) campo.focus();
            }
        });
    });

    /* ------------------------------------------- menu do celular */
    const menu = $("#ak-menu-movel");
    const fundo = $("#ak-fundo-menu");
    let ultimoFoco = null;

    function abrirMenu() {
        if (!menu) return;
        ultimoFoco = document.activeElement;
        menu.classList.add("aberto");
        fundo && fundo.classList.add("aberto");
        menu.setAttribute("aria-hidden", "false");
        document.body.classList.add("ak-sem-rolagem");
        $$("[data-abrir-menu]").forEach(b => b.setAttribute("aria-expanded", "true"));
        const fechar = $("[data-fechar-menu]", menu);
        if (fechar) fechar.focus();
    }

    function fecharMenu() {
        if (!menu || !menu.classList.contains("aberto")) return;
        menu.classList.remove("aberto");
        fundo && fundo.classList.remove("aberto");
        menu.setAttribute("aria-hidden", "true");
        document.body.classList.remove("ak-sem-rolagem");
        $$("[data-abrir-menu]").forEach(b => b.setAttribute("aria-expanded", "false"));
        if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
    }

    $$("[data-abrir-menu]").forEach(b => b.addEventListener("click", abrirMenu));
    $$("[data-fechar-menu]").forEach(b => b.addEventListener("click", fecharMenu));
    fundo && fundo.addEventListener("click", fecharMenu);
    menu && $$("a", menu).forEach(a => a.addEventListener("click", fecharMenu));

    document.addEventListener("keydown", evento => {
        if (evento.key !== "Escape") return;
        fecharMenu();
        fecharGrupos();
        if (busca && !busca.hidden) busca.hidden = true;
    });

    /* ------------------------------------- link ativo por âncora */
    function marcarAncora() {
        const hash = window.location.hash;
        $$("[data-ancora]").forEach(link => {
            const ativo = hash && link.dataset.ancora === hash;
            link.classList.toggle("ativo", Boolean(ativo));
            if (ativo) {
                $$("[data-inicio]").forEach(inicio => inicio.classList.remove("ativo"));
            }
        });
    }
    window.addEventListener("hashchange", marcarAncora);
    marcarAncora();

    /* ---------------------------------------------- preços em R$ */
    const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
    function formatarPrecos(raiz) {
        $$(".preco-brl[data-preco]", raiz).forEach(el => {
            const numero = Number(String(el.dataset.preco).replace(",", "."));
            if (!Number.isNaN(numero)) el.textContent = brl.format(numero);
        });
    }
    formatarPrecos(document);

    /* ------------------------------------------ animação ao rolar */
    const revelar = $$("[data-revelar]");
    if ("IntersectionObserver" in window && revelar.length) {
        const observador = new IntersectionObserver(entradas => {
            entradas.forEach(entrada => {
                if (entrada.isIntersecting) {
                    entrada.target.classList.add("visivel");
                    observador.unobserve(entrada.target);
                }
            });
        }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
        revelar.forEach(el => observador.observe(el));
    } else {
        revelar.forEach(el => el.classList.add("visivel"));
    }

    /* ------------------------------------------- vitrine da home */
    $$("[data-vitrine]").forEach(vitrine => {
        const slides = $$("[data-slide]", vitrine);
        const minis = $$("[data-ir]", vitrine);
        const barra = $("[data-vitrine-progresso]", vitrine);
        if (slides.length < 2) return;

        const TEMPO = 5200;
        let atual = 0;
        let relogio = null;
        const parado = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        function mostrar(indice) {
            atual = (indice + slides.length) % slides.length;
            slides.forEach((slide, i) => {
                const ativo = i === atual;
                slide.classList.toggle("ativo", ativo);
                slide.setAttribute("aria-hidden", String(!ativo));
                $$("a", slide).forEach(a => a.tabIndex = ativo ? 0 : -1);
            });
            minis.forEach((mini, i) => {
                mini.classList.toggle("ativo", i === atual);
                mini.setAttribute("aria-pressed", String(i === atual));
            });
            if (barra) {
                barra.style.transition = "none";
                barra.style.width = "0%";
                void barra.offsetWidth;
                if (!parado) {
                    barra.style.transition = `width ${TEMPO}ms linear`;
                    barra.style.width = "100%";
                }
            }
        }

        function tocar() {
            if (parado) return;
            parar();
            relogio = setInterval(() => mostrar(atual + 1), TEMPO);
        }

        function parar() {
            if (relogio) clearInterval(relogio);
            relogio = null;
        }

        minis.forEach(mini => mini.addEventListener("click", () => {
            mostrar(Number(mini.dataset.ir));
            tocar();
        }));
        vitrine.addEventListener("mouseenter", parar);
        vitrine.addEventListener("mouseleave", tocar);
        vitrine.addEventListener("focusin", parar);
        document.addEventListener("visibilitychange", () => (document.hidden ? parar() : tocar()));

        mostrar(0);
        tocar();
    });

    /* ------------------------------ trabalhos passando (home) */
    // Cada faixa anda sozinha; ao passar o mouse ela desacelera até parar,
    // dá para arrastar com o dedo ou o mouse e o botão pausa tudo.
    $$("[data-trampos]").forEach(secao => {
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
        const linhas = $$(".ak-trampos-linha", secao).map(linha => {
            const trilho = $(".ak-trampos-trilho", linha);
            const grupo = $(".ak-trampos-grupo", linha);
            const tempo = parseFloat(getComputedStyle(linha).getPropertyValue("--ak-tempo")) || 60;
            return {
                linha, trilho, grupo, tempo,
                sentido: linha.classList.contains("ak-trampos-linha--volta") ? -1 : 1,
                largura: 0, pos: 0, vel: 0, mouse: false, foco: false, arraste: null, bloquear: false,
            };
        }).filter(l => l.trilho && l.grupo);
        if (!linhas.length) return;

        secao.classList.add("ak-trampos--js");
        let pausado = false;
        let visivel = true;
        let ultimo = 0;
        let quadro = 0;

        const medir = () => linhas.forEach(l => {
            l.largura = l.grupo.getBoundingClientRect().width;
            if (l.sentido < 0 && !l.pos) l.pos = l.largura * 0.37;   // começa em outro ponto
        });
        const pintar = l => {
            if (!l.largura) return;
            l.pos = ((l.pos % l.largura) + l.largura) % l.largura;
            l.trilho.style.transform = `translate3d(${-l.pos}px,0,0)`;
        };

        function passo(agora) {
            const dt = Math.min(0.05, ultimo ? (agora - ultimo) / 1000 : 0);
            ultimo = agora;
            linhas.forEach(l => {
                if (l.arraste) return;
                const alvo = pausado || l.mouse || l.foco ? 0 : (l.largura / l.tempo) * l.sentido;
                l.vel += (alvo - l.vel) * Math.min(1, dt * 4);        // freia e acelera suave
                l.pos += l.vel * dt;
                pintar(l);
            });
            quadro = visivel ? requestAnimationFrame(passo) : 0;
        }
        const ligar = () => { if (!quadro && visivel && !document.hidden) { ultimo = 0; quadro = requestAnimationFrame(passo); } };
        const desligar = () => { cancelAnimationFrame(quadro); quadro = 0; };

        linhas.forEach(l => {
            l.linha.addEventListener("pointerenter", e => { if (e.pointerType === "mouse") l.mouse = true; });
            l.linha.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") l.mouse = false; });
            l.linha.addEventListener("focusin", () => { l.foco = true; });
            l.linha.addEventListener("focusout", () => { l.foco = false; });
            l.linha.addEventListener("dragstart", e => e.preventDefault());

            l.linha.addEventListener("pointerdown", e => {
                if (e.pointerType === "mouse" && e.button !== 0) return;
                l.arraste = { x: e.clientX, pos: l.pos, ultimoX: e.clientX, t: performance.now(), moveu: false, id: e.pointerId };
            });
            l.linha.addEventListener("pointermove", e => {
                const a = l.arraste;
                if (!a || a.id !== e.pointerId) return;
                const dx = e.clientX - a.x;
                if (!a.moveu && Math.abs(dx) > 6) {
                    a.moveu = true;
                    l.linha.classList.add("arrastando");
                    try { l.linha.setPointerCapture(e.pointerId); } catch (erro) { /* sem captura */ }
                }
                if (!a.moveu) return;
                const agora = performance.now();
                const dtx = Math.max(1, agora - a.t);
                l.vel = (-(e.clientX - a.ultimoX) / dtx) * 1000;      // embalo ao soltar
                a.ultimoX = e.clientX;
                a.t = agora;
                l.pos = a.pos - dx;
                pintar(l);
            });
            const soltar = e => {
                const a = l.arraste;
                if (!a || a.id !== e.pointerId) return;
                l.arraste = null;
                l.vel = Math.max(-1500, Math.min(1500, l.vel || 0));
                if (a.moveu) {
                    // o clique que vem logo depois de arrastar não abre o link
                    l.bloquear = true;
                    setTimeout(() => { l.bloquear = false; l.linha.classList.remove("arrastando"); }, 120);
                }
            };
            l.linha.addEventListener("click", ev => {
                if (l.bloquear) { ev.preventDefault(); ev.stopPropagation(); }
            }, { capture: true });
            l.linha.addEventListener("pointerup", soltar);
            l.linha.addEventListener("pointercancel", soltar);
        });

        const botao = $("[data-trampos-pausa]", secao);
        if (botao) {
            botao.addEventListener("click", () => {
                pausado = !pausado;
                botao.setAttribute("aria-pressed", String(pausado));
                $("span", botao).textContent = pausado ? "Continuar" : "Pausar";
                $("i", botao).className = pausado ? "bi bi-play-fill" : "bi bi-pause-fill";
            });
        }

        if ("IntersectionObserver" in window) {
            new IntersectionObserver(([entrada]) => {
                visivel = entrada.isIntersecting;
                visivel ? ligar() : desligar();
            }, { rootMargin: "120px 0px" }).observe(secao);
        }
        document.addEventListener("visibilitychange", () => (document.hidden ? desligar() : ligar()));
        window.addEventListener("resize", medir, { passive: true });
        window.addEventListener("load", medir);
        medir();
        linhas.forEach(pintar);
        ligar();
    });

    /* --------------------------------------------- zoom das fotos */
    const zoom = $("#ak-zoom");
    if (zoom && typeof zoom.showModal === "function") {
        const foto = $("img", zoom);
        $$("[data-ampliar]").forEach(botao => {
            botao.addEventListener("click", () => {
                foto.src = botao.dataset.ampliar;
                foto.alt = botao.getAttribute("aria-label") || "";
                zoom.showModal();
            });
        });
        $$("[data-fechar-zoom]", zoom).forEach(b => b.addEventListener("click", () => zoom.close()));
        zoom.addEventListener("click", evento => { if (evento.target === zoom) zoom.close(); });
    }

    /* ------------------------------------- avisos somem sozinhos */
    $$(".ak-mensagens .ak-aviso").forEach((aviso, i) => {
        setTimeout(() => {
            aviso.style.transition = "opacity .4s ease";
            aviso.style.opacity = "0";
            setTimeout(() => aviso.remove(), 450);
        }, 5000 + i * 600);
    });
})();
