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


class ErroDeMidiaMiddleware:
    """Rede de segurança dos envios: se guardar ou ler uma foto falhar
    (core.midia.ErroMidia), a pessoa vê uma mensagem clara em vez do erro 500.
    Num envio de formulário volta para a mesma tela com o aviso; num pedido do
    navegador (fetch) responde JSON."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        from .midia import ErroMidia

        if not isinstance(exception, ErroMidia):
            return None
        import logging

        from django.contrib import messages
        from django.http import HttpResponse, JsonResponse
        from django.shortcuts import redirect

        logging.getLogger("core.midia").warning("Envio de foto recusado em %s: %s", request.path, exception)
        mensagem = f"A foto não foi salva: {exception}"
        quer_json = (request.headers.get("x-requested-with") == "XMLHttpRequest"
                     or "application/json" in request.headers.get("Accept", ""))
        if quer_json:
            return JsonResponse({"ok": False, "erro": mensagem}, status=503)
        if request.method == "POST":
            messages.error(request, mensagem)
            return redirect(request.get_full_path())
        resposta = HttpResponse(mensagem, status=503, content_type="text/plain; charset=utf-8")
        resposta["Cache-Control"] = "no-store"
        return resposta
