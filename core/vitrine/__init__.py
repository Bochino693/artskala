"""Itens de vitrine feitos a partir das fotos do Instagram @artskalaa.

São serviços "sob consulta" (preço R$ 0,00 e sem estoque): aparecem no
catálogo com foto e o botão "Pedir orçamento deste produto" no WhatsApp, sem
carrinho. Só os produtos de pronta entrega da loja têm preço.

Cada leva de fotos é um "lote" com a sua migração (0007 = lote 1,
0008 = lote 2, 0009 = lote 3...). A migração roda uma vez só: não recria um item que já
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
    # ------------------------------------------------------------ lote 3
    {
        "lote": 3,
        "nome": "Letras caixa em PVC e acrílico",
        "categoria": "Letreiros",
        "fotos": ["letras-caixa-pvc.jpg"],
        "descricao": (
            "Letras caixa com volume, recortadas em PVC expandido ou acrílico e "
            "pintadas na cor da marca. Para fachadas, recepções e paredes de "
            "destaque, com ou sem iluminação. Orçamento sob consulta."
        ),
    },
    {
        "lote": 3,
        "nome": "Fresagem CNC de ACM e acrílico",
        "categoria": "Letreiros",
        "fotos": ["fresagem-cnc-acm.jpg"],
        "descricao": (
            "Corte e usinagem em router CNC de chapas de ACM, acrílico, PVC e MDF: "
            "letras, logos, fachadas e peças sob medida com acabamento preciso. "
            "Orçamento sob consulta."
        ),
    },
    {
        "lote": 3,
        "nome": "Placa em ACM com impressão digital",
        "categoria": "Placas",
        "fotos": ["placa-acm-impressa-kasuko.jpg"],
        "descricao": (
            "Placa rígida em ACM com impressão digital em alta resolução, como a "
            "da Kasuko Sushi: cores vivas, resistente ao tempo e pronta para "
            "parede, fachada ou cavalete. Orçamento sob consulta."
        ),
    },
    {
        "lote": 3,
        "nome": "Placa redonda em acrílico e ACM",
        "categoria": "Placas",
        "fotos": ["placa-redonda-dojo.jpg"],
        "descricao": (
            "Placa circular com o logo em acrílico e base em ACM, como a do "
            "Sun-Dome Dojo Karatê-Do. Pode ter iluminação de LED e é feita no "
            "tamanho que você precisar. Orçamento sob consulta."
        ),
    },
    {
        "lote": 3,
        "nome": "Placa de identificação em acrílico recortado",
        "categoria": "Placas",
        "fotos": ["placa-acrilico-artskala.jpg"],
        "descricao": (
            "Placa de identificação com o logo recortado em acrílico, número e "
            "endereço, como a da nossa sede. Ideal para galpões, portarias, "
            "salas e condomínios. Orçamento sob consulta."
        ),
    },
    {
        "lote": 3,
        "nome": "Letreiro neon de LED",
        "categoria": "Letreiros",
        "fotos": ["letreiro-neon-led.jpg"],
        "descricao": (
            "Letreiro com o nome ou a frase que você quiser em LED neon flexível, "
            "montado sobre acrílico. Econômico, não esquenta e deixa recepções, "
            "lojas e eventos com cara de marca. Orçamento sob consulta."
        ),
    },
    {
        "lote": 3,
        "nome": "Quadro decorativo impresso em alta resolução",
        "categoria": "Impressão digital",
        "fotos": ["quadro-impresso-ems.jpg"],
        "descricao": (
            "Quadro com impressão digital em alta resolução sobre chapa rígida, "
            "como o da EMS Engenharia: para recepções, escritórios e salas de "
            "reunião, no tamanho da sua parede. Orçamento sob consulta."
        ),
    },
    {
        "lote": 3,
        "nome": "Banner e painel em lona impressa",
        "categoria": "Impressão digital",
        "fotos": ["painel-lona-impresso.jpg"],
        "descricao": (
            "Banner, painel e faixa em lona com impressão digital de alta "
            "definição, com acabamento em bastão, ilhós ou estrutura. Para "
            "eventos, lojas, oficinas e decoração. Orçamento sob consulta."
        ),
    },
    {
        "lote": 3,
        "nome": "Envelopamento de veículos",
        "categoria": "Adesivos",
        "fotos": ["envelopamento-kombi.jpg"],
        "descricao": (
            "Troca de cor e proteção da pintura com envelopamento em vinil "
            "automotivo: carros, Kombis, vans e motos, com acabamento brilho, "
            "fosco ou metálico. Orçamento sob consulta."
        ),
    },
]

# Fotos novas que entram em itens que já existem (carrossel do produto).
FOTOS_EXTRAS = [
    {
        "lote": 3,
        "produto": "Adesivação de veículos e frotas",
        "fotos": [
            "adesivacao-kombi-rappi.jpg",
            "adesivacao-choperia-villy.jpg",
            "adesivacao-picape-ranch.jpg",
            "adesivacao-leone-faixas.jpg",
            "adesivacao-correios.jpg",
        ],
    },
    {
        "lote": 3,
        "produto": "Peças em acrílico e PVC recortadas",
        "fotos": ["placa-recortada-oval.jpg"],
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
    # ------------------------------------------------------------ lote 3
    {
        "lote": 3,
        "titulo": "Placa da Kasuko Sushi",
        "cliente": "Kasuko Sushi",
        "fotos": ["placa-acm-impressa-kasuko.jpg"],
        "descricao": "Placa em ACM com impressão digital em alta resolução para a Kasuko Sushi – Culinária Japonesa.",
    },
    {
        "lote": 3,
        "titulo": "Placa do Sun-Dome Dojo Karatê-Do",
        "cliente": "Sun-Dome Dojo Karatê-Do",
        "fotos": ["placa-redonda-dojo.jpg"],
        "descricao": "Placa redonda com o símbolo do dojo em acrílico sobre base de ACM.",
    },
    {
        "lote": 3,
        "titulo": "Quadro da EMS Engenharia",
        "cliente": "EMS Engenharia",
        "fotos": ["quadro-impresso-ems.jpg"],
        "descricao": "Quadro decorativo impresso em alta resolução, com a marca da EMS Engenharia sobre a ponte estaiada.",
    },
    {
        "lote": 3,
        "titulo": "Adesivação da Kombi Rappi",
        "cliente": "Rappi",
        "fotos": ["adesivacao-kombi-rappi.jpg"],
        "descricao": "Kombi adesivada por completo com a identidade da Rappi, com QR Code e chamadas da campanha.",
    },
    {
        "lote": 3,
        "titulo": "Adesivação da picape Choperia Dom Villy",
        "cliente": "Choperia Dom Villy",
        "fotos": ["adesivacao-choperia-villy.jpg"],
        "descricao": "Logo, telefone e Instagram da Choperia Dom Villy aplicados nas portas da picape.",
    },
    {
        "lote": 3,
        "titulo": "Adesivação da picape Saruê Ranch",
        "cliente": "Saruê Ranch",
        "fotos": ["adesivacao-picape-ranch.jpg"],
        "descricao": "Nome, Instagram e brasão da Saruê Ranch em adesivo de recorte na picape prata.",
    },
    {
        "lote": 3,
        "titulo": "Adesivação do carro da Leone Faixas",
        "cliente": "Leone Faixas",
        "fotos": ["adesivacao-leone-faixas.jpg"],
        "descricao": "Redes sociais e @ da Leone Faixas em adesivo nas portas do carro.",
    },
    {
        "lote": 3,
        "titulo": "Adesivação de veículo dos Correios",
        "cliente": "Correios",
        "fotos": ["adesivacao-correios.jpg"],
        "descricao": "Aplicação da marca dos Correios em veículo de entrega.",
    },
    {
        "lote": 3,
        "titulo": "Placa de identificação da sede ArtSkala",
        "cliente": "ArtSkala Comunicação Visual",
        "fotos": ["placa-acrilico-artskala.jpg"],
        "descricao": "A placa da nossa própria casa: logo recortado em acrílico, com número e galpão, no portão da sede.",
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


def semear_fotos_extras(Produto, ImagemProduto, lotes=(3,)):
    """Põe as fotos de FOTOS_EXTRAS nos itens que existem (e ainda não têm a foto).
    Devolve quantas fotos entraram."""
    criadas = 0
    for extra in FOTOS_EXTRAS:
        if extra.get("lote", 1) not in lotes:
            continue
        produto = Produto.objects.filter(nome_produto=extra["produto"]).first()
        if produto is None:
            continue
        for nome in extra["fotos"]:
            ja_tem = ImagemProduto.objects.filter(produto=produto, imagem__contains=Path(nome).stem).exists()
            if ja_tem or not (PASTA_FOTOS / nome).exists():
                continue
            _salvar_fotos([nome], lambda n, arquivo: ImagemProduto(produto=produto).imagem.save(n, arquivo, save=True))
            criadas += 1
    return criadas


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
