from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils.cache import patch_cache_control

class InternalDomainMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.is_interno = request.get_host().split(':', 1)[0].lower() == settings.INTERNAL_HOST
        if request.is_interno:
            request.urlconf = 'core.urls_interno'
        if not request.is_interno and settings.INTERNAL_SITE_ENABLED and request.path.startswith('/gestao/'):
            response = HttpResponseRedirect('https://' + settings.INTERNAL_HOST + request.get_full_path()[len('/gestao'):])
            response.status_code = 307
        else:
            response = self.get_response(request)
        if request.path.startswith('/gestao/') or request.is_interno:
            patch_cache_control(response, private=True, no_store=True)
            response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
