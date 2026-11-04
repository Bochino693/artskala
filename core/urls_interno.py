"""Rotas do subdomínio interno (opcional): as mesmas telas de /interno/ no site,
só que sem o prefixo. O site não depende dele; serve apenas se um dia o DNS de
interno.artskala.com.br for apontado para a Vercel."""
from django.conf import settings
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

from .urls import ROTAS_INTERNAS
from .views import GestaoDashboardView
from .views_interno import LoginEquipeView, SairEquipeView

urlpatterns = [path("", GestaoDashboardView.as_view(), name="home"), path("system/", admin.site.urls)]
urlpatterns += [path(rota, view, name=nome) for rota, view, nome in ROTAS_INTERNAS]
urlpatterns += [
    path("login/", LoginEquipeView.as_view(), name="login"),
    path("sair/", SairEquipeView.as_view(), name="logout"),
    path("pedido/<int:pk>/", RedirectView.as_view(url=settings.SITE_URL + "/orders/%(pk)s/"), name="order_detail"),
]
