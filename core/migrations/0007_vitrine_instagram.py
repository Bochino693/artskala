"""Itens "sob consulta" feitos com as fotos do Instagram (core/vitrine)."""
from django.db import migrations


def semear(apps, schema_editor):
    # Nos testes o banco é temporário: não envia fotos de exemplo.
    nome_banco = str(schema_editor.connection.settings_dict.get("NAME", ""))
    if "test" in nome_banco or "memory" in nome_banco:
        return
    from core.vitrine import semear as semear_itens
    semear_itens(
        apps.get_model("core", "Produto"),
        apps.get_model("core", "CategoriaProdutos"),
        apps.get_model("core", "ImagemProduto"),
    )


class Migration(migrations.Migration):
    dependencies = [("core", "0006_post_instagram_manual")]
    operations = [migrations.RunPython(semear, migrations.RunPython.noop)]
