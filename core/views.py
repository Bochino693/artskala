from django.shortcuts import render, get_object_or_404
from django.views import View
from django.contrib.auth.models import User

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
            "produtos": Produto.objects.filter(ativo=True)[:8],
            "projetos": Projeto.objects.filter(ativo=True)[:6],
            "categorias": CategoriaProdutos.objects.all(),
        }
        return render(request, "home.html", ctx)


class ProductsView(View):

    def get(self, request):
        ctx = {
            "produtos": Produto.objects.filter(ativo=True),
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
        ctx = {
            "categorias": CategoriaProdutos.objects.prefetch_related(
                "produtos"
            )
        }

        return render(request, "categories.html", ctx)


class ProjectsView(View):

    def get(self, request):
        ctx = {
            "projetos": Projeto.objects.filter(ativo=True)
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


class LoginView(View):

    def get(self, request):
        return render(request, "login.html")


class RegisterView(View):

    def get(self, request):
        return render(request, "register.html")


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
