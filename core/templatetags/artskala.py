"""Filtros de template do site.

{{ url|tamanho:"600x600" }} pede a foto já no tamanho de exibição; com um
número só ({{ url|tamanho:"1600" }}) limita a largura sem recortar.

- Fotos do banco do site (/midia/banco/...): ganham ?w= (e ?h=), e o próprio
  site entrega uma versão menor em WebP (core/views_midia.py). Com largura e
  altura a foto cobre a caixa inteira; o recorte fica com o CSS.
- Fotos antigas do Cloudinary: transformação do Cloudinary (recorte
  inteligente, qualidade e formato automáticos).
- Outros endereços voltam como vieram.
"""
from urllib.parse import urlencode

from django import template

from core.midia import URL_BASE, PREFIXO, medida_permitida

register = template.Library()

_URL_BANCO = URL_BASE + PREFIXO     # "/midia/banco/"


def _tamanho_banco(url, medida):
    try:
        if "x" in medida:
            largura, altura = (int(n) for n in medida.split("x"))
            parametros = {"w": medida_permitida(largura), "h": medida_permitida(altura)}
        else:
            parametros = {"w": medida_permitida(int(medida))}
    except ValueError:
        return url
    if "?" in url:
        return url  # já tem medida
    return f"{url}?{urlencode(parametros)}"


@register.filter
def tamanho(url, medida="800x600"):
    url = str(url or "")
    medida = str(medida).lower()
    if _URL_BANCO in url:
        return _tamanho_banco(url, medida)
    if "res.cloudinary.com" not in url or "/image/upload/" not in url:
        return url
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
