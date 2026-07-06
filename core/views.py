from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Prefetch
from django.http import JsonResponse

from .models import (
    Produto,
    CategoriaProdutos,
    Projeto,
    Carrinho,
    ItemCarrinho,
    Pedido,
    ItemPedido,
    PerfilUsuario,
    ImagemProduto,
    ImagemProjeto,
)


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
    total_valor = sum(item.subtotal() for item in itens)
    return total_itens, total_valor


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
        relacionados = Produto.objects.filter(
            categoria=produto.categoria,
            ativo=True,
        ).exclude(pk=produto.pk).select_related("categoria")[:4]

        ctx = {
            "produto": produto,
            "imagens": produto.imagens.all(),
            "relacionados": relacionados,
        }
        return render(request, "product.html", ctx)


class CategoriesView(View):
    def get(self, request):
        categorias = CategoriaProdutos.objects.filter(ativo=True).annotate(
            total_produtos=Count("produtos", filter=Q(produtos__ativo=True))
        ).order_by("nome_categoria")

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
        categorias = CategoriaProdutos.objects.filter(ativo=True).annotate(
            total_produtos=Count("produtos", filter=Q(produtos__ativo=True))
        ).order_by("nome_categoria")

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


# ---------------------------------------------------------------------------
# Carrinho — leitura (página) + endpoints assíncronos (adicionar/atualizar/remover)
# ---------------------------------------------------------------------------

class CartView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return render(request, "cart.html", {"itens": [], "total": 0})

        carrinho, _created = Carrinho.objects.get_or_create(usuario=request.user)
        itens = carrinho.itens.select_related("produto", "produto__categoria").prefetch_related(
            "produto__imagens"
        )
        total = sum(item.subtotal() for item in itens)

        return render(request, "cart.html", {"carrinho": carrinho, "itens": itens, "total": total})


class AddToCartView(View):
    """
    POST assíncrono chamado pelos botões "Adicionar ao carrinho".
    Retorna JSON para atualizar o badge do ícone sem recarregar a página.
    """

    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"success": False, "auth_required": True, "redirect": "/login/"},
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
            item.save()

        total_itens, total_valor = _resumo_carrinho(carrinho)

        return JsonResponse({
            "success": True,
            "total_itens": total_itens,
            "total_valor": str(total_valor),
            "item_id": item.id,
            "item_quantidade": item.quantidade,
            "item_subtotal": str(item.subtotal()),
        })


class UpdateCartItemView(View):
    """
    POST assíncrono para +/- quantidade ou definir quantidade exata de um item.
    Espera `acao` = "incrementar" | "decrementar" | "definir".
    Se `acao` == "definir", espera também `quantidade`.
    """

    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"success": False}, status=401)

        item = get_object_or_404(ItemCarrinho, pk=pk, carrinho__usuario=request.user)
        acao = request.POST.get("acao", "incrementar")
        removido = False

        if acao == "incrementar":
            item.quantidade += 1
            item.save()
        elif acao == "decrementar":
            item.quantidade -= 1
            if item.quantidade <= 0:
                item.delete()
                removido = True
            else:
                item.save()
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
                item.save()

        carrinho = Carrinho.objects.get(usuario=request.user)
        total_itens, total_valor = _resumo_carrinho(carrinho)

        return JsonResponse({
            "success": True,
            "removido": removido,
            "item_quantidade": 0 if removido else item.quantidade,
            "item_subtotal": "0" if removido else str(item.subtotal()),
            "total_itens": total_itens,
            "total_valor": str(total_valor),
        })


class RemoveCartItemView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"success": False}, status=401)

        item = get_object_or_404(ItemCarrinho, pk=pk, carrinho__usuario=request.user)
        item.delete()

        carrinho = Carrinho.objects.get(usuario=request.user)
        total_itens, total_valor = _resumo_carrinho(carrinho)

        return JsonResponse({
            "success": True,
            "total_itens": total_itens,
            "total_valor": str(total_valor),
        })


# ---------------------------------------------------------------------------
# Checkout — finalização do pedido com escolha de forma de pagamento
# ---------------------------------------------------------------------------

class CheckoutView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        carrinho, _created = Carrinho.objects.get_or_create(usuario=request.user)
        itens = carrinho.itens.select_related("produto").prefetch_related("produto__imagens")
        total = sum(item.subtotal() for item in itens)

        if not itens:
            messages.info(request, "Seu carrinho está vazio.")
            return redirect("cart")

        perfil, _created = PerfilUsuario.objects.get_or_create(
            usuario=request.user,
            defaults=_perfil_defaults(),
        )

        ctx = {
            "carrinho": carrinho,
            "itens": itens,
            "total": total,
            "perfil": perfil,
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
        metodo_pagamento = request.POST.get("metodo_pagamento", "").strip()

        metodos_validos = dict(Pedido.METODOS_PAGAMENTO).keys()

        if not endereco:
            messages.error(request, "Informe o endereço de entrega.")
            return redirect("checkout")

        if metodo_pagamento not in metodos_validos:
            messages.error(request, "Escolha uma forma de pagamento válida.")
            return redirect("checkout")

        total = sum(item.subtotal() for item in itens)

        with transaction.atomic():
            pedido = Pedido.objects.create(
                usuario=request.user,
                valor_total=total,
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
                )

            carrinho.itens.all().delete()

        messages.success(request, "Pedido realizado com sucesso!")
        return redirect("order_detail", pk=pedido.pk)


class OrdersView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        pedidos = Pedido.objects.filter(usuario=request.user).order_by("-criacao")
        return render(request, "orders.html", {"pedidos": pedidos})


class OrderDetailView(View):
    def get(self, request, pk):
        if not request.user.is_authenticated:
            return redirect("login")

        pedido = get_object_or_404(Pedido, pk=pk, usuario=request.user)
        return render(request, "order_detail.html", {"pedido": pedido, "itens": pedido.itens.select_related("produto")})

class ProfileView(View):

    def get(self, request):

        if not request.user.is_authenticated:
            return redirect("login")

        perfil, _ = PerfilUsuario.objects.get_or_create(
            usuario=request.user,
            defaults=_perfil_defaults()
        )

        return render(
            request,
            "profile.html",
            {"perfil": perfil}
        )


    def post(self, request):

        if not request.user.is_authenticated:
            return redirect("login")

        perfil = request.user.perfil

        request.user.first_name = request.POST.get("nome")
        request.user.last_name = request.POST.get("sobrenome")
        request.user.username = request.POST.get("username")
        request.user.email = request.POST.get("email")

        request.user.save()

        perfil.telefone = request.POST.get("telefone")
        perfil.cpf = request.POST.get("cpf")
        perfil.endereco = request.POST.get("endereco")
        perfil.cidade = request.POST.get("cidade")
        perfil.estado = request.POST.get("estado")
        perfil.cep = request.POST.get("cep")

        perfil.save()

        messages.success(
            request,
            "Perfil atualizado com sucesso!"
        )

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
            nome, sobrenome, username, email, password, password_confirm,
            telefone, cpf, endereco, cidade, estado, cep,
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

        messages.success(request, "Conta criada com sucesso. Seja bem-vindo à ArtSkala!")
        return redirect("profile")


class PaymentView(View):
    def get(self, request):
        return render(request, "payment.html")


class PendingOrdersView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")
        pedidos = Pedido.objects.filter(status="PENDENTE").order_by("-criacao")
        return render(request, "pendings.html", {"pedidos": pedidos})


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