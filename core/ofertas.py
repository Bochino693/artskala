from decimal import Decimal
from django.core.exceptions import ValidationError
from django.shortcuts import render
from django.utils import timezone
from .models import Cupom, Promocao

def desconto_cupom(codigo, itens):
    codigo = codigo.strip().upper()
    if not codigo:
        return '', Decimal('0.00')
    now = timezone.now()
    cupom = Cupom.objects.filter(codigo=codigo, ativo=True, inicio__lte=now, fim__gte=now).first()
    if not cupom:
        raise ValidationError('Cupom inválido ou fora da validade.')
    # Não acumula cupom com promoção; preço e elegibilidade calculados no servidor.
    elegivel = sum((i.produto.preco * i.quantidade for i in itens if i.produto.preco_atual() == i.produto.preco), Decimal('0'))
    if elegivel <= 0 or elegivel < cupom.minimo:
        raise ValidationError('O cupom não se aplica: confira o valor mínimo dos itens sem promoção.')
    return cupom.codigo, (elegivel * cupom.percentual / Decimal('100')).quantize(Decimal('0.01'))

def promocoes(request):
    now = timezone.now()
    ofertas = Promocao.objects.filter(ativo=True, produto__ativo=True, inicio__lte=now, fim__gte=now).select_related('produto')
    return render(request, 'promocoes.html', {'ofertas': ofertas})
