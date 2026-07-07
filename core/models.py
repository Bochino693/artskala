from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


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
    preco = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    custo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Custo interno do produto para cálculo de lucro.",
    )
    estoque = models.PositiveIntegerField(default=0)
    avaliacao = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("5.00")),
        ],
    )

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ["nome_produto"]

    def lucro_unitario(self):
        return self.preco - self.custo

    def margem_lucro_percentual(self):
        if self.preco <= 0:
            return Decimal("0.00")
        return (self.lucro_unitario() / self.preco) * Decimal("100")

    def __str__(self):
        return self.nome_produto


class ImagemProduto(Prime):
    produto = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE,
        related_name="imagens",
    )
    imagem = models.ImageField(upload_to="produtos/", blank=True, null=True)

    class Meta:
        verbose_name = "Imagem de Produto"
        verbose_name_plural = "Imagens de Produtos"

    def __str__(self):
        return self.produto.nome_produto if self.produto_id else "Imagem de produto"


class Projeto(Prime):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default="")
    cliente = models.CharField(max_length=150, blank=True, default="")
    data_execucao = models.DateField(null=True, blank=True)

    valor_estimado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Valor de venda estimado do projeto.",
    )
    custo_estimado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Custo interno estimado do projeto.",
    )

    class Meta:
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"
        ordering = ["-criacao"]

    def lucro_estimado(self):
        return self.valor_estimado - self.custo_estimado

    def margem_lucro_percentual(self):
        if self.valor_estimado <= 0:
            return Decimal("0.00")
        return (self.lucro_estimado() / self.valor_estimado) * Decimal("100")

    def __str__(self):
        return self.titulo


class ImagemProjeto(Prime):
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="imagens",
    )
    imagem = models.ImageField(upload_to="projetos/", blank=True, null=True)

    class Meta:
        verbose_name = "Imagem de Projeto"
        verbose_name_plural = "Imagens de Projetos"

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

    def total_itens(self):
        return sum(item.quantidade for item in self.itens.all())

    def total_valor(self):
        return sum((item.subtotal() for item in self.itens.all()), Decimal("0.00"))

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
        unique_together = ("carrinho", "produto")

    def subtotal(self):
        return self.quantidade * self.produto.preco

    def subtotal_custo(self):
        return self.quantidade * self.produto.custo

    def lucro_estimado(self):
        return self.subtotal() - self.subtotal_custo()

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

    METODOS_PAGAMENTO = (
        ("PIX", "Pix"),
        ("CARTAO", "Cartão"),
        ("DINHEIRO", "Dinheiro"),
        ("TRANSFERENCIA", "Transferência"),
        ("BOLETO", "Boleto"),
        ("A_COMBINAR", "A combinar"),
    )

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pedidos",
    )
    status = models.CharField(max_length=20, choices=STATUS, default="PENDENTE")
    metodo_pagamento = models.CharField(
        max_length=20,
        choices=METODOS_PAGAMENTO,
        default="A_COMBINAR",
    )
    valor_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    custo_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Custo total interno do pedido.",
    )
    endereco = models.CharField(max_length=255, blank=True, default="")
    observacoes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ["-criacao"]

    def recalcular_totais(self, salvar=True):
        total_venda = sum((item.subtotal() for item in self.itens.all()), Decimal("0.00"))
        total_custo = sum((item.subtotal_custo() for item in self.itens.all()), Decimal("0.00"))

        self.valor_total = total_venda
        self.custo_total = total_custo

        if salvar:
            self.save(update_fields=["valor_total", "custo_total", "modificado"])

        return self.valor_total

    def lucro_total(self):
        return self.valor_total - self.custo_total

    def margem_lucro_percentual(self):
        if self.valor_total <= 0:
            return Decimal("0.00")
        return (self.lucro_total() / self.valor_total) * Decimal("100")

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
    preco_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    custo_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Custo unitário congelado no momento do pedido.",
    )

    class Meta:
        verbose_name = "Item do Pedido"
        verbose_name_plural = "Itens do Pedido"

    def subtotal(self):
        return self.quantidade * self.preco_unitario

    def subtotal_custo(self):
        return self.quantidade * self.custo_unitario

    def lucro_total(self):
        return self.subtotal() - self.subtotal_custo()

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


class Orcamento(Prime):
    TIPO = (
        ("PRODUTO", "Produto"),
        ("PROJETO", "Projeto"),
        ("MISTO", "Misto"),
    )

    STATUS = (
        ("RASCUNHO", "Rascunho"),
        ("ENVIADO", "Enviado"),
        ("APROVADO", "Aprovado"),
        ("RECUSADO", "Recusado"),
        ("EXPIRADO", "Expirado"),
    )

    FORMAS_PAGAMENTO = (
        ("PIX", "Pix"),
        ("CARTAO", "Cartão"),
        ("DINHEIRO", "Dinheiro"),
        ("TRANSFERENCIA", "Transferência"),
        ("BOLETO", "Boleto"),
        ("A_COMBINAR", "A combinar"),
    )

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="orcamentos",
    )
    titulo = models.CharField(max_length=150)
    tipo = models.CharField(max_length=10, choices=TIPO, default="MISTO")
    status = models.CharField(max_length=10, choices=STATUS, default="RASCUNHO")

    cliente_nome = models.CharField(max_length=150, blank=True, default="")
    cliente_email = models.EmailField(blank=True, default="")
    cliente_telefone = models.CharField(max_length=20, blank=True, default="")

    data_validade = models.DateField(null=True, blank=True)
    data_prevista_entrega = models.DateField(null=True, blank=True)

    desconto_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )

    custo_extra = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Custos adicionais do orçamento, como frete, instalação, mão de obra ou deslocamento.",
    )

    forma_pagamento = models.CharField(
        max_length=20,
        choices=FORMAS_PAGAMENTO,
        default="A_COMBINAR",
    )

    prazo_execucao = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Exemplo: 30 dias úteis, 2 a 3 dias de instalação.",
    )

    observacoes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Orçamento"
        verbose_name_plural = "Orçamentos"
        ordering = ["-criacao"]

    def valor_bruto(self):
        return sum((item.subtotal() for item in self.itens.all()), Decimal("0.00"))

    def valor_desconto(self):
        return (self.valor_bruto() * self.desconto_percentual) / Decimal("100")

    def valor_total(self):
        return self.valor_bruto() - self.valor_desconto()

    def custo_total(self):
        custo_itens = sum((item.subtotal_custo() for item in self.itens.all()), Decimal("0.00"))
        return custo_itens + self.custo_extra

    def lucro_estimado(self):
        return self.valor_total() - self.custo_total()

    def margem_lucro_percentual(self):
        total = self.valor_total()
        if total <= 0:
            return Decimal("0.00")
        return (self.lucro_estimado() / total) * Decimal("100")

    def total_itens(self):
        return self.itens.count()

    def esta_expirado(self):
        if not self.data_validade:
            return False
        if self.status in ("APROVADO", "RECUSADO"):
            return False
        return self.data_validade < timezone.now().date()

    def __str__(self):
        return f"Orçamento #{self.id} - {self.titulo}"


class ItemOrcamento(Prime):
    orcamento = models.ForeignKey(
        Orcamento,
        on_delete=models.CASCADE,
        related_name="itens",
    )
    produto = models.ForeignKey(
        Produto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="itens_orcamento",
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="itens_orcamento",
    )
    descricao = models.CharField(max_length=200, blank=True, default="")

    data_referencia = models.DateField(
        null=True,
        blank=True,
        help_text="Data prevista de execução/entrega deste item.",
    )

    quantidade = models.PositiveIntegerField(default=1)

    valor_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    custo_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Custo unitário estimado para cálculo de lucro.",
    )

    class Meta:
        verbose_name = "Item de Orçamento"
        verbose_name_plural = "Itens de Orçamento"
        ordering = ["id"]

    def subtotal(self):
        return self.quantidade * self.valor_unitario

    def subtotal_custo(self):
        return self.quantidade * self.custo_unitario

    def lucro_total(self):
        return self.subtotal() - self.subtotal_custo()

    def margem_lucro_percentual(self):
        subtotal = self.subtotal()
        if subtotal <= 0:
            return Decimal("0.00")
        return (self.lucro_total() / subtotal) * Decimal("100")

    def nome_display(self):
        if self.produto_id:
            return self.produto.nome_produto
        if self.projeto_id:
            return self.projeto.titulo
        return self.descricao or "Item personalizado"

    def origem_display(self):
        if self.produto_id:
            return "Produto"
        if self.projeto_id:
            return "Projeto"
        return "Avulso"

    def preencher_valores_por_origem(self):
        if self.produto_id:
            if self.valor_unitario == Decimal("0.00"):
                self.valor_unitario = self.produto.preco
            if self.custo_unitario == Decimal("0.00"):
                self.custo_unitario = self.produto.custo

        if self.projeto_id:
            if self.valor_unitario == Decimal("0.00"):
                self.valor_unitario = self.projeto.valor_estimado
            if self.custo_unitario == Decimal("0.00"):
                self.custo_unitario = self.projeto.custo_estimado

    def save(self, *args, **kwargs):
        self.preencher_valores_por_origem()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome_display()
