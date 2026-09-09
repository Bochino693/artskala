from .models import Carrinho
from django.conf import settings
from django.urls import reverse


def enderecos_site(request):
    return {
        "site_url": settings.SITE_URL,
        "google_login_enabled": settings.GOOGLE_LOGIN_ENABLED,
        "gestao_url": ("https://" + settings.INTERNAL_HOST + "/"),
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
