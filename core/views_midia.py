"""Fotos do banco do site: endereço público, cron da cópia e a tela
Gestão > Restaurar fotos (ver core/midia.py e core/restauracao.py)."""
import hmac
import logging
from urllib.parse import quote, urlencode

from django.conf import settings
from django.contrib import messages
from django.db import DatabaseError
from django.http import HttpResponse, HttpResponseNotModified, HttpResponsePermanentRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.utils.cache import quote_etag
from django.utils.http import http_date
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_safe

from .midia import PREFIXO, ErroMidia, medida_permitida, redimensionar
from .models import ArquivoNoBanco
from .views import SuperuserGestaoRequiredMixin

logger = logging.getLogger(__name__)

CACHE_LONGO = "public, max-age=31536000, s-maxage=31536000, immutable"
VERSAO_VARIANTES = "1"     # mude se o jeito de reduzir mudar (invalida os ETags)
TIPOS_NA_TELA = ("image/jpeg", "image/png", "image/webp", "image/gif", "image/avif", "video/mp4", "video/webm")


def _medidas(request):
    """(w, h, endereço canônico ou None). Medida fora da lista vira a mais
    próxima por redirecionamento: poucas variantes, todas em cache."""
    medidas, ajustar = {}, False
    for chave in ("w", "h"):
        bruto = request.GET.get(chave)
        if bruto in (None, ""):
            continue
        try:
            valor = int(bruto)
        except ValueError:
            ajustar = True
            continue
        if valor <= 0:
            ajustar = True
            continue
        medidas[chave] = medida_permitida(valor)
        ajustar = ajustar or medidas[chave] != valor
    if set(request.GET) - {"w", "h"}:
        ajustar = True
    canonico = None
    if ajustar:
        canonico = request.path + (("?" + urlencode(medidas)) if medidas else "")
    return medidas.get("w"), medidas.get("h"), canonico


def _sem_cache(resposta, segundos=0):
    resposta["Cache-Control"] = f"public, max-age={segundos}" if segundos else "no-store"
    return resposta


@require_safe
def midia_banco(request, caminho):
    """/midia/banco/<caminho>: os bytes da foto, com cache de um ano na Vercel."""
    nome = PREFIXO + caminho
    largura, altura, canonico = _medidas(request)
    if canonico:
        resposta = HttpResponsePermanentRedirect(quote(canonico, safe="/?=&"))
        resposta["Cache-Control"] = CACHE_LONGO
        return resposta
    try:
        info = ArquivoNoBanco.objects.filter(nome=nome).values("sha256", "tipo", "criado_em").first()
    except DatabaseError:
        logger.exception("Banco indisponível ao servir %s", nome)
        resposta = _sem_cache(HttpResponse("Foto indisponível no momento.", status=503, content_type="text/plain; charset=utf-8"))
        resposta["Retry-After"] = "30"
        return resposta
    if info is None:
        # Cache curto: o nome pode passar a existir quando a cópia terminar.
        return _sem_cache(HttpResponse("Foto não encontrada.", status=404, content_type="text/plain; charset=utf-8"), 60)

    variante = f"w{largura or 0}h{altura or 0}"
    etag = quote_etag(f"{info['sha256'][:32]}-{variante}-v{VERSAO_VARIANTES}")
    cabecalhos = {"ETag": etag, "Cache-Control": CACHE_LONGO, "Last-Modified": http_date(info["criado_em"].timestamp())}
    pedidos = [e.strip() for e in request.headers.get("If-None-Match", "").split(",") if e.strip()]
    if etag in pedidos or "*" in pedidos or f"W/{etag}" in pedidos:
        resposta = HttpResponseNotModified()
        for chave, valor in cabecalhos.items():
            resposta[chave] = valor
        return resposta

    try:
        dados = bytes(ArquivoNoBanco.objects.filter(nome=nome).values_list("conteudo", flat=True).first() or b"")
    except DatabaseError:
        logger.exception("Banco indisponível ao ler %s", nome)
        resposta = _sem_cache(HttpResponse("Foto indisponível no momento.", status=503, content_type="text/plain; charset=utf-8"))
        resposta["Retry-After"] = "30"
        return resposta

    tipo = info["tipo"] or "application/octet-stream"
    if (largura or altura) and tipo.startswith("image/"):
        menor = redimensionar(dados, largura, altura)
        if menor is not None:
            dados, tipo = menor, "image/webp"

    resposta = HttpResponse(dados, content_type=tipo)
    for chave, valor in cabecalhos.items():
        resposta[chave] = valor
    if tipo not in TIPOS_NA_TELA:
        # SVG, HTML, PDF...: baixa como arquivo, nunca roda como página do site.
        arquivo = caminho.rsplit("/", 1)[-1].replace('"', "").replace("\\", "")
        resposta["Content-Disposition"] = f'attachment; filename="{arquivo}"'
    resposta["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox"
    resposta["Cross-Origin-Resource-Policy"] = "cross-origin"
    return resposta


# ============================================================
# CRON DA VERCEL — cópia automática das fotos antigas
# ============================================================
def rodada_de_copia(segundos=None):
    """Uma rodada curta: cópias do repositório, Instagram e Cloudinary."""
    from .instagram import ErroInstagram, restaurar_fotos
    from .restauracao import espelhar

    segundos = segundos if segundos is not None else getattr(settings, "MIDIA_ESPELHO_SEGUNDOS", 8)
    try:
        instagram = restaurar_fotos(limite=10, segundos=max(1.0, segundos / 3))
    except ErroInstagram as erro:
        instagram = str(erro)
    resumo = espelhar(limite=getattr(settings, "MIDIA_ESPELHO_LIMITE", 40), segundos=segundos, aleatorio=True)
    dados = resumo.como_dict()
    dados["instagram"] = instagram
    return dados


@never_cache
@require_GET
def espelhar_midia_cron(request):
    """Chamado pelo agendador da Vercel (vercel.json). Exige CRON_SECRET: a
    Vercel manda "Authorization: Bearer <CRON_SECRET>". Sem a variável, não
    faz nada. Quem é da gestão (superusuário logado) também pode chamar."""
    segredo = getattr(settings, "CRON_SECRET", "")
    cabecalho = request.headers.get("Authorization", "")
    da_gestao = request.user.is_authenticated and request.user.is_superuser
    if not segredo and not da_gestao:
        return JsonResponse({"ok": True, "feito": False,
                             "motivo": "CRON_SECRET não configurado na Vercel: a cópia automática está desligada."})
    if not da_gestao and not hmac.compare_digest(cabecalho, f"Bearer {segredo}"):
        return JsonResponse({"ok": False, "erro": "não autorizado"}, status=403)
    try:
        dados = rodada_de_copia()
    except DatabaseError:
        logger.exception("Cópia de fotos: banco indisponível")
        return JsonResponse({"ok": False, "erro": "banco indisponível"}, status=503)
    logger.warning("Cópia de fotos: %s | Instagram: %s", dados["resumo"], dados["instagram"])
    return JsonResponse({"ok": True, "feito": True, **dados})


# ============================================================
# GESTÃO > RESTAURAR FOTOS
# ============================================================
TAMANHO_POR_ENVIO = 4 * 1024 * 1024 + 512 * 1024     # a Vercel corta pedidos acima de ~4,5 MB


def _descrever(refs):
    """Lista do que falta, com o item do site (produto, projeto, post) e o link."""
    from django.urls import reverse

    from .models import ImagemProduto, ImagemProjeto, PostInstagram

    produtos = dict(ImagemProduto.objects.filter(pk__in=[r.pk for r in refs if r.modelo is ImagemProduto])
                    .values_list("pk", "produto__nome_produto"))
    produto_ids = dict(ImagemProduto.objects.filter(pk__in=list(produtos)).values_list("pk", "produto_id"))
    projetos = dict(ImagemProjeto.objects.filter(pk__in=[r.pk for r in refs if r.modelo is ImagemProjeto])
                    .values_list("pk", "projeto__titulo"))
    projeto_ids = dict(ImagemProjeto.objects.filter(pk__in=list(projetos)).values_list("pk", "projeto_id"))
    linhas = []
    for ref in refs:
        linha = {"rotulo": ref.modelo._meta.verbose_name, "pk": ref.pk, "campo": ref.campo.name, "nome": ref.nome,
                 "item": "", "link": ""}
        if ref.modelo is ImagemProduto and ref.pk in produtos:
            linha["item"] = produtos[ref.pk]
            linha["link"] = reverse("gestao_produto_detalhe", args=[produto_ids[ref.pk]])
        elif ref.modelo is ImagemProjeto and ref.pk in projetos:
            linha["item"] = projetos[ref.pk]
            linha["link"] = reverse("gestao_projeto_detalhe", args=[projeto_ids[ref.pk]])
        elif ref.modelo is PostInstagram:
            linha["item"] = "Post do Instagram"
            linha["link"] = reverse("gestao_instagram")
        linhas.append(linha)
    return linhas


class GestaoFotosView(SuperuserGestaoRequiredMixin, View):
    """Restaurar fotos: o dono envia os arquivos baixados do Cloudinary (ZIP
    ou soltos; um pedido por arquivo, feito pelo navegador) e cada um volta
    para o lugar certo pelo nome. Também busca de novo no repositório, no
    Instagram e no Cloudinary."""

    secao_gestao = "fotos"
    template_name = "gestao/fotos.html"

    def get(self, request):
        from .midia import midia_no_banco_ativa, nuvem_cloudinary
        from .restauracao import estatisticas, referencias

        refs = list(referencias())
        return render(request, self.template_name, {
            "secao_ativa": "fotos",
            "stats": estatisticas(),
            "faltando": _descrever(refs[:400]),
            "faltando_total": len(refs),
            "no_banco_ativo": midia_no_banco_ativa(),
            "cloudinary_nome": nuvem_cloudinary(),
            "cron_ligado": bool(getattr(settings, "CRON_SECRET", "")),
            "tamanho_por_envio": TAMANHO_POR_ENVIO,
        })

    def post(self, request):
        from .midia import midia_no_banco_ativa

        acao = request.POST.get("acao", "")
        if acao == "arquivo":
            return self._arquivo(request)
        if not midia_no_banco_ativa():
            messages.error(request, "Neste ambiente as fotos não ficam no banco (MIDIA_NO_BANCO desligado).")
            return redirect("gestao_fotos")
        if acao == "buscar":
            from .instagram import ErroInstagram, restaurar_fotos
            from .restauracao import restaurar_locais

            locais = restaurar_locais()
            try:
                instagram = restaurar_fotos(limite=40, segundos=20)
            except ErroInstagram as erro:
                instagram = str(erro)
            messages.success(request, f"{len(locais)} foto(s) voltaram de cópias do próprio site. Instagram: {instagram}.")
        elif acao == "cloudinary":
            from .restauracao import espelhar

            resumo = espelhar(segundos=20)
            (messages.warning if resumo.cloudinary_fora else messages.success)(request, "Cloudinary: " + resumo.texto())
        return redirect("gestao_fotos")

    def _arquivo(self, request):
        from .midia import midia_no_banco_ativa
        from .restauracao import eh_foto, referencias, restaurar_arquivo

        arquivo = request.FILES.get("arquivo")
        caminho = (request.POST.get("caminho") or (arquivo.name if arquivo else "")).strip()[:300]
        if not midia_no_banco_ativa():
            return JsonResponse({"ok": False, "erro": "Neste ambiente as fotos não ficam no banco."}, status=409)
        if not arquivo:
            return JsonResponse({"ok": False, "erro": "Nenhum arquivo chegou."}, status=400)
        if not eh_foto(caminho):
            return JsonResponse({"ok": True, "situacao": "sem_referencia", "caminho": caminho,
                                 "texto": "não é foto (pulado)", "faltando": None})
        try:
            resultado = restaurar_arquivo(caminho, arquivo.read())
        except (DatabaseError, ErroMidia) as erro:
            logger.exception("Restaurar %s", caminho)
            return JsonResponse({"ok": False, "caminho": caminho, "erro": str(erro) if isinstance(erro, ErroMidia)
                                 else "O banco de dados não respondeu. Tente de novo."}, status=503)
        dados = resultado.como_dict()
        dados["ok"] = resultado.situacao != "erro"
        dados["faltando"] = len(list(referencias()))
        return JsonResponse(dados, status=200 if dados["ok"] else 422)
