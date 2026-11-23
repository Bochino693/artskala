"""Fotos no banco do site (core/midia.py), endereço /midia/banco/, cópia das
fotos antigas do Cloudinary e restauração (core/restauracao.py).

O Cloudinary e o Instagram são sempre simulados: nenhum teste acessa a rede.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import DatabaseError
from django.test import RequestFactory, TestCase, override_settings
from PIL import Image

from .midia import ErroMidia, MidiaNoBanco, preparar, url_cloudinary
from .models import ArquivoNoBanco, CategoriaProdutos, ImagemProduto, ImagemProjeto, PostInstagram, Produto, Projeto
from .restauracao import espelhar, nome_no_banco, restaurar_arquivo, restaurar_locais

CACHE_LONGO = "public, max-age=31536000, s-maxage=31536000, immutable"
NO_BANCO = {"default": {"BACKEND": "core.midia.MidiaNoBanco"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


def foto(largura=400, altura=300, formato="JPEG", cor=(216, 31, 39), ruido=False, **opcoes):
    if ruido:
        imagem = Image.frombytes("RGB", (largura, altura), os.urandom(largura * altura * 3))
    else:
        imagem = Image.new("RGB", (largura, altura), cor)
    saida = io.BytesIO()
    imagem.save(saida, formato, **opcoes)
    return saida.getvalue()


def abrir(dados):
    imagem = Image.open(io.BytesIO(dados))
    imagem.load()
    return imagem


def resposta(status=200, conteudo=b"", cabecalhos=None):
    r = mock.Mock(status_code=status, content=conteudo, headers=cabecalhos or {})
    r.text = conteudo.decode("latin-1") if isinstance(conteudo, bytes) else str(conteudo)
    return r


class _NoBanco:
    """Armazenamento padrão = banco do site, com a conta antiga "demo"."""

    def setUp(self):
        super().setUp()
        self.ajuste = override_settings(STORAGES=NO_BANCO, MIDIA_CLOUDINARY_LEGADO="demo")
        self.ajuste.enable()
        self.addCleanup(self.ajuste.disable)
        self.categoria = CategoriaProdutos.objects.create(nome_categoria="Fachadas")
        self.produto = Produto.objects.create(categoria=self.categoria, nome_produto="Fachada em ACM")

    def antiga(self, nome, modelo=ImagemProduto, **campos):
        """Foto antiga, com o nome que o Cloudinary deu (sem banco/)."""
        if modelo is ImagemProduto:
            campos.setdefault("produto", self.produto)
        objeto = modelo.objects.create(**campos)
        modelo.objects.filter(pk=objeto.pk).update(imagem=nome)
        objeto.refresh_from_db()
        return objeto


# ---------------------------------------------------------------- storage
class ArmazenamentoNoBancoTests(_NoBanco, TestCase):
    def test_foto_pequena_fica_como_veio_com_nome_banco_e_sufixo(self):
        dados = foto(400, 300)
        imagem = ImagemProduto.objects.create(produto=self.produto, imagem=SimpleUploadedFile("fachada.jpg", dados, "image/jpeg"))
        nome = imagem.imagem.name
        self.assertRegex(nome, r"^banco/produtos/fachada_[a-z0-9]{7}\.jpg$")
        arquivo = ArquivoNoBanco.objects.get(nome=nome)
        self.assertEqual((bytes(arquivo.conteudo), arquivo.tipo, arquivo.tamanho), (dados, "image/jpeg", len(dados)))
        self.assertEqual(len(arquivo.sha256), 64)
        self.assertEqual(imagem.imagem.url, "/midia/" + nome)
        storage = imagem.imagem.storage
        self.assertTrue(storage.exists(nome))
        self.assertEqual(storage.size(nome), len(dados))
        with storage.open(nome) as aberto:
            self.assertEqual(aberto.read(), dados)
        storage.delete(nome)
        self.assertFalse(storage.exists(nome))

    def test_mesmo_nome_duas_vezes_nunca_reaproveita_o_endereco(self):
        a = ImagemProduto.objects.create(produto=self.produto, imagem=ContentFile(foto(), name="image.jpg"))
        b = ImagemProduto.objects.create(produto=self.produto, imagem=ContentFile(foto(), name="image.jpg"))
        self.assertNotEqual(a.imagem.name, b.imagem.name)
        self.assertEqual(ArquivoNoBanco.objects.count(), 2)

    def test_foto_com_mais_de_2000px_vira_webp_de_2000(self):
        imagem = ImagemProduto.objects.create(produto=self.produto, imagem=ContentFile(foto(3000, 1500), name="grande.jpg"))
        self.assertTrue(imagem.imagem.name.endswith(".webp"))
        arquivo = ArquivoNoBanco.objects.get(nome=imagem.imagem.name)
        self.assertEqual(arquivo.tipo, "image/webp")
        self.assertEqual(abrir(bytes(arquivo.conteudo)).size, (2000, 1000))

    def test_arquivo_pesado_vira_webp_menor(self):
        pesado = foto(900, 900, formato="PNG", ruido=True)
        self.assertGreater(len(pesado), 600 * 1024)
        dados, tipo, extensao = preparar(pesado, "x.png")
        self.assertEqual((tipo, extensao), ("image/webp", ".webp"))
        self.assertLess(len(dados), len(pesado))
        self.assertEqual(abrir(dados).size, (900, 900))

    def test_foto_girada_pelo_celular_fica_em_pe(self):
        exif = Image.Exif()
        exif[0x0112] = 6          # celular deitado: girar 90°
        dados, _tipo, _ext = preparar(foto(2400, 1200, exif=exif.tobytes()), "celular.jpg")
        self.assertEqual(abrir(dados).size, (1000, 2000))

    def test_arquivo_que_nao_e_imagem_fica_como_veio(self):
        self.assertEqual(preparar(b"%PDF-1.4 teste", "tabela.pdf"), (b"%PDF-1.4 teste", "application/pdf", None))

    def test_foto_corrompida_e_vazia_dao_mensagem_clara(self):
        with self.assertRaisesMessage(ErroMidia, "corrompida"):
            preparar(foto(3000, 3000)[:2000], "quebrada.jpg")
        with self.assertRaisesMessage(ErroMidia, "vazio"):
            preparar(b"", "nada.jpg")

    def test_banco_fora_do_ar_vira_erro_midia(self):
        with mock.patch.object(ArquivoNoBanco.objects, "get_or_create", side_effect=DatabaseError("caiu")):
            with self.assertRaisesMessage(ErroMidia, "banco de dados não respondeu"):
                ImagemProduto.objects.create(produto=self.produto, imagem=ContentFile(foto(), name="a.jpg"))

    def test_apagar_a_foto_libera_o_espaco_mas_nao_se_outro_lugar_usa(self):
        a = ImagemProduto.objects.create(produto=self.produto, imagem=ContentFile(foto(), name="a.jpg"))
        b = ImagemProduto.objects.create(produto=self.produto, imagem=ContentFile(foto(), name="b.jpg"))
        projeto = Projeto.objects.create(titulo="Usa a mesma foto")
        ImagemProjeto.objects.create(projeto=projeto, imagem=b.imagem.name)
        with self.captureOnCommitCallbacks(execute=True):
            ImagemProduto.objects.filter(pk__in=[a.pk, b.pk]).delete()     # como "apagar imagens" na gestão
        self.assertEqual(list(ArquivoNoBanco.objects.values_list("nome", flat=True)), [b.imagem.name])

    def test_nome_antigo_aponta_para_o_cloudinary_sem_rede_e_sem_banco(self):
        storage = MidiaNoBanco()
        with mock.patch("requests.get", side_effect=AssertionError("sem rede")), \
                mock.patch("requests.head", side_effect=AssertionError("sem rede")), self.assertNumQueries(0):
            antigo = storage.url("media/produtos/vitrine-fachada_ab12cd")
            novo = storage.url("banco/produtos/a b_x1y2z3w.webp")
        self.assertEqual(antigo, "https://res.cloudinary.com/demo/image/upload/v1/media/produtos/vitrine-fachada_ab12cd")
        self.assertEqual(novo, "/midia/banco/produtos/a%20b_x1y2z3w.webp")

    def test_endereco_antigo_igual_ao_da_biblioteca_do_cloudinary(self):
        import cloudinary.utils
        for nome in ("media/produtos/vitrine-fachada_ab12cd", "media/projetos/ação 1_x9y8z7", "produtos/sem-prefixo.jpg"):
            esperado = cloudinary.utils.cloudinary_url(nome if nome.startswith("media/") else "media/" + nome,
                                                       cloud_name="demo", secure=True)[0]
            self.assertEqual(url_cloudinary(nome, "demo"), esperado)

    def test_sem_conta_do_cloudinary_o_nome_antigo_vai_para_a_pasta_media(self):
        with override_settings(MIDIA_CLOUDINARY_LEGADO=""):
            self.assertEqual(MidiaNoBanco().url("produtos/antiga.jpg"), "/media/produtos/antiga.jpg")

    def test_ler_nome_antigo_baixa_do_cloudinary(self):
        with mock.patch("requests.get", return_value=resposta(200, b"bytes-antigos")) as baixar:
            with MidiaNoBanco().open("media/produtos/a_ab12cd") as arquivo:
                self.assertEqual(arquivo.read(), b"bytes-antigos")
        self.assertIn("res.cloudinary.com/demo/image/upload/v1/media/produtos/a_ab12cd", baixar.call_args[0][0])


class ConfiguracaoTests(TestCase):
    def rodar(self, **ambiente):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLOUDINARY", "DATABASE_URL", "MIDIA_", "VERCEL", "CI"))}
        env.update(ambiente, DJANGO_SETTINGS_MODULE="artskala.settings", PYTHONDONTWRITEBYTECODE="1")
        codigo = ("import django; django.setup(); from django.conf import settings; "
                  "print(settings.STORAGES['default']['BACKEND'], settings.USE_CLOUDINARY)")
        saida = subprocess.run([sys.executable, "-c", codigo], cwd=settings.BASE_DIR, env=env,
                               capture_output=True, text=True, timeout=120)
        self.assertEqual(saida.returncode, 0, saida.stderr)
        return saida.stdout.strip()

    def test_producao_sobe_sem_cloudinary_e_guarda_no_banco(self):
        self.assertEqual(self.rodar(VERCEL="1", SECRET_KEY="x" * 40, DATABASE_URL="postgres://u:p@localhost:6543/db"),
                         "core.midia.MidiaNoBanco False")

    def test_computador_de_desenvolvimento_continua_com_a_pasta_media(self):
        self.assertEqual(self.rodar(), "django.core.files.storage.FileSystemStorage False")


# --------------------------------------------------------------- endereço
class EnderecoDaFotoTests(_NoBanco, TestCase):
    def setUp(self):
        super().setUp()
        self.dados = foto(1200, 800, cor=(20, 120, 200))
        self.imagem = ImagemProduto.objects.create(produto=self.produto, imagem=ContentFile(self.dados, name="vitrine.jpg"))
        self.url = self.imagem.imagem.url

    def test_entrega_os_bytes_com_cache_de_um_ano(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, self.dados)
        self.assertEqual(r["Content-Type"], "image/jpeg")
        self.assertEqual(r["Cache-Control"], CACHE_LONGO)
        self.assertTrue(r["ETag"].startswith('"'))
        self.assertIn("Last-Modified", r)
        self.assertNotIn("Cookie", r.get("Vary", ""))
        self.assertFalse(r.cookies)
        self.assertEqual(self.client.head(self.url).status_code, 200)

    def test_etag_igual_responde_304_sem_corpo(self):
        etag = self.client.get(self.url)["ETag"]
        r = self.client.get(self.url, HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(r.status_code, 304)
        self.assertEqual(r.content, b"")
        self.assertEqual((r["ETag"], r["Cache-Control"]), (etag, CACHE_LONGO))
        self.assertEqual(self.client.get(self.url, HTTP_IF_NONE_MATCH='"outro"').status_code, 200)

    def test_largura_reduz_em_webp_e_cada_medida_tem_etag_propria(self):
        r = self.client.get(self.url + "?w=320")
        self.assertEqual((r.status_code, r["Content-Type"], r["Cache-Control"]), (200, "image/webp", CACHE_LONGO))
        self.assertEqual(abrir(r.content).size, (320, 213))
        self.assertNotEqual(r["ETag"], self.client.get(self.url)["ETag"])
        caixa = self.client.get(self.url + "?w=480&h=480")          # cobre a caixa: o CSS recorta
        self.assertEqual(abrir(caixa.content).size, (720, 480))

    def test_medida_fora_da_lista_vai_para_a_permitida(self):
        r = self.client.get(self.url + "?w=300")
        self.assertEqual(r.status_code, 301)
        self.assertTrue(r["Location"].endswith("?w=320"))
        self.assertEqual(self.client.get(self.url + "?w=abc").status_code, 301)
        self.assertTrue(self.client.get(self.url + "?w=99999")["Location"].endswith("?w=2000"))
        self.assertEqual(self.client.get(self.url + "?outra=1")["Location"], self.url)

    def test_largura_maior_que_a_foto_entrega_o_original(self):
        r = self.client.get(self.url + "?w=2000")
        self.assertEqual((r.status_code, r.content, r["Content-Type"]), (200, self.dados, "image/jpeg"))

    def test_nome_desconhecido_da_404_com_cache_curto(self):
        r = self.client.get("/midia/banco/produtos/nao-existe.jpg")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r["Cache-Control"], "public, max-age=60")

    def test_arquivo_que_nao_e_foto_baixa_como_anexo(self):
        nome = MidiaNoBanco().save("anexos/pagina.html", ContentFile(b"<script>alert(1)</script>"))
        r = self.client.get("/midia/" + nome)
        self.assertEqual(r["Content-Type"], "text/html")
        self.assertTrue(r["Content-Disposition"].startswith("attachment"))
        self.assertIn("sandbox", r["Content-Security-Policy"])

    def test_banco_fora_do_ar_da_503_sem_cache(self):
        with mock.patch.object(ArquivoNoBanco.objects, "filter", side_effect=DatabaseError("caiu")):
            r = self.client.get(self.url)
        self.assertEqual((r.status_code, r["Cache-Control"]), (503, "no-store"))

    def test_filtro_tamanho_usa_w_e_h_nas_fotos_do_banco(self):
        from .templatetags.artskala import tamanho
        self.assertEqual(tamanho(self.url, "480x480"), self.url + "?w=480&h=480")
        self.assertEqual(tamanho(self.url, "1400"), self.url + "?w=1400")
        self.assertEqual(tamanho(self.url, "500x333"), self.url + "?w=540&h=340")
        self.assertEqual(tamanho(self.url + "?w=320", "1400"), self.url + "?w=320")
        cloudinary = "https://res.cloudinary.com/x/image/upload/v1/media/projetos/a.jpg"
        self.assertIn("c_fill,g_auto,w_480,h_480", tamanho(cloudinary, "480x480"))

    def test_paginas_mostram_a_foto_do_banco_e_a_reserva_para_foto_antiga(self):
        pagina = self.client.get(f"/products/{self.produto.pk}/")
        self.assertContains(pagina, self.url + "?w=1200&amp;h=900")
        self.assertContains(pagina, "foto-em-atualizacao.svg")
        self.assertContains(pagina, 'addEventListener("error"')
        antigo = Produto.objects.create(categoria=self.categoria, nome_produto="Letreiro antigo")
        self.antiga("media/produtos/letreiro_ab12cd", produto=antigo)
        pagina = self.client.get(f"/products/{antigo.pk}/")
        self.assertContains(pagina, "https://res.cloudinary.com/demo/image/upload/c_fill,g_auto,w_1200,h_900")


# ----------------------------------------------------- envio pela gestão
class EnvioPelaGestaoTests(_NoBanco, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(get_user_model().objects.create_superuser("dono", "d@example.com", "senha-forte-123"))

    def dados(self, *fotos):
        return {"categoria": self.categoria.pk, "nome_produto": "Totem", "preco": "100,00", "custo": "0", "estoque": "1",
                "imagens": list(fotos)}

    def test_foto_enviada_no_produto_vai_para_o_banco_e_aparece_no_site(self):
        r = self.client.post("/interno/produtos/", self.dados(SimpleUploadedFile("totem.jpg", foto(), "image/jpeg")))
        self.assertEqual(r.status_code, 302)
        produto = Produto.objects.get(nome_produto="Totem")
        nome = produto.imagens.get().imagem.name
        self.assertTrue(nome.startswith("banco/produtos/totem_"))
        self.assertContains(self.client.get(f"/products/{produto.pk}/"), "/midia/" + nome)
        self.assertEqual(self.client.get("/midia/" + nome).status_code, 200)

    def test_falha_ao_guardar_a_foto_nao_da_500_e_salva_o_resto(self):
        with mock.patch("core.midia.gravar", side_effect=ErroMidia("o banco de dados não respondeu")):
            r = self.client.post("/interno/produtos/", self.dados(SimpleUploadedFile("totem.jpg", foto(), "image/jpeg")), follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "1 foto não entrou")
        self.assertContains(r, "totem.jpg: o banco de dados não respondeu")
        self.assertEqual(Produto.objects.get(nome_produto="Totem").imagens.count(), 0)

    def test_post_manual_do_instagram_com_erro_na_foto_avisa(self):
        with mock.patch("core.midia.gravar", side_effect=ErroMidia("sem banco")):
            r = self.client.post("/interno/instagram/", {"acao": "manual", "link": "https://www.instagram.com/p/X/",
                                                         "imagem": SimpleUploadedFile("p.jpg", foto(), "image/jpeg")}, follow=True)
        self.assertContains(r, "A foto não foi salva: sem banco")
        self.assertFalse(PostInstagram.objects.exists())

    def test_rede_de_seguranca_para_qualquer_tela(self):
        from .middleware import ErroDeMidiaMiddleware
        from django.contrib.messages.storage.fallback import FallbackStorage
        meio = ErroDeMidiaMiddleware(lambda request: None)
        pedido = RequestFactory().post("/system/core/imagemproduto/add/")
        pedido.session, pedido._messages = {}, None
        pedido._messages = FallbackStorage(pedido)
        r = meio.process_exception(pedido, ErroMidia("foto grande demais"))
        self.assertEqual((r.status_code, r["Location"]), (302, "/system/core/imagemproduto/add/"))
        r = meio.process_exception(RequestFactory().post("/x/", HTTP_ACCEPT="application/json"), ErroMidia("x"))
        self.assertEqual(r.status_code, 503)
        self.assertIsNone(meio.process_exception(pedido, ValueError("outro erro")))


# ------------------------------------------------- cópia do Cloudinary (5)
class EspelharCloudinaryTests(_NoBanco, TestCase):
    def test_copia_aponta_o_campo_e_nao_repete(self):
        original = foto(500, 400)
        imagem = self.antiga("media/produtos/fachada-loja_ab12cd")
        projeto = Projeto.objects.create(titulo="Loja")
        mesma = self.antiga("media/produtos/fachada-loja_ab12cd", modelo=ImagemProjeto, projeto=projeto)
        with mock.patch("requests.get", return_value=resposta(200, original)) as baixar:
            resumo = espelhar()
        self.assertEqual((resumo.copiadas, resumo.do_cloudinary, resumo.restantes), (1, 1, 0))
        baixar.assert_called_once()
        self.assertEqual(baixar.call_args[0][0], "https://res.cloudinary.com/demo/image/upload/v1/media/produtos/fachada-loja_ab12cd")
        imagem.refresh_from_db()
        mesma.refresh_from_db()
        self.assertEqual(imagem.imagem.name, "banco/media/produtos/fachada-loja_ab12cd")
        self.assertEqual(mesma.imagem.name, imagem.imagem.name)          # todos os lugares que usavam a foto
        self.assertEqual(bytes(ArquivoNoBanco.objects.get().conteudo), original)
        self.assertEqual(self.client.get(imagem.imagem.url).content, original)
        with mock.patch("requests.get", side_effect=AssertionError("não devia baixar de novo")):
            self.assertEqual(espelhar().copiadas, 0)
        self.assertEqual(ArquivoNoBanco.objects.count(), 1)

    def test_conta_desativada_para_na_primeira_resposta_e_avisa(self):
        for i in range(3):
            self.antiga(f"media/produtos/foto-{i}_ab12c{i}")
        desativada = resposta(401, b"", {"x-cld-error": "cloud_name demo is disabled"})
        saida = io.StringIO()
        with mock.patch("requests.get", return_value=desativada) as baixar:
            call_command("espelhar_midia", stdout=saida)
        baixar.assert_called_once()
        self.assertIn("Cloudinary indisponível", saida.getvalue())
        self.assertIn("3 foto(s) esperando", saida.getvalue())
        self.assertFalse(ArquivoNoBanco.objects.exists())
        self.assertFalse(ImagemProduto.objects.filter(imagem__startswith="banco/").exists())

    def test_foto_da_vitrine_volta_do_repositorio_mesmo_com_o_cloudinary_fora(self):
        from .vitrine import PASTA_FOTOS
        imagem = self.antiga("media/produtos/vitrine-placa-cavalete_k2j4h1")
        self.antiga("media/produtos/cliente-novo_ab12cd")
        with mock.patch("requests.get", return_value=resposta(401, b"cloud_name demo is disabled")):
            resumo = espelhar()
        imagem.refresh_from_db()
        self.assertEqual(imagem.imagem.name, "banco/media/produtos/vitrine-placa-cavalete_k2j4h1")
        self.assertEqual((resumo.locais, resumo.esperando), (1, 1))
        self.assertEqual(abrir(self.client.get(imagem.imagem.url).content).size,
                         Image.open(Path(PASTA_FOTOS) / "placa-cavalete.jpg").size)

    def test_foto_que_sumiu_do_cloudinary_nao_trava_a_fila(self):
        self.antiga("media/produtos/sumiu_ab12cd")
        boa = self.antiga("media/produtos/boa_cd34ef")
        respostas = {"sumiu_ab12cd": resposta(404, b"", {"x-cld-error": "Resource not found"}), "boa_cd34ef": resposta(200, foto())}
        with mock.patch("requests.get", side_effect=lambda url, timeout=None: respostas[url.rsplit("/", 1)[-1]]):
            resumo = espelhar()
        self.assertEqual((resumo.copiadas, resumo.faltando_no_cloudinary), (1, ["media/produtos/sumiu_ab12cd"]))
        boa.refresh_from_db()
        self.assertTrue(boa.imagem.name.startswith("banco/"))

    def test_nome_comprido_e_encurtado_sempre_igual(self):
        antigo = "media/produtos/" + "a" * 80 + "_ab12cd"
        novo = nome_no_banco(antigo, 100)
        self.assertEqual(len(novo), 100)
        self.assertEqual(novo, nome_no_banco(antigo, 100))
        self.assertTrue(novo.startswith("banco/media/produtos/aaa"))

    def test_sem_banco_como_armazenamento_nao_faz_nada(self):
        with override_settings(STORAGES={**NO_BANCO, "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}}):
            self.assertIn("não está guardando fotos no banco", espelhar().parado)


class CronDaCopiaTests(_NoBanco, TestCase):
    def test_sem_cron_secret_nao_faz_nada(self):
        self.antiga("media/produtos/a_ab12cd")
        with override_settings(CRON_SECRET=""), mock.patch("requests.get", side_effect=AssertionError("sem rede")):
            r = self.client.get("/api/midia/espelhar/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["feito"])

    def test_com_segredo_errado_recusa_e_certo_copia(self):
        self.antiga("media/produtos/a_ab12cd")
        with override_settings(CRON_SECRET="segredo"):
            self.assertEqual(self.client.get("/api/midia/espelhar/", HTTP_AUTHORIZATION="Bearer errado").status_code, 403)
            with mock.patch("requests.get", return_value=resposta(200, foto())):
                r = self.client.get("/api/midia/espelhar/", HTTP_AUTHORIZATION="Bearer segredo")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json()["copiadas"], r.json()["restantes"]), (1, 0))
        self.assertIn("no-cache", r["Cache-Control"])


# --------------------------------------------- restauração (A e B do dono)
class RestaurarArquivosTests(_NoBanco, TestCase):
    def test_arquivo_da_exportacao_volta_pelo_public_id(self):
        imagem = self.antiga("media/produtos/fachada-loja_ab12cd")
        projeto = Projeto.objects.create(titulo="Loja")
        mesma = self.antiga("media/produtos/fachada-loja_ab12cd", modelo=ImagemProjeto, projeto=projeto)
        resultado = restaurar_arquivo("media/produtos/fachada-loja_ab12cd.jpg", foto())
        self.assertEqual((resultado.situacao, resultado.referencias), ("restaurada", 2))
        imagem.refresh_from_db()
        mesma.refresh_from_db()
        self.assertEqual({imagem.imagem.name, mesma.imagem.name}, {"banco/media/produtos/fachada-loja_ab12cd"})
        self.assertEqual(restaurar_arquivo("media/produtos/fachada-loja_ab12cd.jpg", foto()).situacao, "ja_restaurada")

    def test_casa_pelo_nome_do_arquivo_sem_pasta_e_sem_o_sufixo(self):
        a = self.antiga("media/produtos/letreiro-neon_ab12cd")
        b = self.antiga("media/projetos/painel-lona_x9y8z7")
        self.assertEqual(restaurar_arquivo("Downloads/letreiro-neon_ab12cd.png", foto()).situacao, "restaurada")
        self.assertEqual(restaurar_arquivo("painel-lona.jpg", foto()).situacao, "restaurada")   # nome de exibição
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertTrue(a.imagem.name.startswith("banco/") and b.imagem.name.startswith("banco/"))

    def test_nunca_troca_foto_por_engano(self):
        a = self.antiga("media/produtos/image_ab12cd")
        b = self.antiga("media/produtos/image_cd34ef")
        self.assertEqual(restaurar_arquivo("image.jpg", foto()).situacao, "ambigua")
        self.assertEqual(restaurar_arquivo("outra-coisa.jpg", foto()).situacao, "sem_referencia")
        self.assertEqual(restaurar_arquivo("media/produtos/image_cd34ef.jpg", foto()).situacao, "restaurada")
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual((a.imagem.name, b.imagem.name), ("media/produtos/image_ab12cd", "banco/media/produtos/image_cd34ef"))

    def test_tela_restaurar_fotos(self):
        self.antiga("media/produtos/fachada-loja_ab12cd")
        usuario = get_user_model().objects.create_superuser("dono", "d@example.com", "senha-forte-123")
        self.client.force_login(usuario)
        pagina = self.client.get("/interno/fotos/")
        self.assertContains(pagina, "Restaurar fotos")
        self.assertContains(pagina, "media/produtos/fachada-loja_ab12cd")
        self.assertContains(pagina, "Fachada em ACM")
        self.assertContains(pagina, "gestao/fotos.js")
        r = self.client.post("/interno/fotos/", {"acao": "arquivo", "caminho": "media/media/produtos/fachada-loja_ab12cd.jpg",
                                                 "arquivo": SimpleUploadedFile("fachada-loja_ab12cd.jpg", foto(), "image/jpeg")},
                             HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual((r.status_code, r.json()["situacao"], r.json()["faltando"]), (200, "restaurada", 0))
        r = self.client.post("/interno/fotos/", {"acao": "arquivo", "caminho": "nada.jpg",
                                                 "arquivo": SimpleUploadedFile("nada.jpg", foto(), "image/jpeg")})
        self.assertEqual(r.json()["situacao"], "sem_referencia")
        self.assertContains(self.client.get("/interno/fotos/"), "Nenhuma foto faltando")

    def test_cliente_da_loja_nao_entra(self):
        self.client.force_login(get_user_model().objects.create_user("cliente", "c@example.com", "senha-forte-123"))
        r = self.client.post("/interno/fotos/", {"acao": "arquivo", "arquivo": SimpleUploadedFile("a.jpg", foto())})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(ArquivoNoBanco.objects.exists())

    def test_comando_com_zip_pasta_e_relatorio(self):
        self.antiga("media/produtos/um_aa11bb")
        self.antiga("media/produtos/dois_cc22dd")
        tres = self.antiga("media/projetos/tres_ee33ff", modelo=ImagemProjeto, projeto=Projeto.objects.create(titulo="P"))
        pasta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        with zipfile.ZipFile(pasta / "cloudinary.zip", "w", zipfile.ZIP_DEFLATED) as pacote:
            pacote.writestr("media/produtos/um_aa11bb.jpg", foto())
            pacote.writestr("__MACOSX/media/produtos/._um_aa11bb.jpg", b"lixo")
            pacote.writestr("leia-me.txt", b"texto")
        (pasta / "soltas" / "media" / "produtos").mkdir(parents=True)
        (pasta / "soltas" / "media" / "produtos" / "dois_cc22dd.png").write_bytes(foto(formato="PNG"))
        saida = io.StringIO()
        call_command("restaurar_midia", zip=str(pasta / "cloudinary.zip"), stdout=saida)
        call_command("restaurar_midia", pasta=str(pasta / "soltas"), stdout=saida)
        self.assertIn("1 restaurada", saida.getvalue())
        relatorio = io.StringIO()
        call_command("restaurar_midia", relatorio=True, stdout=relatorio)
        self.assertIn(f"core.ImagemProjeto\t#{tres.pk}\timagem\tmedia/projetos/tres_ee33ff", relatorio.getvalue())
        self.assertNotIn("um_aa11bb", relatorio.getvalue())
        self.assertIn("Faltando: 1 referência(s)", relatorio.getvalue())


class RestaurarDoRepositorioTests(_NoBanco, TestCase):
    def test_vitrine_e_imagens_fixas_voltam_e_nome_duvidoso_fica(self):
        vitrine = self.antiga("media/produtos/vitrine-fachada-acm-letreiro_q1w2e3")
        logo_antigo = self.antiga("media/produtos/artskala-logo-old_r4t5y6")
        logo = self.antiga("media/produtos/artskala-logo_u7i8o9")       # PNG e JPEG diferentes no repositório
        feitas = restaurar_locais()
        self.assertEqual(set(feitas), {vitrine.imagem.name, logo_antigo.imagem.name})
        for objeto in (vitrine, logo_antigo, logo):
            objeto.refresh_from_db()
        self.assertTrue(vitrine.imagem.name.startswith("banco/") and logo_antigo.imagem.name.startswith("banco/"))
        self.assertEqual(logo.imagem.name, "media/produtos/artskala-logo_u7i8o9")
        self.assertEqual(restaurar_locais(), [])                          # de novo: nada a fazer

    def test_banco_novo_vitrine_sem_tabela_de_fotos_fica_pendente_e_volta_do_repositorio(self):
        from django.db import connection

        from .vitrine import semear
        with mock.patch.object(connection.introspection, "table_names", return_value=[]):
            self.assertEqual(semear(Produto, CategoriaProdutos, ImagemProduto, lotes=(1,)), 7)
        self.assertFalse(ArquivoNoBanco.objects.exists())
        self.assertEqual(ImagemProduto.objects.filter(imagem="produtos/vitrine-placa-cavalete.jpg").count(), 1)
        self.assertEqual(len(restaurar_locais()), 7)
        self.assertFalse(ImagemProduto.objects.exclude(imagem__startswith="banco/").exists())

    def test_migracao_restaura_sozinha_e_nunca_derruba_o_deploy(self):
        import importlib

        from django.apps import apps
        migracao = importlib.import_module("core.migrations.0012_restaurar_fotos_do_repositorio")
        vitrine = self.antiga("media/produtos/vitrine-placa-cavalete_a1b2c3")
        editor = mock.Mock(connection=mock.Mock(alias="default"))
        migracao.restaurar(apps, editor)
        vitrine.refresh_from_db()
        self.assertTrue(vitrine.imagem.name.startswith("banco/"))
        with mock.patch("core.restauracao.restaurar_locais", side_effect=RuntimeError("qualquer coisa")):
            migracao.restaurar(apps, editor)                              # só registra no log


class InstagramNoBancoTests(_NoBanco, TestCase):
    def falso_get(self, url, params=None, timeout=None):
        r = mock.Mock(status_code=200)
        if url.endswith("/me/media"):
            r.json.return_value = {"data": [{"id": "111", "media_type": "IMAGE", "media_url": "https://cdn/111.jpg",
                                             "permalink": "https://www.instagram.com/p/A/", "timestamp": "2026-11-01T12:00:00+0000"}]}
        elif url.endswith("/refresh_access_token"):
            r.json.return_value = {"access_token": "novo", "expires_in": 5184000}
        elif url.endswith("/222"):
            r.json.return_value = {"media_type": "IMAGE", "media_url": "https://cdn/222.jpg"}
        else:
            r.content = foto(80, 80)
            r.json.side_effect = ValueError
        return r

    def test_busca_do_instagram_grava_no_banco_e_traz_de_novo_as_fotos_presas(self):
        from .instagram import restaurar_fotos, sincronizar
        antigo = PostInstagram.objects.create(instagram_id="111", link="https://www.instagram.com/p/A/")
        PostInstagram.objects.filter(pk=antigo.pk).update(imagem="media/instagram/ig-111_ab12cd")
        velho = PostInstagram.objects.create(instagram_id="222", link="https://www.instagram.com/p/B/")
        PostInstagram.objects.filter(pk=velho.pk).update(imagem="media/instagram/ig-222_cd34ef")
        manual = PostInstagram.objects.create(link="https://www.instagram.com/p/C/")
        PostInstagram.objects.filter(pk=manual.pk).update(imagem="media/instagram/manual_ef56gh")
        with override_settings(INSTAGRAM_TOKEN="token"), mock.patch("core.instagram.requests.get", side_effect=self.falso_get):
            sincronizar()
            antigo.refresh_from_db()
            self.assertRegex(antigo.imagem.name, r"^banco/instagram/ig-111_[a-z0-9]{7}\.jpg$")
            self.assertIn("1 foto(s) trazida(s)", restaurar_fotos())
        velho.refresh_from_db()
        manual.refresh_from_db()
        self.assertTrue(velho.imagem.name.startswith("banco/instagram/ig-222_"))
        self.assertEqual(manual.imagem.name, "media/instagram/manual_ef56gh")   # manual: só pela tela Restaurar fotos
