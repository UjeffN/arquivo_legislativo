"""
Formulários do app Documentos
"""
from pathlib import Path
import re

from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings

from .models import Documento, TipoDocumento
from apps.caixas.models import Caixa


def _get_upload_limits():
    config = getattr(settings, 'ARQUIVO_DIGITAL_CONFIG', {})
    allowed_extensions = tuple(config.get('ALLOWED_EXTENSIONS', ['.pdf']))
    max_upload_size = int(config.get('MAX_UPLOAD_SIZE', 500 * 1024 * 1024))
    return allowed_extensions, max_upload_size


def _validar_arquivo_pdf(arquivo):
    if not arquivo:
        return arquivo

    allowed_extensions, max_upload_size = _get_upload_limits()
    if Path(arquivo.name).suffix.lower() not in allowed_extensions:
        raise ValidationError('Apenas arquivos PDF são permitidos.')

    if arquivo.size > max_upload_size:
        max_mb = max_upload_size // (1024 * 1024)
        raise ValidationError(f'O arquivo não pode ser maior que {max_mb}MB.')

    try:
        header = arquivo.read(1024)
        arquivo.seek(0)
    except Exception:
        header = b''

    if b'%PDF' not in header:
        raise ValidationError('O arquivo enviado não é um PDF válido.')

    return arquivo


def extrair_numero_documento_do_nome(nome):
    """Extrai o número no padrão '<tipo> XXX/AAAA' a partir do nome."""
    if not nome:
        return ''

    match = re.search(r'\b[\wÀ-ÿ]+(?:\s+[\wÀ-ÿ]+)*\s+(\d{1,6}/\d{4})\b', nome, re.IGNORECASE)
    return match.group(1) if match else ''


def preencher_numero_documento_por_nome(cleaned_data):
    numero_documento = (cleaned_data.get('numero_documento') or '').strip()
    if numero_documento:
        cleaned_data['numero_documento'] = numero_documento
        return cleaned_data

    numero_extraido = extrair_numero_documento_do_nome(cleaned_data.get('nome'))
    if numero_extraido:
        cleaned_data['numero_documento'] = numero_extraido

    return cleaned_data


def _resolver_categoria_atual(valor):
    if isinstance(valor, TipoDocumento):
        return valor
    if not valor:
        return None
    try:
        return TipoDocumento.objects.filter(pk=valor).first()
    except (TypeError, ValueError):
        return None


def _queryset_categorias_disponiveis(categoria_atual=None):
    categorias_ativas = TipoDocumento.objects.filter(ativo=True).order_by('nome')
    categoria_atual = _resolver_categoria_atual(categoria_atual)
    if categoria_atual and not categoria_atual.ativo:
        return (categorias_ativas | TipoDocumento.objects.filter(pk=categoria_atual.pk)).distinct()
    return categorias_ativas


def _configurar_campo_categoria(field, categoria_atual=None):
    field.label = 'Categoria do Documento'
    field.help_text = 'Selecione a categoria usada na classificacao do documento.'
    field.queryset = _queryset_categorias_disponiveis(categoria_atual)
    field.empty_label = 'Selecione uma categoria'


class DocumentoUploadForm(forms.ModelForm):
    """Formulário para upload de documento com extração OCR"""

    arquivo_pdf = forms.FileField(
        label="Arquivo PDF",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf',
            'required': True
        }),
        help_text="Selecione o arquivo PDF do documento digitalizado"
    )

    class Meta:
        model = Documento
        fields = [
            'nome', 'assunto', 'tipo_documento', 'departamento',
            'numero_documento', 'data_documento',
            'caixa', 'palavra_chave', 'observacao'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome completo do documento'
            }),
            'assunto': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Assunto ou resumo do documento'
            }),
            'tipo_documento': forms.Select(attrs={
                'class': 'form-select'
            }),
            'departamento': forms.Select(attrs={
                'class': 'form-select select-autocomplete'
            }),
            'numero_documento': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 404/2024'
            }),
                        'data_documento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'caixa': forms.Select(attrs={
                'class': 'form-select select-autocomplete'
            }),
            'palavra_chave': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Palavras-chave para busca'
            }),
            'observacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observações adicionais'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _configurar_campo_categoria(self.fields['tipo_documento'])

        # Listar todas as caixas ordenadas por número
        self.fields['caixa'].queryset = Caixa.objects.all().order_by('numero')

        # Adicionar campos de ajuda
        self.fields['departamento'].required = True
        self.fields['numero_documento'].required = False
        self.fields['numero_documento'].help_text = "Preenchido automaticamente pelo nome quando houver padrão tipo 404/2024; pode ser editado."
        if 'ano_documento' in self.fields:
            self.fields['ano_documento'].help_text = "Ano do documento"
        self.fields['data_documento'].help_text = "Data de emissão do documento"
        self.fields['caixa'].help_text = "Selecione a caixa onde o documento será armazenado"

    def clean_arquivo_pdf(self):
        """Validação do arquivo PDF"""
        return _validar_arquivo_pdf(self.cleaned_data.get('arquivo_pdf'))

    def clean(self):
        """Validação cruzada dos campos"""
        cleaned_data = super().clean()
        preencher_numero_documento_por_nome(cleaned_data)

        if not cleaned_data.get('numero_documento'):
            self.add_error('numero_documento', 'Informe o número do documento ou inclua no nome o padrão 404/2024.')

        data_documento = cleaned_data.get('data_documento')
        ano_documento = cleaned_data.get('ano_documento')
        caixa = cleaned_data.get('caixa')

        # Validar ano vs data
        if data_documento and ano_documento:
            if data_documento.year != ano_documento:
                raise ValidationError('O ano do documento deve coincidir com o ano da data.')

        # Validar data vs caixa
        if caixa and data_documento:
            if data_documento < caixa.data_criacao:
                raise ValidationError('Data do documento não pode ser anterior à data de criação da caixa.')

            if caixa.data_fechamento and data_documento > caixa.data_fechamento:
                raise ValidationError('Data do documento não pode ser posterior à data de fechamento da caixa.')


class DocumentoOCRForm(forms.Form):
    """Formulário para upload inicial com processamento OCR"""

    arquivo_pdf = forms.FileField(
        label="Arquivo PDF",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf',
            'required': True,
            'id': 'arquivo_pdf'
        }),
        help_text="Selecione o arquivo PDF do documento para extração automática de dados"
    )

    def clean_arquivo_pdf(self):
        """Validação do arquivo PDF"""
        return _validar_arquivo_pdf(self.cleaned_data.get('arquivo_pdf'))


class DocumentoConfirmacaoForm(forms.ModelForm):
    """Formulário de confirmação após OCR"""

    arquivo_pdf = forms.FileField(
        label="Arquivo PDF",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf',
            'required': False  # Não obrigatório na confirmação
        }),
        required=False,
        help_text="Arquivo PDF (já carregado)"
    )

    caixa = forms.ModelChoiceField(
        label="Caixa (Opcional)",
        queryset=Caixa.objects.all().order_by('numero'),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select select-autocomplete'
        }),
        help_text="Selecione uma caixa existente ou deixe em branco para escolher pasta"
    )

    pasta_destino = forms.CharField(
        label="Pasta de Destino",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: media/BIBLIOTECA_LEGISLATIVA/Memorando/2024/09_September'
        }),
        required=False,
        help_text="Caminho completo da pasta onde o arquivo será salvo (usado se não selecionar caixa)"
    )

    texto_extraido = forms.CharField(
        label="Texto Extraído (OCR)",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'readonly': True
        }),
        required=False,
        help_text="Texto extraído do documento via OCR (somente leitura)"
    )

    confianca_ocr = forms.IntegerField(
        label="Confiança do OCR (%)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'readonly': True
        }),
        required=False,
        help_text="Nível de confiança da extração automática"
    )

    arquivo_original_name = forms.CharField(
        label="Nome Original",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True
        }),
        required=False,
        help_text="Nome original do arquivo enviado"
    )

    class Meta:
        model = Documento
        fields = [
            'arquivo_pdf', 'nome', 'assunto', 'tipo_documento', 'departamento',
            'numero_documento', 'data_documento',
            'caixa', 'pasta_destino', 'palavra_chave', 'observacao',
            'texto_extraido', 'confianca_ocr', 'arquivo_original_name'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome completo do documento'
            }),
            'assunto': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Assunto ou resumo do documento'
            }),
            'tipo_documento': forms.Select(attrs={
                'class': 'form-select select-autocomplete'
            }),
            'departamento': forms.Select(attrs={
                'class': 'form-select select-autocomplete'
            }),
            'numero_documento': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 404/2024'
            }),
                        'data_documento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'palavra_chave': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Palavras-chave para busca'
            }),
            'observacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observações adicionais'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categoria_atual = self.initial.get('tipo_documento')
        _configurar_campo_categoria(self.fields['tipo_documento'], categoria_atual)

        # Listar todas as caixas ordenadas por número
        self.fields['caixa'].queryset = Caixa.objects.all().order_by('numero')
        self.fields['departamento'].required = True
        self.fields['numero_documento'].required = False
        self.fields['numero_documento'].help_text = "Preenchido automaticamente pelo nome quando houver padrão tipo 404/2024; pode ser editado."

        # Sugerir pasta destino baseado nos dados do documento
        if self.initial.get('departamento') and self.initial.get('tipo_documento') and self.initial.get('data_documento'):
            depto = self.initial.get('departamento')
            tipo = self.initial.get('tipo_documento')
            data = self.initial.get('data_documento')

            # Converter string para date se necessário
            if isinstance(data, str):
                from datetime import datetime
                try:
                    data = datetime.strptime(data, '%Y-%m-%d').date()
                except ValueError:
                    data = None

            if depto and tipo and data and hasattr(data, 'month'):
                # Gerar sugestão de pasta
                import calendar
                depto_nome = str(depto).replace(' ', '_').replace('/', '_')
                tipo_nome = str(tipo).replace(' ', '_').replace('/', '_')
                mes_nome = calendar.month_name[data.month].title()

                pasta_sugerida = f"media/{depto_nome}/{tipo_nome}/{data.year}/{data.month:02d}_{mes_nome}"
                self.fields['pasta_destino'].widget.attrs.update({
                    'placeholder': f'Ex: {pasta_sugerida}',
                    'value': pasta_sugerida
                })

        # Destacar campos preenchidos pelo OCR
        if self.initial.get('ocr_preenchido'):
            campos_ocr = ['nome', 'assunto', 'tipo_documento',
                         'data_documento']  # REMOVIDO: numero_documento

            for campo in campos_ocr:
                if campo in self.fields and self.initial.get(campo):
                    self.fields[campo].widget.attrs.update({
                        'class': 'form-control ocr-preenchido',
                        'title': 'Preenchido automaticamente pelo OCR'
                    })

            # Campos readonly do OCR
            campos_readonly = ['texto_extraido', 'confianca_ocr', 'arquivo_original_name']
            for campo in campos_readonly:
                if campo in self.fields:
                    self.fields[campo].widget.attrs.update({
                        'class': 'form-control ocr-readonly',
                        'title': 'Extraído automaticamente pelo OCR'
                    })

    def clean_arquivo_pdf(self):
        """Validação opcional do arquivo no passo de confirmação."""
        arquivo = self.cleaned_data.get('arquivo_pdf')
        if not arquivo:
            return arquivo
        return _validar_arquivo_pdf(arquivo)

    def clean(self):
        cleaned_data = super().clean()
        preencher_numero_documento_por_nome(cleaned_data)

        if not cleaned_data.get('numero_documento'):
            self.add_error('numero_documento', 'Informe o número do documento ou inclua no nome o padrão 404/2024.')

        return cleaned_data


class DocumentoEditForm(forms.ModelForm):
    """Formulário para edição de documento"""

    class Meta:
        model = Documento
        fields = [
            'nome', 'assunto', 'tipo_documento', 'departamento',
            'numero_documento', 'data_documento',
            'caixa', 'palavra_chave', 'observacao'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome completo do documento'
            }),
            'assunto': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Assunto ou resumo do documento'
            }),
            'tipo_documento': forms.Select(attrs={
                'class': 'form-select'
            }),
            'departamento': forms.Select(attrs={
                'class': 'form-select select-autocomplete'
            }),
            'numero_documento': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 404/2024'
            }),
            'data_documento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'caixa': forms.Select(attrs={
                'class': 'form-select select-autocomplete'
            }),
            'palavra_chave': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Palavras-chave para busca'
            }),
            'observacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observações adicionais'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categoria_atual = self.instance.tipo_documento if self.instance and self.instance.pk else None
        _configurar_campo_categoria(self.fields['tipo_documento'], categoria_atual)

        # Listar todas as caixas ordenadas por número
        self.fields['caixa'].queryset = Caixa.objects.all().order_by('numero')

        # Adicionar campos de ajuda
        self.fields['departamento'].required = True
        self.fields['numero_documento'].required = False
        self.fields['numero_documento'].help_text = "Preenchido automaticamente pelo nome quando houver padrão tipo 404/2024; pode ser editado."
        self.fields['data_documento'].help_text = "Data de emissão do documento"
        self.fields['caixa'].help_text = "Selecione a caixa onde o documento está armazenado"

    def clean(self):
        cleaned_data = super().clean()
        preencher_numero_documento_por_nome(cleaned_data)

        if not cleaned_data.get('numero_documento'):
            self.add_error('numero_documento', 'Informe o número do documento ou inclua no nome o padrão 404/2024.')

        return cleaned_data


class DocumentoPastaForm(forms.Form):
    """Formulário para seleção de pasta de destino"""

    pasta_destino = forms.CharField(
        label="Pasta de Destino",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: media/BIBLIOTECA_LEGISLATIVA/Memorando/2024/09_September'
        }),
        required=True,
        help_text="Caminho completo da pasta onde o arquivo será salvo"
    )

    def clean_pasta_destino(self):
        """Validação da pasta destino"""
        pasta = self.cleaned_data.get('pasta_destino')

        if pasta:
            # Verificar se começa com media/
            if not pasta.startswith('media/'):
                raise ValidationError('A pasta deve começar com "media/"')

            # Verificar caracteres inválidos
            import re
            if re.search(r'[<>:"|?*]', pasta):
                raise ValidationError('A pasta contém caracteres inválidos.')

        return pasta


class CategoriaDocumentoForm(forms.ModelForm):
    class Meta:
        model = TipoDocumento
        fields = ['nome', 'descricao', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Memorando, Resolucao, Contrato',
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descreva quando esta categoria deve ser utilizada.',
            }),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        labels = {
            'nome': 'Nome da Categoria',
            'descricao': 'Descricao',
            'ativo': 'Categoria ativa',
        }
        help_texts = {
            'nome': 'Use um nome curto e claro para a classificacao dos documentos.',
            'descricao': 'Campo opcional para orientar o cadastro e a busca.',
        }

    def clean_nome(self):
        nome = (self.cleaned_data.get('nome') or '').strip()
        if not nome:
            raise ValidationError('Informe o nome da categoria.')

        existente = TipoDocumento.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk)
        if existente.exists():
            categoria = existente.first()
            if categoria.ativo:
                raise ValidationError('Ja existe uma categoria ativa com esse nome.')
            raise ValidationError(
                'Ja existe uma categoria inativa com esse nome. Edite a categoria existente para reativa-la.'
            )
        return nome

    def clean_descricao(self):
        return (self.cleaned_data.get('descricao') or '').strip()
