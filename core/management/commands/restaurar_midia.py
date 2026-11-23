"""python manage.py restaurar_midia — traz de volta as fotos antigas sem o Cloudinary.

    python manage.py restaurar_midia --relatorio
        lista o que ainda falta (modelo, id, campo, nome antigo) e se há
        cópia no repositório.

    python manage.py restaurar_midia --local
        usa as cópias que já estão no repositório (fotos da vitrine,
        core/static, staticfiles, pasta media/) e o próprio Instagram (posts
        trazidos pela API).

    python manage.py restaurar_midia --zip Downloads/cloudinary.zip
    python manage.py restaurar_midia --pasta Downloads/cloudinary
        arquivos baixados da Biblioteca de Mídia do Cloudinary (ou de outra
        cópia): cada um volta pelo nome (pasta + nome sem extensão), para
        todos os lugares que usavam aquela foto.

Use --simular para ver sem gravar. Rodar de novo não duplica nada. É a mesma
lógica da tela Gestão > Restaurar fotos.
"""
import zipfile

from django.core.management.base import BaseCommand, CommandError

from core.midia import midia_no_banco_ativa
from core.restauracao import (
    Indice,
    arquivos_de_pasta,
    arquivos_de_zip,
    estatisticas,
    referencias,
    relatorio,
    restaurar_arquivo,
    restaurar_locais,
)


class Command(BaseCommand):
    help = "Restaura as fotos antigas a partir do repositório, do Instagram ou de uma exportação do Cloudinary."

    def add_arguments(self, parser):
        parser.add_argument("--relatorio", action="store_true", help="Lista o que ainda falta.")
        parser.add_argument("--local", action="store_true", help="Usa as cópias do repositório e o Instagram.")
        parser.add_argument("--zip", help="ZIP baixado do Cloudinary.")
        parser.add_argument("--pasta", help="Pasta com as fotos baixadas do Cloudinary.")
        parser.add_argument("--simular", action="store_true", help="Só mostra o que faria.")

    def handle(self, *args, **opcoes):
        if not any(opcoes[o] for o in ("relatorio", "local", "zip", "pasta")):
            opcoes["relatorio"] = True
        if (opcoes["local"] or opcoes["zip"] or opcoes["pasta"]) and not midia_no_banco_ativa():
            raise CommandError("Este ambiente não guarda as fotos no banco. Para gravar no banco de produção, "
                               "rode com DATABASE_URL (ou MIDIA_NO_BANCO=1).")
        if opcoes["local"]:
            self._local(opcoes["simular"])
        for origem in ("zip", "pasta"):
            if opcoes[origem]:
                self._exportacao(origem, opcoes[origem], opcoes["simular"])
        if opcoes["relatorio"]:
            self._relatorio()

    def _local(self, simular):
        nomes = restaurar_locais(simular=simular)
        for nome in nomes:
            self.stdout.write(f"  {'(simulação) ' if simular else ''}do repositório: {nome}")
        self.stdout.write(self.style.SUCCESS(f"{len(nomes)} foto(s) {'voltariam' if simular else 'voltaram'} de cópias do repositório."))
        if not simular:
            from core.instagram import ErroInstagram, restaurar_fotos
            try:
                self.stdout.write(f"Instagram: {restaurar_fotos(limite=200)}.")
            except ErroInstagram as erro:
                self.stdout.write(self.style.WARNING(f"Instagram: {erro}"))

    def _exportacao(self, origem, caminho, simular):
        try:
            arquivos = arquivos_de_zip(caminho) if origem == "zip" else arquivos_de_pasta(caminho)
            contagem = {}
            for relativo, dados in arquivos:
                if simular:
                    antigo, motivo = Indice({ref.nome for ref in referencias()}).casar(relativo)
                    situacao = "restaurada" if antigo else motivo
                    self.stdout.write(f"  (simulação) {relativo}: {situacao}{' -> ' + antigo if antigo else ''}")
                else:
                    resultado = restaurar_arquivo(relativo, dados)
                    situacao = resultado.situacao
                    self.stdout.write(f"  {relativo}: {resultado.texto()}")
                contagem[situacao] = contagem.get(situacao, 0) + 1
        except (OSError, ValueError, zipfile.BadZipFile) as erro:
            raise CommandError(f"Não consegui ler {caminho}: {erro}")
        partes = [f"{n} {s.replace('_', ' ')}" for s, n in sorted(contagem.items())]
        self.stdout.write(self.style.SUCCESS("Arquivos: " + (", ".join(partes) or "nenhuma foto encontrada") + "."))

    def _relatorio(self):
        linhas = relatorio()
        for rotulo, pk, campo, nome, local in linhas:
            self.stdout.write(f"{rotulo}\t#{pk}\t{campo}\t{nome}" + ("\t(tem cópia no repositório: use --local)" if local else ""))
        stats = estatisticas()
        self.stdout.write(self.style.SUCCESS(
            f"Faltando: {len(linhas)} referência(s) ({stats['nomes_pendentes']} foto(s) diferentes). "
            f"No banco do site: {stats['no_banco']} arquivo(s), {stats['megabytes']} MB."))
