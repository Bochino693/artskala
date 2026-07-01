from django.contrib import admin
from django.utils.html import format_html

from .models import (
    CategoriaProdutos,
    Produto,
    ImagemProduto,
    Projeto,
    ImagemProjeto,
    Carrinho,
    ItemCarrinho,
    Pedido,
    ItemPedido,
    PerfilUsuario,
)


# ============================================================
# CONFIGURAÇÃO GERAL DO PAINEL
# ============================================================

admin.site.site_header = "ArtSkala Admin"
admin.site.site_title = "ArtSkala"
admin.site.index_title = "Painel Administrativo"


# ============================================================
# CATEGORIAS
# ============================================================

@admin.register(CategoriaProdutos)
class CategoriaProdutosAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nome_categoria",
        "ativo",
        "criacao",
        "modificado",
    )

    list_filter = (
        "ativo",
        "criacao",
    )

    search_fields = (
        "nome_categoria",
    )

    list_editable = (
        "ativo",
    )

    ordering = (
        "nome_categoria",
    )


# ============================================================
# PRODUTOS
# ============================================================

class ImagemProdutoInline(admin.TabularInline):
    model = ImagemProduto
    extra = 1
    fields = (
        "imagem",
        "preview_imagem",
        "ativo",
    )
    readonly_fields = (
        "preview_imagem",
    )

    def preview_imagem(self, obj):
        if obj and obj.imagem:
            return format_html(
                '<img src="{}" style="width: 90px; height: 70px; object-fit: cover; border-radius: 10px;" />',
                obj.imagem.url
            )

        return "Sem imagem"

    preview_imagem.short_description = "Prévia"


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "preview_imagem",
        "nome_produto",
        "categoria",
        "preco",
        "estoque",
        "avaliacao",
        "ativo",
        "criacao",
    )

    list_filter = (
        "ativo",
        "categoria",
        "criacao",
    )

    search_fields = (
        "nome_produto",
        "descricao_produto",
        "categoria__nome_categoria",
    )

    list_editable = (
        "preco",
        "estoque",
        "ativo",
    )

    ordering = (
        "-criacao",
    )

    inlines = [
        ImagemProdutoInline,
    ]

    fieldsets = (
        (
            "Informações do Produto",
            {
                "fields": (
                    "categoria",
                    "nome_produto",
                    "descricao_produto",
                )
            },
        ),
        (
            "Comercial",
            {
                "fields": (
                    "preco",
                    "estoque",
                    "avaliacao",
                    "ativo",
                )
            },
        ),
    )

    def preview_imagem(self, obj):
        imagem = obj.imagens.first()

        if imagem and imagem.imagem:
            return format_html(
                '<img src="{}" style="width: 80px; height: 60px; object-fit: cover; border-radius: 10px;" />',
                imagem.imagem.url
            )

        return "Sem imagem"

    preview_imagem.short_description = "Imagem"


@admin.register(ImagemProduto)
class ImagemProdutoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "produto",
        "preview_imagem",
        "ativo",
        "criacao",
    )

    list_filter = (
        "ativo",
        "criacao",
    )

    search_fields = (
        "produto__nome_produto",
    )

    readonly_fields = (
        "preview_imagem",
    )

    def preview_imagem(self, obj):
        if obj and obj.imagem:
            return format_html(
                '<img src="{}" style="width: 120px; height: 90px; object-fit: cover; border-radius: 12px;" />',
                obj.imagem.url
            )

        return "Sem imagem"

    preview_imagem.short_description = "Prévia"


# ============================================================
# PROJETOS / PORTFÓLIO
# ============================================================

class ImagemProjetoInline(admin.TabularInline):
    model = ImagemProjeto
    extra = 1
    fields = (
        "imagem",
        "preview_imagem",
        "ativo",
    )
    readonly_fields = (
        "preview_imagem",
    )

    def preview_imagem(self, obj):
        if obj and obj.imagem:
            return format_html(
                '<img src="{}" style="width: 90px; height: 70px; object-fit: cover; border-radius: 10px;" />',
                obj.imagem.url
            )

        return "Sem imagem"

    preview_imagem.short_description = "Prévia"


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "preview_imagem",
        "titulo",
        "cliente",
        "data_execucao",
        "ativo",
        "criacao",
    )

    list_filter = (
        "ativo",
        "data_execucao",
        "criacao",
    )

    search_fields = (
        "titulo",
        "descricao",
        "cliente",
    )

    list_editable = (
        "ativo",
    )

    ordering = (
        "-criacao",
    )

    inlines = [
        ImagemProjetoInline,
    ]

    fieldsets = (
        (
            "Informações do Projeto",
            {
                "fields": (
                    "titulo",
                    "descricao",
                    "cliente",
                    "data_execucao",
                    "ativo",
                )
            },
        ),
    )

    def preview_imagem(self, obj):
        imagem = obj.imagens.first()

        if imagem and imagem.imagem:
            return format_html(
                '<img src="{}" style="width: 80px; height: 60px; object-fit: cover; border-radius: 10px;" />',
                imagem.imagem.url
            )

        return "Sem imagem"

    preview_imagem.short_description = "Imagem"


@admin.register(ImagemProjeto)
class ImagemProjetoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "projeto",
        "preview_imagem",
        "ativo",
        "criacao",
    )

    list_filter = (
        "ativo",
        "criacao",
    )

    search_fields = (
        "projeto__titulo",
        "projeto__cliente",
    )

    readonly_fields = (
        "preview_imagem",
    )

    def preview_imagem(self, obj):
        if obj and obj.imagem:
            return format_html(
                '<img src="{}" style="width: 120px; height: 90px; object-fit: cover; border-radius: 12px;" />',
                obj.imagem.url
            )

        return "Sem imagem"

    preview_imagem.short_description = "Prévia"


# ============================================================
# CARRINHO
# ============================================================

class ItemCarrinhoInline(admin.TabularInline):
    model = ItemCarrinho
    extra = 0
    fields = (
        "produto",
        "quantidade",
        "subtotal_item",
        "ativo",
    )
    readonly_fields = (
        "subtotal_item",
    )

    def subtotal_item(self, obj):
        if obj and obj.produto:
            return f"R$ {obj.subtotal():.2f}"

        return "R$ 0,00"

    subtotal_item.short_description = "Subtotal"


@admin.register(Carrinho)
class CarrinhoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "usuario",
        "total_itens",
        "valor_total",
        "ativo",
        "criacao",
    )

    list_filter = (
        "ativo",
        "criacao",
    )

    search_fields = (
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
        "usuario__email",
    )

    inlines = [
        ItemCarrinhoInline,
    ]

    def total_itens(self, obj):
        return obj.itens.count()

    total_itens.short_description = "Itens"

    def valor_total(self, obj):
        total = sum(
            item.subtotal()
            for item in obj.itens.all()
        )

        return f"R$ {total:.2f}"

    valor_total.short_description = "Total"


@admin.register(ItemCarrinho)
class ItemCarrinhoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "carrinho",
        "produto",
        "quantidade",
        "subtotal_item",
        "ativo",
        "criacao",
    )

    list_filter = (
        "ativo",
        "criacao",
    )

    search_fields = (
        "carrinho__usuario__username",
        "produto__nome_produto",
    )

    list_editable = (
        "quantidade",
        "ativo",
    )

    def subtotal_item(self, obj):
        return f"R$ {obj.subtotal():.2f}"

    subtotal_item.short_description = "Subtotal"


# ============================================================
# PEDIDOS
# ============================================================

class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 0
    fields = (
        "produto",
        "quantidade",
        "preco_unitario",
        "subtotal_item",
        "ativo",
    )
    readonly_fields = (
        "subtotal_item",
    )

    def subtotal_item(self, obj):
        if obj and obj.produto:
            return f"R$ {obj.subtotal():.2f}"

        return "R$ 0,00"

    subtotal_item.short_description = "Subtotal"


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "usuario",
        "status",
        "valor_total",
        "total_itens",
        "ativo",
        "criacao",
    )

    list_filter = (
        "status",
        "ativo",
        "criacao",
    )

    search_fields = (
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
        "usuario__email",
        "endereco",
    )

    list_editable = (
        "status",
        "ativo",
    )

    ordering = (
        "-criacao",
    )

    inlines = [
        ItemPedidoInline,
    ]

    fieldsets = (
        (
            "Cliente",
            {
                "fields": (
                    "usuario",
                )
            },
        ),
        (
            "Pedido",
            {
                "fields": (
                    "status",
                    "valor_total",
                    "endereco",
                    "ativo",
                )
            },
        ),
    )

    def total_itens(self, obj):
        return obj.itens.count()

    total_itens.short_description = "Itens"


@admin.register(ItemPedido)
class ItemPedidoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "pedido",
        "produto",
        "quantidade",
        "preco_unitario",
        "subtotal_item",
        "ativo",
        "criacao",
    )

    list_filter = (
        "ativo",
        "criacao",
    )

    search_fields = (
        "pedido__usuario__username",
        "produto__nome_produto",
    )

    list_editable = (
        "quantidade",
        "ativo",
    )

    def subtotal_item(self, obj):
        return f"R$ {obj.subtotal():.2f}"

    subtotal_item.short_description = "Subtotal"


# ============================================================
# PERFIL DO USUÁRIO
# ============================================================

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "usuario",
        "nome_completo",
        "telefone",
        "cpf",
        "cidade",
        "estado",
        "cep",
        "ativo",
        "criacao",
    )

    list_filter = (
        "estado",
        "ativo",
        "criacao",
    )

    search_fields = (
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
        "usuario__email",
        "telefone",
        "cpf",
        "cidade",
        "estado",
        "cep",
    )

    list_editable = (
        "ativo",
    )

    fieldsets = (
        (
            "Usuário",
            {
                "fields": (
                    "usuario",
                    "ativo",
                )
            },
        ),
        (
            "Contato",
            {
                "fields": (
                    "telefone",
                    "cpf",
                )
            },
        ),
        (
            "Endereço",
            {
                "fields": (
                    "endereco",
                    "cidade",
                    "estado",
                    "cep",
                )
            },
        ),
    )

    def nome_completo(self, obj):
        nome = obj.usuario.get_full_name()

        if nome:
            return nome

        return obj.usuario.username

    nome_completo.short_description = "Nome"
