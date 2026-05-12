"""
Views do app Caixas
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db import transaction
from apps.core.pagination import paginate_with_show_all
from .models import Caixa
from .forms import CaixaForm
from apps.documentos.models import Documento, LogAuditoria


def _require_perm(request, perm):
    if not request.user.has_perm(perm):
        raise PermissionDenied


@login_required
def listar_caixas(request):
    """Lista todas as caixas"""
    _require_perm(request, 'caixas.view_caixa')
    from apps.departamentos.models import Departamento

    caixas_qs = Caixa.objects.all()

    # Filtros
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    depto_id = request.GET.get('departamento', '')

    if search:
        caixas_qs = caixas_qs.filter(
            models.Q(numero__icontains=search) |
            models.Q(localizacao_fisica__icontains=search) |
            models.Q(descricao__icontains=search)
        )

    # Adicionar capacidade calculada para cada caixa
    caixas = []
    for caixa in caixas_qs:
        documentos_count = caixa.documento_set.count()
        capacidade = caixa.capacidade_maxima if hasattr(caixa, 'capacidade_maxima') else 100
        if capacidade > 0:
            caixa.capacity_percentage = int((documentos_count / capacidade) * 100)
        else:
            caixa.capacity_percentage = 0
        caixa.documentos_count = documentos_count

        # Aplicar filtro de status após o cálculo
        if status == 'cheia' and caixa.capacity_percentage < 90:
            continue
        if status == 'ativa' and caixa.capacity_percentage >= 90:
            continue

        caixas.append(caixa)

    context = {
        'titulo': 'Gerenciamento de Caixas',
        'caixas': caixas,
        'caixas_ativas': [c for c in caixas if c.capacity_percentage < 90],
        'caixas_cheias': [c for c in caixas if c.capacity_percentage >= 90],
        'total_documentos': sum(c.documentos_count for c in caixas),
        'departamentos': Departamento.objects.all(),
    }

    return render(request, 'caixas/listar.html', context)


@login_required
def historico_movimentacoes(request):
    """Histórico administrativo de movimentações entre caixas."""
    _require_perm(request, 'caixas.view_caixa')
    logs = LogAuditoria.objects.filter(
        models.Q(descricao__startswith='TRANSFERÊNCIA:') |
        models.Q(descricao__startswith='DESVINCULACAO_CAIXA:')
    ).select_related('documento', 'usuario').order_by('-data_hora')

    page_obj, pagination_state = paginate_with_show_all(
        request,
        logs,
        default_per_page=30,
        item_label='eventos',
    )

    context = {
        'titulo': 'Histórico de Movimentações',
        'page_obj': page_obj,
        'logs': page_obj,
        'pagination_state': pagination_state,
    }
    return render(request, 'caixas/historico_movimentacoes.html', context)


@login_required
def criar_caixa(request):
    """Cria uma nova caixa"""
    _require_perm(request, 'caixas.add_caixa')
    if request.method == 'POST':
        form = CaixaForm(request.POST)
        if form.is_valid():
            caixa = form.save()
            messages.success(request, f'Caixa {caixa.numero:04d} criada com sucesso!')
            return redirect('caixas:detalhe_caixa', pk=caixa.pk)
    else:
        form = CaixaForm()

    context = {
        'titulo': 'Criar Nova Caixa',
        'form': form,
        'action': 'Criar'
    }

    return render(request, 'caixas/form_caixa.html', context)


@login_required
def detalhe_caixa(request, pk):
    """Detalhes de uma caixa específica"""
    _require_perm(request, 'caixas.view_caixa')
    caixa = get_object_or_404(Caixa, pk=pk)
    documentos = caixa.documento_set.all().order_by('-data_upload')[:10]

    context = {
        'titulo': f'Detalhes da Caixa {f"{caixa.numero:04d}"}',
        'caixa': caixa,
        'documentos': documentos,
        'total_documentos': caixa.quantidade_documentos,
    }

    return render(request, 'caixas/detalhe_caixa.html', context)


@login_required
def editar_caixa(request, pk):
    """Edita uma caixa existente"""
    _require_perm(request, 'caixas.change_caixa')
    caixa = get_object_or_404(Caixa, pk=pk)

    if request.method == 'POST':
        form = CaixaForm(request.POST, instance=caixa)
        if form.is_valid():
            caixa = form.save()
            messages.success(request, f'Caixa {f"{caixa.numero:04d}"} atualizada com sucesso!')
            return redirect('caixas:detalhe_caixa', pk=caixa.pk)
    else:
        form = CaixaForm(instance=caixa)

    context = {
        'titulo': f'Editar Caixa {f"{caixa.numero:04d}"}',
        'form': form,
        'caixa': caixa,
        'action': 'Editar'
    }

    return render(request, 'caixas/form_caixa.html', context)


@login_required
def imprimir_etiqueta(request, pk):
    """Gera etiqueta para impressão da caixa"""
    _require_perm(request, 'caixas.view_caixa')
    caixa = get_object_or_404(Caixa, pk=pk)

    context = {
        'caixa': caixa,
        'titulo': f'Etiqueta - Caixa {f"{caixa.numero:04d}"}',
    }

    return render(request, 'caixas/imprimir_etiqueta.html', context)


@login_required
def excluir_caixa(request, pk):
    """Exclui caixa com desvinculação prévia dos documentos vinculados."""
    _require_perm(request, 'caixas.delete_caixa')

    caixa = get_object_or_404(Caixa, pk=pk)
    documentos = list(Documento.objects.filter(caixa=caixa).order_by('id'))
    documentos_ids = [doc.id for doc in documentos]

    if request.method == 'GET':
        context = {
            'titulo': f'Confirmar Exclusão da Caixa {caixa.numero:04d}',
            'caixa': caixa,
            'documentos': documentos,
            'total_documentos': len(documentos),
        }
        return render(request, 'caixas/confirmar_exclusao.html', context)

    if request.method != 'POST':
        messages.error(request, 'Método inválido para exclusão de caixa.')
        return redirect('caixas:listar_caixas')

    if request.POST.get('confirmar_exclusao') != '1':
        messages.info(request, 'Exclusão da caixa cancelada.')
        return redirect('caixas:detalhe_caixa', pk=caixa.pk)

    with transaction.atomic():
        for documento in documentos:
            LogAuditoria.objects.create(
                documento=documento,
                usuario=request.user,
                acao='ATUALIZADO',
                descricao=(
                    f'DESVINCULACAO_CAIXA: caixa_id={caixa.id}; '
                    f'caixa_nome="{caixa.nome}"; '
                    f'documento_id={documento.id}; '
                    f'documentos_afetados={documentos_ids}'
                ),
                ip_address=_get_client_ip(request)
            )
            documento.caixa = None
            documento.save(update_fields=['caixa', 'atualizado_em'])
        caixa.delete()

    messages.success(
        request,
        f'Caixa "{caixa.nome}" excluída com sucesso. '
        f'{len(documentos_ids)} documento(s) foram desvinculados sem perda de dados.'
    )

    return redirect('caixas:listar_caixas')


def _get_client_ip(request):
    """Obtém IP do cliente para auditoria."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')
