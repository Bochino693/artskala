from django.db.models import Count, Q
from django.utils.functional import SimpleLazyObject

from .models import Carrinho, CategoriaProdutos
from django.conf import settings
from django.urls import reverse


def enderecos_site(request):
    return {
        "site_url": settings.SITE_URL,
        "google_login_enabled": settings.GOOGLE_LOGIN_ENABLED,
        # Com o subdomínio interno desligado, a gestão continua em /gestao/.
        "gestao_url": (
            "https://" + settings.INTERNAL_HOST + "/"
            if settings.INTERNAL_SITE_ENABLED
            else reverse("gestao_dashboard")
        ),
    }


def carrinho_contexto(request):
    """
    Disponibiliza `carrinho_total_itens` em TODOS os templates (via base.html),
    sem precisar que cada view passe isso manualmente no contexto.
    """
    total_itens = 0

    if request.user.is_authenticated:
        carrinho = Carrinho.objects.filter(usuario=request.user).first()

        if carrinho:
            total_itens = sum(item.quantidade for item in carrinho.itens.all())

    return {"carrinho_total_itens": total_itens}


def menu_site(request):
    """Categorias do painel "Produtos" do cabeçalho e do menu do celular.
    Só consulta o banco se a página usar o menu."""
    def categorias():
        return list(
            CategoriaProdutos.objects.filter(ativo=True)
            .annotate(total_produtos=Count("produtos", filter=Q(produtos__ativo=True)))
            .order_by("nome_categoria")
        )

    return {"menu_categorias": SimpleLazyObject(categorias)}
