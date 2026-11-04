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
        from .models import CategoriaProdutos
        config = configuracao()
        posts = PostInstagram.objects.order_by("-publicado_em", "-id")[:30]
        return render(request, self.template_name, {
            "secao_ativa": "instagram",
            "config": config,
            "token_final": config.token[-4:] if config.token else "",
            "posts": posts,
            "no_site": PostInstagram.objects.filter(ativo=True).exclude(imagem="").exclude(imagem__isnull=True).count(),
            "categorias_json": list(CategoriaProdutos.objects.filter(ativo=True).order_by("nome_categoria").values_list("nome_categoria", flat=True)),
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

        elif acao == "print_item":
            return self._item_do_print(request)

        elif acao == "alternar":
            post = get_object_or_404(PostInstagram, pk=request.POST.get("post"))
            post.ativo = not post.ativo
            post.save(update_fields=["ativo", "modificado"])
            messages.success(request, "Post " + ("mostrado" if post.ativo else "escondido") + " no site.")

        return redirect("gestao_instagram")

    def _item_do_print(self, request):
        """Uma foto recortada do print (feito no navegador) vira produto
        "sob consulta" ou projeto do portfólio. Responde em JSON."""
        from django.http import JsonResponse
        from django.utils.text import slugify

        from .models import CategoriaProdutos, ImagemProduto, ImagemProjeto, Produto, Projeto
        from .vitrine import melhorar_foto

        tipo = request.POST.get("tipo", "produto")
        nome = request.POST.get("nome", "").strip()[:150]
        foto = request.FILES.get("foto")
        if not nome:
            return JsonResponse({"ok": False, "erro": "Dê um nome ao item."}, status=400)
        if not foto or foto.size > 8 * 1024 * 1024:
            return JsonResponse({"ok": False, "erro": "Foto ausente ou grande demais."}, status=400)
        try:
            arquivo = melhorar_foto(foto, nome=f"print-{slugify(nome)[:60] or 'foto'}.jpg")
        except ValueError as erro:
            return JsonResponse({"ok": False, "erro": str(erro)}, status=400)
        descricao = request.POST.get("descricao", "").strip()

        if tipo == "projeto":
            if Projeto.objects.filter(titulo=nome).exists():
                return JsonResponse({"ok": False, "erro": f'Já existe o projeto "{nome}".'}, status=409)
            projeto = Projeto.objects.create(
                titulo=nome, cliente=request.POST.get("cliente", "").strip()[:150],
                descricao=descricao or "Projeto de comunicação visual criado, produzido e instalado pela ArtSkala.",
            )
            ImagemProjeto.objects.create(projeto=projeto, imagem=arquivo)
            return JsonResponse({"ok": True, "tipo": "projeto", "id": projeto.pk})

        if Produto.objects.filter(nome_produto=nome).exists():
            return JsonResponse({"ok": False, "erro": f'Já existe o produto "{nome}".'}, status=409)
        nome_categoria = (request.POST.get("categoria_nova", "").strip() or request.POST.get("categoria", "").strip())[:120]
        if not nome_categoria:
            return JsonResponse({"ok": False, "erro": "Escolha a categoria."}, status=400)
        categoria = CategoriaProdutos.objects.filter(nome_categoria__iexact=nome_categoria).first() \
            or CategoriaProdutos.objects.create(nome_categoria=nome_categoria)
        produto = Produto.objects.create(
            categoria=categoria, nome_produto=nome, preco=0, custo=0, estoque=0,
            descricao_produto=(descricao or "Produzido sob medida pela ArtSkala, com acabamento profissional. Orçamento sob consulta.")[:500],
        )
        ImagemProduto.objects.create(produto=produto, imagem=arquivo)
        return JsonResponse({"ok": True, "tipo": "produto", "id": produto.pk})
