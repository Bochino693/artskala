"""Validação comercial da Artskala, sem dependências do Lazer & Sport."""
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from .models import Orcamento, ItemOrcamento, Produto, Projeto


class OrcamentoForm(forms.ModelForm):
    class Meta:
        model = Orcamento
        fields = ("titulo", "tipo", "cliente_nome", "cliente_email", "cliente_telefone",
                  "cliente_documento", "cep", "endereco", "numero", "complemento", "bairro",
                  "cidade", "uf", "latitude", "longitude", "distancia_km", "tempo_deslocamento_min",
                  "data_validade", "data_prevista_entrega", "desconto_percentual",
                  "custo_extra", "forma_pagamento", "prazo_execucao", "observacoes")

    # Campos decimais chegam com máscara ("1.234,56", "12,5"): normaliza antes de validar.
    DECIMAIS = ("desconto_percentual", "custo_extra", "latitude", "longitude", "distancia_km")

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            from .dinheiro import para_decimal
            data = data.copy()
            for campo in self.DECIMAIS:
                valor = data.get(campo)
                if valor not in (None, ""):
                    data[campo] = str(para_decimal(valor))
            if data.get("uf"):
                data["uf"] = data["uf"].strip().upper()[:2]
        super().__init__(data, *args, **kwargs)
        for campo in ("cliente_documento", "cep", "endereco", "numero", "complemento", "bairro",
                      "cidade", "uf", "latitude", "longitude", "distancia_km", "tempo_deslocamento_min"):
            self.fields[campo].required = False


class ItemForm(forms.Form):
    produto = forms.ModelChoiceField(Produto.objects.filter(ativo=True), required=False)
    projeto = forms.ModelChoiceField(Projeto.objects.filter(ativo=True), required=False)
    descricao = forms.CharField(max_length=200, required=False)
    data = forms.DateField(required=False)
    quantidade = forms.IntegerField(min_value=1, max_value=99999)
    valor = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2)
    custo = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2)

    def clean(self):
        data = super().clean()
        if data.get("produto") and data.get("projeto"):
            raise ValidationError("Escolha produto ou projeto, não ambos.")
        if not any(data.get(key) for key in ("produto", "projeto", "descricao")):
            raise ValidationError("Informe um produto, projeto ou descrição.")
        return data


def validar_itens(post):
    campos = ("produto", "projeto", "descricao", "data", "quantidade", "valor", "custo")
    from .dinheiro import para_decimal
    listas = {key: post.getlist("item_%s[]" % key) for key in campos}
    for chave in ("valor", "custo"):          # "1.500,00" dos campos com máscara
        listas[chave] = [str(para_decimal(v)) if str(v).strip() else v for v in listas[chave]]
    tamanhos = {len(values) for values in listas.values()}
    if len(tamanhos) != 1 or not 1 <= len(listas["quantidade"]) <= 100:
        raise ValidationError("Informe de 1 a 100 itens completos no orçamento.")
    itens = []
    for index in range(len(listas["quantidade"])):
        form = ItemForm({key: values[index] for key, values in listas.items()})
        if not form.is_valid():
            erros = "; ".join(str(error) for errors in form.errors.values() for error in errors)
            raise ValidationError("Item %d: %s" % (index + 1, erros))
        d = form.cleaned_data
        item = ItemOrcamento(produto=d["produto"], projeto=d["projeto"], descricao=d["descricao"],
            data_referencia=d["data"], quantidade=d["quantidade"],
            valor_unitario=d["valor"], custo_unitario=d["custo"])
        # Mantém a regra existente de preenchimento por origem.
        item.preencher_valores_por_origem()
        itens.append(item)
    return itens
