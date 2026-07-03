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
        ordering = ["nome_categoria"]

    def __str__(self):
        return self.nome_categoria


class Produto(Prime):
    categoria = models.ForeignKey(
        CategoriaProdutos,
        on_delete=models.PROTECT,
        related_name="produtos",
    )
    nome_produto = models.CharField(max_length=150)
    descricao_produto = models.TextField(max_length=500, blank=True, default="")
    preco = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estoque = models.PositiveIntegerField(default=0)
    avaliacao = models.DecimalField(max_digits=3, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ["nome_produto"]

    def __str__(self):
        return self.nome_produto


class ImagemProduto(Prime):
    produto = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE,
        related_name="imagens",
    )
    imagem = models.ImageField(upload_to="produtos/", blank=True, null=True)

    def __str__(self):
        return self.produto.nome_produto if self.produto_id else "Imagem de produto"


class Projeto(Prime):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default="")
    cliente = models.CharField(max_length=150, blank=True, default="")
    data_execucao = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"
        ordering = ["-criacao"]

    def __str__(self):
        return self.titulo


class ImagemProjeto(Prime):
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="imagens",
    )
    imagem = models.ImageField(upload_to="projetos/", blank=True, null=True)

    def __str__(self):
        return self.projeto.titulo if self.projeto_id else "Imagem de projeto"


class Carrinho(Prime):
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="carrinho",
    )

    class Meta:
        verbose_name = "Carrinho"
        verbose_name_plural = "Carrinhos"

    def __str__(self):
        return f"Carrinho - {self.usuario.username}"


class ItemCarrinho(Prime):
    carrinho = models.ForeignKey(
        Carrinho,
        on_delete=models.CASCADE,
        related_name="itens",
    )
    produto = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE,
    )
    quantidade = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Item do Carrinho"
        verbose_name_plural = "Itens do Carrinho"

    def subtotal(self):
        return self.quantidade * self.produto.preco

    def __str__(self):
        return self.produto.nome_produto


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
        related_name="pedidos",
    )
    status = models.CharField(max_length=20, choices=STATUS, default="PENDENTE")
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    endereco = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ["-criacao"]

    def __str__(self):
        return f"Pedido #{self.id}"


class ItemPedido(Prime):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="itens",
    )
    produto = models.ForeignKey(
        Produto,
        on_delete=models.PROTECT,
    )
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Item do Pedido"
        verbose_name_plural = "Itens do Pedido"

    def subtotal(self):
        return self.quantidade * self.preco_unitario

    def __str__(self):
        return self.produto.nome_produto


class PerfilUsuario(Prime):
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil",
    )
    telefone = models.CharField(max_length=20, blank=True, default="")
    cpf = models.CharField(max_length=14, blank=True, default="")
    endereco = models.CharField(max_length=255, blank=True, default="")
    cidade = models.CharField(max_length=100, blank=True, default="")
    estado = models.CharField(max_length=2, blank=True, default="")
    cep = models.CharField(max_length=9, blank=True, default="")

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"

    def __str__(self):
        return self.usuario.username
