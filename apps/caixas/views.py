"""
Views do app Caixas
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.models.deletion import ProtectedError
from .models import Caixa
from .forms import CaixaForm


@login_required
def listar_caixas(request):
    """Lista todas as caixas"""
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
    
    return render(request, 'admin/caixas_listar.html', context)


@login_required
def criar_caixa(request):
    """Cria uma nova caixa"""
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
    caixa = get_object_or_404(Caixa, pk=pk)
    
    context = {
        'caixa': caixa,
        'titulo': f'Etiqueta - Caixa {f"{caixa.numero:04d}"}',
    }
    
    return render(request, 'caixas/imprimir_etiqueta.html', context)


@login_required
def excluir_caixa(request, pk):
    """Exclui uma caixa quando não há documentos vinculados"""
    if request.method != 'POST':
        messages.error(request, 'Método inválido para exclusão de caixa.')
        return redirect('caixas:listar_caixas')

    caixa = get_object_or_404(Caixa, pk=pk)
    caixa_label = f"{caixa.numero:04d}"

    try:
        caixa.delete()
        messages.success(request, f'Caixa {caixa_label} excluída com sucesso!')
    except ProtectedError:
        messages.error(
            request,
            f'Não é possível excluir a caixa {caixa_label} porque existem documentos vinculados.'
        )

    return redirect('caixas:listar_caixas')
