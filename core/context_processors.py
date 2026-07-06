from .models import Carrinho


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