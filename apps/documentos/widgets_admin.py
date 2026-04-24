"""
Widgets customizados para o Django Admin
"""
from django import forms


class DepartamentoSelectAdmin(forms.Select):
    """Widget customizado para campo Departamento no Admin com autocomplete"""
    
    def __init__(self, attrs=None, choices=()):
        default_attrs = {
            'class': 'form-select select-autocomplete',
            'data-placeholder': 'Digite para buscar departamentos...'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs, choices)
    
    class Media:
        css = {
            'all': ('documentos/css/select_autocomplete.css',)
        }
        js = ('documentos/js/select_autocomplete.js',)
