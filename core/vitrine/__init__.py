"""Itens de vitrine feitos a partir das fotos do Instagram @artskalaa.

São serviços "sob consulta" (preço R$ 0,00 e sem estoque): aparecem no
catálogo com foto e o botão "Pedir orçamento deste produto" no WhatsApp, sem
carrinho. Só os produtos de pronta entrega da loja têm preço.

Cada leva de fotos é um "lote" com a sua migração (0007 = lote 1,
0008 = lote 2...). A migração roda uma vez só: não recria um item que já
exista com o mesmo nome, nem um que a equipe tenha apagado depois.
"""
from pathlib import Path

from django.core.files import File

PASTA_FOTOS = Path(__file__).resolve().parent / "fotos"

ITENS = [
    # ------------------------------------------------------------ lote 1
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
    # ------------------------------------------------------------ lote 2
    {
        "lote": 2,
        "nome": "Adesivo de recorte para paredes e vitrines",
        "categoria": "Adesivos",
        "fotos": ["adesivo-parede-galpao.jpg"],
        "descricao": (
            "Logo e letras em adesivo de recorte para paredes, vitrines e placas, "
            "como na Galpão Motoparts. Vinil de alta durabilidade, recortado no "
            "formato exato da marca e aplicado pela nossa equipe. Orçamento sob consulta."
        ),
    },
    {
        "lote": 2,
        "nome": "Painel vazado recortado a laser",
        "categoria": "Fachadas",
        "fotos": ["painel-vazado-laser.jpg"],
        "descricao": (
            "Painel em chapa metálica ou ACM recortado a laser com desenho vazado, "
            "acabamento efeito corten ou na cor da marca. Para fachadas, brises, "
            "divisórias e portões. Orçamento sob consulta."
        ),
    },
]

# Portfólio (Projetos realizados) com os trabalhos das fotos, por cliente.
PROJETOS = [
    {
        "lote": 2,
        "titulo": "Fachada da Distribuidora Fashion Make Up",
        "cliente": "Fashion Make Up Cosméticos",
        "fotos": ["fachada-acm-letreiro.jpg"],
        "descricao": "Fachada revestida em ACM preto com letreiro em relevo: produção e instalação ArtSkala.",
    },
    {
        "lote": 2,
        "titulo": "Letreiro e placa da Le Petit Macarons Boutique",
        "cliente": "Le Petit Macarons Boutique",
        "fotos": ["letreiro-acrilico-led.jpg", "placa-cavalete.jpg", "pecas-acrilico-recortadas.jpg"],
        "descricao": (
            "Letreiro recortado em acrílico com iluminação de LED e placa em cavalete "
            "para a calçada, do corte das peças à montagem final."
        ),
    },
    {
        "lote": 2,
        "titulo": "Comunicação visual da Galpão Motoparts",
        "cliente": "Galpão Motoparts",
        "fotos": ["adesivo-parede-galpao.jpg"],
        "descricao": "Placa com o logo e adesivos de recorte para a loja da Galpão Motoparts.",
    },
    {
        "lote": 2,
        "titulo": "Adesivação da picape Villa Festas",
        "cliente": "Villa Festas",
        "fotos": ["adesivacao-picape.jpg"],
        "descricao": "Adesivação completa da picape com a identidade da Villa Festas.",
    },
    {
        "lote": 2,
        "titulo": "Luminoso de hambúrguer com LED neon",
        "cliente": "",
        "fotos": ["luminoso-led-neon.jpg"],
        "descricao": "Peça luminosa recortada no formato do hambúrguer, com impressão em alta definição e LED neon.",
    },
]


def _salvar_fotos(nomes, criar_foto):
    for nome in nomes:
        caminho = PASTA_FOTOS / nome
        if caminho.exists():
            with caminho.open("rb") as arquivo:
                criar_foto(f"vitrine-{nome}", File(arquivo))


def semear(Produto, CategoriaProdutos, ImagemProduto, lotes=(1,)):
    """Cria os itens dos lotes pedidos que ainda não existem. Devolve quantos criou."""
    criados = 0
    for item in ITENS:
        if item.get("lote", 1) not in lotes:
            continue
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
        _salvar_fotos(item["fotos"], lambda nome, arquivo: ImagemProduto(produto=produto).imagem.save(nome, arquivo, save=True))
        criados += 1
    return criados


def semear_projetos(Projeto, ImagemProjeto, lotes=(2,)):
    """Cria os projetos do portfólio que ainda não existem. Devolve quantos criou."""
    criados = 0
    for item in PROJETOS:
        if item.get("lote", 1) not in lotes or Projeto.objects.filter(titulo=item["titulo"]).exists():
            continue
        projeto = Projeto.objects.create(titulo=item["titulo"], cliente=item["cliente"], descricao=item["descricao"])
        _salvar_fotos(item["fotos"], lambda nome, arquivo: ImagemProjeto(projeto=projeto).imagem.save(nome, arquivo, save=True))
        criados += 1
    return criados


def melhorar_foto(arquivo, nome="foto.jpg"):
    """Foto recortada de print: amplia as pequenas (2x) com nitidez e salva em
    JPEG. Recusa o que não for imagem. Devolve um ContentFile."""
    from io import BytesIO

    from django.core.files.base import ContentFile
    from PIL import Image, ImageFilter, UnidentifiedImageError

    try:
        imagem = Image.open(arquivo)
        imagem.load()
    except (UnidentifiedImageError, OSError) as erro:
        raise ValueError("O arquivo não é uma imagem.") from erro
    imagem = imagem.convert("RGB")
    if imagem.width < 700:
        imagem = imagem.resize((imagem.width * 2, imagem.height * 2), Image.LANCZOS)
        imagem = imagem.filter(ImageFilter.UnsharpMask(radius=1.6, percent=70, threshold=2))
    imagem.thumbnail((1800, 1800))
    saida = BytesIO()
    imagem.save(saida, "JPEG", quality=88, optimize=True, progressive=True)
    return ContentFile(saida.getvalue(), name=nome)
