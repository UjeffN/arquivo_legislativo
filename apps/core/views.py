"""
Views do app Core
"""
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from apps.documentos.models import Documento, TipoDocumento, LogAuditoria
from apps.caixas.models import Caixa
from apps.departamentos.models import Departamento
from django.db.models import Sum, F, ExpressionWrapper, FloatField


def home(request):
    """Página principal do sistema com estatísticas reais"""
    hoje = timezone.now()
    inicio_dia = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = inicio_dia - timedelta(days=hoje.weekday())
    inicio_mes = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Estatísticas de Documentos
    total_documentos = Documento.objects.count()
    documentos_mes = Documento.objects.filter(data_upload__gte=inicio_mes).count()
    documentos_semana = Documento.objects.filter(data_upload__gte=inicio_semana).count()
    uploads_hoje = Documento.objects.filter(data_upload__gte=inicio_dia).count()
    
    # Estatísticas de Caixas
    total_caixas = Caixa.objects.count()
    caixas_novas = Caixa.objects.filter(criado_em__gte=inicio_mes).count()
    
    # Percentual de Ocupação das Caixas
    capacidade_total = Caixa.objects.aggregate(total=Sum('capacidade_maxima'))['total'] or 0
    documentos_em_caixas = Documento.objects.filter(caixa__isnull=False).count()
    caixas_ocupacao = (documentos_em_caixas / capacidade_total * 100) if capacidade_total > 0 else 0
    
    # Estatísticas de Departamentos e Tipos
    total_departamentos = Departamento.objects.count()
    total_tipos = TipoDocumento.objects.count()
    
    # OCR Stats
    ocr_processados = Documento.objects.filter(ocr_processado=True).count()
    ocr_percentual = (ocr_processados / total_documentos * 100) if total_documentos > 0 else 0

    # Atividade Recente (Misturando Logs de Auditoria)
    recent_logs = LogAuditoria.objects.all().order_by('-id')[:10]
    
    atividades = []
    for log in recent_logs:
        icon = 'fa-info-circle'
        color = 'gray'
        
        if log.acao == 'CRIAÇÃO':
            icon = 'fa-plus-circle'
            color = 'green'
        elif log.acao == 'EDIÇÃO':
            icon = 'fa-edit'
            color = 'blue'
        elif log.acao == 'VISUALIZADO':
            icon = 'fa-eye'
            color = 'purple'
        elif log.acao == 'EXCLUSÃO':
            icon = 'fa-trash'
            color = 'red'
            
        atividades.append({
            'titulo': log.acao.title(),
            'descricao': log.descricao,
            'data': log.documento.data_upload if log.documento else timezone.now(), # Fallback se necessário
            'icon': icon,
            'color': color
        })
    
    # Se não houver logs suficientes, complementar com documentos recentes
    if len(atividades) < 3:
        recent_docs = Documento.objects.all().order_by('-data_upload')[:5]
        for doc in recent_docs:
            atividades.append({
                'titulo': 'Upload',
                'descricao': f'Documento: {doc.numero_formatado}',
                'data': doc.data_upload,
                'icon': 'fa-upload',
                'color': 'blue'
            })

    atividades = atividades[:6] # Top 6 atividades

    context = {
        'total_documentos': total_documentos,
        'documentos_mes_count': documentos_mes,
        'documentos_semana_count': documentos_semana,
        'uploads_hoje': uploads_hoje,
        'total_caixas': total_caixas,
        'caixas_novas_count': caixas_novas,
        'caixas_ocupacao': round(caixas_ocupacao, 1),
        'total_departamentos': total_departamentos,
        'total_tipos': total_tipos,
        'ocr_processados': ocr_processados,
        'ocr_percentual': round(ocr_percentual, 1),
        'atividades': atividades,
    }
    
    return render(request, 'admin/home.html', context)
