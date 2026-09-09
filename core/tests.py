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
