"""Entrada da área interna (gestão) por rota no próprio site: /interno/.

Não depende de subdomínio. O login é o da equipe: só superusuário entra; um
cliente da loja que tentar recebe o aviso e continua com a conta dele no site.
"""
from django import forms
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme


class LoginEquipeForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Usuário ou senha incorretos. Confira e tente de novo.",
        "inactive": "Este usuário está desativado.",
        "sem_acesso": "Este acesso é só para a equipe ArtSkala. Entre com um usuário da gestão.",
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_superuser:
            raise forms.ValidationError(self.error_messages["sem_acesso"], code="sem_acesso")


class LoginEquipeView(auth_views.LoginView):
    template_name = "gestao/login.html"
    authentication_form = LoginEquipeForm
    next_page = reverse_lazy("gestao_dashboard")

    def dispatch(self, request, *args, **kwargs):
        # Quem já é da equipe vai direto para a gestão (ou para onde ia).
        if request.method == "GET" and request.user.is_authenticated and request.user.is_superuser:
            destino = request.GET.get("next", "")
            if not url_has_allowed_host_and_scheme(destino, {request.get_host()}, require_https=request.is_secure()):
                destino = reverse("gestao_dashboard")
            return redirect(destino)
        return super().dispatch(request, *args, **kwargs)


class SairEquipeView(auth_views.LogoutView):
    next_page = reverse_lazy("interno_login")
