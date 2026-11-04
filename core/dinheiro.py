"""Dinheiro e números no formato brasileiro, num lugar só.

para_decimal("R$ 1.234,56") -> Decimal("1234.56")   (também "1234.56", "1,5", "10 %")
formatar_brl(Decimal("1234.5")) -> "R$ 1.234,50"
codigo(produto) -> "PRD-000012"  (o código das etiquetas e da busca rápida)
"""
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_LIXO = re.compile(r"[^\d,.\-]")


def para_decimal(valor, padrao="0"):
    """Lê o que vier do formulário: com ou sem "R$", ponto de milhar e vírgula."""
    if valor is None:
        return Decimal(padrao)
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    texto = _LIXO.sub("", str(valor).replace("\xa0", " "))
    negativo = texto.startswith("-")
    texto = texto.replace("-", "")
    if not texto:
        return Decimal(padrao)
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):      # 1.234,56
            texto = texto.replace(".", "").replace(",", ".")
        else:                                          # 1,234.56
            texto = texto.replace(",", "")
    elif "," in texto:                                 # 1234,56 / 1,5
        texto = texto.replace(".", "").replace(",", ".")
        if texto.count(".") > 1:
            return Decimal(padrao)
    elif texto.count(".") > 1:                         # 1.234.567
        texto = texto.replace(".", "")
    try:
        numero = Decimal(texto)
    except InvalidOperation:
        return Decimal(padrao)
    return -numero if negativo else numero


def formatar_numero(valor, casas=2):
    """1234.5 -> "1.234,50" (milhar com ponto, decimal com vírgula)."""
    numero = para_decimal(valor)
    quantum = Decimal(1).scaleb(-casas) if casas else Decimal(1)
    numero = numero.quantize(quantum, rounding=ROUND_HALF_UP)
    sinal = "-" if numero < 0 else ""
    inteiro, _, fracao = f"{abs(numero):f}".partition(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    texto = ".".join(grupos)
    if casas:
        texto += "," + fracao.ljust(casas, "0")[:casas]
    return sinal + texto


def formatar_brl(valor):
    texto = formatar_numero(valor or 0, 2)
    if texto.startswith("-"):
        return "-R$ " + texto[1:]
    return "R$ " + texto


PREFIXOS = {
    "Produto": "PRD",
    "Pedido": "PED",
    "Orcamento": "ORC",
    "Projeto": "PRJ",
}
_CODIGO = re.compile(r"^\s*#?\s*(PRD|PED|ORC|PRJ)\s*[-:/ ]?\s*0*(\d+)\s*$", re.IGNORECASE)


def codigo(objeto):
    prefixo = PREFIXOS.get(type(objeto).__name__, "ART")
    return f"{prefixo}-{objeto.pk:06d}"


def ler_codigo(texto):
    """"PRD-000012", "prd12", "#PED 7" -> ("PRD", 12). Outro texto -> None."""
    achado = _CODIGO.match(str(texto or ""))
    if not achado:
        return None
    return achado.group(1).upper(), int(achado.group(2))
