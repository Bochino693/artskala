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

    def test_email_oficial(self):
        pagina = self.client.get('/')
        self.assertContains(pagina, 'mailto:artskala@gmail.com')
        self.assertNotContains(pagina, 'Atendimento@artskala.com.br')

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
    """Gestão em /interno/ no próprio site; o subdomínio é opcional (e o antigo segue aceito)."""

    def setUp(self):
        self.gestor = get_user_model().objects.create_superuser('equipe', 'equipe@example.com', 'senha-forte-123')

    def test_dominio_interno_novo(self):
        self.assertContains(self.client.get('/login/', HTTP_HOST='interno.artskala.com.br'), 'Acesso da equipe')
        self.client.force_login(self.gestor)
        resposta = self.client.get('/', HTTP_HOST='interno.artskala.com.br')
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('no-store', resposta['Cache-Control'])
        self.assertEqual(self.client.get('/projetos/', HTTP_HOST='interno.artskala.com.br').status_code, 200)

    def test_gestao_por_rota_no_proprio_site(self):
        # sem depender do subdomínio: /interno/ no próprio domínio
        anonimo = self.client.get('/interno/projetos/')
        self.assertEqual(anonimo.status_code, 302)
        self.assertEqual(anonimo['Location'], '/interno/login/?next=/interno/projetos/')
        self.assertContains(self.client.get('/interno/login/'), 'Acesso da equipe')
        entrou = self.client.post('/interno/login/?next=/interno/projetos/',
                                  {'username': 'equipe', 'password': 'senha-forte-123', 'next': '/interno/projetos/'})
        self.assertEqual(entrou['Location'], '/interno/projetos/')
        for rota in ('', 'produtos/', 'projetos/', 'orcamentos/', 'pedidos/', 'relatorio/', 'instagram/', 'perfil/'):
            resposta = self.client.get('/interno/' + rota)
            self.assertEqual(resposta.status_code, 200, rota)
            self.assertIn('no-store', resposta['Cache-Control'])
        painel = self.client.get('/interno/')
        self.assertContains(painel, 'href="/interno/produtos/"')
        self.assertContains(painel, 'action="/interno/sair/"')
        self.assertEqual(self.client.get('/gestao/projetos/').status_code, 200)     # link antigo continua
        self.assertContains(self.client.get('/'), 'href="/interno/"')
        self.assertEqual(self.client.get('/interno/login/')['Location'], '/interno/')  # já logado
        self.client.post('/interno/sair/')
        self.assertEqual(self.client.get('/interno/').status_code, 302)

    def test_login_da_equipe_recusa_cliente(self):
        get_user_model().objects.create_user('cliente', password='senha-forte-123')
        resposta = self.client.post('/interno/login/', {'username': 'cliente', 'password': 'senha-forte-123'})
        self.assertContains(resposta, 'só para a equipe ArtSkala')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(self.client.post('/interno/login/', {'username': 'equipe', 'password': 'errada'}),
                            'Usuário ou senha incorretos')

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


class _InstagramSimulado:
    """Mídia em pasta temporária e respostas falsas da API do Instagram."""

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


class InstagramAutomaticoTests(_InstagramSimulado, TestCase):
    """Posts trazidos pela API oficial do Instagram (requisições simuladas)."""

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


class PaginaProdutoTests(TestCase):
    def setUp(self):
        from .models import CategoriaProdutos, Produto
        self.produto = Produto.objects.create(categoria=CategoriaProdutos.objects.create(nome_categoria='Toldos'),
                                              nome_produto='Toldo retrátil', preco=1890, estoque=3)

    def test_ficha_e_carrinho_sem_recarregar(self):
        from .models import ItemCarrinho
        resposta = self.client.get('/products/%s/' % self.produto.pk)
        self.assertContains(resposta, 'class="ak-form-carrinho"')
        self.assertContains(resposta, 'Toldo%20retr%C3%A1til')      # WhatsApp já com o nome do produto
        user = get_user_model().objects.create_user('cliente', password='teste123')
        self.client.force_login(user)
        r = self.client.post('/carrinho/adicionar/%s/' % self.produto.pk, {'quantidade': 2}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.json()['total_itens'], 2)
        self.assertEqual(ItemCarrinho.objects.get().quantidade, 2)

    def test_sem_estoque_vira_orcamento(self):
        self.produto.estoque = 0
        self.produto.save()
        resposta = self.client.get('/products/%s/' % self.produto.pk)
        self.assertNotContains(resposta, 'class="ak-form-carrinho"')
        self.assertContains(resposta, 'Pedir orçamento deste produto')


class GestaoInstagramTests(_InstagramSimulado, TestCase):
    """Tela Gestão > Instagram: colar o token, buscar na hora e post à mão."""

    def setUp(self):
        super().setUp()
        self.gestor = get_user_model().objects.create_superuser('equipe', 'e@example.com', 'senha-forte-123')
        self.client.force_login(self.gestor)

    def test_colar_token_ja_busca_os_posts(self):
        from .models import ConfigInstagram, PostInstagram
        with self.settings(INSTAGRAM_TOKEN=''):
            self.assertContains(self.client.get('/gestao/instagram/'), 'Não conectado')
            with self.respostas():
                self.client.post('/gestao/instagram/', {'acao': 'token', 'token': 'IGAA' + 'x' * 40})
        self.assertEqual(PostInstagram.objects.count(), 2)
        self.assertTrue(ConfigInstagram.objects.get().token)
        pagina = self.client.get('/instagram/', HTTP_HOST='interno.artskala.com.br')
        self.assertContains(pagina, 'Conectado')
        self.assertContains(pagina, 'Fachada em ACM pronta!')

    def test_post_manual_aparece_com_curtidas(self):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import PostInstagram
        foto = io.BytesIO()
        Image.new('RGB', (50, 50), (236, 50, 55)).save(foto, 'JPEG')
        self.client.post('/gestao/instagram/', {
            'acao': 'manual', 'link': 'https://www.instagram.com/p/MANUAL1/', 'legenda': 'Letreiro novo na Mooca',
            'curtidas': '87', 'comentarios': '5', 'tipo': 'IMAGE',
            'imagem': SimpleUploadedFile('foto.jpg', foto.getvalue(), content_type='image/jpeg'),
        })
        post = PostInstagram.objects.get()
        self.assertTrue(post.instagram_id.startswith('manual-'))
        home = self.client.get('/')
        self.assertContains(home, 'href="https://www.instagram.com/p/MANUAL1/"')
        self.assertContains(home, 'Letreiro novo na Mooca')
        self.assertContains(home, '87')
        self.client.post('/gestao/instagram/', {'acao': 'alternar', 'post': post.pk})
        self.assertNotContains(self.client.get('/'), 'MANUAL1')

    def test_link_que_nao_e_do_instagram_e_recusado(self):
        from .models import PostInstagram
        self.client.post('/gestao/instagram/', {'acao': 'manual', 'link': 'https://exemplo.com/x'})
        self.assertFalse(PostInstagram.objects.exists())

    def test_cliente_comum_nao_entra(self):
        self.client.force_login(get_user_model().objects.create_user('cliente', password='senha-forte-123'))
        self.assertEqual(self.client.get('/gestao/instagram/').status_code, 302)


class CronSemSegredoTests(_InstagramSimulado, TestCase):
    def test_agendador_da_vercel_uma_vez_por_hora(self):
        with self.settings(CRON_SECRET=''), self.respostas():
            self.assertEqual(self.client.get('/api/instagram/sincronizar/', HTTP_USER_AGENT='vercel-cron/1.0').status_code, 200)
            self.assertEqual(self.client.get('/api/instagram/sincronizar/', HTTP_USER_AGENT='vercel-cron/1.0').status_code, 403)
            self.assertEqual(self.client.get('/api/instagram/sincronizar/', HTTP_USER_AGENT='curl/8').status_code, 403)


class VitrineInstagramTests(TestCase):
    """Itens "sob consulta" feitos com as fotos do Instagram (core/vitrine)."""

    def setUp(self):
        import shutil
        import tempfile
        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta, ignore_errors=True)
        self.media = self.settings(MEDIA_ROOT=self.pasta)
        self.media.enable()
        self.addCleanup(self.media.disable)

    def test_cria_itens_sob_consulta_com_foto_sem_duplicar(self):
        from .models import CategoriaProdutos, ImagemProduto, Produto
        from .vitrine import ITENS, semear
        self.assertFalse(Produto.objects.exists())          # a migração não roda nos testes
        loja = Produto.objects.create(categoria=CategoriaProdutos.objects.create(nome_categoria='Banners'),
                                      nome_produto='Banner em lona', preco=89, estoque=10)
        lote1 = [i for i in ITENS if i.get('lote', 1) == 1]
        self.assertEqual(semear(Produto, CategoriaProdutos, ImagemProduto), len(lote1))
        self.assertEqual(semear(Produto, CategoriaProdutos, ImagemProduto), 0)
        self.assertEqual(semear(Produto, CategoriaProdutos, ImagemProduto, lotes=(2, 3)), len(ITENS) - len(lote1))
        novos = Produto.objects.exclude(pk=loja.pk)
        self.assertEqual(novos.count(), len(ITENS))
        self.assertFalse(novos.exclude(preco=0).exists())
        self.assertFalse(novos.exclude(estoque=0).exists())
        self.assertEqual(ImagemProduto.objects.count(), len(ITENS))
        self.assertTrue(CategoriaProdutos.objects.filter(nome_categoria='Letreiros').exists())
        fachada = Produto.objects.get(nome_produto='Fachada em ACM com letreiro')
        pagina = self.client.get('/products/%s/' % fachada.pk)
        self.assertContains(pagina, 'Sob consulta')
        self.assertContains(pagina, 'Pedir orçamento deste produto')
        self.assertNotContains(pagina, 'class="ak-form-carrinho"')
        catalogo = self.client.get('/products/')
        self.assertContains(catalogo, 'R$ 89,00')                 # item da loja continua com preço
        self.assertContains(catalogo, 'Luminoso recortado com LED neon')
        self.assertTrue(CategoriaProdutos.objects.filter(nome_categoria='Impressão digital').exists())

    def test_todas_as_fotos_existem(self):
        from .vitrine import FOTOS_EXTRAS, ITENS, PASTA_FOTOS, PROJETOS
        nomes = {f for grupo in (ITENS, PROJETOS, FOTOS_EXTRAS) for item in grupo for f in item['fotos']}
        faltando = sorted(n for n in nomes if not (PASTA_FOTOS / n).exists())
        self.assertEqual(faltando, [])

    def test_fotos_extras_entram_no_item_existente_uma_vez(self):
        from .models import CategoriaProdutos, ImagemProduto, Produto
        from .vitrine import FOTOS_EXTRAS, semear, semear_fotos_extras
        self.assertEqual(semear_fotos_extras(Produto, ImagemProduto), 0)      # sem o item, não faz nada
        semear(Produto, CategoriaProdutos, ImagemProduto)
        total = sum(len(e['fotos']) for e in FOTOS_EXTRAS if e['lote'] == 3)
        self.assertEqual(semear_fotos_extras(Produto, ImagemProduto), total)
        self.assertEqual(semear_fotos_extras(Produto, ImagemProduto), 0)
        frota = Produto.objects.get(nome_produto='Adesivação de veículos e frotas')
        self.assertEqual(frota.imagens.count(), 6)
        self.assertContains(self.client.get('/products/%s/' % frota.pk), 'adesivacao-kombi-rappi')


    def test_portfolio_de_projetos(self):
        from .models import ImagemProjeto, Projeto
        from .vitrine import PROJETOS, semear_projetos
        self.assertEqual(semear_projetos(Projeto, ImagemProjeto, lotes=(2, 3)), len(PROJETOS))
        self.assertEqual(semear_projetos(Projeto, ImagemProjeto, lotes=(2, 3)), 0)
        le_petit = Projeto.objects.get(cliente='Le Petit Macarons Boutique')
        self.assertEqual(le_petit.imagens.count(), 3)
        self.assertContains(self.client.get('/projects/%s/' % le_petit.pk), 'data-ampliar')
        self.assertContains(self.client.get('/'), 'Comunicação visual da Galpão Motoparts')


class PrintsDoInstagramTests(TestCase):
    """Gestão > Instagram > prints: cada recorte vira produto sob consulta ou projeto."""

    def setUp(self):
        import shutil
        import tempfile
        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta, ignore_errors=True)
        self.media = self.settings(MEDIA_ROOT=self.pasta)
        self.media.enable()
        self.addCleanup(self.media.disable)
        self.client.force_login(get_user_model().objects.create_superuser('equipe', 'e@example.com', 'senha-forte-123'))

    def foto(self, largura=330):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        b = io.BytesIO()
        Image.new('RGB', (largura, largura), (200, 30, 40)).save(b, 'JPEG')
        return SimpleUploadedFile('recorte.jpg', b.getvalue(), content_type='image/jpeg')

    def test_recorte_vira_produto_sob_consulta_ampliado(self):
        from PIL import Image
        from .models import Produto
        r = self.client.post('/gestao/instagram/', {'acao': 'print_item', 'tipo': 'produto', 'nome': 'Totem vertical',
                                                    'categoria': '', 'categoria_nova': 'Totens', 'foto': self.foto()})
        self.assertTrue(r.json()['ok'])
        produto = Produto.objects.get(nome_produto='Totem vertical')
        self.assertEqual((produto.preco, produto.estoque, produto.categoria.nome_categoria), (0, 0, 'Totens'))
        self.assertEqual(Image.open(produto.imagens.get().imagem.path).width, 660)   # print pequeno sai 2x
        repetido = self.client.post('/gestao/instagram/', {'acao': 'print_item', 'tipo': 'produto', 'nome': 'Totem vertical',
                                                           'categoria': 'Totens', 'foto': self.foto()})
        self.assertEqual(repetido.status_code, 409)

    def test_recorte_vira_projeto(self):
        from .models import Projeto
        r = self.client.post('/gestao/instagram/', {'acao': 'print_item', 'tipo': 'projeto', 'nome': 'Fachada Studio 4',
                                                    'cliente': 'Studio 4', 'foto': self.foto(900)})
        self.assertTrue(r.json()['ok'])
        self.assertEqual(Projeto.objects.get().imagens.count(), 1)

    def test_recusa_arquivo_que_nao_e_imagem(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        r = self.client.post('/gestao/instagram/', {'acao': 'print_item', 'nome': 'X', 'categoria': 'Placas',
                                                    'foto': SimpleUploadedFile('a.jpg', b'nao-e-imagem')})
        self.assertEqual(r.status_code, 400)
        self.assertContains(self.client.get('/gestao/instagram/'), 'id="dados-categorias"')
