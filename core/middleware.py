from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils.cache import patch_cache_control


class InternalDomainMiddleware:
    """Entrada do painel por host exato; autorização continua nas views."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.is_interno = request.get_host().split(":", 1)[0].lower() == settings.INTERNAL_HOST
        if request.is_interno and request.path == "/" and request.method in ("GET", "HEAD"):
            response = HttpResponseRedirect("/gestao/")
        else:
            response = self.get_response(request)
        if request.path.startswith("/gestao/") or request.is_interno:
            patch_cache_control(response, private=True, no_store=True)
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response
