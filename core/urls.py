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
    GestaoPerfilView,
    GestaoProdutosView,
    GestaoProjetosView,



)

from .ofertas import promocoes
from .views_instagram import GestaoInstagramView, sincronizar_instagram
from .views_interno import LoginEquipeView, SairEquipeView
from .views_gestao import (
    BuscaRapidaView,
    EquipeView,
    EtiquetasView,
    GestaoPedidoDetalheView,
    GestaoPedidosView,
    QrCodeView,
)

urlpatterns = [
    path("promocoes/", promocoes, name="promocoes"),
    path("api/instagram/sincronizar/", sincronizar_instagram, name="instagram_sincronizar"),
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


]

# ============================================================
# ÁREA INTERNA (gestão) — por rota no próprio site, sem subdomínio.
# /interno/... é o endereço oficial; /gestao/... abre as mesmas telas para
# os links antigos continuarem funcionando.
# ============================================================
ROTAS_INTERNAS = [
    ("", GestaoDashboardView.as_view(), "gestao_dashboard"),
    ("login/", LoginEquipeView.as_view(), "interno_login"),
    ("sair/", SairEquipeView.as_view(), "interno_logout"),
    ("pedidos/", GestaoPedidosView.as_view(), "gestao_pedidos"),
    ("pedidos/<int:pk>/", GestaoPedidoDetalheView.as_view(), "gestao_pedido_detalhe"),
    ("buscar/", BuscaRapidaView.as_view(), "gestao_buscar"),
    ("etiquetas/", EtiquetasView.as_view(), "gestao_etiquetas"),
    ("etiquetas/qr.svg", QrCodeView.as_view(), "gestao_qrcode"),
    ("equipe/", EquipeView.as_view(), "gestao_equipe"),
    ("instagram/", GestaoInstagramView.as_view(), "gestao_instagram"),
    ("relatorio/", RelatorioOrcamentosView.as_view(), "gestao_relatorio"),
    # Produtos: sem pk = lista + formulário de novo produto (GET) / criação (POST)
    # com pk = edição (GET/POST) e exclusão lógica (DELETE)
    ("produtos/", GestaoProdutosView.as_view(), "gestao_produtos"),
    ("produtos/<int:pk>/", GestaoProdutosView.as_view(), "gestao_produto_detalhe"),
    # Projetos: mesmo padrão dos produtos
    ("projetos/", GestaoProjetosView.as_view(), "gestao_projetos"),
    ("projetos/<int:pk>/", GestaoProjetosView.as_view(), "gestao_projeto_detalhe"),
    # Uma única view cuida de listar, criar, editar, trocar status e excluir.
    ("orcamentos/", OrcamentoView.as_view(), "orcamentos"),
    ("orcamentos/<int:pk>/", OrcamentoView.as_view(), "orcamento_detalhe"),
    ("orcamentos/<int:pk>/imprimir/", PropostaImpressaoView.as_view(), "proposta_impressao"),
    ("perfil/", GestaoPerfilView.as_view(), "gestao_perfil"),
]

urlpatterns += [path("interno/" + rota, view, name=nome) for rota, view, nome in ROTAS_INTERNAS]
urlpatterns += [path("gestao/" + rota, view) for rota, view, _nome in ROTAS_INTERNAS]
