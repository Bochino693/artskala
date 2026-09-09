from django.shortcuts import get_object_or_404, render
from django.views import View
from .models import Orcamento
from .views import SuperuserGestaoRequiredMixin


class PropostaImpressaoView(SuperuserGestaoRequiredMixin, View):
    def get(self, request, pk):
        proposta = get_object_or_404(Orcamento.objects.prefetch_related("itens__produto", "itens__projeto"),
                                   pk=pk, usuario=request.user, ativo=True)
        return render(request, "gestao/proposta_impressao.html", {"proposta": proposta})
