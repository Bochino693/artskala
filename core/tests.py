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
        response = self.client.get('/', HTTP_HOST='interno.artskala.com.br')
        self.assertRedirects(response, '/gestao/', fetch_redirect_response=False)
