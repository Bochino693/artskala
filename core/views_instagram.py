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
    if request.user.is_authenticated and request.user.is_superuser:
        return True
    # Sem CRON_SECRET configurado, aceita o agendador da Vercel no máximo uma
    # vez por hora (a busca só lê o Instagram e não duplica nada).
    if not segredo and request.headers.get("User-Agent", "").startswith("vercel-cron"):
        from datetime import timedelta
        from django.utils import timezone
        from .instagram import configuracao
        ultima = configuracao().ultima_sincronizacao
        return ultima is None or timezone.now() - ultima > timedelta(minutes=55)
    return False


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


# ============================================================
# GESTÃO > INSTAGRAM
# ============================================================
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from .instagram import configuracao
from .models import PostInstagram
from .views import SuperuserGestaoRequiredMixin


def _numero(valor):
    try:
        return max(0, int(str(valor).strip()))
    except (TypeError, ValueError):
        return None


class GestaoInstagramView(SuperuserGestaoRequiredMixin, View):
    """Conectar o Instagram (colar o token), buscar posts na hora e cuidar do
    bloco "Acompanhe no Instagram" da home, sem precisar mexer na Vercel."""

    template_name = "gestao/instagram.html"

    def get(self, request):
        config = configuracao()
        posts = PostInstagram.objects.order_by("-publicado_em", "-id")[:30]
        return render(request, self.template_name, {
            "secao_ativa": "instagram",
            "config": config,
            "token_final": config.token[-4:] if config.token else "",
            "posts": posts,
            "no_site": PostInstagram.objects.filter(ativo=True).exclude(imagem="").exclude(imagem__isnull=True).count(),
        })

    def post(self, request):
        acao = request.POST.get("acao", "")
        if acao == "token":
            token = request.POST.get("token", "").strip()
            if len(token) < 20:
                messages.error(request, "Cole o token inteiro gerado no painel da Meta.")
                return redirect("gestao_instagram")
            config = configuracao()
            config.token, config.expira_em = token, None
            config.save(update_fields=["token", "expira_em"])
            acao = "sincronizar"   # já busca os posts com o token novo

        if acao == "sincronizar":
            try:
                messages.success(request, "Instagram: " + sincronizar() + ".")
            except ErroInstagram as erro:
                registrar_erro(erro)
                messages.error(request, f"Instagram: {erro}")

        elif acao == "manual":
            link = request.POST.get("link", "").strip()
            foto = request.FILES.get("imagem")
            if not link.startswith(("https://www.instagram.com/", "https://instagram.com/")):
                messages.error(request, "Cole o link do post (começa com https://www.instagram.com/).")
            elif not foto:
                messages.error(request, "Envie a foto do post.")
            else:
                PostInstagram.objects.create(
                    link=link, imagem=foto, legenda=request.POST.get("legenda", "").strip(),
                    curtidas=_numero(request.POST.get("curtidas")), comentarios=_numero(request.POST.get("comentarios")),
                    tipo=request.POST.get("tipo") if request.POST.get("tipo") in {"IMAGE", "VIDEO", "CAROUSEL_ALBUM"} else "IMAGE",
                    publicado_em=timezone.now(),
                )
                messages.success(request, "Post adicionado ao bloco do Instagram.")

        elif acao == "alternar":
            post = get_object_or_404(PostInstagram, pk=request.POST.get("post"))
            post.ativo = not post.ativo
            post.save(update_fields=["ativo", "modificado"])
            messages.success(request, "Post " + ("mostrado" if post.ativo else "escondido") + " no site.")

        return redirect("gestao_instagram")
