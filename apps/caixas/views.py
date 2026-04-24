"""
Views do app Caixas
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Caixa
from .forms import CaixaForm


@login_required
def listar_caixas(request):
    """Lista todas as caixas"""
    caixas = Caixa.objects.all()
    
    context = {
        'titulo': 'Gerenciamento de Caixas',
        'caixas': caixas,
    }
    
    return render(request, 'caixas/listar_caixas.html', context)


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
