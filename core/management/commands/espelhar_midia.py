"""python manage.py espelhar_midia — copia para o banco do site as fotos antigas.

Para cada foto (FileField/ImageField de qualquer modelo) cujo nome não começa
com "banco/": baixa do Cloudinary (ou usa a cópia que já existe no
repositório, como as fotos da vitrine), guarda no banco como
"banco/<nome antigo>" e aponta o campo para o nome novo. O original no
Cloudinary não é apagado.

Se o Cloudinary responder 401/"disabled" (conta desativada), para de tentar e
avisa quantas fotos ficaram esperando. Rodar de novo continua de onde parou e
não duplica nada.

    python manage.py espelhar_midia --simular
    python manage.py espelhar_midia
    python manage.py espelhar_midia --limite 50

No computador, contra o banco de produção, basta ter DATABASE_URL (e
CLOUDINARY_CLOUD_NAME) no ambiente: com DATABASE_URL o site guarda as fotos
no banco, como em produção.
"""
from django.core.management.base import BaseCommand

from core.restauracao import espelhar, estatisticas


class Command(BaseCommand):
    help = "Copia as fotos antigas (Cloudinary) para o banco do site e aponta os campos para a cópia."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=0, help="Para depois de copiar N fotos (0 = todas).")
        parser.add_argument("--simular", action="store_true", help="Só mostra o que faria, sem gravar nada.")

    def handle(self, *args, **opcoes):
        resumo = espelhar(limite=opcoes["limite"] or None, simular=opcoes["simular"], aviso=self.stdout.write)
        if resumo.parado:
            self.stdout.write(self.style.WARNING(resumo.parado))
            return
        for nome in resumo.faltando_no_cloudinary:
            self.stdout.write(self.style.WARNING(f"  não existe no Cloudinary: {nome}"))
        for nome, erro in resumo.erros:
            self.stdout.write(self.style.ERROR(f"  erro em {nome}: {erro}"))
        estilo = self.style.WARNING if resumo.cloudinary_fora else self.style.SUCCESS
        self.stdout.write(estilo(("(simulação) " if opcoes["simular"] else "") + resumo.texto()))
        if resumo.cloudinary_fora:
            self.stdout.write("Quando a conta do Cloudinary voltar, rode de novo (o cron da Vercel também tenta todo dia).")
        stats = estatisticas()
        self.stdout.write(f"Banco do site: {stats['no_banco']} arquivo(s), {stats['megabytes']} MB.")
