import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View

from .models import (
    Carrinho,
    CategoriaProdutos,
    ImagemProduto,
    ImagemProjeto,
    ItemCarrinho,
    ItemOrcamento,
    ItemPedido,
    Orcamento,
    Pedido,
    PerfilUsuario,
    Produto,
    Projeto,
)

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.shortcuts import redirect


class SuperuserGestaoRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = "login"

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect("login")

        messages.error(
            self.request,
            "Você não tem permissão para acessar a área de gestão."
        )
        return redirect("home")


# ============================================================
# HELPERS GERAIS
# ============================================================

def _to_decimal(valor, default="0"):
    try:
        if valor is None:
            return Decimal(default)
        valor = str(valor).strip().replace(".", "").replace(",", ".") if "," in str(valor) else str(valor).strip()
        return Decimal(valor)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _to_date(valor):
    if not valor:
        return None
    return parse_date(str(valor))


def _decimal_float(valor):
    try:
        return float(valor)
    except Exception:
        return 0.0


def _perfil_defaults():
    return {
        "telefone": "",
        "cpf": "",
        "endereco": "",
        "cidade": "",
        "estado": "",
        "cep": "",
    }


def _produtos_ativos():
    imagens_validas = ImagemProduto.objects.exclude(imagem="")
    return (
        Produto.objects.filter(ativo=True)
        .select_related("categoria")
        .prefetch_related(Prefetch("imagens", queryset=imagens_validas))
    )


def _projetos_ativos():
    imagens_validas = ImagemProjeto.objects.exclude(imagem="")
    return Projeto.objects.filter(ativo=True).prefetch_related(
        Prefetch("imagens", queryset=imagens_validas)
    )


def _resumo_carrinho(carrinho):
    itens = carrinho.itens.select_related("produto")
    total_itens = sum(item.quantidade for item in itens)
    total_valor = sum((item.subtotal() for item in itens), Decimal("0.00"))
    return total_itens, total_valor


def _orcamentos_usuario(request):
    return (
        Orcamento.objects.filter(usuario=request.user, ativo=True)
        .prefetch_related("itens", "itens__produto", "itens__projeto")
    )


def _montar_linha_orcamento(orcamento):
    bruto = orcamento.valor_bruto()
    desconto = orcamento.valor_desconto()
    total = orcamento.valor_total()
    custo = orcamento.custo_total()
    lucro = orcamento.lucro_estimado()
    margem = orcamento.margem_lucro_percentual()

    return {
        "orcamento": orcamento,
        "bruto": bruto,
        "desconto": desconto,
        "total": total,
        "custo": custo,
        "lucro": lucro,
        "margem": margem,
    }


def _dados_grafico_mensal_orcamentos(orcamentos):
    dados = {}

    for orcamento in orcamentos:
        mes = timezone.localtime(orcamento.criacao).strftime("%m/%Y")

        if mes not in dados:
            dados[mes] = {
                "receita": Decimal("0.00"),
                "custo": Decimal("0.00"),
                "lucro": Decimal("0.00"),
                "quantidade": 0,
            }

        dados[mes]["receita"] += orcamento.valor_total()
        dados[mes]["custo"] += orcamento.custo_total()
        dados[mes]["lucro"] += orcamento.lucro_estimado()
        dados[mes]["quantidade"] += 1

    labels = list(dados.keys())

    return {
        "labels": labels,
        "receita": [_decimal_float(dados[mes]["receita"]) for mes in labels],
        "custo": [_decimal_float(dados[mes]["custo"]) for mes in labels],
        "lucro": [_decimal_float(dados[mes]["lucro"]) for mes in labels],
        "quantidade": [dados[mes]["quantidade"] for mes in labels],
    }


# ============================================================
# SITE PÚBLICO
# ============================================================

class HomeView(View):
    def get(self, request):
        ctx = {
            "produtos": _produtos_ativos().order_by("-criacao")[:8],
            "projetos": _projetos_ativos().order_by("-criacao")[:6],
            "categorias": CategoriaProdutos.objects.filter(ativo=True).annotate(
                total_produtos=Count("produtos", filter=Q(produtos__ativo=True))
            ),
        }
        return render(request, "home.html", ctx)


class ProductsView(View):
    def get(self, request):
        categoria_id = request.GET.get("categoria")
        produtos = _produtos_ativos().order_by("nome_produto")
        categoria_ativa = None

        if categoria_id:
            try:
                categoria_ativa = int(categoria_id)
                produtos = produtos.filter(categoria_id=categoria_ativa)
            except (TypeError, ValueError):
                categoria_ativa = None

        ctx = {
            "produtos": produtos,
            "categorias": CategoriaProdutos.objects.filter(ativo=True).order_by("nome_categoria"),
            "categoria_ativa": categoria_ativa,
        }
        return render(request, "products.html", ctx)


class ProductDetailView(View):
    def get(self, request, pk):
        produto = get_object_or_404(_produtos_ativos(), pk=pk)

        relacionados = (
            Produto.objects.filter(categoria=produto.categoria, ativo=True)
            .exclude(pk=produto.pk)
            .select_related("categoria")[:4]
        )

        ctx = {
            "produto": produto,
            "imagens": produto.imagens.all(),
            "relacionados": relacionados,
        }
        return render(request, "product.html", ctx)


class CategoriesView(View):
    def get(self, request):
        categorias = (
            CategoriaProdutos.objects.filter(ativo=True)
            .annotate(total_produtos=Count("produtos", filter=Q(produtos__ativo=True)))
            .order_by("nome_categoria")
        )

        ctx = {
            "categorias": categorias,
            "total_categorias": categorias.count(),
            "total_produtos": Produto.objects.filter(ativo=True).count(),
        }
        return render(request, "categories.html", ctx)


class CategoryDetailView(View):
    def get(self, request, pk):
        categoria = get_object_or_404(
            CategoriaProdutos.objects.filter(ativo=True).annotate(
                total_produtos=Count("produtos", filter=Q(produtos__ativo=True))
            ),
            pk=pk,
        )

        produtos = _produtos_ativos().filter(categoria=categoria).order_by("nome_produto")

        categorias = (
            CategoriaProdutos.objects.filter(ativo=True)
            .annotate(total_produtos=Count("produtos", filter=Q(produtos__ativo=True)))
            .order_by("nome_categoria")
        )

        ctx = {
            "categoria": categoria,
            "categorias": categorias,
            "produtos": produtos,
        }
        return render(request, "category_detail.html", ctx)


class ProjectsView(View):
    def get(self, request):
        ctx = {
            "projetos": _projetos_ativos().order_by("-criacao"),
        }
        return render(request, "projects.html", ctx)


class ProjectDetailView(View):
    def get(self, request, pk):
        projeto = get_object_or_404(_projetos_ativos(), pk=pk)

        ctx = {
            "projeto": projeto,
            "imagens": projeto.imagens.all(),
        }
        return render(request, "project_detail.html", ctx)


# ============================================================
# CARRINHO
# ============================================================

class CartView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return render(request, "cart.html", {"itens": [], "total": Decimal("0.00")})

        carrinho, _created = Carrinho.objects.get_or_create(usuario=request.user)

        itens = (
            carrinho.itens.select_related("produto", "produto__categoria")
            .prefetch_related("produto__imagens")
        )

        total = sum((item.subtotal() for item in itens), Decimal("0.00"))

        return render(
            request,
            "cart.html",
            {
                "carrinho": carrinho,
                "itens": itens,
                "total": total,
            },
        )


class AddToCartView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse(
                {
                    "success": False,
                    "auth_required": True,
                    "redirect": reverse("login"),
                },
                status=401,
            )

        produto = get_object_or_404(Produto, pk=pk, ativo=True)

        try:
            quantidade = int(request.POST.get("quantidade", 1))
        except (TypeError, ValueError):
            quantidade = 1

        quantidade = max(1, quantidade)

        carrinho, _created = Carrinho.objects.get_or_create(usuario=request.user)

        item, criado = ItemCarrinho.objects.get_or_create(
            carrinho=carrinho,
            produto=produto,
            defaults={"quantidade": quantidade},
        )

        if not criado:
            item.quantidade += quantidade
            item.save(update_fields=["quantidade", "modificado"])

        total_itens, total_valor = _resumo_carrinho(carrinho)

        return JsonResponse(
            {
                "success": True,
                "total_itens": total_itens,
                "total_valor": str(total_valor),
                "item_id": item.id,
                "item_quantidade": item.quantidade,
                "item_subtotal": str(item.subtotal()),
            }
        )


class UpdateCartItemView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"success": False}, status=401)

        item = get_object_or_404(
            ItemCarrinho,
            pk=pk,
            carrinho__usuario=request.user,
        )

        acao = request.POST.get("acao", "incrementar")
        removido = False

        if acao == "incrementar":
            item.quantidade += 1
            item.save(update_fields=["quantidade", "modificado"])

        elif acao == "decrementar":
            item.quantidade -= 1

            if item.quantidade <= 0:
                item.delete()
                removido = True
            else:
                item.save(update_fields=["quantidade", "modificado"])

        elif acao == "definir":
            try:
                nova_quantidade = int(request.POST.get("quantidade", 1))
            except (TypeError, ValueError):
                nova_quantidade = 1

            if nova_quantidade <= 0:
                item.delete()
                removido = True
            else:
                item.quantidade = nova_quantidade
                item.save(update_fields=["quantidade", "modificado"])

        carrinho = get_object_or_404(Carrinho, usuario=request.user)
        total_itens, total_valor = _resumo_carrinho(carrinho)

        return JsonResponse(
            {
                "success": True,
                "removido": removido,
                "item_quantidade": 0 if removido else item.quantidade,
                "item_subtotal": "0" if removido else str(item.subtotal()),
                "total_itens": total_itens,
                "total_valor": str(total_valor),
            }
        )


class RemoveCartItemView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"success": False}, status=401)

        item = get_object_or_404(
            ItemCarrinho,
            pk=pk,
            carrinho__usuario=request.user,
        )

        item.delete()

        carrinho = get_object_or_404(Carrinho, usuario=request.user)
        total_itens, total_valor = _resumo_carrinho(carrinho)

        return JsonResponse(
            {
                "success": True,
                "total_itens": total_itens,
                "total_valor": str(total_valor),
            }
        )


# ============================================================
# CHECKOUT / PEDIDOS DO SITE
# ============================================================

class CheckoutView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        carrinho, _created = Carrinho.objects.get_or_create(usuario=request.user)

        itens = (
            carrinho.itens.select_related("produto")
            .prefetch_related("produto__imagens")
        )

        if not itens.exists():
            messages.info(request, "Seu carrinho está vazio.")
            return redirect("cart")

        total = sum((item.subtotal() for item in itens), Decimal("0.00"))

        perfil, _created = PerfilUsuario.objects.get_or_create(
            usuario=request.user,
            defaults=_perfil_defaults(),
        )

        ctx = {
            "carrinho": carrinho,
            "itens": itens,
            "total": total,
            "perfil": perfil,
            "metodos_pagamento": Pedido.METODOS_PAGAMENTO,
        }

        return render(request, "checkout.html", ctx)

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        carrinho = get_object_or_404(Carrinho, usuario=request.user)
        itens = list(carrinho.itens.select_related("produto"))

        if not itens:
            messages.error(request, "Seu carrinho está vazio.")
            return redirect("cart")

        endereco = request.POST.get("endereco", "").strip()
        metodo_pagamento = request.POST.get("metodo_pagamento", "A_COMBINAR").strip()

        metodos_validos = dict(Pedido.METODOS_PAGAMENTO).keys()

        if not endereco:
            messages.error(request, "Informe o endereço de entrega.")
            return redirect("checkout")

        if metodo_pagamento not in metodos_validos:
            messages.error(request, "Escolha uma forma de pagamento válida.")
            return redirect("checkout")

        with transaction.atomic():
            pedido = Pedido.objects.create(
                usuario=request.user,
                endereco=endereco,
                metodo_pagamento=metodo_pagamento,
                status="PENDENTE",
            )

            for item in itens:
                ItemPedido.objects.create(
                    pedido=pedido,
                    produto=item.produto,
                    quantidade=item.quantidade,
                    preco_unitario=item.produto.preco,
                    custo_unitario=item.produto.custo,
                )

            pedido.recalcular_totais(salvar=True)
            carrinho.itens.all().delete()

        messages.success(request, "Pedido realizado com sucesso!")
        return redirect("order_detail", pk=pedido.pk)


class OrdersView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        pedidos = (
            Pedido.objects.filter(usuario=request.user)
            .order_by("-criacao")
            .prefetch_related("itens__produto")
        )

        return render(request, "orders.html", {"pedidos": pedidos})


class OrderDetailView(View):
    def get(self, request, pk):
        if not request.user.is_authenticated:
            return redirect("login")

        pedido = get_object_or_404(
            Pedido.objects.prefetch_related("itens__produto"),
            pk=pk,
            usuario=request.user,
        )

        return render(
            request,
            "order_detail.html",
            {
                "pedido": pedido,
                "itens": pedido.itens.select_related("produto"),
            },
        )


class PendingOrdersView(LoginRequiredMixin, View):
    login_url = "login"

    def get(self, request):
        if not request.user.is_staff:
            messages.error(request, "Você não tem permissão para acessar pedidos pendentes.")
            return redirect("home")

        pedidos = (
            Pedido.objects.filter(status="PENDENTE")
            .order_by("-criacao")
            .prefetch_related("itens__produto")
        )

        return render(request, "pendings.html", {"pedidos": pedidos})


# ============================================================
# PERFIL / CADASTRO / LOGIN
# ============================================================

class ProfileView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        perfil, _created = PerfilUsuario.objects.get_or_create(
            usuario=request.user,
            defaults=_perfil_defaults(),
        )

        return render(request, "profile.html", {"perfil": perfil})

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        perfil, _created = PerfilUsuario.objects.get_or_create(
            usuario=request.user,
            defaults=_perfil_defaults(),
        )

        request.user.first_name = request.POST.get("nome", "").strip()
        request.user.last_name = request.POST.get("sobrenome", "").strip()
        request.user.username = request.POST.get("username", "").strip()
        request.user.email = request.POST.get("email", "").strip().lower()
        request.user.save()

        perfil.telefone = request.POST.get("telefone", "").strip()
        perfil.cpf = request.POST.get("cpf", "").strip()
        perfil.endereco = request.POST.get("endereco", "").strip()
        perfil.cidade = request.POST.get("cidade", "").strip()
        perfil.estado = request.POST.get("estado", "").strip().upper()
        perfil.cep = request.POST.get("cep", "").strip()
        perfil.save()

        messages.success(request, "Perfil atualizado com sucesso!")
        return redirect("profile")


class RegisterView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect("profile")

        return render(request, "register.html")

    def post(self, request):
        if request.user.is_authenticated:
            return redirect("profile")

        nome = request.POST.get("nome", "").strip()
        sobrenome = request.POST.get("sobrenome", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "").strip()
        password_confirm = request.POST.get("password_confirm", "").strip()

        telefone = request.POST.get("telefone", "").strip()
        cpf = request.POST.get("cpf", "").strip()
        endereco = request.POST.get("endereco", "").strip()
        cidade = request.POST.get("cidade", "").strip()
        estado = request.POST.get("estado", "").strip().upper()
        cep = request.POST.get("cep", "").strip()

        ctx = {"dados": request.POST}

        campos_obrigatorios = [
            nome,
            sobrenome,
            username,
            email,
            password,
            password_confirm,
            telefone,
            cpf,
            endereco,
            cidade,
            estado,
            cep,
        ]

        if not all(campos_obrigatorios):
            messages.error(request, "Preencha todos os campos obrigatórios.")
            return render(request, "register.html", ctx)

        if password != password_confirm:
            messages.error(request, "As senhas não conferem.")
            return render(request, "register.html", ctx)

        if User.objects.filter(username=username).exists():
            messages.error(request, "Este nome de usuário já está em uso.")
            return render(request, "register.html", ctx)

        if User.objects.filter(email=email).exists():
            messages.error(request, "Este e-mail já está cadastrado.")
            return render(request, "register.html", ctx)

        if len(estado) != 2:
            messages.error(request, "Informe o estado com 2 letras. Exemplo: SP.")
            return render(request, "register.html", ctx)

        try:
            validate_password(password)
        except ValidationError as erros:
            for erro in erros:
                messages.error(request, erro)
            return render(request, "register.html", ctx)

        try:
            with transaction.atomic():
                usuario = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=nome,
                    last_name=sobrenome,
                )

                PerfilUsuario.objects.create(
                    usuario=usuario,
                    telefone=telefone,
                    cpf=cpf,
                    endereco=endereco,
                    cidade=cidade,
                    estado=estado,
                    cep=cep,
                )

                login(request, usuario)

        except Exception:
            messages.error(request, "Não foi possível criar sua conta. Tente novamente.")
            return render(request, "register.html", ctx)

        messages.success(request, "Conta criada com sucesso. Seja bem-vindo!")
        return redirect("profile")


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect("home")

        return render(request, "login.html")

    def post(self, request):
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        next_url = request.POST.get("next") or request.GET.get("next")

        if not username or not password:
            messages.error(request, "Informe seu usuário e sua senha.")
            return render(request, "login.html")

        usuario = authenticate(request, username=username, password=password)

        if usuario is None:
            messages.error(request, "Usuário ou senha inválidos.")
            return render(request, "login.html")

        if not usuario.is_active:
            messages.error(request, "Este usuário está inativo.")
            return render(request, "login.html")

        login(request, usuario)
        return redirect(next_url or "home")


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect("home")


class PaymentView(View):
    def get(self, request):
        return render(request, "payment.html")


# ============================================================
# ÁREA INTERNA — DASHBOARD
# ============================================================

class GestaoDashboardView(SuperuserGestaoRequiredMixin, View):
    login_url = "login"

    def get(self, request):
        orcamentos = _orcamentos_usuario(request)
        pedidos = (
            Pedido.objects.filter(usuario=request.user)
            .prefetch_related("itens__produto")
            .order_by("-criacao")
        )

        total_orcamentos = orcamentos.count()
        total_pedidos = pedidos.count()

        valor_total_orcamentos = sum(
            (orcamento.valor_total() for orcamento in orcamentos),
            Decimal("0.00"),
        )

        valor_aprovado = sum(
            (orcamento.valor_total() for orcamento in orcamentos if orcamento.status == "APROVADO"),
            Decimal("0.00"),
        )

        custo_aprovado = sum(
            (orcamento.custo_total() for orcamento in orcamentos if orcamento.status == "APROVADO"),
            Decimal("0.00"),
        )

        lucro_aprovado = valor_aprovado - custo_aprovado

        valor_pedidos = sum(
            (pedido.valor_total for pedido in pedidos),
            Decimal("0.00"),
        )

        custo_pedidos = sum(
            (pedido.custo_total for pedido in pedidos),
            Decimal("0.00"),
        )

        lucro_pedidos = valor_pedidos - custo_pedidos

        resumo_status = orcamentos.values("status").annotate(total=Count("id"))
        resumo_status_dict = {item["status"]: item["total"] for item in resumo_status}

        resumo_status_lista = [
            {
                "chave": chave,
                "rotulo": rotulo,
                "total": resumo_status_dict.get(chave, 0),
            }
            for chave, rotulo in Orcamento.STATUS
        ]

        grafico_orcamentos = _dados_grafico_mensal_orcamentos(orcamentos.order_by("criacao"))

        ctx = {
            "total_orcamentos": total_orcamentos,
            "total_pedidos": total_pedidos,

            "valor_total_orcamentos": valor_total_orcamentos,
            "valor_aprovado": valor_aprovado,
            "custo_aprovado": custo_aprovado,
            "lucro_aprovado": lucro_aprovado,

            "valor_pedidos": valor_pedidos,
            "custo_pedidos": custo_pedidos,
            "lucro_pedidos": lucro_pedidos,

            "resumo_status_lista": resumo_status_lista,
            "orcamentos_recentes": orcamentos.order_by("-criacao")[:6],
            "pedidos_recentes": pedidos[:6],

            "grafico_labels": json.dumps(grafico_orcamentos["labels"]),
            "grafico_receita": json.dumps(grafico_orcamentos["receita"]),
            "grafico_custo": json.dumps(grafico_orcamentos["custo"]),
            "grafico_lucro": json.dumps(grafico_orcamentos["lucro"]),

            "secao_ativa": "dashboard",
        }

        return render(request, "gestao/dashboard.html", ctx)


# ============================================================
# ÁREA INTERNA — PRODUTOS
# ============================================================

class GestaoProdutosView(SuperuserGestaoRequiredMixin, View):
    login_url = "login"
    template_name = "gestao/produtos.html"

    def get(self, request, pk=None):
        produto = None

        if pk:
            produto = get_object_or_404(
                Produto.objects.prefetch_related("imagens"),
                pk=pk,
                ativo=True,
            )

        produtos = Produto.objects.filter(ativo=True).select_related("categoria").order_by("nome_produto")

        busca = request.GET.get("q", "").strip()
        categoria_filtro = request.GET.get("categoria", "").strip()

        if busca:
            produtos = produtos.filter(
                Q(nome_produto__icontains=busca) |
                Q(descricao_produto__icontains=busca)
            )

        if categoria_filtro:
            produtos = produtos.filter(categoria_id=categoria_filtro)

        ctx = {
            "produto": produto,
            "produtos": produtos,
            "categorias": CategoriaProdutos.objects.filter(ativo=True).order_by("nome_categoria"),
            "busca": busca,
            "categoria_filtro": categoria_filtro,
            "secao_ativa": "produtos",
        }

        return render(request, self.template_name, ctx)

    def post(self, request, pk=None):
        produto = None

        if pk:
            produto = get_object_or_404(Produto, pk=pk, ativo=True)

        categoria_id = request.POST.get("categoria", "").strip()
        nome_produto = request.POST.get("nome_produto", "").strip()

        if not categoria_id:
            messages.error(request, "Selecione uma categoria para o produto.")
            return redirect(request.path)

        if not nome_produto:
            messages.error(request, "Informe o nome do produto.")
            return redirect(request.path)

        categoria = get_object_or_404(CategoriaProdutos, pk=categoria_id, ativo=True)

        with transaction.atomic():
            if produto is None:
                produto = Produto()

            produto.categoria = categoria
            produto.nome_produto = nome_produto
            produto.descricao_produto = request.POST.get("descricao_produto", "").strip()
            produto.preco = _to_decimal(request.POST.get("preco", "0"))
            produto.custo = _to_decimal(request.POST.get("custo", "0"))

            try:
                produto.estoque = max(0, int(request.POST.get("estoque", 0)))
            except (TypeError, ValueError):
                produto.estoque = 0

            produto.avaliacao = _to_decimal(request.POST.get("avaliacao", "0"))
            produto.ativo = True
            produto.save()

            imagens_apagar = request.POST.getlist("apagar_imagens[]")
            if imagens_apagar:
                ImagemProduto.objects.filter(
                    pk__in=imagens_apagar,
                    produto=produto,
                ).delete()

            for imagem in request.FILES.getlist("imagens"):
                if imagem:
                    ImagemProduto.objects.create(produto=produto, imagem=imagem)

        messages.success(request, "Produto salvo com sucesso!")
        return redirect("gestao_produto_detalhe", pk=produto.pk)

    def delete(self, request, pk):
        produto = get_object_or_404(Produto, pk=pk, ativo=True)
        produto.ativo = False
        produto.save(update_fields=["ativo", "modificado"])

        return JsonResponse(
            {
                "success": True,
                "redirect": reverse("gestao_produtos"),
            }
        )


# ============================================================
# ÁREA INTERNA — PROJETOS
# ============================================================

class GestaoProjetosView(SuperuserGestaoRequiredMixin, View):
    login_url = "login"
    template_name = "gestao/projetos.html"

    def get(self, request, pk=None):
        projeto = None

        if pk:
            projeto = get_object_or_404(
                Projeto.objects.prefetch_related("imagens"),
                pk=pk,
                ativo=True,
            )

        projetos = Projeto.objects.filter(ativo=True).order_by("-criacao")

        busca = request.GET.get("q", "").strip()

        if busca:
            projetos = projetos.filter(
                Q(titulo__icontains=busca) |
                Q(cliente__icontains=busca) |
                Q(descricao__icontains=busca)
            )

        ctx = {
            "projeto": projeto,
            "projetos": projetos,
            "busca": busca,
            "secao_ativa": "projetos",
        }

        return render(request, self.template_name, ctx)

    def post(self, request, pk=None):
        projeto = None

        if pk:
            projeto = get_object_or_404(Projeto, pk=pk, ativo=True)

        titulo = request.POST.get("titulo", "").strip()

        if not titulo:
            messages.error(request, "Informe o título do projeto.")
            return redirect(request.path)

        with transaction.atomic():
            if projeto is None:
                projeto = Projeto()

            projeto.titulo = titulo
            projeto.descricao = request.POST.get("descricao", "").strip()
            projeto.cliente = request.POST.get("cliente", "").strip()
            projeto.data_execucao = _to_date(request.POST.get("data_execucao"))
            projeto.valor_estimado = _to_decimal(request.POST.get("valor_estimado", "0"))
            projeto.custo_estimado = _to_decimal(request.POST.get("custo_estimado", "0"))
            projeto.ativo = True
            projeto.save()

            imagens_apagar = request.POST.getlist("apagar_imagens[]")
            if imagens_apagar:
                ImagemProjeto.objects.filter(
                    pk__in=imagens_apagar,
                    projeto=projeto,
                ).delete()

            for imagem in request.FILES.getlist("imagens"):
                if imagem:
                    ImagemProjeto.objects.create(projeto=projeto, imagem=imagem)

        messages.success(request, "Projeto salvo com sucesso!")
        return redirect("gestao_projeto_detalhe", pk=projeto.pk)

    def delete(self, request, pk):
        projeto = get_object_or_404(Projeto, pk=pk, ativo=True)
        projeto.ativo = False
        projeto.save(update_fields=["ativo", "modificado"])

        return JsonResponse(
            {
                "success": True,
                "redirect": reverse("gestao_projetos"),
            }
        )


# ============================================================
# ÁREA INTERNA — ORÇAMENTOS
# ============================================================

class OrcamentoView(SuperuserGestaoRequiredMixin, View):
    login_url = "login"
    template_name = "gestao/orcamentos.html"

    def get(self, request, pk=None):
        if pk:
            orcamento = get_object_or_404(
                Orcamento.objects.prefetch_related("itens__produto", "itens__projeto"),
                pk=pk,
                usuario=request.user,
                ativo=True,
            )
        else:
            orcamento = None

        orcamentos = _orcamentos_usuario(request).order_by("-criacao")

        status_filtro = request.GET.get("status", "")
        tipo_filtro = request.GET.get("tipo", "")
        busca = request.GET.get("q", "").strip()

        if status_filtro:
            orcamentos = orcamentos.filter(status=status_filtro)

        if tipo_filtro:
            orcamentos = orcamentos.filter(tipo=tipo_filtro)

        if busca:
            orcamentos = orcamentos.filter(
                Q(titulo__icontains=busca) |
                Q(cliente_nome__icontains=busca) |
                Q(cliente_email__icontains=busca) |
                Q(cliente_telefone__icontains=busca)
            )

        linhas_orcamentos = [_montar_linha_orcamento(item) for item in orcamentos]

        ctx = {
            "orcamento": orcamento,
            "orcamentos": orcamentos,
            "linhas_orcamentos": linhas_orcamentos,

            "status_choices": Orcamento.STATUS,
            "tipo_choices": Orcamento.TIPO,
            "formas_pagamento": Orcamento.FORMAS_PAGAMENTO,

            "status_filtro": status_filtro,
            "tipo_filtro": tipo_filtro,
            "busca": busca,

            "produtos": Produto.objects.filter(ativo=True).order_by("nome_produto"),
            "projetos": Projeto.objects.filter(ativo=True).order_by("titulo"),

            "secao_ativa": "orcamentos",
        }

        return render(request, self.template_name, ctx)

    def post(self, request, pk=None):
        if pk:
            orcamento = get_object_or_404(
                Orcamento,
                pk=pk,
                usuario=request.user,
                ativo=True,
            )
        else:
            orcamento = None

        titulo = request.POST.get("titulo", "").strip()

        if not titulo:
            messages.error(request, "Informe um título para o orçamento.")
            return redirect(request.path)

        with transaction.atomic():
            if orcamento is None:
                orcamento = Orcamento(usuario=request.user)

            orcamento.titulo = titulo
            orcamento.tipo = request.POST.get("tipo", "MISTO")
            orcamento.status = request.POST.get("status", orcamento.status or "RASCUNHO")

            if orcamento.status not in dict(Orcamento.STATUS):
                orcamento.status = "RASCUNHO"

            orcamento.cliente_nome = request.POST.get("cliente_nome", "").strip()
            orcamento.cliente_email = request.POST.get("cliente_email", "").strip()
            orcamento.cliente_telefone = request.POST.get("cliente_telefone", "").strip()

            orcamento.data_validade = _to_date(request.POST.get("data_validade"))
            orcamento.data_prevista_entrega = _to_date(request.POST.get("data_prevista_entrega"))

            orcamento.desconto_percentual = _to_decimal(request.POST.get("desconto_percentual", "0"))
            orcamento.custo_extra = _to_decimal(request.POST.get("custo_extra", "0"))

            orcamento.forma_pagamento = request.POST.get("forma_pagamento", "A_COMBINAR")
            if orcamento.forma_pagamento not in dict(Orcamento.FORMAS_PAGAMENTO):
                orcamento.forma_pagamento = "A_COMBINAR"

            orcamento.prazo_execucao = request.POST.get("prazo_execucao", "").strip()
            orcamento.observacoes = request.POST.get("observacoes", "").strip()
            orcamento.save()

            self._salvar_itens(request, orcamento)

        messages.success(request, "Orçamento salvo com sucesso!")
        return redirect("orcamento_detalhe", pk=orcamento.pk)

    def _salvar_itens(self, request, orcamento):
        produtos_ids = request.POST.getlist("item_produto[]")
        projetos_ids = request.POST.getlist("item_projeto[]")
        descricoes = request.POST.getlist("item_descricao[]")
        datas_referencia = request.POST.getlist("item_data[]")
        quantidades = request.POST.getlist("item_quantidade[]")
        valores = request.POST.getlist("item_valor[]")
        custos = request.POST.getlist("item_custo[]")

        linhas = zip(
            produtos_ids,
            projetos_ids,
            descricoes,
            datas_referencia,
            quantidades,
            valores,
            custos,
        )

        orcamento.itens.all().delete()

        for produto_id, projeto_id, descricao, data_ref, quantidade, valor, custo in linhas:
            descricao = descricao.strip()

            if not any([produto_id, projeto_id, descricao]):
                continue

            try:
                quantidade_int = max(1, int(quantidade or 1))
            except (TypeError, ValueError):
                quantidade_int = 1

            item = ItemOrcamento(
                orcamento=orcamento,
                descricao=descricao,
                data_referencia=_to_date(data_ref),
                quantidade=quantidade_int,
                valor_unitario=_to_decimal(valor),
                custo_unitario=_to_decimal(custo),
            )

            if produto_id:
                item.produto_id = produto_id

            if projeto_id:
                item.projeto_id = projeto_id

            item.save()

    def put(self, request, pk):
        orcamento = get_object_or_404(
            Orcamento,
            pk=pk,
            usuario=request.user,
            ativo=True,
        )

        try:
            dados = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse(
                {
                    "success": False,
                    "erro": "JSON inválido.",
                },
                status=400,
            )

        novo_status = dados.get("status")

        if novo_status not in dict(Orcamento.STATUS):
            return JsonResponse(
                {
                    "success": False,
                    "erro": "Status inválido.",
                },
                status=400,
            )

        orcamento.status = novo_status
        orcamento.save(update_fields=["status", "modificado"])

        return JsonResponse(
            {
                "success": True,
                "status": orcamento.status,
                "status_display": orcamento.get_status_display(),
            }
        )

    def delete(self, request, pk):
        orcamento = get_object_or_404(
            Orcamento,
            pk=pk,
            usuario=request.user,
            ativo=True,
        )

        orcamento.ativo = False
        orcamento.save(update_fields=["ativo", "modificado"])

        return JsonResponse(
            {
                "success": True,
                "redirect": reverse("orcamentos"),
            }
        )


# ============================================================
# ÁREA INTERNA — PEDIDOS
# ============================================================

class GestaoPedidosView(SuperuserGestaoRequiredMixin, View):
    login_url = "login"

    def get(self, request):
        pedidos = (
            Pedido.objects.filter(usuario=request.user)
            .order_by("-criacao")
            .prefetch_related("itens__produto")
        )

        status_filtro = request.GET.get("status", "").strip()
        busca = request.GET.get("q", "").strip()

        if status_filtro:
            pedidos = pedidos.filter(status=status_filtro)

        if busca:
            pedidos = pedidos.filter(
                Q(id__icontains=busca) |
                Q(endereco__icontains=busca)
            )

        ctx = {
            "pedidos": pedidos,
            "status_choices": Pedido.STATUS,
            "status_filtro": status_filtro,
            "busca": busca,
            "secao_ativa": "pedidos",
        }

        return render(request, "gestao/pedidos.html", ctx)


class GestaoPedidoDetalheView(SuperuserGestaoRequiredMixin, View):
    login_url = "login"

    def get(self, request, pk):
        pedido = get_object_or_404(
            Pedido.objects.prefetch_related("itens__produto"),
            pk=pk,
            usuario=request.user,
        )

        ctx = {
            "pedido": pedido,
            "itens": pedido.itens.select_related("produto"),
            "status_choices": Pedido.STATUS,
            "secao_ativa": "pedidos",
        }

        return render(request, "gestao/pedido_detalhe.html", ctx)

    def put(self, request, pk):
        pedido = get_object_or_404(Pedido, pk=pk, usuario=request.user)

        try:
            dados = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse(
                {
                    "success": False,
                    "erro": "JSON inválido.",
                },
                status=400,
            )

        novo_status = dados.get("status")

        if novo_status not in dict(Pedido.STATUS):
            return JsonResponse(
                {
                    "success": False,
                    "erro": "Status inválido.",
                },
                status=400,
            )

        pedido.status = novo_status
        pedido.save(update_fields=["status", "modificado"])

        return JsonResponse(
            {
                "success": True,
                "status": pedido.status,
                "status_display": pedido.get_status_display(),
            }
        )


# ============================================================
# ÁREA INTERNA — RELATÓRIOS
# ============================================================

class RelatorioOrcamentosView(SuperuserGestaoRequiredMixin, View):
    login_url = "login"

    def get(self, request):
        orcamentos = _orcamentos_usuario(request)

        inicio = request.GET.get("inicio", "")
        fim = request.GET.get("fim", "")
        status_filtro = request.GET.get("status", "")

        if inicio:
            orcamentos = orcamentos.filter(criacao__date__gte=inicio)

        if fim:
            orcamentos = orcamentos.filter(criacao__date__lte=fim)

        if status_filtro:
            orcamentos = orcamentos.filter(status=status_filtro)

        orcamentos = orcamentos.order_by("-criacao")

        linhas = []

        soma_bruto = Decimal("0.00")
        soma_desconto = Decimal("0.00")
        soma_total = Decimal("0.00")
        soma_custo = Decimal("0.00")
        soma_lucro = Decimal("0.00")

        for orcamento in orcamentos:
            linha = _montar_linha_orcamento(orcamento)
            linhas.append(linha)

            soma_bruto += linha["bruto"]
            soma_desconto += linha["desconto"]
            soma_total += linha["total"]
            soma_custo += linha["custo"]
            soma_lucro += linha["lucro"]

        ticket_medio = Decimal("0.00")
        if linhas:
            ticket_medio = soma_total / Decimal(len(linhas))

        margem_media = Decimal("0.00")
        if soma_total > 0:
            margem_media = (soma_lucro / soma_total) * Decimal("100")

        por_status = orcamentos.values("status").annotate(total=Count("id")).order_by("status")

        por_mes = (
            orcamentos.annotate(mes=TruncMonth("criacao"))
            .values("mes")
            .annotate(total=Count("id"))
            .order_by("mes")
        )

        grafico = _dados_grafico_mensal_orcamentos(orcamentos.order_by("criacao"))

        ctx = {
            "linhas": linhas,

            "por_mes": por_mes,
            "por_status": por_status,

            "soma_bruto": soma_bruto,
            "soma_desconto": soma_desconto,
            "soma_total": soma_total,
            "soma_custo": soma_custo,
            "soma_lucro": soma_lucro,
            "ticket_medio": ticket_medio,
            "margem_media": margem_media,

            "inicio": inicio,
            "fim": fim,
            "status_filtro": status_filtro,
            "status_choices": Orcamento.STATUS,

            "grafico_labels": json.dumps(grafico["labels"]),
            "grafico_receita": json.dumps(grafico["receita"]),
            "grafico_custo": json.dumps(grafico["custo"]),
            "grafico_lucro": json.dumps(grafico["lucro"]),
            "grafico_quantidade": json.dumps(grafico["quantidade"]),

            "secao_ativa": "relatorio",
        }

        return render(request, "gestao/relatorio.html", ctx)


class GestaoPerfilView(SuperuserGestaoRequiredMixin, View):
    template_name = "gestao/perfil.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "secao_ativa": "gestao_perfil",
            }
        )

    def post(self, request):
        usuario = request.user

        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()

        if not username:
            messages.error(request, "Informe o nome de usuário.")
            return redirect("gestao_perfil")

        if not email:
            messages.error(request, "Informe o e-mail.")
            return redirect("gestao_perfil")

        if User.objects.filter(username=username).exclude(pk=usuario.pk).exists():
            messages.error(request, "Este nome de usuário já está em uso.")
            return redirect("gestao_perfil")

        if User.objects.filter(email=email).exclude(pk=usuario.pk).exists():
            messages.error(request, "Este e-mail já está cadastrado.")
            return redirect("gestao_perfil")

        usuario.first_name = first_name
        usuario.last_name = last_name
        usuario.username = username
        usuario.email = email
        usuario.save(update_fields=[
            "first_name",
            "last_name",
            "username",
            "email",
        ])

        messages.success(request, "Perfil da gestão atualizado com sucesso!")
        return redirect("gestao_perfil")

