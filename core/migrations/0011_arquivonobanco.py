"""Tabela das fotos guardadas no próprio banco do site (só cria a tabela)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_orcamento_endereco"),
    ]

    operations = [
        migrations.CreateModel(
            name="ArquivoNoBanco",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=255, unique=True)),
                ("conteudo", models.BinaryField()),
                ("tipo", models.CharField(default="application/octet-stream", max_length=100)),
                ("tamanho", models.PositiveIntegerField(default=0)),
                ("sha256", models.CharField(max_length=64)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Arquivo no banco",
                "verbose_name_plural": "Arquivos no banco (fotos)",
                "ordering": ["-criado_em"],
            },
        ),
    ]
