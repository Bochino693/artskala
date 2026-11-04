"""Aplica as migrações pendentes quando o site sobe na Vercel.

Sem isto, uma atualização que cria tabelas (ex.: a 0004 de promoções,
cupons e vídeos) só funciona depois de alguém rodar `python manage.py
migrate` contra o banco de produção; até lá, páginas como a do projeto
davam erro 500 ("relation core_videoprojeto does not exist").

- Só roda no site no ar (MIGRAR_AO_INICIAR, ligado por padrão na Vercel).
- No Postgres, uma trava (pg_advisory_xact_lock) garante que só uma
  instância migra por vez; as outras esperam e encontram tudo aplicado.
  A trava é da transação, o que funciona no pooler do Supabase (porta 6543).
- Se algo falhar, registra no log e o site continua subindo.
"""
import logging

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from django.db.migrations.executor import MigrationExecutor

logger = logging.getLogger(__name__)

CHAVE_TRAVA = 48072026  # número fixo da trava de migração no Postgres


def pendentes(conexao):
    executor = MigrationExecutor(conexao)
    return executor.migration_plan(executor.loader.graph.leaf_nodes())


def migrar_pendentes(forcar=False):
    """Devolve a lista de migrações aplicadas (vazia se não havia nada)."""
    if not (forcar or getattr(settings, "MIGRAR_AO_INICIAR", False)):
        return []

    from django.core.management import call_command

    conexao = connections[DEFAULT_DB_ALIAS]
    aplicadas = []
    try:
        plano = pendentes(conexao)
        if not plano:
            return []

        if conexao.vendor == "postgresql":
            with transaction.atomic(using=DEFAULT_DB_ALIAS):
                with conexao.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [CHAVE_TRAVA])
                plano = pendentes(conexao)  # outra instância pode ter migrado enquanto esperávamos
                if plano:
                    call_command("migrate", interactive=False, verbosity=1)
        else:
            call_command("migrate", interactive=False, verbosity=1)

        aplicadas = [f"{m.app_label}.{m.name}" for m, _volta in plano]
        if aplicadas:
            logger.warning("Migrações aplicadas ao iniciar: %s", ", ".join(aplicadas))
    except Exception:
        logger.exception("Não foi possível aplicar as migrações ao iniciar; rode `python manage.py migrate`.")
    finally:
        conexao.close()
    return aplicadas
