"""Entrar e cadastrar com o Google: o que a gestão precisa saber.

O botão só aparece no site quando GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET estão
nas variáveis da Vercel (ver artskala/settings.py). Aqui ficam o estado, o
endereço de retorno que vai no console do Google e a lista de clientes que
entraram por ele.
"""
from django.apps import apps
from django.conf import settings


def google_ativo():
    return bool(getattr(settings, "GOOGLE_LOGIN_ENABLED", False))


def endereco_de_retorno():
    """O "URI de redirecionamento autorizado" do console do Google."""
    return settings.SITE_URL.rstrip("/") + "/accounts/google/login/callback/"


def ids_com_google():
    """Ids dos usuários que têm conta Google ligada (vazio se o allauth não está ativo)."""
    if not apps.is_installed("allauth.socialaccount"):
        return set()
    from allauth.socialaccount.models import SocialAccount
    return set(SocialAccount.objects.filter(provider="google").values_list("user_id", flat=True))
