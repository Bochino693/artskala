"""Traz de volta as fotos antigas (as que ainda apontam para o Cloudinary).

Toda foto com nome sem "banco/" é uma referência antiga. Ela volta a
aparecer quando os bytes dela são guardados no banco como "banco/<nome
antigo>" e o campo passa a apontar para esse nome. As fontes, da mais segura
para a menos:

1. Cópias que já estão no repositório do site (fotos da vitrine em
   core/vitrine/fotos, imagens de core/static e staticfiles, uma pasta media/
   do projeto). Só vale um arquivo que case sem dúvida com o nome antigo.
2. O próprio Instagram, para os posts trazidos pela API (core/instagram.py).
3. A exportação da Biblioteca de Mídia do Cloudinary que o dono baixou
   (Gestão > Restaurar fotos, ou `restaurar_midia --zip/--pasta`).
4. O Cloudinary, quando a conta voltar (comando espelhar_midia e o cron).

Nunca põe uma foto errada: se dois arquivos diferentes servem para o mesmo
nome (ou um arquivo serve para dois nomes diferentes), não faz nada e avisa.
Rodar de novo não duplica nada.
"""
import hashlib
import logging
import posixpath
import random
import re
import time
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.db import models

from .midia import (
    PREFIXO,
    ErroMidia,
    armazenamento_legado,
    campos_de_arquivo,
    eh_do_banco,
    gravar,
    midia_no_banco_ativa,
    nuvem_cloudinary,
    preparar,
    url_cloudinary,
)

logger = logging.getLogger(__name__)

SUFIXO_CLOUDINARY = re.compile(r"_[a-z0-9]{6}$")    # "use_filename" do Cloudinary
HASH_ESTATICO = re.compile(r"\.[0-9a-f]{12}$")      # collectstatic: logo.051e406bd07b.png
EXTENSOES_FOTO = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff"}
PASTAS_SEM_FOTO = {"__macosx"}


# ------------------------------------------------------------- referências
@dataclass
class Referencia:
    modelo: type
    campo: models.Field
    pk: int
    nome: str

    @property
    def rotulo(self):
        return f"{self.modelo._meta.app_label}.{self.modelo.__name__}"


def referencias(registro=None, pendentes=True):
    """Referências antigas (pendentes=True) ou já no banco (pendentes=False)."""
    for modelo, campo in campos_de_arquivo(registro):
        nome_campo = campo.attname
        consulta = modelo._default_manager.exclude(**{nome_campo: ""}).exclude(**{f"{nome_campo}__isnull": True})
        filtro = {f"{nome_campo}__startswith": PREFIXO}
        consulta = consulta.exclude(**filtro) if pendentes else consulta.filter(**filtro)
        for pk, nome in consulta.order_by("pk").values_list("pk", nome_campo):
            yield Referencia(modelo, campo, pk, str(nome))


def agrupar(refs):
    grupos = OrderedDict()
    for ref in refs:
        grupos.setdefault(ref.nome, []).append(ref)
    return grupos


# ---------------------------------------------------------------- nomes
def sem_extensao(caminho):
    caminho = PurePosixPath(caminho)
    sufixo = caminho.suffix
    if sufixo and len(sufixo) <= 6 and sufixo[1:].isalnum():
        return str(caminho.with_suffix(""))
    return str(caminho)


def chave(caminho):
    """Nome comparável: barras normais, sem extensão, sem "media/", minúsculo."""
    caminho = str(caminho or "").replace("\\", "/").strip()
    while caminho.startswith(("./", "/")):
        caminho = caminho[1:] if caminho.startswith("/") else caminho[2:]
    if caminho.startswith(PREFIXO):
        caminho = caminho[len(PREFIXO):]
    caminho = sem_extensao(caminho)
    if caminho.lower().startswith("media/"):
        caminho = caminho[len("media/"):]
    return caminho.casefold()


def base(chave_):
    return chave_.rsplit("/", 1)[-1]


def tronco(base_):
    return SUFIXO_CLOUDINARY.sub("", base_)


def nome_no_banco(antigo, limite=100):
    """"banco/<nome antigo>", encurtado (sempre do mesmo jeito) se não couber."""
    novo = PREFIXO + str(antigo).lstrip("/")
    if len(novo) <= limite:
        return novo
    marca = "-" + hashlib.sha1(str(antigo).encode()).hexdigest()[:8]
    raiz, extensao = posixpath.splitext(novo)
    if len(extensao) > 6:
        raiz, extensao = novo, ""
    return raiz[: limite - len(marca) - len(extensao)] + marca + extensao


class Indice:
    """Casa um arquivo (pelo caminho) com um nome antigo, sem adivinhar."""

    def __init__(self, nomes):
        self.por_chave, self.por_base = defaultdict(set), defaultdict(set)
        self.por_tronco, self.por_tronco_pasta = defaultdict(set), defaultdict(set)
        for nome in nomes:
            k = chave(nome)
            b = base(k)
            self.por_chave[k].add(nome)
            self.por_base[b].add(nome)
            t = tronco(b)
            if t != b and len(t) >= 3:
                self.por_tronco[t].add(nome)
                self.por_tronco_pasta[posixpath.join(posixpath.dirname(k), t)].add(nome)

    def casar(self, caminho):
        """Devolve (nome antigo ou None, motivo)."""
        k = chave(caminho)
        b = base(k)
        tentativas = [(self.por_chave, k), (self.por_base, b)]
        if "/" in k:
            tentativas.append((self.por_tronco_pasta, k))
        tentativas.append((self.por_tronco, b))
        for mapa, valor in tentativas:
            achados = mapa.get(valor)
            if achados:
                if len(achados) == 1:
                    return next(iter(achados)), "ok"
                return None, "ambigua"
        return None, "sem_referencia"


# ------------------------------------------------------------ gravar cópia
def guardar_copia(antigo, dados, refs, modelo_arquivo=None):
    """Guarda os bytes como banco/<antigo> e repõe todas as referências."""
    limite = min((ref.campo.max_length or 100) for ref in refs) if refs else 100
    novo = nome_no_banco(antigo, limite)
    dados, tipo, _extensao = preparar(dados, antigo)
    gravar(novo, dados, tipo, modelo=modelo_arquivo)
    repontar(antigo, novo, refs)
    return novo


def repontar(antigo, novo, refs):
    por_campo = defaultdict(list)
    for ref in refs:
        por_campo[(ref.modelo, ref.campo.attname)].append(ref.pk)
    total = 0
    for (modelo, nome_campo), pks in por_campo.items():
        total += modelo._default_manager.filter(pk__in=pks, **{nome_campo: antigo}).update(**{nome_campo: novo})
    return total


# --------------------------------------------- B) arquivo enviado pelo dono
@dataclass
class Resultado:
    situacao: str            # restaurada | ja_restaurada | sem_referencia | ambigua | erro
    caminho: str
    antigo: str = ""
    novo: str = ""
    referencias: int = 0
    mensagem: str = ""

    TEXTOS = {
        "restaurada": "restaurada",
        "ja_restaurada": "já estava restaurada",
        "sem_referencia": "nenhuma foto do site usa este arquivo",
        "ambigua": "serve para mais de uma foto: não usei para não trocar fotos",
        "erro": "erro",
    }

    def texto(self):
        texto = self.TEXTOS.get(self.situacao, self.situacao)
        if self.situacao == "restaurada":
            texto += f" ({self.referencias} lugar{'es' if self.referencias != 1 else ''})"
        return texto + (f": {self.mensagem}" if self.mensagem else "")

    def como_dict(self):
        return {"situacao": self.situacao, "caminho": self.caminho, "antigo": self.antigo, "novo": self.novo,
                "referencias": self.referencias, "texto": self.texto()}


def eh_foto(caminho):
    partes = [p.casefold() for p in PurePosixPath(str(caminho).replace("\\", "/")).parts]
    if any(p in PASTAS_SEM_FOTO or p.startswith("._") for p in partes):
        return False
    return PurePosixPath(partes[-1] if partes else "").suffix in EXTENSOES_FOTO


def restaurar_arquivo(caminho, dados, registro=None, modelo_arquivo=None):
    """Um arquivo da exportação do Cloudinary (ou de qualquer cópia): acha a
    foto do site que usa esse nome e a traz de volta."""
    pendentes = list(referencias(registro))
    antigo, motivo = Indice({ref.nome for ref in pendentes}).casar(caminho)
    if antigo is None:
        if motivo == "sem_referencia":
            feitas = {ref.nome[len(PREFIXO):] for ref in referencias(registro, pendentes=False)}
            if Indice(feitas).casar(caminho)[0]:
                return Resultado("ja_restaurada", caminho)
        return Resultado(motivo, caminho)
    refs = [ref for ref in pendentes if ref.nome == antigo]
    try:
        novo = guardar_copia(antigo, dados, refs, modelo_arquivo)
    except ErroMidia as erro:
        return Resultado("erro", caminho, antigo, mensagem=str(erro))
    return Resultado("restaurada", caminho, antigo, novo, len(refs))


def arquivos_de_pasta(pasta):
    pasta = Path(pasta)
    for arquivo in sorted(pasta.rglob("*")):
        relativo = arquivo.relative_to(pasta).as_posix()
        if arquivo.is_file() and eh_foto(relativo):
            yield relativo, arquivo.read_bytes()


def arquivos_de_zip(caminho_zip, maximo=25 * 1024 * 1024):
    import zipfile
    with zipfile.ZipFile(caminho_zip) as pacote:
        for info in pacote.infolist():
            if info.is_dir() or not eh_foto(info.filename) or ".." in PurePosixPath(info.filename).parts:
                continue
            if info.file_size > maximo:
                logger.warning("%s grande demais no ZIP, pulado.", info.filename)
                continue
            yield info.filename, pacote.read(info)


# ------------------------------------------------ A) cópias no repositório
@dataclass
class FontesLocais:
    exatos: dict = field(default_factory=dict)        # chave do caminho relativo -> Path
    troncos: dict = field(default_factory=dict)       # nome do arquivo -> {sha: Path}
    vitrine: dict = field(default_factory=dict)       # nome da foto da vitrine -> Path

    def casar(self, nome):
        """Path da cópia local que é, sem dúvida, a foto desse nome antigo."""
        k = chave(nome)
        if k in self.exatos:
            return self.exatos[k]
        b = base(k)
        t = tronco(b)
        if t.startswith("vitrine-") and t[len("vitrine-"):] in self.vitrine:
            return self.vitrine[t[len("vitrine-"):]]
        for candidato in dict.fromkeys((b, t)):
            if len(candidato) < 4:
                continue
            copias = self.troncos.get(candidato)
            if copias:
                return next(iter(copias.values())) if len(copias) == 1 else None   # duas fotos diferentes: não arrisca
        return None


def pastas_locais():
    raiz = Path(settings.BASE_DIR)
    pastas_media = [raiz / "media"]
    media_root = getattr(settings, "MEDIA_ROOT", None)
    if media_root and Path(media_root) not in pastas_media:
        pastas_media.append(Path(media_root))
    return pastas_media, [raiz / "core" / "static" / "images", raiz / "staticfiles" / "images"]


def fontes_locais():
    from .vitrine import PASTA_FOTOS

    fontes = FontesLocais()
    pastas_media, pastas_imagens = pastas_locais()

    def registrar_tronco(arquivo):
        nome = HASH_ESTATICO.sub("", sem_extensao(arquivo.name)).casefold()
        sha = hashlib.sha256(arquivo.read_bytes()).hexdigest()
        fontes.troncos.setdefault(nome, {})[sha] = arquivo

    for pasta in pastas_media:
        if pasta.is_dir():
            for arquivo in pasta.rglob("*"):
                if arquivo.is_file() and eh_foto(arquivo.name):
                    fontes.exatos.setdefault(chave(arquivo.relative_to(pasta).as_posix()), arquivo)
                    registrar_tronco(arquivo)
    for pasta in pastas_imagens:
        if pasta.is_dir():
            for arquivo in pasta.iterdir():
                if arquivo.is_file() and eh_foto(arquivo.name):
                    registrar_tronco(arquivo)
    if Path(PASTA_FOTOS).is_dir():
        for arquivo in Path(PASTA_FOTOS).iterdir():
            if arquivo.is_file() and eh_foto(arquivo.name):
                fontes.vitrine[sem_extensao(arquivo.name).casefold()] = arquivo
    return fontes


def restaurar_locais(registro=None, modelo_arquivo=None, simular=False):
    """Fotos antigas que têm cópia no repositório. Devolve a lista de nomes."""
    if not midia_no_banco_ativa():
        return []
    fontes = fontes_locais()
    feitas = []
    for antigo, refs in agrupar(referencias(registro)).items():
        origem = fontes.casar(antigo)
        if origem is None:
            continue
        if not simular:
            try:
                guardar_copia(antigo, origem.read_bytes(), refs, modelo_arquivo)
            except ErroMidia as erro:
                logger.warning("Não restaurei %s de %s: %s", antigo, origem, erro)
                continue
        feitas.append(antigo)
    return feitas


# ------------------------------------------------------ 4) cópia do Cloudinary
class CloudinaryFora(Exception):
    """O Cloudinary não está entregando nada (conta desativada, fora do ar)."""


def baixar_cloudinary(nome):
    import requests

    nuvem = nuvem_cloudinary()
    if not nuvem:
        raise CloudinaryFora("CLOUDINARY_CLOUD_NAME não está configurado")
    try:
        resposta = requests.get(url_cloudinary(nome, nuvem), timeout=(5, 20))
    except requests.RequestException as erro:
        raise CloudinaryFora(f"o Cloudinary não respondeu ({erro.__class__.__name__})") from erro
    motivo = resposta.headers.get("x-cld-error", "")
    if resposta.status_code == 200 and resposta.content:
        return resposta.content
    texto = ""
    if "text" in resposta.headers.get("content-type", "") or not resposta.content[:1]:
        texto = (resposta.text or "")[:300]
    if resposta.status_code == 401 or "disabled" in (motivo + texto).lower():
        raise CloudinaryFora(f"o Cloudinary respondeu {resposta.status_code} ({motivo or texto.strip() or 'conta desativada'})")
    if resposta.status_code >= 500 or resposta.status_code == 429:
        raise CloudinaryFora(f"o Cloudinary respondeu {resposta.status_code} (fora do ar)")
    raise FileNotFoundError(f"{resposta.status_code} {motivo}".strip())


@dataclass
class Resumo:
    copiadas: int = 0
    locais: int = 0
    do_cloudinary: int = 0
    faltando_no_cloudinary: list = field(default_factory=list)
    esperando: int = 0
    erros: list = field(default_factory=list)
    cloudinary_fora: str = ""
    tempo_esgotado: bool = False
    parado: str = ""
    restantes: int = 0

    def texto(self):
        if self.parado:
            return self.parado
        partes = [f"{self.copiadas} foto(s) copiada(s) para o banco"]
        if self.copiadas:
            partes[0] += f" ({self.locais} do repositório, {self.do_cloudinary} do Cloudinary)"
        if self.cloudinary_fora:
            partes.append(f"Cloudinary indisponível: {self.cloudinary_fora}; {self.esperando} foto(s) esperando a conta voltar")
        if self.faltando_no_cloudinary:
            partes.append(f"{len(self.faltando_no_cloudinary)} não existem mais no Cloudinary")
        if self.erros:
            partes.append(f"{len(self.erros)} com erro")
        if self.tempo_esgotado:
            partes.append("o tempo desta rodada acabou (o resto vai na próxima)")
        partes.append(f"faltam {self.restantes}")
        return "; ".join(partes) + "."

    def como_dict(self):
        return {"copiadas": self.copiadas, "locais": self.locais, "do_cloudinary": self.do_cloudinary,
                "esperando": self.esperando, "faltando_no_cloudinary": self.faltando_no_cloudinary[:50],
                "erros": [f"{n}: {e}" for n, e in self.erros[:50]], "cloudinary_fora": self.cloudinary_fora,
                "tempo_esgotado": self.tempo_esgotado, "restantes": self.restantes, "resumo": self.texto()}


def espelhar(limite=None, segundos=None, aleatorio=False, simular=False, registro=None, aviso=None):
    """Copia para o banco as fotos antigas: do repositório quando há cópia
    local, senão do Cloudinary (ou da pasta media/ no computador de
    desenvolvimento). Para de tentar o Cloudinary no primeiro sinal de conta
    desativada ou fora do ar. `limite` conta fotos copiadas; `segundos` é o
    tempo máximo da rodada (o cron usa os dois)."""
    resumo = Resumo()
    if not midia_no_banco_ativa():
        resumo.parado = ("O site não está guardando fotos no banco (STORAGES padrão não é MidiaNoBanco): "
                         "nada a copiar. Em produção isso é automático; no computador use MIDIA_NO_BANCO=1.")
        return resumo
    inicio = time.monotonic()
    legado = armazenamento_legado()
    local_pasta = not nuvem_cloudinary()
    fontes = fontes_locais()
    grupos = list(agrupar(referencias(registro)).items())
    if aleatorio:
        random.shuffle(grupos)      # um nome que sempre falha não trava a fila

    feitos = set()
    for antigo, refs in grupos:
        if limite and resumo.copiadas >= limite:
            break
        if segundos and time.monotonic() - inicio > segundos:
            resumo.tempo_esgotado = True
            break
        origem = fontes.casar(antigo)
        fonte = "local"
        try:
            if origem is not None:
                dados = origem.read_bytes()
            elif local_pasta:
                # Sem o nome da conta do Cloudinary: só a pasta media/ (computador de desenvolvimento).
                if not legado.exists(antigo):
                    resumo.cloudinary_fora = "CLOUDINARY_CLOUD_NAME não configurado (sem o endereço das fotos antigas)"
                    resumo.esperando += 1
                    continue
                with legado.open(antigo) as arquivo:
                    dados = arquivo.read()
            elif resumo.cloudinary_fora:
                resumo.esperando += 1
                continue
            else:
                fonte = "cloudinary"
                dados = baixar_cloudinary(antigo)
        except CloudinaryFora as erro:
            resumo.cloudinary_fora = str(erro)
            resumo.esperando += 1
            if aviso:
                aviso(f"Cloudinary indisponível ({erro}). Sigo só com as cópias do repositório.")
            continue
        except FileNotFoundError:
            resumo.faltando_no_cloudinary.append(antigo)
            continue
        except OSError as erro:
            resumo.erros.append((antigo, str(erro)))
            continue
        if not simular:
            try:
                guardar_copia(antigo, dados, refs)
            except ErroMidia as erro:
                resumo.erros.append((antigo, str(erro)))
                continue
        feitos.add(antigo)
        resumo.copiadas += 1
        if fonte == "local":
            resumo.locais += 1
        else:
            resumo.do_cloudinary += 1
        if aviso:
            aviso(f"  {'(simulação) ' if simular else ''}{antigo} -> {nome_no_banco(antigo)} [{fonte}]")

    resumo.restantes = len([nome for nome, _refs in grupos if nome not in feitos])
    return resumo


# ------------------------------------------------------------------ relatório
def relatorio(registro=None):
    """[(rótulo do modelo, pk, campo, nome, tem cópia local?)] do que falta."""
    fontes = fontes_locais()
    return [(ref.rotulo, ref.pk, ref.campo.name, ref.nome, fontes.casar(ref.nome) is not None)
            for ref in referencias(registro)]


def estatisticas():
    from django.db.models import Count, Sum

    from .models import ArquivoNoBanco
    totais = ArquivoNoBanco.objects.aggregate(quantos=Count("id"), bytes=Sum("tamanho"))
    pendentes = list(referencias())
    return {
        "no_banco": totais["quantos"] or 0,
        "megabytes": round((totais["bytes"] or 0) / 1048576, 1),
        "pendentes": len(pendentes),
        "nomes_pendentes": len({ref.nome for ref in pendentes}),
    }
