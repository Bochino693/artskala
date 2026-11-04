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
