"""Gestão: busca rápida, pedidos da loja e impressão de etiquetas."""
import json
import re
from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View

from .dinheiro import codigo, formatar_brl, ler_codigo
from .models import Orcamento, Pedido, Produto, Projeto
from .views import SuperuserGestaoRequiredMixin

REMETENTE = {
    "nome": "ArtSkala Comunicação Visual",
    "endereco": "Rua Eduardo Zumkeller, 170 — Galpão 01",
    "cidade": "São Paulo - SP",
    "telefone": "(11) 2235-3589",
}

PAGINAS = [
    ("Painel", "gestao_dashboard", "Resumo do negócio"),
    ("Produtos", "gestao_produtos", "Catálogo, preços e estoque"),
    ("Projetos", "gestao_projetos", "Portfólio"),
    ("Orçamentos", "orcamentos", "Propostas e produção"),
    ("Novo orçamento", "orcamentos", "Abrir o formulário"),
    ("Pedidos do site", "gestao_pedidos", "Compras da loja"),
    ("Etiquetas", "gestao_etiquetas", "Preço, envio, produção e livre"),
    ("Relatórios", "gestao_relatorio", "Receita, custo e lucro"),
    ("Instagram", "gestao_instagram", "Posts e prints"),
    ("Perfil", "gestao_perfil", "Sua conta"),
]


def _url_site(request, nome, pk):
    """Endereço público (produto/projeto) mesmo quando a gestão abre pelo subdomínio."""
    caminho = reverse(nome, args=[pk], urlconf=settings.ROOT_URLCONF)
    if getattr(request, "is_interno", False):
        return settings.SITE_URL + caminho
    return request.build_absolute_uri(caminho)


def _digitos(texto):
    return re.sub(r"\D", "", str(texto or ""))


def cliente_do_pedido(pedido):
    """Nome, contato e endereço do cliente (perfil + endereço do pedido)."""
    usuario = pedido.usuario
    try:
        perfil = usuario.perfil
    except Exception:  # sem perfil cadastrado
        perfil = None
    telefone = getattr(perfil, "telefone", "") or ""
    cidade = " - ".join(p for p in (getattr(perfil, "cidade", ""), getattr(perfil, "estado", "")) if p)
    cep = getattr(perfil, "cep", "") or ""
    endereco = pedido.endereco or getattr(perfil, "endereco", "") or ""
    digitos = _digitos(telefone)
    if digitos and not digitos.startswith("55"):
        digitos = "55" + digitos
    nome = usuario.get_full_name() or usuario.username
    return {
        "nome": nome,
        "email": usuario.email,
        "telefone": telefone,
        "cpf": getattr(perfil, "cpf", "") or "",
        "endereco": endereco,
        "cidade": cidade,
        "cep": cep,
        "whatsapp": (
            f"https://wa.me/{digitos}?text="
            + quote(f"Olá, {nome.split()[0]}! Aqui é da ArtSkala, sobre o seu pedido #{pedido.pk}.")
            if len(digitos) >= 12 else ""
        ),
    }


# ============================================================ busca rápida

class BuscaRapidaView(SuperuserGestaoRequiredMixin, View):
    secao_gestao = "buscar"
    """JSON da busca rápida (Ctrl+K). Aceita o código das etiquetas (PRD-000012)."""

    LIMITE = 6

    def get(self, request):
        termo = request.GET.get("q", "").strip()[:80]
        resultados = []

        lido = ler_codigo(termo)
        if lido:
            achado = self._por_codigo(*lido)
            if achado:
                return JsonResponse({"resultados": [achado], "exato": True})

        if not termo:
            resultados = [self._pagina(*p) for p in PAGINAS]
            return JsonResponse({"resultados": resultados, "exato": False})

        resultados += [self._pagina(*p) for p in PAGINAS if termo.lower() in p[0].lower()][:3]

        for produto in Produto.objects.filter(ativo=True).filter(
            Q(nome_produto__icontains=termo) | Q(categoria__nome_categoria__icontains=termo)
        ).select_related("categoria").order_by("nome_produto")[: self.LIMITE]:
            resultados.append(self._produto(produto))

        filtro_orc = Q(titulo__icontains=termo) | Q(cliente_nome__icontains=termo) | Q(cliente_telefone__icontains=termo)
        if termo.isdigit():
            filtro_orc |= Q(pk=int(termo))
        for orcamento in Orcamento.objects.filter(ativo=True).filter(filtro_orc).order_by("-criacao")[: self.LIMITE]:
            resultados.append(self._orcamento(orcamento))

        filtro_ped = (
            Q(usuario__username__icontains=termo) | Q(usuario__first_name__icontains=termo)
            | Q(usuario__last_name__icontains=termo) | Q(usuario__email__icontains=termo)
            | Q(endereco__icontains=termo)
        )
        if termo.isdigit():
            filtro_ped |= Q(pk=int(termo))
        for pedido in Pedido.objects.filter(filtro_ped).select_related("usuario").order_by("-criacao")[: self.LIMITE]:
            resultados.append(self._pedido(pedido))

        for projeto in Projeto.objects.filter(ativo=True).filter(
            Q(titulo__icontains=termo) | Q(cliente__icontains=termo)
        ).order_by("-criacao")[: self.LIMITE]:
            resultados.append(self._projeto(projeto))

        return JsonResponse({"resultados": resultados[:24], "exato": False})

    def _por_codigo(self, prefixo, pk):
        if prefixo == "PRD":
            obj = Produto.objects.filter(pk=pk, ativo=True).select_related("categoria").first()
            return obj and self._produto(obj)
        if prefixo == "PED":
            obj = Pedido.objects.filter(pk=pk).select_related("usuario").first()
            return obj and self._pedido(obj)
        if prefixo == "ORC":
            obj = Orcamento.objects.filter(pk=pk, ativo=True).first()
            return obj and self._orcamento(obj)
        if prefixo == "PRJ":
            obj = Projeto.objects.filter(pk=pk, ativo=True).first()
            return obj and self._projeto(obj)
        return None

    @staticmethod
    def _pagina(titulo, rota, detalhe):
        url = reverse(rota)
        if titulo == "Novo orçamento":
            url += "?novo=1"
        return {"tipo": "Tela", "titulo": titulo, "detalhe": detalhe, "url": url, "codigo": ""}

    @staticmethod
    def _produto(p):
        preco = formatar_brl(p.preco) if p.preco > 0 else "Sob consulta"
        return {
            "tipo": "Produto", "titulo": p.nome_produto, "codigo": codigo(p),
            "detalhe": f"{p.categoria.nome_categoria if p.categoria_id else 'Sem categoria'} · {preco} · estoque {p.estoque}",
            "url": reverse("gestao_produto_detalhe", args=[p.pk]),
        }

    @staticmethod
    def _orcamento(o):
        return {
            "tipo": "Orçamento", "titulo": o.titulo, "codigo": codigo(o),
            "detalhe": f"{o.cliente_nome or 'Sem cliente'} · {o.get_status_display()} · {formatar_brl(o.valor_total())}",
            "url": reverse("orcamento_detalhe", args=[o.pk]),
        }

    @staticmethod
    def _pedido(p):
        nome = p.usuario.get_full_name() or p.usuario.username
        return {
            "tipo": "Pedido", "titulo": f"Pedido #{p.pk} · {nome}", "codigo": codigo(p),
            "detalhe": f"{p.criacao:%d/%m/%Y} · {p.get_status_display()} · {formatar_brl(p.valor_total)}",
            "url": reverse("gestao_pedido_detalhe", args=[p.pk]),
        }

    @staticmethod
    def _projeto(p):
        return {
            "tipo": "Projeto", "titulo": p.titulo, "codigo": codigo(p),
            "detalhe": p.cliente or "Projeto realizado",
            "url": reverse("gestao_projeto_detalhe", args=[p.pk]),
        }


# ============================================================ pedidos

def _pedidos_base():
    return Pedido.objects.select_related("usuario", "usuario__perfil").prefetch_related("itens__produto")


class GestaoPedidosView(SuperuserGestaoRequiredMixin, View):
    secao_gestao = "pedidos"
    """Todos os pedidos da loja (de todos os clientes)."""

    def get(self, request):
        todos = _pedidos_base()
        status_filtro = request.GET.get("status", "").strip()
        busca = request.GET.get("q", "").strip()

        pedidos = todos.order_by("-criacao")
        if status_filtro in dict(Pedido.STATUS):
            pedidos = pedidos.filter(status=status_filtro)
        if busca:
            lido = ler_codigo(busca)
            filtro = (
                Q(usuario__username__icontains=busca) | Q(usuario__first_name__icontains=busca)
                | Q(usuario__last_name__icontains=busca) | Q(usuario__email__icontains=busca)
                | Q(endereco__icontains=busca) | Q(cupom_codigo__icontains=busca)
            )
            numero = lido[1] if lido and lido[0] == "PED" else (int(busca.lstrip("#")) if busca.lstrip("#").isdigit() else None)
            if numero is not None:
                filtro |= Q(pk=numero)
            pedidos = pedidos.filter(filtro)

        validos = todos.exclude(status="CANCELADO")
        somas = validos.aggregate(valor=Sum("valor_total"), custo=Sum("custo_total"))
        receita = somas["valor"] or Decimal("0")
        custo = somas["custo"] or Decimal("0")
        quantidade_validos = validos.count()
        por_status = dict(todos.values_list("status").annotate(n=Count("id")))

        ctx = {
            "pedidos": pedidos[:200],
            "status_choices": Pedido.STATUS,
            "status_filtro": status_filtro,
            "busca": busca,
            "funil": [{"chave": c, "nome": n, "total": por_status.get(c, 0)} for c, n in Pedido.STATUS],
            "total_pedidos": todos.count(),
            "total_valor": receita,
            "total_lucro": receita - custo,
            "ticket_medio": (receita / quantidade_validos) if quantidade_validos else Decimal("0"),
            "secao_ativa": "pedidos",
        }
        return render(request, "gestao/pedidos.html", ctx)


class GestaoPedidoDetalheView(SuperuserGestaoRequiredMixin, View):
    secao_gestao = "pedidos"
    def get(self, request, pk):
        pedido = get_object_or_404(_pedidos_base(), pk=pk)
        itens = list(pedido.itens.select_related("produto"))
        subtotal = sum((i.subtotal() for i in itens), Decimal("0"))
        ctx = {
            "pedido": pedido,
            "itens": itens,
            "subtotal": subtotal,
            "cliente": cliente_do_pedido(pedido),
            "status_choices": Pedido.STATUS,
            "secao_ativa": "pedidos",
        }
        return render(request, "gestao/pedido_detalhe.html", ctx)

    def put(self, request, pk):
        pedido = get_object_or_404(Pedido, pk=pk)
        try:
            dados = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "erro": "JSON inválido."}, status=400)
        novo_status = dados.get("status")
        if novo_status not in dict(Pedido.STATUS):
            return JsonResponse({"success": False, "erro": "Status inválido."}, status=400)
        pedido.status = novo_status
        pedido.save(update_fields=["status", "modificado"])
        return JsonResponse({"success": True, "status": pedido.status, "status_display": pedido.get_status_display()})


# ============================================================ etiquetas

# Folhas e rolos. Medidas em milímetros; "folha" é o tamanho do papel.
MODELOS_ETIQUETA = [
    {"id": "a4-65", "nome": "A4 · 65 por folha — 38,2 × 21,2 mm (tipo Pimaco A4251)", "folha": [210, 297], "w": 38.2, "h": 21.2, "colunas": 5, "linhas": 13, "gx": 0, "gy": 0},
    {"id": "a4-33", "nome": "A4 · 33 por folha — 63,5 × 25,4 mm (tipo Pimaco A4256)", "folha": [210, 297], "w": 63.5, "h": 25.4, "colunas": 3, "linhas": 11, "gx": 2.5, "gy": 0},
    {"id": "a4-21", "nome": "A4 · 21 por folha — 63,5 × 38,1 mm (tipo Pimaco A4260)", "folha": [210, 297], "w": 63.5, "h": 38.1, "colunas": 3, "linhas": 7, "gx": 2.5, "gy": 0},
    {"id": "a4-16", "nome": "A4 · 16 por folha — 99,0 × 33,9 mm (tipo Pimaco A4262)", "folha": [210, 297], "w": 99.0, "h": 33.9, "colunas": 2, "linhas": 8, "gx": 2.5, "gy": 0},
    {"id": "a4-14", "nome": "A4 · 14 por folha — 99,0 × 38,1 mm (tipo Pimaco A4263)", "folha": [210, 297], "w": 99.0, "h": 38.1, "colunas": 2, "linhas": 7, "gx": 2.5, "gy": 0},
    {"id": "a4-10", "nome": "A4 · 10 por folha — 99,0 × 57,0 mm", "folha": [210, 297], "w": 99.0, "h": 57.0, "colunas": 2, "linhas": 5, "gx": 2.5, "gy": 0},
    {"id": "a4-4", "nome": "A4 · 4 por folha — 99,0 × 139,0 mm (envio)", "folha": [210, 297], "w": 99.0, "h": 139.0, "colunas": 2, "linhas": 2, "gx": 2.5, "gy": 0},
    {"id": "rolo-100x150", "nome": "Térmica · 100 × 150 mm (envio)", "folha": [100, 150], "w": 100, "h": 150, "colunas": 1, "linhas": 1, "gx": 0, "gy": 0, "rolo": True},
    {"id": "rolo-100x50", "nome": "Térmica · 100 × 50 mm", "folha": [100, 50], "w": 100, "h": 50, "colunas": 1, "linhas": 1, "gx": 0, "gy": 0, "rolo": True},
    {"id": "rolo-60x40", "nome": "Térmica · 60 × 40 mm", "folha": [60, 40], "w": 60, "h": 40, "colunas": 1, "linhas": 1, "gx": 0, "gy": 0, "rolo": True},
    {"id": "rolo-50x30", "nome": "Térmica · 50 × 30 mm", "folha": [50, 30], "w": 50, "h": 30, "colunas": 1, "linhas": 1, "gx": 0, "gy": 0, "rolo": True},
    {"id": "rolo-40x25", "nome": "Térmica · 40 × 25 mm (preço)", "folha": [40, 25], "w": 40, "h": 25, "colunas": 1, "linhas": 1, "gx": 0, "gy": 0, "rolo": True},
    {"id": "personalizado", "nome": "Personalizado (digite as medidas)", "folha": [210, 297], "w": 63.5, "h": 38.1, "colunas": 3, "linhas": 7, "gx": 2.5, "gy": 0},
]
MODELO_PADRAO = {"produto": "a4-33", "pedido": "a4-4", "orcamento": "a4-10", "projeto": "a4-21", "livre": "a4-21"}
TIPOS_ETIQUETA = [
    ("produto", "Produto / preço"),
    ("pedido", "Pedido / envio"),
    ("orcamento", "Ordem de produção"),
    ("projeto", "Projeto"),
    ("livre", "Texto livre"),
]


def _etiquetas_produtos(request):
    dados = []
    for p in Produto.objects.filter(ativo=True).select_related("categoria").order_by("nome_produto")[:500]:
        dados.append({
            "id": p.pk, "codigo": codigo(p), "busca": f"{p.nome_produto} {p.categoria.nome_categoria if p.categoria_id else ''} {codigo(p)}".lower(),
            "titulo": p.nome_produto,
            "linha": p.categoria.nome_categoria if p.categoria_id else "",
            "preco": formatar_brl(p.preco_atual()) if p.preco_atual() > 0 else "Sob consulta",
            "preco_de": formatar_brl(p.preco) if p.preco_atual() < p.preco else "",
            "estoque": p.estoque,
            "qr": _url_site(request, "product_detail", p.pk),
            "lista": f"{formatar_brl(p.preco) if p.preco > 0 else 'Sob consulta'} · estoque {p.estoque}",
        })
    return dados


def _etiquetas_pedidos(request):
    dados = []
    for p in _pedidos_base().exclude(status="CANCELADO").order_by("-criacao")[:150]:
        c = cliente_do_pedido(p)
        itens = sum(i.quantidade for i in p.itens.all())
        dados.append({
            "id": p.pk, "codigo": codigo(p), "busca": f"{p.pk} {c['nome']} {c['email']} {codigo(p)}".lower(),
            "titulo": c["nome"], "endereco": c["endereco"], "cidade": c["cidade"], "cep": c["cep"],
            "telefone": c["telefone"], "itens": f"{itens} {'item' if itens == 1 else 'itens'}",
            "data": f"{p.criacao:%d/%m/%Y}", "status": p.get_status_display(),
            "qr": request.build_absolute_uri(reverse("gestao_pedido_detalhe", args=[p.pk])),
            "lista": f"#{p.pk} · {p.criacao:%d/%m/%Y} · {p.get_status_display()} · {formatar_brl(p.valor_total)}",
        })
    return dados


def _etiquetas_orcamentos(request):
    dados = []
    for o in Orcamento.objects.filter(ativo=True).prefetch_related("itens__produto", "itens__projeto").order_by("-criacao")[:150]:
        itens = [f"{i.quantidade}× {i.nome_display()}" for i in o.itens.all()][:4]
        dados.append({
            "id": o.pk, "codigo": codigo(o), "busca": f"{o.pk} {o.titulo} {o.cliente_nome} {codigo(o)}".lower(),
            "titulo": o.titulo, "cliente": o.cliente_nome, "telefone": o.cliente_telefone,
            "entrega": f"{o.data_prevista_entrega:%d/%m/%Y}" if o.data_prevista_entrega else "",
            "itens": itens, "status": o.get_status_display(),
            "qr": request.build_absolute_uri(reverse("orcamento_detalhe", args=[o.pk])),
            "lista": f"{o.cliente_nome or 'Sem cliente'} · {o.get_status_display()} · {formatar_brl(o.valor_total())}",
        })
    return dados


def _etiquetas_projetos(request):
    dados = []
    for p in Projeto.objects.filter(ativo=True).order_by("-criacao")[:200]:
        dados.append({
            "id": p.pk, "codigo": codigo(p), "busca": f"{p.titulo} {p.cliente} {codigo(p)}".lower(),
            "titulo": p.titulo, "cliente": p.cliente,
            "data": f"{p.data_execucao:%d/%m/%Y}" if p.data_execucao else "",
            "qr": _url_site(request, "project_detail", p.pk),
            "lista": p.cliente or "Projeto realizado",
        })
    return dados


class EtiquetasView(SuperuserGestaoRequiredMixin, View):
    secao_gestao = "etiquetas"
    def get(self, request):
        tipo = request.GET.get("tipo", "produto")
        if tipo not in dict(TIPOS_ETIQUETA):
            tipo = "produto"
        selecionados = [int(n) for n in re.findall(r"\d+", request.GET.get("ids", ""))][:300]
        dados = {
            "produto": _etiquetas_produtos(request),
            "pedido": _etiquetas_pedidos(request),
            "orcamento": _etiquetas_orcamentos(request),
            "projeto": _etiquetas_projetos(request),
        }
        ctx = {
            "tipos": TIPOS_ETIQUETA,
            "tipo": tipo,
            "dados_etiquetas": {
                "itens": dados,
                "modelos": MODELOS_ETIQUETA,
                "padrao": MODELO_PADRAO,
                "tipo": tipo,
                "selecionados": selecionados,
                "remetente": {**REMETENTE, "email": settings.EMAIL_CONTATO},
                "qr": reverse("gestao_qrcode"),
            },
            "secao_ativa": "etiquetas",
        }
        return render(request, "gestao/etiquetas.html", ctx)


class QrCodeView(SuperuserGestaoRequiredMixin, View):
    secao_gestao = "etiquetas"
    """QR code em SVG (nítido em qualquer tamanho de etiqueta)."""

    def get(self, request):
        import qrcode
        import qrcode.image.svg

        texto = request.GET.get("d", "")[:400]
        if not texto:
            raise Http404
        imagem = qrcode.make(texto, image_factory=qrcode.image.svg.SvgPathImage, border=1,
                             error_correction=qrcode.constants.ERROR_CORRECT_M)
        resposta = HttpResponse(imagem.to_string(encoding="unicode"), content_type="image/svg+xml")
        resposta["Cache-Control"] = "private, max-age=86400"
        return resposta


# ============================================================ equipe e clientes

class EquipeView(SuperuserGestaoRequiredMixin, View):
    """Equipe (quem entra na gestão e com qual função) e clientes do site."""
    secao_gestao = "equipe"

    def _equipe(self):
        from django.contrib.auth.models import User
        from .equipe import FUNCOES, funcoes_do_usuario

        grupos = [f["grupo"] for f in FUNCOES]
        pessoas = (User.objects.filter(Q(is_superuser=True) | Q(is_staff=True) | Q(groups__name__in=grupos))
                   .distinct().prefetch_related("groups").order_by("-is_active", "first_name", "username"))
        linhas = []
        for u in pessoas:
            funcoes = funcoes_do_usuario(u) if u.is_active else ({"gestao"} if u.is_superuser else
                      {f["codigo"] for f in FUNCOES if f["grupo"] in {g.name for g in u.groups.all()}})
            linhas.append({"u": u, "funcao": next(iter(sorted(funcoes)), "")})
        return linhas

    def _clientes(self, busca):
        from django.contrib.auth.models import User
        vendidos = Q(pedidos__status__in=("PENDENTE", "PAGO", "ENVIADO", "ENTREGUE"))
        clientes = (User.objects.filter(is_staff=False, is_superuser=False)
                    .select_related("perfil")
                    .annotate(n_pedidos=Count("pedidos", filter=vendidos, distinct=True),
                              gasto=Sum("pedidos__valor_total", filter=vendidos))
                    .order_by("-gasto", "-date_joined"))
        if busca:
            clientes = clientes.filter(Q(username__icontains=busca) | Q(first_name__icontains=busca)
                                       | Q(last_name__icontains=busca) | Q(email__icontains=busca)
                                       | Q(perfil__telefone__icontains=busca) | Q(perfil__cidade__icontains=busca))
        return clientes

    def get(self, request):
        from datetime import timedelta
        from django.contrib.auth.models import User
        from django.utils import timezone
        from .equipe import FUNCOES

        aba = "clientes" if request.GET.get("aba") == "clientes" else "equipe"
        busca = request.GET.get("q", "").strip()[:80]
        equipe = self._equipe()
        todos_clientes = User.objects.filter(is_staff=False, is_superuser=False)
        clientes = self._clientes(busca)
        lista_clientes = []
        for c in clientes[:300]:
            try:
                perfil = c.perfil
            except Exception:
                perfil = None
            telefone = getattr(perfil, "telefone", "") or ""
            digitos = _digitos(telefone)
            if digitos and not digitos.startswith("55"):
                digitos = "55" + digitos
            lista_clientes.append({
                "u": c, "telefone": telefone,
                "cidade": " - ".join(p for p in (getattr(perfil, "cidade", ""), getattr(perfil, "estado", "")) if p),
                "n_pedidos": c.n_pedidos, "gasto": c.gasto or Decimal("0"),
                "whatsapp": f"https://wa.me/{digitos}" if len(digitos) >= 12 else "",
            })
        from .google import endereco_de_retorno, google_ativo, ids_com_google
        com_google = ids_com_google()
        for linha in lista_clientes:
            linha["google"] = linha["u"].pk in com_google
        ctx = {
            "google": {
                "ativo": google_ativo(),
                "total": User.objects.filter(pk__in=com_google, is_staff=False, is_superuser=False).count(),
                "retorno": endereco_de_retorno(),
                "origem": settings.SITE_URL,
            },
            "aba": aba,
            "busca": busca,
            "funcoes": FUNCOES,
            "equipe": equipe,
            "ativos": sum(1 for p in equipe if p["u"].is_active),
            "contagem_funcoes": {f["codigo"]: sum(1 for p in equipe if p["u"].is_active and p["funcao"] == f["codigo"]) for f in FUNCOES},
            "clientes": lista_clientes,
            "clientes_total": todos_clientes.count(),
            "clientes_com_pedido": todos_clientes.filter(pedidos__isnull=False).distinct().count(),
            "clientes_novos": todos_clientes.filter(date_joined__gte=timezone.now() - timedelta(days=30)).count(),
            "secao_ativa": "equipe",
        }
        return render(request, "gestao/equipe.html", ctx)

    def post(self, request):
        from django.contrib import messages
        from django.contrib.auth.models import User
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        from django.core.validators import validate_email
        from django.db import transaction
        from django.shortcuts import redirect
        from .equipe import POR_CODIGO, definir_funcao, funcoes_do_usuario

        acao = request.POST.get("acao")
        voltar = redirect(reverse("gestao_equipe"))

        def gestores_ativos(exceto=None):
            qs = User.objects.filter(is_active=True, is_superuser=True)
            return qs.exclude(pk=exceto).count() if exceto else qs.count()

        if acao == "alternar":
            pessoa = get_object_or_404(User, pk=request.POST.get("pk"))
            if pessoa == request.user:
                messages.error(request, "Você não pode desativar a sua própria conta.")
            elif pessoa.is_active and pessoa.is_superuser and gestores_ativos(exceto=pessoa.pk) == 0:
                messages.error(request, "Precisa ficar pelo menos uma pessoa ativa com a função Gestão.")
            else:
                pessoa.is_active = not pessoa.is_active
                pessoa.save(update_fields=["is_active"])
                messages.success(request, f"{pessoa.get_full_name() or pessoa.username} {'reativado(a)' if pessoa.is_active else 'desativado(a)'}.")
            return voltar

        if acao != "salvar":
            return voltar

        pk = request.POST.get("pk") or None
        pessoa = get_object_or_404(User, pk=pk) if pk else User()
        nome = request.POST.get("first_name", "").strip()[:150]
        sobrenome = request.POST.get("last_name", "").strip()[:150]
        usuario = request.POST.get("username", "").strip()[:150]
        email = request.POST.get("email", "").strip().lower()[:254]
        senha = request.POST.get("password", "")
        funcao = request.POST.get("funcao", "")
        erros = []
        if not usuario or not re.fullmatch(r"[\w.@+-]+", usuario):
            erros.append("Usuário: use letras, números e . _ - (sem espaço).")
        elif User.objects.filter(username__iexact=usuario).exclude(pk=pessoa.pk).exists():
            erros.append("Já existe alguém com esse usuário.")
        if email:
            try:
                validate_email(email)
            except ValidationError:
                erros.append("E-mail inválido.")
            else:
                if User.objects.filter(email__iexact=email).exclude(pk=pessoa.pk).exists():
                    erros.append("Esse e-mail já está em outra conta.")
        if funcao not in POR_CODIGO:
            erros.append("Escolha a função da pessoa.")
        if not pk and not senha:
            erros.append("Defina uma senha para o primeiro acesso.")
        if senha:
            try:
                validate_password(senha, pessoa if pk else None)
            except ValidationError as e:
                erros.extend(e.messages)
        if pk and pessoa == request.user and funcao != "gestao":
            erros.append("Você não pode tirar a função Gestão de você mesmo(a).")
        if pk and pessoa.is_superuser and funcao != "gestao" and gestores_ativos(exceto=pessoa.pk) == 0:
            erros.append("Precisa ficar pelo menos uma pessoa ativa com a função Gestão.")
        if erros:
            messages.error(request, "Não foi salvo: " + " ".join(erros))
            return voltar

        with transaction.atomic():
            pessoa.username, pessoa.first_name, pessoa.last_name, pessoa.email = usuario, nome, sobrenome, email
            if senha:
                pessoa.set_password(senha)
            if pessoa != request.user:
                pessoa.is_active = request.POST.get("ativo", "1") == "1"
            pessoa.save()
            definir_funcao(pessoa, funcao)
        if senha and pessoa == request.user:
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, pessoa)
        messages.success(request, f"{pessoa.get_full_name() or pessoa.username} salvo(a) como {POR_CODIGO[funcao]['titulo']}.")
        return voltar
