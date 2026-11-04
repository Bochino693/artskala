from django.db.models import Count, Q
from django.utils.functional import SimpleLazyObject

from .models import Carrinho, CategoriaProdutos
from django.conf import settings
from django.urls import reverse


def enderecos_site(request):
    return {
        "site_url": settings.SITE_URL,
        "email_contato": settings.EMAIL_CONTATO,
        "google_login_enabled": settings.GOOGLE_LOGIN_ENABLED,
        # A gestão fica em /interno/ no próprio site (sem subdomínio).
        "gestao_url": reverse("gestao_dashboard"),
        # "Abrir o site" de dentro da gestão: no próprio domínio é a raiz.
        "loja_url": settings.SITE_URL if getattr(request, "is_interno", False) else "/",
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


def gestao_acesso(request):
    """`pode.<tela>` nos templates da gestão: o menu mostra só o que a função abre."""
    from .equipe import funcoes_do_usuario, mapa_de_acesso, POR_CODIGO

    def mapa():
        return mapa_de_acesso(request.user)

    def funcao():
        codigos = funcoes_do_usuario(request.user)
        return ", ".join(POR_CODIGO[c]["titulo"] for c in sorted(codigos)) or ""

    return {"pode": SimpleLazyObject(mapa), "funcao_equipe": SimpleLazyObject(funcao)}
