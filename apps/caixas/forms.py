"""
Formulários do app Caixas
"""
from django import forms
from .models import Caixa


class CaixaForm(forms.ModelForm):
    """Formulário para criação e edição de caixas"""
    
    class Meta:
        model = Caixa
        fields = [
            'nome', 'descricao', 'localizacao_fisica', 'capacidade_maxima'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome da caixa (ex: Documentos Fiscais 2024)'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição detalhada do conteúdo da caixa'
            }),
            'localizacao_fisica': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Estante A, Prateleira 3'
            }),
            'capacidade_maxima': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10000,
                'placeholder': '100'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Adicionar campos de ajuda
        self.fields['nome'].help_text = "Nome descritivo da caixa (opcional)"
        self.fields['descricao'].help_text = "Conteúdo detalhado da caixa"
        self.fields['localizacao_fisica'].help_text = "Onde a caixa está fisicamente armazenada"
        self.fields['capacidade_maxima'].help_text = "Número máximo de documentos que esta caixa pode conter"
