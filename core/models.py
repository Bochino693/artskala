from django.db import models
from django.contrib.auth.models import User


class Prime(models.Model):
    ativo = models.BooleanField(default=True)
    modificado = models.DateTimeField(auto_now=True)
    criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class CategoriaProdutos(Prime):
    nome_categoria = models.CharField(max_length=120)

    class Meta:
        verbose_name = "Categoria de Produto"
        verbose_name_plural = "Categorias de Produtos"

    def __str__(self):
        return self.nome_categoria


class Produto(Prime):
    categoria = models.ForeignKey(
        CategoriaProdutos,
        on_delete=models.CASCADE,
        related_name="produtos"
    )

    nome_produto = models.CharField(max_length=150)
    descricao_produto = models.TextField(max_length=500)
    preco = models.DecimalField(max_digits=12, decimal_places=2)
    estoque = models.PositiveIntegerField(default=0)
    avaliacao = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0
    )

    def __str__(self):
        return self.nome_produto

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"


class ImagemProduto(Prime):
    produto = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE,
        related_name="imagens"
    )

    imagem = models.ImageField(upload_to="produtos/")

    def __str__(self):
        return self.produto.nome_produto


# PORTFÓLIO DE PROJETOS


class Projeto(Prime):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    cliente = models.CharField(max_length=150, blank=True)
    data_execucao = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.titulo


class ImagemProjeto(Prime):
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="imagens"
    )

    imagem = models.ImageField(upload_to="projetos/")

    def __str__(self):
        return self.projeto.titulo


# CARRINHO


class Carrinho(Prime):
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="carrinho"
    )

    def __str__(self):
        return f"Carrinho - {self.usuario.username}"


class ItemCarrinho(Prime):
    carrinho = models.ForeignKey(
        Carrinho,
        on_delete=models.CASCADE,
        related_name="itens"
    )

    produto = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE
    )

    quantidade = models.PositiveIntegerField(default=1)

    def subtotal(self):
        return self.quantidade * self.produto.preco

    def __str__(self):
        return self.produto.nome_produto


# PEDIDOS


class Pedido(Prime):

    STATUS = (
        ("PENDENTE", "Pendente"),
        ("PAGO", "Pago"),
        ("ENVIADO", "Enviado"),
        ("ENTREGUE", "Entregue"),
        ("CANCELADO", "Cancelado"),
    )

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pedidos"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS,
        default="PENDENTE"
    )

    valor_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    endereco = models.CharField(max_length=255)

    def __str__(self):
        return f"Pedido #{self.id}"


class ItemPedido(Prime):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="itens"
    )

    produto = models.ForeignKey(
        Produto,
        on_delete=models.PROTECT
    )

    quantidade = models.PositiveIntegerField(default=1)

    preco_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    def subtotal(self):
        return self.quantidade * self.preco_unitario

    def __str__(self):
        return self.produto.nome_produto



from django.contrib.auth.models import User

class PerfilUsuario(Prime):
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    telefone = models.CharField(max_length=20)
    cpf = models.CharField(max_length=14)
    endereco = models.CharField(max_length=255)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    cep = models.CharField(max_length=9)

    def __str__(self):
        return self.usuario.username
