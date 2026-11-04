"""Filtros de template do site.

{{ url|tamanho:"600x600" }} pede ao Cloudinary a foto já no tamanho de
exibição (recorte inteligente, qualidade e formato automáticos); com um número
só ({{ url|tamanho:"1600" }}) limita a largura sem recortar. Fica nítida e
leve; fora do Cloudinary devolve o endereço como veio.
"""
from django import template

register = template.Library()


@register.filter
def tamanho(url, medida="800x600"):
    url = str(url or "")
    if "res.cloudinary.com" not in url or "/image/upload/" not in url:
        return url
    medida = str(medida).lower()
    try:
        if "x" in medida:   # recorta no formato pedido (cartões, mosaico)
            largura, altura = (int(n) for n in medida.split("x"))
            transformacao = f"c_fill,g_auto,w_{largura},h_{altura},q_auto:good,f_auto"
        else:               # só limita a largura, sem recortar (galeria, zoom)
            transformacao = f"c_limit,w_{int(medida)},q_auto:good,f_auto"
    except ValueError:
        return url
    inicio, resto = url.split("/image/upload/", 1)
    if resto.split("/", 1)[0].startswith(("c_", "w_", "h_", "q_", "f_")):
        return url  # já tem transformação
    return f"{inicio}/image/upload/{transformacao}/{resto}"


# ----------------------------------------------------------- dinheiro e números
# {{ valor|brl }} -> "R$ 1.234,56"   {{ valor|pct }} -> "12,5%"
# {{ valor|moeda_campo }} -> "1.234,56" (valor inicial dos campos com máscara)
# {{ objeto|codigo }} -> "PRD-000012" (etiquetas e busca rápida)
from core.dinheiro import codigo as _codigo, formatar_brl, formatar_numero  # noqa: E402


@register.filter
def brl(valor):
    return formatar_brl(valor)


@register.filter
def pct(valor, casas=1):
    try:
        casas = int(casas)
    except (TypeError, ValueError):
        casas = 1
    return formatar_numero(valor or 0, casas) + "%"


@register.filter
def moeda_campo(valor):
    return formatar_numero(valor or 0, 2)


@register.filter
def numero_br(valor, casas=0):
    try:
        casas = int(casas)
    except (TypeError, ValueError):
        casas = 0
    return formatar_numero(valor or 0, casas)


@register.filter
def codigo(objeto):
    try:
        return _codigo(objeto)
    except (AttributeError, TypeError, ValueError):
        return ""


@register.filter
def get_item(dicionario, chave):
    try:
        return dicionario.get(chave, "")
    except AttributeError:
        return ""
