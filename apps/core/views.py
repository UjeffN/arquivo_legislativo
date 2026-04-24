"""
Views do app Core
"""
from django.shortcuts import render


def home(request):
    """Página principal do sistema"""
    return render(request, 'core/home.html')
