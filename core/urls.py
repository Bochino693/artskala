from django.urls import path
from .views_comercial import PropostaImpressaoView

from .views import (
    HomeView,
    ProductsView,
    ProductDetailView,
    CategoriesView,
    CategoryDetailView,
    ProjectsView,
    ProjectDetailView,
    CartView,
    CheckoutView,
    OrdersView,
    OrderDetailView,
    ProfileView,
    LoginView,
    LogoutView,
    RegisterView,
    PaymentView,
    PendingOrdersView,
    AddToCartView,
    RemoveCartItemView,
    UpdateCartItemView,
    CartView,
    RelatorioOrcamentosView,
    OrcamentoView,
    GestaoDashboardView,
    GestaoPedidosView,
    GestaoPerfilView,
    GestaoProdutosView,
    GestaoProjetosView,



)

urlpatterns = [
    path("gestao/orcamentos/<int:pk>/imprimir/", PropostaImpressaoView.as_view(), name="proposta_impressao"),
    path("", HomeView.as_view(), name="home"),

    path("products/", ProductsView.as_view(), name="products"),
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product_detail"),

    path("categories/", CategoriesView.as_view(), name="categories"),
    path("categories/<int:pk>/", CategoryDetailView.as_view(), name="category_detail"),

    path("projects/", ProjectsView.as_view(), name="projects"),
    path("projects/<int:pk>/", ProjectDetailView.as_view(), name="project_detail"),

    # Carrinho — página + endpoints assíncronos
    path("carrinho/", CartView.as_view(), name="cart"),
    path("carrinho/adicionar/<int:pk>/", AddToCartView.as_view(), name="cart_add"),
    path("carrinho/atualizar/<int:pk>/", UpdateCartItemView.as_view(), name="cart_update"),
    path("carrinho/remover/<int:pk>/", RemoveCartItemView.as_view(), name="cart_remove"),

    path("finalizar/", CheckoutView.as_view(), name="checkout"),

    path("checkout/", CheckoutView.as_view(), name="checkout"),

    path("orders/", OrdersView.as_view(), name="orders"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order_detail"),

    path("profile/", ProfileView.as_view(), name="profile"),

    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", RegisterView.as_view(), name="register"),

    path("payment/", PaymentView.as_view(), name="payment"),

    path("pendings/", PendingOrdersView.as_view(), name="pendings"),

    path("gestao/", GestaoDashboardView.as_view(), name="gestao_dashboard"),
    path("gestao/pedidos/", GestaoPedidosView.as_view(), name="gestao_pedidos"),
    path("gestao/relatorio/", RelatorioOrcamentosView.as_view(), name="gestao_relatorio"),

    # Produtos: sem pk = lista + formulário de novo produto (GET) / criação (POST)
    # com pk = edição (GET/POST) e exclusão lógica (DELETE)
    path("gestao/produtos/", GestaoProdutosView.as_view(), name="gestao_produtos"),
    path("gestao/produtos/<int:pk>/", GestaoProdutosView.as_view(), name="gestao_produto_detalhe"),

    # Projetos: mesmo padrão dos produtos
    path("gestao/projetos/", GestaoProjetosView.as_view(), name="gestao_projetos"),
    path("gestao/projetos/<int:pk>/", GestaoProjetosView.as_view(), name="gestao_projeto_detalhe"),

    # Uma unica view cuida de listar, criar, editar, trocar status e excluir.
    path("gestao/orcamentos/", OrcamentoView.as_view(), name="orcamentos"),
    path("gestao/orcamentos/<int:pk>/", OrcamentoView.as_view(), name="orcamento_detalhe"),

    path("gestao/perfil/", GestaoPerfilView.as_view(), name="gestao_perfil"),

]
