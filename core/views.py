from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q

from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Count, Q

from .models import (
    Produto,
    CategoriaProdutos,
    Projeto,
    Carrinho,
    Pedido,
    PerfilUsuario
)

class HomeView(View):

    def get(self, request):
        ctx = {
            "produtos": Produto.objects.filter(
                ativo=True
            ).select_related(
                "categoria"
            ).prefetch_related(
                "imagens"
            )[:8],

            "projetos": Projeto.objects.filter(
                ativo=True
            ).prefetch_related(
                "imagens"
            )[:6],

            "categorias": CategoriaProdutos.objects.filter(
                ativo=True
            ).annotate(
                total_produtos=Count(
                    "produtos",
                    filter=Q(produtos__ativo=True)
                )
            ),
        }

        return render(request, "home.html", ctx)

class ProductsView(View):

    def get(self, request):
        categoria_id = request.GET.get("categoria")

        produtos = Produto.objects.filter(
            ativo=True
        ).select_related("categoria").prefetch_related("imagens")

        if categoria_id:
            produtos = produtos.filter(categoria_id=categoria_id)

        ctx = {
            "produtos": produtos,
            "categorias": CategoriaProdutos.objects.filter(ativo=True),
            "categoria_ativa": int(categoria_id) if categoria_id else None,
        }

        return render(request, "products.html", ctx)

class ProductDetailView(View):

    def get(self, request, pk):
        produto = get_object_or_404(
            Produto,
            pk=pk,
            ativo=True
        )

        ctx = {
            "produto": produto,
            "imagens": produto.imagens.all(),
            "relacionados": Produto.objects.filter(
                categoria=produto.categoria,
                ativo=True
            ).exclude(pk=produto.pk)[:4]
        }

        return render(request, "product_detail.html", ctx)

class CategoriesView(View):

    def get(self, request):
        categorias = CategoriaProdutos.objects.filter(
            ativo=True
        ).annotate(
            total_produtos=Count(
                "produtos",
                filter=Q(produtos__ativo=True)
            )
        ).order_by("nome_categoria")

        total_produtos = Produto.objects.filter(
            ativo=True
        ).count()

        ctx = {
            "categorias": categorias,
            "total_categorias": categorias.count(),
            "total_produtos": total_produtos,
        }

        return render(request, "categories.html", ctx)


class CategoryDetailView(View):

    def get(self, request, pk):
        categoria = get_object_or_404(
            CategoriaProdutos.objects.filter(
                ativo=True
            ).annotate(
                total_produtos=Count(
                    "produtos",
                    filter=Q(produtos__ativo=True)
                )
            ),
            pk=pk
        )

        produtos = Produto.objects.filter(
            categoria=categoria,
            ativo=True
        ).select_related(
            "categoria"
        ).prefetch_related(
            "imagens"
        ).order_by("nome_produto")

        categorias = CategoriaProdutos.objects.filter(
            ativo=True
        ).annotate(
            total_produtos=Count(
                "produtos",
                filter=Q(produtos__ativo=True)
            )
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
            "projetos": Projeto.objects.filter(
                ativo=True
            ).prefetch_related(
                "imagens"
            ).order_by("-criacao")
        }

        return render(request, "projects.html", ctx)

class ProjectDetailView(View):

    def get(self, request, pk):

        projeto = get_object_or_404(
            Projeto,
            pk=pk,
            ativo=True
        )

        ctx = {
            "projeto": projeto,
            "imagens": projeto.imagens.all()
        }

        return render(request, "project_detail.html", ctx)


class CartView(View):

    def get(self, request):

        if not request.user.is_authenticated:
            return render(request, "cart.html")

        carrinho, created = Carrinho.objects.get_or_create(
            usuario=request.user
        )

        itens = carrinho.itens.select_related("produto")

        total = sum(
            item.subtotal()
            for item in itens
        )

        ctx = {
            "carrinho": carrinho,
            "itens": itens,
            "total": total,
        }

        return render(request, "cart.html", ctx)


class CheckoutView(View):

    def get(self, request):

        if not request.user.is_authenticated:
            return render(request, "login.html")

        carrinho = get_object_or_404(
            Carrinho,
            usuario=request.user
        )

        total = sum(
            item.subtotal()
            for item in carrinho.itens.all()
        )

        ctx = {
            "carrinho": carrinho,
            "total": total
        }

        return render(request, "checkout.html", ctx)


class OrdersView(View):

    def get(self, request):

        if not request.user.is_authenticated:
            return render(request, "login.html")

        pedidos = Pedido.objects.filter(
            usuario=request.user
        ).order_by("-criacao")

        ctx = {
            "pedidos": pedidos
        }

        return render(request, "orders.html", ctx)


class OrderDetailView(View):

    def get(self, request, pk):

        pedido = get_object_or_404(
            Pedido,
            pk=pk,
            usuario=request.user
        )

        ctx = {
            "pedido": pedido,
            "itens": pedido.itens.select_related("produto")
        }

        return render(request, "order_detail.html", ctx)


class ProfileView(View):

    def get(self, request):

        if not request.user.is_authenticated:
            return render(request, "login.html")

        perfil, created = PerfilUsuario.objects.get_or_create(
            usuario=request.user
        )

        ctx = {
            "perfil": perfil
        }

        return render(request, "profile.html", ctx)

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

        ctx = {
            "dados": request.POST,
        }

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

        messages.success(request, "Conta criada com sucesso. Seja bem-vindo à ArtSkala!")
        return redirect("profile")


class PaymentView(View):

    def get(self, request):
        return render(request, "payment.html")


class PendingOrdersView(View):

    def get(self, request):

        pedidos = Pedido.objects.filter(
            status="PENDENTE"
        )

        ctx = {
            "pedidos": pedidos
        }

        return render(request, "pendings.html", ctx)


class LoginView(View):

    def get(self, request):
        if request.user.is_authenticated:
            return render(request, "login.html")

        return render(request, "login.html")

    def post(self, request):
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        next_url = request.POST.get("next") or request.GET.get("next")

        if not username or not password:
            messages.error(request, "Informe seu usuário e sua senha.")
            return render(request, "login.html")

        usuario = authenticate(
            request,
            username=username,
            password=password
        )

        if usuario is None:
            messages.error(request, "Usuário ou senha inválidos.")
            return render(request, "login.html")

        if not usuario.is_active:
            messages.error(request, "Este usuário está inativo.")
            return render(request, "login.html")

        login(request, usuario)

        if next_url:
            return redirect(next_url)

        if usuario.is_staff or usuario.is_superuser:
            return redirect("home")

        return redirect("home")


class LogoutView(View):

    def get(self, request):
        logout(request)
        return redirect("home")


