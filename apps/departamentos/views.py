from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.pagination import paginate_with_show_all
from apps.documentos.models import Documento

from .forms import DepartamentoForm
from .models import Departamento


def _require_perm(request, perm):
    if not request.user.has_perm(perm):
        raise PermissionDenied


@login_required
def listar_departamentos(request):
    _require_perm(request, "departamentos.view_departamento")

    termo_busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    departamentos = Departamento.objects.annotate(
        total_documentos=Count("documento", distinct=True)
    ).order_by("nome")

    if termo_busca:
        departamentos = departamentos.filter(nome__icontains=termo_busca)

    if status == "ativos":
        departamentos = departamentos.filter(ativo=True)
    elif status == "inativos":
        departamentos = departamentos.filter(ativo=False)

    page_obj, pagination_state = paginate_with_show_all(
        request,
        departamentos,
        default_per_page=20,
        item_label="departamentos",
    )

    return render(request, "departamentos/listar.html", {
        "departamentos": page_obj,
        "total_departamentos": departamentos.count(),
        "filtros": {
            "q": termo_busca,
            "status": status,
        },
        "pagination_state": pagination_state,
    })


@login_required
def criar_departamento(request):
    _require_perm(request, "departamentos.add_departamento")

    if request.method == "POST":
        form = DepartamentoForm(request.POST)
        if form.is_valid():
            departamento = form.save()
            messages.success(request, f'Departamento "{departamento}" criado com sucesso.')
            return redirect("departamentos:listar")
    else:
        form = DepartamentoForm(initial={"ativo": True})

    return render(request, "departamentos/form.html", {
        "form": form,
        "titulo": "Novo Departamento",
        "subtitulo": "Cadastre um departamento para organizar os documentos.",
        "acao": "Criar Departamento",
    })


@login_required
def editar_departamento(request, departamento_id):
    _require_perm(request, "departamentos.change_departamento")
    departamento = get_object_or_404(Departamento, id=departamento_id)

    if request.method == "POST":
        form = DepartamentoForm(request.POST, instance=departamento)
        if form.is_valid():
            departamento = form.save()
            messages.success(request, f'Departamento "{departamento}" atualizado com sucesso.')
            return redirect("departamentos:listar")
    else:
        form = DepartamentoForm(instance=departamento)

    return render(request, "departamentos/form.html", {
        "form": form,
        "departamento": departamento,
        "titulo": "Editar Departamento",
        "subtitulo": "Atualize os dados do departamento selecionado.",
        "acao": "Salvar Alterações",
    })


@login_required
def excluir_departamento(request, departamento_id):
    _require_perm(request, "departamentos.delete_departamento")
    departamento = get_object_or_404(
        Departamento.objects.annotate(total_documentos=Count("documento", distinct=True)),
        id=departamento_id,
    )

    if request.method == "POST":
        with transaction.atomic():
            documentos_afetados = Documento.objects.filter(departamento=departamento).update(departamento=None)
            descricao = str(departamento)
            departamento.delete()

        messages.success(
            request,
            f'Departamento "{descricao}" excluído. {documentos_afetados} documento(s) ficaram sem departamento.',
        )
        return redirect("departamentos:listar")

    return render(request, "departamentos/confirmar_exclusao.html", {
        "departamento": departamento,
        "documentos_afetados": departamento.total_documentos,
    })
