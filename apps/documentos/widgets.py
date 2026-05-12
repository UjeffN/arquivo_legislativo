"""
Widgets customizados para o app Documentos
"""
from django import forms
from django.urls import reverse_lazy


class DepartamentoAutocompleteWidget(forms.TextInput):
    """
    Widget com autocomplete para campo Departamento
    Permite digitar e buscar automaticamente por nome
    """

    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'form-control departamento-autocomplete',
            'placeholder': 'Digite o nome do departamento...',
            'data-autocomplete-url': reverse_lazy('documentos:departamento_autocomplete')
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    class Media:
        css = {
            'all': ('https://code.jquery.com/ui/1.13.2/themes/base/jquery-ui.css',
                   'documentos/css/departamento_autocomplete.css')
        }
        js = ('https://code.jquery.com/jquery-3.6.0.min.js',
              'https://code.jquery.com/ui/1.13.2/jquery-ui.min.js',
              'documentos/js/departamento_autocomplete.js')
