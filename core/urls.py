from django.urls import path

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
)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),

    path("products/", ProductsView.as_view(), name="products"),
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product_detail"),

    path("categories/", CategoriesView.as_view(), name="categories"),
    path("categories/<int:pk>/", CategoryDetailView.as_view(), name="category_detail"),

    path("projects/", ProjectsView.as_view(), name="projects"),
    path("projects/<int:pk>/", ProjectDetailView.as_view(), name="project_detail"),

    path("cart/", CartView.as_view(), name="cart"),

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