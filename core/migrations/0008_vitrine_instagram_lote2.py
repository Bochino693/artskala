"""Lote 2 da vitrine: mais 2 serviços "sob consulta" e o portfólio de projetos
com os trabalhos das fotos do Instagram (core/vitrine)."""
from django.db import migrations


def semear(apps, schema_editor):
    nome_banco = str(schema_editor.connection.settings_dict.get("NAME", ""))
    if "test" in nome_banco or "memory" in nome_banco:
        return
    from core.vitrine import semear as semear_itens, semear_projetos
    semear_itens(
        apps.get_model("core", "Produto"),
        apps.get_model("core", "CategoriaProdutos"),
        apps.get_model("core", "ImagemProduto"),
        lotes=(2,),
    )
    semear_projetos(apps.get_model("core", "Projeto"), apps.get_model("core", "ImagemProjeto"), lotes=(2,))


class Migration(migrations.Migration):
    dependencies = [("core", "0007_vitrine_instagram")]
    operations = [migrations.RunPython(semear, migrations.RunPython.noop)]
