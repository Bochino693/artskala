"""Fotos antigas que têm cópia no próprio repositório voltam sozinhas.

As fotos da vitrine (core/vitrine/fotos) foram enviadas ao Cloudinary pelas
migrações 0007 a 0009. Com a conta de lá desativada, elas sumiram do site;
aqui elas são guardadas no banco do site e os campos passam a apontar para a
cópia (core/restauracao.py). Roda uma vez, sozinha, quando o site sobe.

Nunca derruba o deploy: qualquer falha fica no log e o resto é feito pelo
cron diário (/api/midia/espelhar/), por `restaurar_midia --local` ou pela
tela Gestão > Restaurar fotos. Fora de produção (fotos na pasta media/) não
faz nada.
"""
import logging

from django.db import migrations, transaction


def restaurar(apps, schema_editor):
    logger = logging.getLogger("core.midia")
    try:
        from core.restauracao import restaurar_locais

        with transaction.atomic(using=schema_editor.connection.alias):
            feitas = restaurar_locais(registro=apps, modelo_arquivo=apps.get_model("core", "ArquivoNoBanco"))
        if feitas:
            logger.warning("%d foto(s) antigas voltaram de cópias do repositório.", len(feitas))
    except Exception:
        logger.exception("Restauração das fotos do repositório pulada; o cron e a gestão tentam de novo.")


class Migration(migrations.Migration):
    dependencies = [("core", "0011_arquivonobanco")]
    operations = [migrations.RunPython(restaurar, migrations.RunPython.noop)]
