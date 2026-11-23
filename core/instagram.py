"""Traz os posts do @artskalaa pela API oficial do Instagram.

Usa a "Instagram API com login do Instagram" (conta profissional: Empresa ou
Criador de conteúdo). O token de longa duração vale 60 dias; aqui ele é
renovado sozinho quando faltam menos de 15 dias, e o novo fica salvo no banco
(ConfigInstagram), então a variável INSTAGRAM_TOKEN só precisa ser colada
uma vez.

A foto de cada post é copiada para o nosso armazenamento (o próprio banco do
site em produção, core/midia.py): os links de mídia do Instagram expiram, e a
cópia sai nítida no tamanho certo. Vídeos (Reels) entram pela capa.

Fotos de posts que ficaram presas no Cloudinary (conta desativada) são
baixadas de novo do próprio Instagram: na busca diária (posts recentes) e em
restaurar_fotos() (qualquer post trazido pela API, pelo id).
"""
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .midia import ErroMidia, eh_do_banco, midia_no_banco_ativa
from .models import ConfigInstagram, PostInstagram

logger = logging.getLogger(__name__)

API = "https://graph.instagram.com"
CAMPOS = "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count"
TEMPO_LIMITE = 20  # segundos por requisição
RENOVAR_COM_DIAS = 15


class ErroInstagram(Exception):
    pass


def configuracao():
    config = ConfigInstagram.objects.order_by("pk").first()
    if config is None:
        config = ConfigInstagram.objects.create(token=getattr(settings, "INSTAGRAM_TOKEN", ""))
    elif not config.token and getattr(settings, "INSTAGRAM_TOKEN", ""):
        config.token = settings.INSTAGRAM_TOKEN
        config.save(update_fields=["token"])
    return config


def _get(caminho, **params):
    try:
        resposta = requests.get(f"{API}/{caminho}", params=params, timeout=TEMPO_LIMITE)
    except requests.RequestException as erro:
        raise ErroInstagram(f"Sem resposta do Instagram ({erro.__class__.__name__}).") from erro
    dados = {}
    try:
        dados = resposta.json()
    except ValueError:
        pass
    if resposta.status_code != 200:
        mensagem = (dados.get("error") or {}).get("message") if isinstance(dados, dict) else ""
        raise ErroInstagram(f"Instagram respondeu {resposta.status_code}: {mensagem or 'erro desconhecido'}")
    return dados


def renovar_token(config, forcar=False):
    """Renova o token de 60 dias quando está perto de vencer."""
    agora = timezone.now()
    if not forcar and config.expira_em and config.expira_em - agora > timedelta(days=RENOVAR_COM_DIAS):
        return False
    dados = _get("refresh_access_token", grant_type="ig_refresh_token", access_token=config.token)
    config.token = dados.get("access_token") or config.token
    config.expira_em = agora + timedelta(seconds=int(dados.get("expires_in") or 60 * 86400))
    config.save(update_fields=["token", "expira_em"])
    return True


def _baixar(url):
    resposta = requests.get(url, timeout=TEMPO_LIMITE)
    if resposta.status_code != 200 or not resposta.content:
        raise ErroInstagram(f"Não consegui baixar a foto ({resposta.status_code}).")
    return resposta.content


def precisa_foto(post):
    """Sem foto, ou (em produção) com a foto antiga que ficou no Cloudinary."""
    nome = post.imagem.name if post.imagem else ""
    return not nome or (midia_no_banco_ativa() and not eh_do_banco(nome))


def _guardar_foto(post, url_foto):
    post.imagem.save(f"ig-{post.instagram_id}.jpg", ContentFile(_baixar(url_foto)), save=False)


def sincronizar(limite=18):
    """Busca os posts mais recentes e grava os novos. Devolve um resumo em texto."""
    config = configuracao()
    if not config.token:
        raise ErroInstagram("Falta o token: crie a variável INSTAGRAM_TOKEN na Vercel (veja LEIA-ME-SITE-V3.txt).")

    try:
        renovar_token(config)
    except ErroInstagram as erro:
        # Um token ainda válido continua servindo; o erro fica registrado.
        logger.warning("Não renovei o token do Instagram: %s", erro)

    dados = _get("me/media", fields=CAMPOS, limit=min(max(limite, 1), 50), access_token=config.token)
    novos = atualizados = sem_foto = 0
    for item in dados.get("data", []):
        tipo = item.get("media_type") or "IMAGE"
        url_foto = item.get("thumbnail_url") if tipo == "VIDEO" else item.get("media_url")
        post, criado = PostInstagram.objects.get_or_create(
            instagram_id=str(item["id"]),
            defaults={"link": item.get("permalink") or "https://www.instagram.com/artskalaa/"},
        )
        post.tipo = tipo
        post.legenda = item.get("caption") or ""
        post.link = item.get("permalink") or post.link
        post.publicado_em = parse_datetime(item.get("timestamp") or "") or post.publicado_em
        post.curtidas = item.get("like_count")
        post.comentarios = item.get("comments_count")
        if url_foto and precisa_foto(post):
            try:
                _guardar_foto(post, url_foto)
            except (ErroInstagram, ErroMidia, requests.RequestException) as erro:
                logger.warning("Post %s sem foto: %s", post.instagram_id, erro)
                sem_foto += 1
        post.save()
        if criado:
            novos += 1
        else:
            atualizados += 1

    resumo = f"{novos} novo(s), {atualizados} atualizado(s)" + (f", {sem_foto} sem foto" if sem_foto else "")
    config.ultima_sincronizacao = timezone.now()
    config.ultimo_resultado = resumo
    config.save(update_fields=["ultima_sincronizacao", "ultimo_resultado"])
    return resumo


def restaurar_fotos(limite=30, segundos=None):
    """Baixa de novo, pelo id, a foto dos posts trazidos pela API que ficou no
    Cloudinary (ou que nunca veio). Posts manuais não têm como: esses voltam
    pela tela Restaurar fotos. Devolve um resumo em texto."""
    import time

    if not midia_no_banco_ativa():
        return "nada a fazer (as fotos não estão no banco neste ambiente)"
    alvos = [post for post in PostInstagram.objects.exclude(instagram_id__startswith="manual-").order_by("-publicado_em", "-id")
             if precisa_foto(post)]
    if not alvos:
        return "nenhuma foto do Instagram faltando"
    config = configuracao()
    if not config.token:
        raise ErroInstagram(f"{len(alvos)} foto(s) de posts esperando, mas falta o token do Instagram (Gestão > Instagram).")
    inicio, trazidas, falhas, seguidas = time.monotonic(), 0, 0, 0
    for post in alvos[:limite]:
        if segundos and time.monotonic() - inicio > segundos:
            break
        try:
            dados = _get(post.instagram_id, fields="media_type,media_url,thumbnail_url", access_token=config.token)
            url_foto = dados.get("thumbnail_url") if dados.get("media_type") == "VIDEO" else dados.get("media_url")
            if not url_foto:
                raise ErroInstagram("o post não tem foto")
            _guardar_foto(post, url_foto)
            post.save(update_fields=["imagem", "modificado"])
        except (ErroInstagram, ErroMidia, requests.RequestException) as erro:
            logger.warning("Foto do post %s não voltou: %s", post.instagram_id, erro)
            falhas += 1
            seguidas += 1
            if seguidas >= 3:          # token vencido ou API fora: tenta outro dia
                break
            continue
        trazidas += 1
        seguidas = 0
    faltam = len(alvos) - trazidas
    return f"{trazidas} foto(s) trazida(s) de novo do Instagram" + (f", {falhas} com erro" if falhas else "") + \
        (f", faltam {faltam}" if faltam else "")


def registrar_erro(erro):
    config = configuracao()
    config.ultima_sincronizacao = timezone.now()
    config.ultimo_resultado = f"Erro: {erro}"
    config.save(update_fields=["ultima_sincronizacao", "ultimo_resultado"])
