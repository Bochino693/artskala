"""Endpoint que o agendador (cron) da Vercel chama para trazer os posts novos."""
import hmac

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .instagram import ErroInstagram, registrar_erro, sincronizar


def _autorizado(request):
    # A Vercel manda "Authorization: Bearer <CRON_SECRET>"; a equipe logada também pode chamar.
    segredo = getattr(settings, "CRON_SECRET", "")
    cabecalho = request.headers.get("Authorization", "")
    if segredo and hmac.compare_digest(cabecalho, f"Bearer {segredo}"):
        return True
    return request.user.is_authenticated and request.user.is_superuser


@never_cache
@require_GET
def sincronizar_instagram(request):
    if not _autorizado(request):
        return JsonResponse({"ok": False, "erro": "não autorizado"}, status=403)
    try:
        resumo = sincronizar()
    except ErroInstagram as erro:
        registrar_erro(erro)
        return JsonResponse({"ok": False, "erro": str(erro)}, status=502)
    return JsonResponse({"ok": True, "resumo": resumo})
