"""Lote 3 da vitrine: mais serviços "sob consulta", fotos novas na adesivação de
veículos e mais projetos no portfólio (core/vitrine)."""
from django.db import migrations


def semear(apps, schema_editor):
    nome_banco = str(schema_editor.connection.settings_dict.get("NAME", ""))
    if "test" in nome_banco or "memory" in nome_banco:
        return
    from core.vitrine import semear as semear_itens, semear_fotos_extras, semear_projetos
    Produto = apps.get_model("core", "Produto")
    ImagemProduto = apps.get_model("core", "ImagemProduto")
    semear_itens(Produto, apps.get_model("core", "CategoriaProdutos"), ImagemProduto, lotes=(3,))
    semear_fotos_extras(Produto, ImagemProduto, lotes=(3,))
    semear_projetos(apps.get_model("core", "Projeto"), apps.get_model("core", "ImagemProjeto"), lotes=(3,))


class Migration(migrations.Migration):
    dependencies = [("core", "0008_vitrine_instagram_lote2")]
    operations = [migrations.RunPython(semear, migrations.RunPython.noop)]
