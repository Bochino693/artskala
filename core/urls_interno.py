"""Rotas próprias do subdomínio interno, sem prefixo gestao."""
from django.urls import path
from django.contrib import admin
from .urls import urlpatterns as public_patterns
from .views import GestaoDashboardView
from django.contrib.auth import views as auth_views
urlpatterns = [path('', GestaoDashboardView.as_view(), name='home'), path('system/', admin.site.urls)]
for item in public_patterns:
    route = str(item.pattern)
    if route.startswith('gestao/'):
        urlpatterns.append(path(route[len('gestao/'):], item.callback, name=item.name))
urlpatterns += [path('login/', auth_views.LoginView.as_view(template_name='gestao/login.html', next_page='/'), name='login'), path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout')]

from django.views.generic import RedirectView
from django.conf import settings
urlpatterns += [path('pedido/<int:pk>/', RedirectView.as_view(url=settings.SITE_URL + '/orders/%(pk)s/'), name='order_detail')]
