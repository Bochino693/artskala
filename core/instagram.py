"""Traz os posts do @artskalaa pela API oficial do Instagram.

Usa a "Instagram API com login do Instagram" (conta profissional: Empresa ou
Criador de conteúdo). O token de longa duração vale 60 dias; aqui ele é
renovado sozinho quando faltam menos de 15 dias, e o novo fica salvo no banco
(ConfigInstagram), então a variável INSTAGRAM_TOKEN só precisa ser colada
uma vez.

A foto de cada post é copiada para o nosso armazenamento (Cloudinary em
produção): os links de mídia do Instagram expiram, e a cópia sai nítida no
tamanho certo. Vídeos (Reels) entram pela capa.
"""
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.dateparse import parse_datetime

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
        if not post.imagem and url_foto:
            try:
                post.imagem.save(f"ig-{post.instagram_id}.jpg", ContentFile(_baixar(url_foto)), save=False)
            except (ErroInstagram, requests.RequestException) as erro:
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


def registrar_erro(erro):
    config = configuracao()
    config.ultima_sincronizacao = timezone.now()
    config.ultimo_resultado = f"Erro: {erro}"
    config.save(update_fields=["ultima_sincronizacao", "ultimo_resultado"])
