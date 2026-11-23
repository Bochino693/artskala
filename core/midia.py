"""Fotos guardadas no próprio banco do site (sem depender de serviço de fora).

Por que: as fotos ficavam no Cloudinary. Quando a conta de lá foi
desativada, todas as fotos sumiram do site e nenhum envio funcionava. Agora
cada foto enviada vai para a tabela ArquivoNoBanco (no mesmo PostgreSQL do
Supabase que guarda produtos e pedidos) e é servida pelo próprio site em
/midia/banco/..., com cache de um ano na Vercel. Se o site está no ar, as
fotos estão no ar.

- Nomes novos: "banco/" + o caminho original do envio, com o sufixo
  aleatório de sempre (ex.: banco/produtos/fachada_k3j9x2a.webp). O sufixo
  garante que um endereço nunca é reaproveitado, então o cache pode ser
  "imutável".
- Fotos grandes (mais de 2000 px ou de 600 KB) viram WebP de até 2000 px,
  em boa qualidade (e sem os dados de GPS do celular).
- Nomes antigos (sem "banco/") continuam apontando para o Cloudinary, só
  como legado: o comando espelhar_midia copia cada um para cá.
- url() não acessa a rede nem o banco: só monta o endereço.
"""
import hashlib
import logging
import mimetypes
import os
import re
from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import quote

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage
from django.db import DatabaseError, IntegrityError, models, transaction
from django.utils.crypto import get_random_string
from django.utils.deconstruct import deconstructible

logger = logging.getLogger(__name__)

PREFIXO = "banco/"
URL_BASE = "/midia/"                    # endereço público: /midia/banco/...
LADO_MAXIMO = 2000                      # px
LIMITE_SEM_MEXER = 600 * 1024           # até isso (e 2000 px) a foto fica como veio
QUALIDADE_WEBP = 82
TAMANHO_MAXIMO = 20 * 1024 * 1024       # recusa arquivos maiores que 20 MB
FORMATOS_WEB = {"JPEG", "PNG", "GIF", "WEBP"}

# Larguras/alturas aceitas em ?w= e ?h= (as que as telas usam e algumas a mais).
MEDIDAS = (64, 96, 104, 112, 120, 160, 200, 240, 320, 340, 400, 480, 540, 600,
           640, 720, 800, 900, 960, 1080, 1200, 1400, 1600, 2000)


class ErroMidia(Exception):
    """Falha ao guardar ou ler uma foto. A mensagem já é para a pessoa ler."""


def eh_do_banco(nome):
    return str(nome or "").startswith(PREFIXO)


def medida_permitida(valor):
    """A menor medida da lista que cobre o pedido (ou a maior de todas)."""
    valor = int(valor)
    for medida in MEDIDAS:
        if medida >= valor:
            return medida
    return MEDIDAS[-1]


def midia_no_banco_ativa():
    """True quando o armazenamento padrão do site é o banco (produção)."""
    padrao = (getattr(settings, "STORAGES", {}) or {}).get("default") or {}
    return str(padrao.get("BACKEND", "")).endswith(".MidiaNoBanco")


# ------------------------------------------------------------------ preparar
def preparar(dados, nome="arquivo"):
    """Recebe os bytes enviados e devolve (bytes, tipo, extensão nova ou None).

    Fotos dentro do limite ficam como vieram. As grandes (ou em formato que o
    navegador não mostra, como TIFF e BMP) viram WebP de até 2000 px. O que
    não é imagem é guardado como veio."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if len(dados) > TAMANHO_MAXIMO:
        raise ErroMidia(f"O arquivo tem {len(dados) / 1048576:.1f} MB; o máximo é {TAMANHO_MAXIMO // 1048576} MB.")
    if not dados:
        raise ErroMidia("O arquivo chegou vazio. Tente enviar de novo.")

    try:
        imagem = Image.open(BytesIO(dados))
        formato = imagem.format
    except UnidentifiedImageError:
        tipo = mimetypes.guess_type(nome)[0] or "application/octet-stream"
        return dados, tipo, None
    except Image.DecompressionBombError as erro:
        raise ErroMidia("A foto tem pixels demais para o site. Diminua o tamanho e envie de novo.") from erro
    except (OSError, ValueError) as erro:
        raise ErroMidia("A foto parece corrompida. Abra e salve de novo no celular ou computador.") from erro

    tipo_original = Image.MIME.get(formato or "", "application/octet-stream")
    largura, altura = imagem.size
    grande = max(largura, altura) > LADO_MAXIMO or len(dados) > LIMITE_SEM_MEXER
    if formato in FORMATOS_WEB and (not grande or getattr(imagem, "is_animated", False)):
        return dados, tipo_original, None

    try:
        if formato == "JPEG":
            imagem.draft(imagem.mode, (LADO_MAXIMO, LADO_MAXIMO))  # decodifica já reduzida (rápido)
        imagem = ImageOps.exif_transpose(imagem)
        transparente = imagem.mode in ("RGBA", "LA", "PA") or (imagem.mode == "P" and "transparency" in imagem.info)
        perfil_cor = imagem.info.get("icc_profile")
        imagem = imagem.convert("RGBA" if transparente else "RGB")
        imagem.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)
        saida = BytesIO()
        extras = {"icc_profile": perfil_cor} if perfil_cor else {}
        imagem.save(saida, "WEBP", quality=QUALIDADE_WEBP, method=4, **extras)
    except Image.DecompressionBombError as erro:
        raise ErroMidia("A foto tem pixels demais para o site. Diminua o tamanho e envie de novo.") from erro
    except (OSError, ValueError, SyntaxError) as erro:
        raise ErroMidia("A foto parece corrompida. Abra e salve de novo no celular ou computador.") from erro

    novo = saida.getvalue()
    if formato in FORMATOS_WEB and max(largura, altura) <= LADO_MAXIMO and len(novo) >= len(dados):
        return dados, tipo_original, None     # o original já era menor
    return novo, "image/webp", ".webp"


def trocar_extensao(nome, extensao):
    pasta, arquivo = os.path.split(nome)
    raiz = arquivo.split(".", 1)[0] if "." in arquivo else arquivo
    return os.path.join(pasta, raiz + extensao) if pasta else raiz + extensao


# ------------------------------------------------------------- gravar e ler
def _modelo(modelo=None):
    if modelo is not None:
        return modelo
    from .models import ArquivoNoBanco
    return ArquivoNoBanco


def gravar(nome, dados, tipo, modelo=None):
    """Grava os bytes com esse nome exato. Devolve True se criou, False se o
    nome já existia (nada muda). Falha de banco vira ErroMidia."""
    modelo = _modelo(modelo)
    try:
        with transaction.atomic():
            _arquivo, criado = modelo.objects.get_or_create(
                nome=nome,
                defaults={"conteudo": dados, "tipo": tipo[:100], "tamanho": len(dados),
                          "sha256": hashlib.sha256(dados).hexdigest()},
            )
        return criado
    except IntegrityError:
        return False                           # outro envio gravou o mesmo nome ao mesmo tempo
    except DatabaseError as erro:
        logger.exception("Não consegui gravar %s no banco", nome)
        raise ErroMidia("Não consegui guardar a foto agora (o banco de dados não respondeu). "
                        "Tente de novo em alguns instantes.") from erro


def ler(nome, modelo=None):
    modelo = _modelo(modelo)
    conteudo = modelo.objects.filter(nome=nome).values_list("conteudo", flat=True).first()
    if conteudo is None:
        raise FileNotFoundError(nome)
    return bytes(conteudo)


# ------------------------------------------------------------------- legado
def nuvem_cloudinary():
    """Nome da conta do Cloudinary (só para montar os endereços antigos)."""
    return getattr(settings, "MIDIA_CLOUDINARY_LEGADO", "") or ""


def url_cloudinary(nome, nuvem):
    """Mesmo endereço que o django-cloudinary-storage montava, sem rede."""
    prefixo = (getattr(settings, "MEDIA_URL", "/media/") or "").lstrip("/")
    if prefixo and not prefixo.endswith("/"):
        prefixo += "/"
    if prefixo and not nome.startswith(prefixo):
        nome = prefixo + nome
    versao = "" if re.match(r"^v\d+/", nome) or "/" not in nome else "v1/"
    return f"https://res.cloudinary.com/{nuvem}/image/upload/{versao}{quote(nome, safe='/:')}"


@deconstructible
class LegadoCloudinary:
    """Leitura das fotos antigas que ficaram no Cloudinary. Nada daqui roda
    ao montar uma página: só o comando de cópia (espelhar_midia) baixa."""

    tempo_limite = (5, 20)

    def __init__(self, nuvem):
        self.nuvem = nuvem

    def url(self, nome):
        return url_cloudinary(nome, self.nuvem)

    def baixar(self, nome):
        import requests
        return requests.get(self.url(nome), timeout=self.tempo_limite)

    def open(self, nome, mode="rb"):
        resposta = self.baixar(nome)
        if resposta.status_code != 200:
            raise FileNotFoundError(f"{nome}: Cloudinary respondeu {resposta.status_code}")
        return ContentFile(resposta.content, name=nome)

    def exists(self, nome):
        import requests
        try:
            return requests.head(self.url(nome), timeout=self.tempo_limite).status_code == 200
        except requests.RequestException:
            return False

    def size(self, nome):
        import requests
        try:
            resposta = requests.head(self.url(nome), timeout=self.tempo_limite)
        except requests.RequestException:
            return None
        return int(resposta.headers.get("content-length") or 0) if resposta.status_code == 200 else None

    def delete(self, nome):
        # O original no Cloudinary não é apagado daqui: fica como cópia de segurança.
        logger.info("Pedido para apagar %s (Cloudinary) ignorado.", nome)


def armazenamento_legado():
    nuvem = nuvem_cloudinary()
    if nuvem:
        return LegadoCloudinary(nuvem)
    return FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)


# ----------------------------------------------------------------- storage
@deconstructible
class MidiaNoBanco(Storage):
    """Armazenamento padrão do site em produção (settings.STORAGES)."""

    def __init__(self):
        self._legado = None

    @property
    def legado(self):
        if self._legado is None:
            self._legado = armazenamento_legado()
        return self._legado

    # envio -------------------------------------------------------------
    def save(self, name, content, max_length=None):
        if name is None:
            name = content.name
        if hasattr(content, "seek"):
            try:
                content.seek(0)
            except (OSError, ValueError):
                pass
        if hasattr(content, "chunks"):
            dados = b"".join(content.chunks())
        else:
            dados = content.read()
        dados, tipo, extensao = preparar(dados, name)
        if extensao:
            name = trocar_extensao(name, extensao)
        arquivo = ContentFile(dados, name=name)
        arquivo.tipo_midia = tipo
        return super().save(name, arquivo, max_length=max_length)

    def get_available_name(self, name, max_length=None):
        name = str(name).replace("\\", "/").lstrip("/")
        if not eh_do_banco(name):
            name = PREFIXO + name
        pasta, arquivo = os.path.split(name)
        extensao = "".join(PurePosixPath(arquivo).suffixes)
        raiz = arquivo[: len(arquivo) - len(extensao)] if extensao else arquivo
        # Sempre com sufixo: o mesmo endereço nunca é usado para outra foto.
        sufixo = "_" + get_random_string(7).lower()
        if max_length and len(name) + len(sufixo) > max_length:
            raiz = raiz[: max(1, len(raiz) - (len(name) + len(sufixo) - max_length))]
        return super().get_available_name(os.path.join(pasta, raiz + sufixo + extensao), max_length)

    def _save(self, name, content):
        dados = content.read() if not hasattr(content, "chunks") else b"".join(content.chunks())
        tipo = getattr(content, "tipo_midia", None) or mimetypes.guess_type(name)[0] or "application/octet-stream"
        for _tentativa in range(3):
            if gravar(name, dados, tipo):
                return name
            name = self.get_available_name(name)     # nome ocupado ao mesmo tempo: outro sufixo
        raise ErroMidia("Não consegui um nome livre para a foto. Tente de novo.")

    # leitura ------------------------------------------------------------
    def url(self, name):
        name = str(name or "")
        if eh_do_banco(name):
            return URL_BASE + quote(name, safe="/")
        return self.legado.url(name)

    def _open(self, name, mode="rb"):
        if eh_do_banco(name):
            return ContentFile(ler(name), name=name)
        return self.legado.open(name, mode)

    def exists(self, name):
        if eh_do_banco(name):
            from .models import ArquivoNoBanco
            return ArquivoNoBanco.objects.filter(nome=name).exists()
        return self.legado.exists(name)

    def size(self, name):
        if eh_do_banco(name):
            from .models import ArquivoNoBanco
            tamanho = ArquivoNoBanco.objects.filter(nome=name).values_list("tamanho", flat=True).first()
            if tamanho is None:
                raise FileNotFoundError(name)
            return tamanho
        return self.legado.size(name)

    def delete(self, name):
        if eh_do_banco(name):
            from .models import ArquivoNoBanco
            ArquivoNoBanco.objects.filter(nome=name).delete()
            return
        self.legado.delete(name)

    def listdir(self, path):
        from .models import ArquivoNoBanco
        path = str(path or "").rstrip("/")
        prefixo = path + "/" if path else ""
        pastas, arquivos = set(), []
        for nome in ArquivoNoBanco.objects.filter(nome__startswith=prefixo).values_list("nome", flat=True):
            resto = nome[len(prefixo):]
            if "/" in resto:
                pastas.add(resto.split("/", 1)[0])
            else:
                arquivos.append(resto)
        return sorted(pastas), sorted(arquivos)


# ------------------------------------------------------- variantes (?w=, ?h=)
def redimensionar(dados, largura=None, altura=None):
    """Versão menor da foto (WebP) para ?w= e ?h=. Sem os dois, ou se a foto
    já é menor, devolve None (serve o original). Com os dois, a foto é
    reduzida até cobrir a caixa largura x altura (o recorte é do CSS)."""
    from PIL import Image, ImageOps

    if not largura and not altura:
        return None
    try:
        imagem = Image.open(BytesIO(dados))
    except Exception:  # não é imagem: serve como está
        return None
    if getattr(imagem, "is_animated", False):
        return None
    w, h = imagem.size
    deitada = (imagem.getexif() or {}).get(0x0112, 1) in (5, 6, 7, 8)
    if deitada:
        w, h = h, w                                  # foto girada pelo EXIF
    escalas = []
    if largura:
        escalas.append(largura / w)
    if altura:
        escalas.append(altura / h)
    escala = max(escalas) if (largura and altura) else escalas[0]
    if escala >= 1:
        return None
    novo = (max(1, round(w * escala)), max(1, round(h * escala)))
    try:
        if imagem.format == "JPEG":
            imagem.draft(imagem.mode, (novo[1], novo[0]) if deitada else novo)
        imagem = ImageOps.exif_transpose(imagem)
        transparente = imagem.mode in ("RGBA", "LA", "PA") or (imagem.mode == "P" and "transparency" in imagem.info)
        perfil_cor = imagem.info.get("icc_profile")
        imagem = imagem.convert("RGBA" if transparente else "RGB").resize(novo, Image.LANCZOS)
        saida = BytesIO()
        extras = {"icc_profile": perfil_cor} if perfil_cor else {}
        imagem.save(saida, "WEBP", quality=80, method=4, **extras)
    except (OSError, ValueError, SyntaxError):
        logger.warning("Não consegui reduzir uma foto do banco; servindo o original.")
        return None
    return saida.getvalue()


# ------------------------------------------------- limpeza ao apagar uma foto
def campos_de_arquivo(registro=None):
    """(modelo, campo) de todo FileField/ImageField do site. `registro` pode
    ser o das migrações (modelos históricos)."""
    if registro is None:
        from django.apps import apps as registro
    for modelo in registro.get_models():
        meta = modelo._meta
        if meta.abstract or meta.proxy or not meta.managed:
            continue
        for campo in meta.concrete_fields:
            if isinstance(campo, models.FileField):
                yield modelo, campo


def em_uso(nome):
    return any(modelo._default_manager.filter(**{campo.attname: nome}).exists() for modelo, campo in campos_de_arquivo())


def apagar_se_ninguem_usa(nome):
    """Some com os bytes de uma foto do banco que nenhum registro usa mais
    (ex.: "apagar imagens" na gestão). Uma foto usada em dois lugares fica."""
    from .models import ArquivoNoBanco
    try:
        if eh_do_banco(nome) and not em_uso(nome):
            ArquivoNoBanco.objects.filter(nome=nome).delete()
    except DatabaseError:
        logger.warning("Não consegui apagar %s do banco (fica para depois).", nome)


def ao_apagar_registro(sender, instance, **kwargs):
    for campo in instance._meta.concrete_fields:
        if isinstance(campo, models.FileField):
            nome = str(getattr(instance, campo.attname) or "")
            if eh_do_banco(nome):
                # Depois do commit: se a exclusão for desfeita, a foto fica.
                transaction.on_commit(lambda nome=nome: apagar_se_ninguem_usa(nome))


def ligar_limpeza():
    from django.db.models.signals import post_delete

    for modelo in {modelo for modelo, _campo in campos_de_arquivo()}:
        post_delete.connect(ao_apagar_registro, sender=modelo, dispatch_uid=f"midia-limpeza-{modelo._meta.label}")
