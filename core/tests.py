from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Orcamento, ItemOrcamento


class ComercialTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('gestor', 'gestor@example.com', 'test-password')
        self.client.force_login(self.user)

    def dados(self):
        return {'titulo': 'Fachada', 'tipo': 'MISTO', 'desconto_percentual': '10',
                'item_produto[]': [''], 'item_projeto[]': [''], 'item_descricao[]': ['Letreiro'],
                'item_data[]': [''], 'item_quantidade[]': ['2'],
                'item_valor[]': ['100.50'], 'item_custo[]': ['40.00']}

    def test_criar_e_imprimir(self):
        response = self.client.post(reverse('orcamentos'), self.dados())
        self.assertEqual(response.status_code, 302)
        proposta = Orcamento.objects.get()
        self.assertEqual(str(proposta.valor_total()), '180.9000')
        detail = self.client.get(reverse('orcamento_detalhe', args=[proposta.pk]))
        self.assertContains(detail, 'itens-orcamento')
        self.assertContains(detail, '100.50')
        self.assertContains(self.client.get(reverse('proposta_impressao', args=[proposta.pk])), 'Letreiro')

    def test_edicao_invalida_preserva_itens(self):
        self.client.post(reverse('orcamentos'), self.dados())
        proposta = Orcamento.objects.get()
        item_pk = proposta.itens.get().pk
        dados = self.dados()
        dados['item_quantidade[]'] = ['-2']
        self.client.post(reverse('orcamento_detalhe', args=[proposta.pk]), dados)
        self.assertEqual(proposta.itens.get().pk, item_pk)

    def test_lista_e_privacidade(self):
        response = self.client.get(reverse('orcamentos'))
        self.assertContains(response, 'Novo orçamento')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')

    def test_proposta_de_outro_usuario_nao_abre(self):
        other = get_user_model().objects.create_user('outro')
        proposta = Orcamento.objects.create(usuario=other, titulo='Restrita', tipo='MISTO')
        self.assertEqual(self.client.get(reverse('proposta_impressao', args=[proposta.pk])).status_code, 404)

    def test_visitante_nao_imprime(self):
        proposta = Orcamento.objects.create(usuario=self.user, titulo='Privada', tipo='MISTO')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('proposta_impressao', args=[proposta.pk])).status_code, 302)

    def test_subdominio(self):
        response = self.client.get('/', HTTP_HOST='innterno.artskala.com')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/orcamentos/"')


class LojaTests(TestCase):
    def setUp(self):
        from .models import CategoriaProdutos, Produto
        self.produto = Produto.objects.create(categoria=CategoriaProdutos.objects.create(nome_categoria='Placas'), nome_produto='Letreiro', preco=100, estoque=5)

    def test_promocao_e_cupom_sem_acumulo(self):
        from .models import Promocao, Cupom, ItemCarrinho
        from .ofertas import desconto_cupom
        from django.utils import timezone
        from datetime import timedelta
        from decimal import Decimal
        from django.core.exceptions import ValidationError
        now = timezone.now()
        Cupom.objects.create(codigo='TESTE', percentual=10, inicio=now-timedelta(days=1), fim=now+timedelta(days=1))
        item = ItemCarrinho(produto=self.produto, quantidade=2)
        self.assertEqual(desconto_cupom('teste', [item])[1], Decimal('20.00'))
        Promocao.objects.create(produto=self.produto, titulo='Oferta', percentual=20, inicio=now-timedelta(days=1), fim=now+timedelta(days=1))
        self.assertEqual(item.subtotal(), Decimal('160.00'))
        with self.assertRaises(ValidationError):
            desconto_cupom('TESTE', [item])

    def test_paginas_publicas(self):
        from .models import Projeto
        projeto = Projeto.objects.create(titulo='Fachada')
        self.assertContains(self.client.get('/projects/%s/' % projeto.pk), 'Fachada')
        self.assertEqual(self.client.get('/promocoes/').status_code, 200)
        self.assertEqual(self.client.get('/login/').status_code, 200)
        self.assertEqual(self.client.get('/register/').status_code, 200)

    def test_login_interno(self):
        response = self.client.get('/login/', HTTP_HOST='innterno.artskala.com')
        self.assertContains(response, 'Acesso da equipe')
        response = self.client.get('/', HTTP_HOST='innterno.artskala.com')
        self.assertEqual(response.status_code, 302)


    def test_checkout_salva_desconto(self):
        from .models import Carrinho, ItemCarrinho, Cupom, Pedido
        from django.utils import timezone
        from datetime import timedelta
        from decimal import Decimal
        user = get_user_model().objects.create_user('comprador', password='teste123')
        self.client.force_login(user)
        cart = Carrinho.objects.create(usuario=user)
        ItemCarrinho.objects.create(carrinho=cart, produto=self.produto, quantidade=2)
        now = timezone.now()
        Cupom.objects.create(codigo='DEZ', percentual=10, inicio=now-timedelta(days=1), fim=now+timedelta(days=1))
        self.assertContains(self.client.get('/finalizar/?cupom=DEZ'), '180,00')
        self.client.post('/finalizar/', {'endereco': 'Rua Teste 1', 'metodo_pagamento': 'A_COMBINAR', 'cupom': 'DEZ'})
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.valor_total, Decimal('180.00'))
        pedido.recalcular_totais()
        self.assertEqual(pedido.valor_total, Decimal('180.00'))


class InstagramImportTests(TestCase):
    """Importa a exportação oficial do Instagram (ZIP com content/posts_1.json)."""

    def setUp(self):
        import io
        import json
        import shutil
        import tempfile
        import zipfile
        from PIL import Image

        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta, ignore_errors=True)
        self.media = self.settings(MEDIA_ROOT=self.pasta + '/media')
        self.media.enable()
        self.addCleanup(self.media.disable)

        foto = io.BytesIO()
        Image.new('RGB', (40, 30), (236, 50, 55)).save(foto, 'JPEG')
        legenda = 'Fachada nova em ACM \U0001F525\n#comunicacaovisual @cliente'.encode('utf-8').decode('latin-1')
        posts = [
            {'title': legenda, 'creation_timestamp': 1761926400,
             'media': [{'uri': 'media/posts/202510/foto1.jpg'}, {'uri': 'media/posts/202510/foto2.jpg'},
                       {'uri': 'media/posts/202510/video.mp4'}]},
            {'media': [{'uri': 'media/posts/202509/foto3.jpg', 'title': 'Toldo retrátil pronto',
                        'creation_timestamp': 1759000000}]},
            {'title': 'Só vídeo', 'creation_timestamp': 1758000000, 'media': [{'uri': 'media/posts/202509/v.mp4'}]},
        ]
        self.zip = self.pasta + '/instagram.zip'
        with zipfile.ZipFile(self.zip, 'w') as z:
            z.writestr('instagram-artskalaa/your_instagram_activity/content/posts_1.json', json.dumps(posts))
            for nome in ('foto1', 'foto2', 'foto3'):
                z.writestr(f'instagram-artskalaa/media/posts/2025{"10" if nome != "foto3" else "09"}/{nome}.jpg', foto.getvalue())

    def importar(self, *args):
        import io
        from django.core.management import call_command
        saida = io.StringIO()
        call_command('importar_instagram', self.zip, *args, stdout=saida)
        return saida.getvalue()

    def test_cria_projetos_com_fotos_sem_duplicar(self):
        from .models import Projeto
        self.importar()
        self.assertEqual(Projeto.objects.count(), 2)   # o post só com vídeo fica de fora
        fachada = Projeto.objects.get(titulo='Fachada nova em ACM')
        self.assertIn('\U0001F525', fachada.descricao)  # acento/emoji consertado
        self.assertEqual(fachada.imagens.count(), 2)
        self.assertTrue(fachada.ativo)
        self.assertIn('2 já existiam', self.importar())
        self.assertEqual(Projeto.objects.count(), 2)
        self.assertContains(self.client.get('/projects/%s/' % fachada.pk), 'data-ampliar')

    def test_simular_nao_grava_e_rascunho_fica_inativo(self):
        from .models import Projeto
        self.assertIn('seriam criados', self.importar('--simular'))
        self.assertFalse(Projeto.objects.exists())
        self.importar('--rascunho', '--limite', '1')
        self.assertEqual(list(Projeto.objects.values_list('ativo', flat=True)), [False])

    def test_como_produtos(self):
        from django.core.management.base import CommandError
        from .models import Produto
        with self.assertRaises(CommandError):
            self.importar('--tipo', 'produto')
        self.importar('--tipo', 'produto', '--categoria', 'Toldos')
        toldo = Produto.objects.get(nome_produto='Toldo retrátil pronto')
        self.assertEqual(toldo.categoria.nome_categoria, 'Toldos')
        self.assertEqual(toldo.imagens.count(), 1)
        self.assertContains(self.client.get('/products/'), 'Sob consulta')


class SiteNovoTests(TestCase):
    """Estrutura nova do site: busca, menu de categorias e páginas da conta."""

    def setUp(self):
        from .models import CategoriaProdutos, Produto
        self.categoria = CategoriaProdutos.objects.create(nome_categoria='Toldos')
        Produto.objects.create(categoria=self.categoria, nome_produto='Toldo retrátil', preco=1890)
        Produto.objects.create(categoria=self.categoria, nome_produto='Faixa', preco=60, descricao_produto='lona')

    def test_busca_de_produtos(self):
        resposta = self.client.get('/products/', {'q': 'retrátil'})
        self.assertContains(resposta, 'Toldo retrátil')
        self.assertNotContains(resposta, '>Faixa<')
        self.assertContains(self.client.get('/products/', {'q': 'LONA'}), 'Faixa')

    def test_menu_mostra_categorias_e_cores_da_marca(self):
        resposta = self.client.get('/')
        self.assertContains(resposta, 'site/artskala.css')
        self.assertContains(resposta, 'Toldos <b>2</b>', html=False)
        self.assertContains(resposta, 'data-cart-count')

    def test_pedidos_do_cliente(self):
        from .models import Pedido, ItemPedido, Produto
        user = get_user_model().objects.create_user('cliente', password='teste123')
        outro = get_user_model().objects.create_user('outro', password='teste123')
        pedido = Pedido.objects.create(usuario=user, metodo_pagamento='PIX', endereco='Rua A, 1')
        ItemPedido.objects.create(pedido=pedido, produto=Produto.objects.first(), quantidade=1, preco_unitario=10, custo_unitario=5)
        pedido.recalcular_totais(salvar=True)
        self.client.force_login(user)
        self.assertContains(self.client.get('/orders/'), '#%s' % pedido.pk)
        detalhe = self.client.get('/orders/%s/' % pedido.pk)
        self.assertContains(detalhe, 'Pedido <span>#%s</span>' % pedido.pk, html=False)
        self.assertContains(detalhe, 'Rua A, 1')
        self.client.force_login(outro)
        self.assertEqual(self.client.get('/orders/%s/' % pedido.pk).status_code, 404)

    def test_paginas_publicas_novas(self):
        for url in ['/', '/products/', '/categories/', '/categories/%s/' % self.categoria.pk, '/projects/', '/promocoes/', '/payment/']:
            self.assertEqual(self.client.get(url).status_code, 200, url)


class AreaInternaTests(TestCase):
    """Gestão em interno.artskala.com.br (o endereço antigo segue aceito)."""

    def setUp(self):
        self.gestor = get_user_model().objects.create_superuser('equipe', 'equipe@example.com', 'senha-forte-123')

    def test_dominio_interno_novo(self):
        self.assertContains(self.client.get('/login/', HTTP_HOST='interno.artskala.com.br'), 'Acesso da equipe')
        self.client.force_login(self.gestor)
        resposta = self.client.get('/', HTTP_HOST='interno.artskala.com.br')
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('no-store', resposta['Cache-Control'])
        self.assertEqual(self.client.get('/projetos/', HTTP_HOST='interno.artskala.com.br').status_code, 200)

    def test_gestao_do_site_vai_para_o_interno(self):
        from django.test import override_settings
        with override_settings(INTERNAL_SITE_ENABLED=True):
            resposta = self.client.get('/gestao/projetos/')
            self.assertEqual(resposta.status_code, 307)
            self.assertEqual(resposta['Location'], 'https://interno.artskala.com.br/projetos/')
            self.client.force_login(self.gestor)
            self.assertContains(self.client.get('/'), 'https://interno.artskala.com.br/')
        with override_settings(INTERNAL_SITE_ENABLED=False):
            self.assertContains(self.client.get('/'), 'href="/gestao/"')

    def test_cliente_comum_nao_entra_no_interno(self):
        cliente = get_user_model().objects.create_user('cliente', password='senha-forte-123')
        self.client.force_login(cliente)
        self.assertEqual(self.client.get('/', HTTP_HOST='interno.artskala.com.br').status_code, 403)


class MigracaoAutomaticaTests(TestCase):
    def test_sem_pendencias_nao_faz_nada(self):
        from .auto_migracao import migrar_pendentes
        self.assertEqual(migrar_pendentes(forcar=True), [])
        self.assertEqual(migrar_pendentes(), [])   # desligado fora da Vercel

    def test_aplica_o_que_falta(self):
        from unittest import mock
        from . import auto_migracao
        falsa = mock.Mock(app_label='core', name='x')
        falsa.name = '0099_teste'
        with mock.patch.object(auto_migracao, 'pendentes', return_value=[(falsa, False)]), \
                mock.patch('django.core.management.call_command') as migrate:
            self.assertEqual(auto_migracao.migrar_pendentes(forcar=True), ['core.0099_teste'])
        migrate.assert_called_once_with('migrate', interactive=False, verbosity=1)


class InstagramAutomaticoTests(TestCase):
    """Posts trazidos pela API oficial do Instagram (requisições simuladas)."""

    def setUp(self):
        import shutil
        import tempfile
        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta, ignore_errors=True)
        self.media = self.settings(MEDIA_ROOT=self.pasta, INSTAGRAM_TOKEN='token-inicial', CRON_SECRET='segredo-cron')
        self.media.enable()
        self.addCleanup(self.media.disable)

    def respostas(self):
        import io
        from unittest import mock
        from PIL import Image
        foto = io.BytesIO()
        Image.new('RGB', (60, 60), (236, 50, 55)).save(foto, 'JPEG')
        posts = {'data': [
            {'id': '111', 'caption': 'Fachada em ACM pronta! #artskala', 'media_type': 'IMAGE',
             'media_url': 'https://cdn.exemplo/111.jpg', 'permalink': 'https://www.instagram.com/p/AAA111/',
             'timestamp': '2026-11-01T12:00:00+0000', 'like_count': 42, 'comments_count': 3},
            {'id': '222', 'caption': 'Bastidores da instalação', 'media_type': 'VIDEO',
             'thumbnail_url': 'https://cdn.exemplo/222.jpg', 'media_url': 'https://cdn.exemplo/222.mp4',
             'permalink': 'https://www.instagram.com/reel/BBB222/', 'timestamp': '2026-10-30T12:00:00+0000'},
        ]}
        renovado = {'access_token': 'token-renovado', 'token_type': 'bearer', 'expires_in': 5184000}

        def falso_get(url, params=None, timeout=None):
            r = mock.Mock(status_code=200)
            if url.endswith('/me/media'):
                r.json.return_value = posts
            elif url.endswith('/refresh_access_token'):
                r.json.return_value = renovado
            else:
                r.content = foto.getvalue()
                r.json.side_effect = ValueError
            return r
        return mock.patch('core.instagram.requests.get', side_effect=falso_get)

    def test_sincroniza_sem_duplicar_e_renova_token(self):
        from .instagram import sincronizar
        from .models import ConfigInstagram, PostInstagram
        with self.respostas():
            self.assertEqual(sincronizar(), '2 novo(s), 0 atualizado(s)')
            self.assertEqual(sincronizar(), '0 novo(s), 2 atualizado(s)')
        self.assertEqual(PostInstagram.objects.count(), 2)
        reel = PostInstagram.objects.get(instagram_id='222')
        self.assertEqual(reel.tipo, 'VIDEO')
        self.assertTrue(reel.imagem)           # capa do vídeo
        config = ConfigInstagram.objects.get()
        self.assertEqual(config.token, 'token-renovado')
        self.assertIsNotNone(config.expira_em)

    def test_home_leva_direto_para_o_post(self):
        with self.respostas():
            from .instagram import sincronizar
            sincronizar()
        resposta = self.client.get('/')
        self.assertContains(resposta, 'href="https://www.instagram.com/p/AAA111/"')
        self.assertContains(resposta, 'Fachada em ACM pronta!')
        self.assertContains(resposta, 'bi-play-fill')   # selo de vídeo
        self.assertContains(resposta, '42')

    def test_endpoint_do_cron_exige_segredo(self):
        self.assertEqual(self.client.get('/api/instagram/sincronizar/').status_code, 403)
        with self.respostas():
            resposta = self.client.get('/api/instagram/sincronizar/', HTTP_AUTHORIZATION='Bearer segredo-cron')
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()['ok'])

    def test_sem_token_avisa(self):
        from .instagram import ErroInstagram, sincronizar
        with self.settings(INSTAGRAM_TOKEN=''):
            with self.assertRaises(ErroInstagram):
                sincronizar()


class FotosNitidasTests(TestCase):
    def test_filtro_tamanho(self):
        from .templatetags.artskala import tamanho
        url = 'https://res.cloudinary.com/x/image/upload/v1/media/projetos/a.jpg'
        self.assertEqual(tamanho(url, '480x480'), 'https://res.cloudinary.com/x/image/upload/c_fill,g_auto,w_480,h_480,q_auto:good,f_auto/v1/media/projetos/a.jpg')
        self.assertIn('c_limit,w_1600', tamanho(url, '1600'))
        self.assertEqual(tamanho('/media/a.jpg', '480x480'), '/media/a.jpg')

    def test_icone_da_aba(self):
        resposta = self.client.get('/favicon.ico')
        self.assertEqual(resposta.status_code, 301)
        self.assertIn('images/favicon.ico', resposta['Location'])
        self.assertContains(self.client.get('/'), 'apple-touch-icon')
