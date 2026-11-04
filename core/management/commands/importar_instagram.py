"""Importa as fotos do Instagram da ArtSkala para o site.

Usa a EXPORTAÇÃO OFICIAL que o próprio Instagram gera para o dono da conta
(nada de raspar o site do Instagram):

  Instagram > Configurações > Central de Contas > Suas informações e
  permissões > Baixar suas informações > Baixar ou transferir informações >
  conta @artskalaa > Algumas das suas informações > "Conteúdo" (publicações)
  > Baixar no dispositivo > Formato: JSON > Qualidade da mídia: Alta.

O Instagram manda um link por e-mail com um ZIP. Depois:

  python manage.py importar_instagram caminho/do/instagram.zip --simular
  python manage.py importar_instagram caminho/do/instagram.zip

Cada publicação vira um Projeto (portfólio) com as fotos dela; a legenda vira
o título (primeira linha) e a descrição. Rodar de novo não duplica: uma
publicação já importada (mesmo título e data) é pulada.

Com --tipo produto --categoria "Fachadas" as publicações viram produtos
(preço R$ 0,00 aparece no site como "Sob consulta").
"""
import json
import re
import zipfile
from datetime import date, datetime
from pathlib import Path, PurePosixPath

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import CategoriaProdutos, ImagemProduto, ImagemProjeto, Produto, Projeto

EXTENSOES_FOTO = {".jpg", ".jpeg", ".png", ".webp"}
TAMANHO_MAXIMO = 15 * 1024 * 1024  # 15 MB por foto


def corrigir_texto(texto):
    """O JSON do Instagram vem com acentos "quebrados" (UTF-8 lido como
    Latin-1: "fachada nova ğŸ”¥" em vez de "fachada nova 🔥")."""
    texto = texto or ""
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


def titulo_da_legenda(legenda, limite):
    """Primeira linha útil da legenda, sem hashtags, menções e emojis soltos."""
    for linha in legenda.splitlines():
        linha = re.sub(r"[#@]\S+", "", linha)
        linha = re.sub(r"[^\w\s.,;:!?()&/+%ºª°'\"-]", "", linha).strip(" -–—.,;:")
        linha = re.sub(r"\s{2,}", " ", linha)
        if len(linha) >= 3:
            return linha[:limite].rstrip()
    return ""


class Exportacao:
    """Lê a exportação (ZIP ou pasta já extraída) do mesmo jeito."""

    def __init__(self, caminho):
        self.caminho = Path(caminho)
        if not self.caminho.exists():
            raise CommandError(f"Não encontrei {self.caminho}.")
        self.zip = zipfile.ZipFile(self.caminho) if self.caminho.is_file() else None
        if self.zip is None and not self.caminho.is_dir():
            raise CommandError("Informe o ZIP da exportação ou a pasta extraída.")

    def nomes(self):
        if self.zip:
            return [n for n in self.zip.namelist() if not n.endswith("/")]
        return [p.relative_to(self.caminho).as_posix() for p in self.caminho.rglob("*") if p.is_file()]

    def ler(self, nome):
        nome = str(PurePosixPath(nome))
        if ".." in PurePosixPath(nome).parts:
            raise CommandError(f"Caminho inválido na exportação: {nome}")
        if self.zip:
            info = self.zip.getinfo(nome)
            if info.file_size > TAMANHO_MAXIMO:
                return None
            return self.zip.read(info)
        arquivo = self.caminho / nome
        if arquivo.stat().st_size > TAMANHO_MAXIMO:
            return None
        return arquivo.read_bytes()

    def existe(self, nome):
        if self.zip:
            try:
                self.zip.getinfo(nome)
                return True
            except KeyError:
                return False
        return (self.caminho / nome).is_file()

    def publicacoes(self):
        """Lista de publicações: [{"legenda", "data", "fotos": [caminhos]}]."""
        arquivos = sorted(
            n for n in self.nomes()
            if re.search(r"(^|/)posts_\d+\.json$", n) and "/content/" in "/" + n
        )
        if not arquivos:
            raise CommandError(
                "Não achei content/posts_1.json. Confira se a exportação foi pedida em "
                "formato JSON e com \"Conteúdo\" (publicações) marcado."
            )
        # As fotos ficam relativas à raiz da exportação (às vezes dentro de uma pasta).
        raizes = {""}
        for arquivo in arquivos:
            partes = PurePosixPath(arquivo).parts
            if "content" in partes:
                indice = partes.index("content")
                raizes.add("/".join(partes[:max(0, indice - 1)]))
                raizes.add("/".join(partes[:indice]))

        resultado = []
        for arquivo in arquivos:
            dados = json.loads(self.ler(arquivo).decode("utf-8"))
            if isinstance(dados, dict):
                dados = dados.get("ig_posts") or dados.get("posts") or []
            for post in dados:
                midias = post.get("media") or []
                legenda = corrigir_texto(post.get("title") or (midias[0].get("title") if midias else ""))
                carimbo = post.get("creation_timestamp") or (midias[0].get("creation_timestamp") if midias else None)
                fotos = []
                for midia in midias:
                    uri = (midia.get("uri") or "").lstrip("/")
                    if PurePosixPath(uri).suffix.lower() not in EXTENSOES_FOTO:
                        continue
                    for raiz in sorted(raizes, key=len, reverse=True):
                        candidato = f"{raiz}/{uri}" if raiz else uri
                        if self.existe(candidato):
                            fotos.append(candidato)
                            break
                quando = None
                if carimbo:
                    quando = timezone.localtime(datetime.fromtimestamp(int(carimbo), tz=timezone.get_current_timezone())).date()
                resultado.append({"legenda": legenda.strip(), "data": quando, "fotos": fotos})
        return resultado


class Command(BaseCommand):
    help = "Importa publicações da exportação oficial do Instagram como projetos (ou produtos) com fotos."

    def add_arguments(self, parser):
        parser.add_argument("exportacao", help="ZIP baixado do Instagram ou a pasta extraída.")
        parser.add_argument("--tipo", choices=["projeto", "produto"], default="projeto",
                            help="O que criar para cada publicação (padrão: projeto).")
        parser.add_argument("--categoria", default="",
                            help='Categoria dos produtos (obrigatória com --tipo produto). Ex.: "Fachadas".')
        parser.add_argument("--desde", default="", help="Só publicações a partir desta data (AAAA-MM-DD).")
        parser.add_argument("--limite", type=int, default=0, help="Importar no máximo N publicações.")
        parser.add_argument("--rascunho", action="store_true",
                            help="Cria desativado, para revisar na gestão antes de aparecer no site.")
        parser.add_argument("--simular", action="store_true", help="Só mostra o que seria importado.")

    def handle(self, *args, **opcoes):
        exportacao = Exportacao(opcoes["exportacao"])
        desde = None
        if opcoes["desde"]:
            try:
                desde = date.fromisoformat(opcoes["desde"])
            except ValueError:
                raise CommandError("Use --desde no formato AAAA-MM-DD.")

        categoria = None
        if opcoes["tipo"] == "produto":
            if not opcoes["categoria"].strip():
                raise CommandError('Com --tipo produto informe --categoria "Nome da categoria".')
            if not opcoes["simular"]:
                categoria, _ = CategoriaProdutos.objects.get_or_create(nome_categoria=opcoes["categoria"].strip())

        publicacoes = [p for p in exportacao.publicacoes() if p["fotos"]]
        publicacoes.sort(key=lambda p: p["data"] or date.min, reverse=True)
        if desde:
            publicacoes = [p for p in publicacoes if p["data"] and p["data"] >= desde]
        if opcoes["limite"] > 0:
            publicacoes = publicacoes[:opcoes["limite"]]

        criados = pulados = fotos_total = 0
        for numero, post in enumerate(publicacoes, start=1):
            limite = 150 if opcoes["tipo"] == "produto" else 200
            titulo = titulo_da_legenda(post["legenda"], limite)
            if not titulo:
                titulo = f"Projeto ArtSkala {post['data'].strftime('%d/%m/%Y')}" if post["data"] else f"Projeto ArtSkala {numero}"

            if opcoes["tipo"] == "produto":
                ja_existe = Produto.objects.filter(nome_produto=titulo).exists()
            else:
                ja_existe = Projeto.objects.filter(titulo=titulo, data_execucao=post["data"]).exists()
            if ja_existe:
                pulados += 1
                self.stdout.write(f"  já importado: {titulo}")
                continue

            self.stdout.write(f"  {'(simulação) ' if opcoes['simular'] else ''}{titulo} — {len(post['fotos'])} foto(s)")
            if opcoes["simular"]:
                criados += 1
                fotos_total += len(post["fotos"])
                continue

            with transaction.atomic():
                if opcoes["tipo"] == "produto":
                    objeto = Produto.objects.create(
                        categoria=categoria, nome_produto=titulo, descricao_produto=post["legenda"][:500],
                        ativo=not opcoes["rascunho"],
                    )
                else:
                    objeto = Projeto.objects.create(
                        titulo=titulo, descricao=post["legenda"], data_execucao=post["data"],
                        ativo=not opcoes["rascunho"],
                    )
                for indice, foto in enumerate(post["fotos"], start=1):
                    conteudo = exportacao.ler(foto)
                    if not conteudo:
                        self.stdout.write(self.style.WARNING(f"    foto grande demais, pulada: {foto}"))
                        continue
                    nome = f"instagram-{objeto.pk}-{indice}{PurePosixPath(foto).suffix.lower()}"
                    if opcoes["tipo"] == "produto":
                        ImagemProduto.objects.create(produto=objeto, imagem=ContentFile(conteudo, name=nome))
                    else:
                        ImagemProjeto.objects.create(projeto=objeto, imagem=ContentFile(conteudo, name=nome))
                    fotos_total += 1
            criados += 1

        verbo = "seriam criados" if opcoes["simular"] else "criados"
        rotulo = "produtos" if opcoes["tipo"] == "produto" else "projetos"
        self.stdout.write(self.style.SUCCESS(
            f"{criados} {rotulo} {verbo} com {fotos_total} foto(s); {pulados} já existiam."
        ))
        if opcoes["rascunho"] and not opcoes["simular"] and criados:
            self.stdout.write("Eles estão desativados: revise na gestão e marque como ativos para aparecerem no site.")
