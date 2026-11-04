"""Funções da equipe na gestão (como no Lazer & Sport: grupos do Django).

- Gestão: tudo, inclusive equipe, relatórios e Instagram (é superusuário).
- Vendas: painel, orçamentos, pedidos, produtos, etiquetas.
- Produção: painel, orçamentos (ordens de produção), projetos, etiquetas.
"""
from django.contrib.auth.models import Group

FUNCOES = [
    {"codigo": "gestao", "grupo": "Equipe · Gestão", "titulo": "Gestão", "icone": "◆",
     "descricao": "Acesso total: equipe, relatórios, Instagram, preços e custos."},
    {"codigo": "vendas", "grupo": "Equipe · Vendas", "titulo": "Vendas", "icone": "▤",
     "descricao": "Orçamentos, pedidos da loja, produtos e etiquetas."},
    {"codigo": "producao", "grupo": "Equipe · Produção", "titulo": "Produção", "icone": "▧",
     "descricao": "Ordens de produção (orçamentos), projetos e etiquetas."},
]
POR_CODIGO = {f["codigo"]: f for f in FUNCOES}

# Tela -> funções que podem abrir (superusuário sempre pode).
ACESSO = {
    "dashboard": {"gestao", "vendas", "producao"},
    "buscar": {"gestao", "vendas", "producao"},
    "orcamentos": {"gestao", "vendas", "producao"},
    "etiquetas": {"gestao", "vendas", "producao"},
    "perfil": {"gestao", "vendas", "producao"},
    "pedidos": {"gestao", "vendas"},
    "produtos": {"gestao", "vendas"},
    "projetos": {"gestao", "producao"},
    "relatorio": {"gestao"},
    "instagram": {"gestao"},
    "equipe": {"gestao"},
}


def funcoes_do_usuario(user):
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return set()
    if user.is_superuser:
        return {"gestao"}
    if not user.is_staff:
        return set()
    grupos = {g.name for g in user.groups.all()}
    return {f["codigo"] for f in FUNCOES if f["grupo"] in grupos}


def eh_equipe(user):
    return bool(funcoes_do_usuario(user))


def pode(user, secao):
    funcoes = funcoes_do_usuario(user)
    if "gestao" in funcoes:
        return True
    if secao is None:
        return False
    return bool(funcoes & ACESSO.get(secao, set()))


def mapa_de_acesso(user):
    return {secao: pode(user, secao) for secao in ACESSO}


def definir_funcao(user, codigo):
    """Troca a função do usuário (só os grupos da equipe; os outros ficam)."""
    grupos = {f["grupo"]: Group.objects.get_or_create(name=f["grupo"])[0] for f in FUNCOES}
    user.groups.remove(*grupos.values())
    if codigo in POR_CODIGO:
        user.groups.add(grupos[POR_CODIGO[codigo]["grupo"]])
    user.is_staff = codigo in POR_CODIGO
    user.is_superuser = codigo == "gestao"
    user.save(update_fields=["is_staff", "is_superuser"])


ROTULOS_TELAS = {
    "dashboard": "Painel", "orcamentos": "Orçamentos", "pedidos": "Pedidos do site", "produtos": "Produtos",
    "projetos": "Projetos", "etiquetas": "Etiquetas", "relatorio": "Relatórios", "instagram": "Instagram",
    "equipe": "Equipe e clientes", "perfil": "Perfil",
}


def mapa_de_acesso_por_funcao(codigo):
    """[(nome da tela, True)] das telas que uma função abre (para a lista da equipe)."""
    if codigo == "gestao":
        return [(nome, True) for nome in ROTULOS_TELAS.values()]
    return [(ROTULOS_TELAS[t], True) for t, funcoes in ACESSO.items() if codigo in funcoes and t in ROTULOS_TELAS]
