from django.conf import settings
from django.utils.cache import patch_cache_control

ROTAS_PRIVADAS = ("/interno/", "/gestao/")


class InternalDomainMiddleware:
    """A gestão fica em /interno/ no próprio site (sem depender de subdomínio).
    Se o subdomínio interno for apontado um dia, ele abre as mesmas telas sem o
    prefixo. Páginas internas nunca vão para cache nem para o Google."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.is_interno = request.get_host().split(':', 1)[0].lower() in settings.INTERNAL_HOSTS
        if request.is_interno:
            request.urlconf = 'core.urls_interno'
        response = self.get_response(request)
        if request.is_interno or request.path.startswith(ROTAS_PRIVADAS):
            patch_cache_control(response, private=True, no_store=True)
            response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
