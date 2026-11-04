"""Números do painel da gestão: receita, custo e lucro por mês, funil de
orçamentos, receita por categoria, campeões de venda, clientes novos e a
fila do que precisa de atenção. Tudo calculado no servidor; o navegador só
desenha (core/static/gestao/graficos.js)."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone

from .dinheiro import formatar_brl
from .models import ItemPedido, Orcamento, Pedido, Produto

ZERO = Decimal("0")
MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
PEDIDOS_VENDIDOS = ("PAGO", "ENVIADO", "ENTREGUE")
PALETA = ["#c9233c", "#286caf", "#167c5b", "#b7791f", "#6b4fc9", "#0f8fa3", "#8a94a6"]


def _mes(d):
    return date(d.year, d.month, 1)


def _lista_meses(quantos, hoje):
    atual = _mes(hoje)
    saida = []
    for _ in range(quantos):
        saida.append(atual)
        anterior = atual - timedelta(days=1)
        atual = _mes(anterior)
    return list(reversed(saida))


def _variacao(atual, anterior):
    atual, anterior = Decimal(atual or 0), Decimal(anterior or 0)
    if anterior == 0:
        return None if atual == 0 else 100.0
    return float((atual - anterior) / abs(anterior) * 100)


def dados_do_painel(meses=12, hoje=None):
    hoje = hoje or timezone.localdate()
    lista = _lista_meses(meses, hoje)
    inicio = lista[0]
    chave = {m: i for i, m in enumerate(lista)}

    receita = [ZERO] * meses
    custo = [ZERO] * meses
    criados = [0] * meses
    aprovados = [0] * meses
    categorias = defaultdict(lambda: ZERO)
    campeoes = defaultdict(lambda: {"valor": ZERO, "qtd": 0})

    orcamentos = list(
        Orcamento.objects.filter(ativo=True)
        .prefetch_related("itens__produto__categoria", "itens__projeto")
    )
    for o in orcamentos:
        m = _mes(timezone.localtime(o.criacao))
        if m in chave:
            criados[chave[m]] += 1
        if o.status != "APROVADO" or m not in chave:
            continue
        i = chave[m]
        aprovados[i] += 1
        receita[i] += o.valor_total()
        custo[i] += o.custo_total()
        fator = (Decimal("1") - o.desconto_percentual / Decimal("100"))
        for item in o.itens.all():
            valor = item.subtotal() * fator
            if item.produto_id:
                nome_cat = item.produto.categoria.nome_categoria if item.produto.categoria_id else "Sem categoria"
                nome = item.produto.nome_produto
            elif item.projeto_id:
                nome_cat, nome = "Projetos", item.projeto.titulo
            else:
                nome_cat, nome = "Serviços avulsos", (item.descricao or "Item avulso")[:60]
            categorias[nome_cat] += valor
            campeoes[nome]["valor"] += valor
            campeoes[nome]["qtd"] += item.quantidade

    pedidos = Pedido.objects.filter(status__in=PEDIDOS_VENDIDOS, criacao__date__gte=inicio)
    for p in pedidos:
        m = _mes(timezone.localtime(p.criacao))
        if m in chave:
            receita[chave[m]] += p.valor_total
            custo[chave[m]] += p.custo_total
    for item in ItemPedido.objects.filter(pedido__in=pedidos).select_related("produto__categoria"):
        nome_cat = item.produto.categoria.nome_categoria if item.produto.categoria_id else "Sem categoria"
        categorias[nome_cat] += item.subtotal()
        campeoes[item.produto.nome_produto]["valor"] += item.subtotal()
        campeoes[item.produto.nome_produto]["qtd"] += item.quantidade

    clientes_mes = [0] * meses
    for d in User.objects.filter(is_staff=False, is_superuser=False, date_joined__date__gte=inicio).values_list("date_joined", flat=True):
        m = _mes(timezone.localtime(d))
        if m in chave:
            clientes_mes[chave[m]] += 1

    lucro = [r - c for r, c in zip(receita, custo)]

    # ------------------------------------------------ cartões do topo
    i_atual, i_ant = meses - 1, meses - 2
    abertos = [o for o in orcamentos if o.status in ("RASCUNHO", "ENVIADO") and not o.esta_expirado()]
    decididos = sum(1 for o in orcamentos if o.status in ("APROVADO", "RECUSADO") and _mes(timezone.localtime(o.criacao)) >= inicio)
    ganhos = sum(aprovados)
    vendas_qtd = ganhos + pedidos.count()
    receita_total = sum(receita, ZERO)
    clientes_total = User.objects.filter(is_staff=False, is_superuser=False).count()

    kpis = {
        "receita_mes": receita[i_atual], "receita_var": _variacao(receita[i_atual], receita[i_ant]),
        "lucro_mes": lucro[i_atual], "lucro_var": _variacao(lucro[i_atual], lucro[i_ant]),
        "margem_mes": float(lucro[i_atual] / receita[i_atual] * 100) if receita[i_atual] else 0.0,
        "receita_periodo": receita_total,
        "lucro_periodo": sum(lucro, ZERO),
        "abertos_valor": sum((o.valor_total() for o in abertos), ZERO), "abertos_qtd": len(abertos),
        "aprovacao": (ganhos / decididos * 100) if decididos else 0.0, "decididos": decididos,
        "ticket": (receita_total / vendas_qtd) if vendas_qtd else ZERO,
        "despachar": Pedido.objects.filter(status="PAGO").count(),
        "clientes": clientes_total, "clientes_mes": clientes_mes[i_atual],
    }

    # ------------------------------------------------ funil
    por_status = defaultdict(lambda: {"qtd": 0, "valor": ZERO})
    for o in orcamentos:
        chave_status = "EXPIRADO" if o.esta_expirado() else o.status
        por_status[chave_status]["qtd"] += 1
        por_status[chave_status]["valor"] += o.valor_total()
    funil = [{"chave": c, "nome": n, "qtd": por_status[c]["qtd"], "valor": float(por_status[c]["valor"])} for c, n in Orcamento.STATUS]

    # ------------------------------------------------ categorias e campeões
    ordenadas = sorted(categorias.items(), key=lambda kv: kv[1], reverse=True)
    fatias = [{"nome": n, "valor": float(v)} for n, v in ordenadas[:6] if v > 0]
    resto = sum((v for _, v in ordenadas[6:]), ZERO)
    if resto > 0:
        fatias.append({"nome": "Outras", "valor": float(resto)})
    for i, f in enumerate(fatias):
        f["cor"] = PALETA[i % len(PALETA)]
    top = sorted(campeoes.items(), key=lambda kv: kv[1]["valor"], reverse=True)[:6]

    rotulos = [f"{MESES_PT[m.month - 1]}/{str(m.year)[2:]}" for m in lista]
    graficos = {
        "meses": rotulos,
        "receita": [float(v) for v in receita],
        "custo": [float(v) for v in custo],
        "lucro": [float(v) for v in lucro],
        "criados": criados,
        "aprovados": aprovados,
        "clientes": clientes_mes,
        "funil": funil,
        "categorias": fatias,
        "top": [{"nome": n, "valor": float(d["valor"]), "qtd": d["qtd"]} for n, d in top if d["valor"] > 0],
    }

    return {"kpis": kpis, "graficos": graficos, "fila": fila_de_trabalho(orcamentos, hoje)}


def fila_de_trabalho(orcamentos, hoje):
    """O que precisa de alguém hoje, do mais urgente para o menos."""
    fila = []
    semana = hoje + timedelta(days=7)
    for o in orcamentos:
        if o.status == "ENVIADO" and o.data_validade and hoje <= o.data_validade <= semana:
            dias = (o.data_validade - hoje).days
            fila.append({"nivel": "atencao", "titulo": f"Orçamento vence {'hoje' if dias == 0 else f'em {dias} dia' + ('s' if dias > 1 else '')}",
                         "detalhe": f"{o.titulo} · {o.cliente_nome or 'sem cliente'} · {formatar_brl(o.valor_total())}",
                         "url_nome": "orcamento_detalhe", "pk": o.pk, "acao": "Cobrar cliente"})
        if o.status == "APROVADO" and o.data_prevista_entrega and o.data_prevista_entrega <= semana:
            atrasado = o.data_prevista_entrega < hoje
            fila.append({"nivel": "critico" if atrasado else "atencao",
                         "titulo": "Entrega atrasada" if atrasado else f"Entrega em {o.data_prevista_entrega:%d/%m}",
                         "detalhe": f"{o.titulo} · {o.cliente_nome or 'sem cliente'}" + (f" · {o.distancia_km} km" if o.distancia_km else ""),
                         "url_nome": "orcamento_detalhe", "pk": o.pk, "acao": "Ver produção"})
    for p in Pedido.objects.filter(status="PAGO").select_related("usuario").order_by("criacao")[:10]:
        fila.append({"nivel": "critico", "titulo": "Pedido pago aguardando envio",
                     "detalhe": f"#{p.pk} · {p.usuario.get_full_name() or p.usuario.username} · {formatar_brl(p.valor_total)}",
                     "url_nome": "gestao_pedido_detalhe", "pk": p.pk, "acao": "Despachar"})
    limite = timezone.now() - timedelta(days=2)
    for p in Pedido.objects.filter(status="PENDENTE", criacao__lt=limite).select_related("usuario").order_by("criacao")[:5]:
        fila.append({"nivel": "info", "titulo": "Pedido pendente há mais de 2 dias",
                     "detalhe": f"#{p.pk} · {p.usuario.get_full_name() or p.usuario.username} · {formatar_brl(p.valor_total)}",
                     "url_nome": "gestao_pedido_detalhe", "pk": p.pk, "acao": "Falar com o cliente"})
    for prod in Produto.objects.filter(ativo=True, preco__gt=0, estoque=0).order_by("nome_produto")[:5]:
        fila.append({"nivel": "info", "titulo": "Produto da loja sem estoque",
                     "detalhe": f"{prod.nome_produto} · {formatar_brl(prod.preco)}",
                     "url_nome": "gestao_produto_detalhe", "pk": prod.pk, "acao": "Repor"})
    ordem = {"critico": 0, "atencao": 1, "info": 2}
    return sorted(fila, key=lambda f: ordem[f["nivel"]])[:12]

