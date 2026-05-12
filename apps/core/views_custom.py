"""
Views customizadas para o Sistema de Arquivo Digital
"""

from django.shortcuts import redirect
from django.contrib.auth import logout
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

@require_POST
@login_required
def custom_logout(request):
    """
    View customizada de logout que aceita apenas POST
    Redireciona para a página de login após logout
    """
    # Faz o logout do usuário
    logout(request)

    # Redireciona para a página de login
    return redirect('login')
