"""Itens de vitrine feitos a partir das fotos do Instagram @artskalaa.

São serviços "sob consulta" (preço R$ 0,00 e sem estoque): aparecem no
catálogo com foto e o botão "Pedir orçamento deste produto" no WhatsApp, sem
carrinho. Só os produtos de pronta entrega da loja têm preço.

A migração 0007 chama `semear` uma vez; ela não recria um item que já
exista com o mesmo nome (nem um que a equipe tenha apagado depois, porque a
migração não roda de novo).
"""
from pathlib import Path

from django.core.files import File

PASTA_FOTOS = Path(__file__).resolve().parent / "fotos"

ITENS = [
    {
        "nome": "Fachada em ACM com letreiro",
        "categoria": "Fachadas",
        "fotos": ["fachada-acm-letreiro.jpg"],
        "descricao": (
            "Fachada revestida em ACM (alumínio composto) com letreiro em relevo, "
            "como a da Distribuidora Fashion Make Up. Medimos o local, criamos o "
            "projeto da arte, produzimos e instalamos. Orçamento sob consulta."
        ),
    },
    {
        "nome": "Fachada com lona impressa",
        "categoria": "Fachadas",
        "fotos": ["fachada-lona-impressa.jpg"],
        "descricao": (
            "Fachada em lona com impressão digital em alta resolução, esticada em "
            "estrutura metálica: grande, resistente ao sol e à chuva e com ótimo "
            "custo para comércios de rua. Orçamento sob consulta."
        ),
    },
    {
        "nome": "Letreiro em acrílico com LED",
        "categoria": "Letreiros",
        "fotos": ["letreiro-acrilico-led.jpg"],
        "descricao": (
            "Letreiro recortado em acrílico e ACM com iluminação de LED por dentro "
            "(backlight), como o da Le Petit Macarons Boutique. Feito sob medida, "
            "no formato da sua marca. Orçamento sob consulta."
        ),
    },
    {
        "nome": "Placa em cavalete para calçada",
        "categoria": "Placas",
        "fotos": ["placa-cavalete.jpg"],
        "descricao": (
            "Placa com a sua marca em cavalete metálico, para chamar a atenção na "
            "calçada ou na entrada da loja. Recorte no formato do logo e pintura "
            "na cor que você escolher. Orçamento sob consulta."
        ),
    },
    {
        "nome": "Luminoso recortado com LED neon",
        "categoria": "Letreiros",
        "fotos": ["luminoso-led-neon.jpg"],
        "descricao": (
            "Peça luminosa recortada no formato do seu produto, com impressão em "
            "alta definição e LED neon flexível. Perfeita para hamburguerias, "
            "lanchonetes e vitrines. Orçamento sob consulta."
        ),
    },
    {
        "nome": "Adesivação de veículos e frotas",
        "categoria": "Adesivos",
        "fotos": ["adesivacao-picape.jpg"],
        "descricao": (
            "Adesivação de carros, picapes, vans e frotas com a identidade da sua "
            "empresa: vinil de alta durabilidade, aplicação sem bolhas e layout "
            "criado pela nossa equipe. Orçamento sob consulta."
        ),
    },
    {
        "nome": "Peças em acrílico e PVC recortadas",
        "categoria": "Letreiros",
        "fotos": ["pecas-acrilico-recortadas.jpg"],
        "descricao": (
            "Corte de letras, logos e peças em acrílico, PVC e ACM para letreiros, "
            "displays, decoração e sinalização, com acabamento profissional. "
            "Orçamento sob consulta."
        ),
    },
]


def semear(Produto, CategoriaProdutos, ImagemProduto):
    """Cria os itens que ainda não existem. Devolve quantos foram criados."""
    criados = 0
    for item in ITENS:
        if Produto.objects.filter(nome_produto=item["nome"]).exists():
            continue
        categoria = CategoriaProdutos.objects.filter(nome_categoria__iexact=item["categoria"]).first()
        if categoria is None:
            categoria = CategoriaProdutos.objects.create(nome_categoria=item["categoria"])
        produto = Produto.objects.create(
            categoria=categoria,
            nome_produto=item["nome"],
            descricao_produto=item["descricao"][:500],
            preco=0,
            custo=0,
            estoque=0,
        )
        for nome in item["fotos"]:
            caminho = PASTA_FOTOS / nome
            if not caminho.exists():
                continue
            with caminho.open("rb") as arquivo:
                foto = ImagemProduto(produto=produto)
                foto.imagem.save(f"vitrine-{nome}", File(arquivo), save=True)
        criados += 1
    return criados
