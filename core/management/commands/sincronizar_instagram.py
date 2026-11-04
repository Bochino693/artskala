"""python manage.py sincronizar_instagram — traz os posts novos do @artskalaa agora."""
from django.core.management.base import BaseCommand, CommandError

from core.instagram import ErroInstagram, registrar_erro, sincronizar


class Command(BaseCommand):
    help = "Busca os posts mais recentes do Instagram pela API oficial e grava os novos."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=18, help="Quantos posts recentes conferir (máx. 50).")

    def handle(self, *args, **opcoes):
        try:
            resumo = sincronizar(limite=opcoes["limite"])
        except ErroInstagram as erro:
            registrar_erro(erro)
            raise CommandError(str(erro))
        self.stdout.write(self.style.SUCCESS(f"Instagram: {resumo}."))
