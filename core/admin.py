from django.contrib import admin

from django.contrib import admin
from .models import CategoriaProdutos, Produto


@admin.register(CategoriaProdutos)
class CategoriaProdutosAdmin(admin.ModelAdmin):
    list_display = ('nome_categoria', 'ativo', 'criacao', 'modificado')
    search_fields = ('nome_categoria',)
    list_filter = ('ativo', 'criacao')
    ordering = ('nome_categoria',)
    list_editable = ('ativo',)
    readonly_fields = ('criacao', 'modificado')

    fieldsets = (
        ("Informações", {
            "fields": ("nome_categoria", "ativo")
        }),
        ("Datas", {
            "fields": ("criacao", "modificado"),
            "classes": ("collapse",)
        }),
    )


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome_produto', 'ativo', 'criacao')
    search_fields = ('nome_produto', 'descricao_produto')
    list_filter = ('ativo', 'criacao')
    ordering = ('nome_produto',)
    list_editable = ('ativo',)
    readonly_fields = ('criacao', 'modificado')

    fieldsets = (
        ("Produto", {
            "fields": (
                "nome_produto",
                "descricao_produto",
                "imagem_produto",
                "ativo"
            )
        }),
        ("Datas", {
            "fields": ("criacao", "modificado"),
            "classes": ("collapse",)
        }),
    )
