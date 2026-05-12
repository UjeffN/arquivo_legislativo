"""
Serviços de Download em Lote - Sistema de Arquivo Digital
"""

import os
import zipfile
from datetime import datetime
from pathlib import Path
from django.conf import settings
from .models import LogAuditoria


class DownloadLoteService:
    """
    Serviço para download de documentos em lote
    """

    def __init__(self):
        self.temp_dir = Path(settings.BASE_DIR) / 'temp' / 'downloads'
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = 300  # 5 minutos

    def criar_zip_documentos(self, documentos, nome_arquivo=None, usuario=None):
        """
        Cria um arquivo ZIP com os documentos selecionados

        Args:
            documentos: QuerySet ou lista de objetos Documento
            nome_arquivo: Nome personalizado para o arquivo ZIP
            usuario: Objeto User para validação de permissões

        Returns:
            dict: Dicionário com informações do download
        """
        if not documentos:
            raise ValueError("Nenhum documento selecionado")

        # Higiene contínua dos temporários
        self.limpar_arquivos_temporarios(idade_horas=24)

        # Validar permissões de acesso
        if usuario:
            documentos_validados = []
            for doc in documentos:
                if self._validar_permissao_acesso(doc, usuario):
                    documentos_validados.append(doc)
                else:
                    # Log de tentativa de acesso negado
                    LogAuditoria.objects.create(
                        documento=doc,
                        usuario=usuario,
                        acao=LogAuditoria.Acao.ACESSO_NEGADO_DOWNLOAD,
                        descricao=f'Acesso negado ao documento "{doc.nome}" em download em lote',
                        ip_address=getattr(usuario, 'ip_address', '0.0.0.0')
                    )
            documentos = documentos_validados

            if not documentos:
                raise ValueError("Nenhum documento com permissão de acesso")

        # Gerar nome do arquivo ZIP padronizado
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        quantidade = len(documentos)

        if nome_arquivo:
            # Limpar nome do arquivo
            nome_arquivo = nome_arquivo.replace(' ', '_').replace('/', '_').replace('\\', '_')
            nome_arquivo_zip = f"{nome_arquivo}_{quantidade}docs_{timestamp}.zip"
        else:
            nome_arquivo_zip = f"download_lote_{quantidade}docs_{timestamp}.zip"

        # Caminho completo do arquivo ZIP
        caminho_zip = self.temp_dir / nome_arquivo_zip

        # Estatísticas do processamento
        stats = {
            'total_documentos': len(documentos),
            'arquivos_processados': 0,
            'arquivos_ignorados': 0,
            'erros': [],
            'tamanho_total': 0,
            'nome_zip': nome_arquivo_zip,
            'caminho_zip': str(caminho_zip)
        }

        # Criar arquivo ZIP com tratamento de erros
        try:
            with zipfile.ZipFile(caminho_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
                for documento in documentos:
                    try:
                        field = documento.arquivo_pdf
                        if field and getattr(field, 'name', None):
                            # Validar integridade do arquivo
                            if self._validar_arquivo(field):
                                # Nome do arquivo no ZIP: usar nome original do documento
                                nome_original = documento.nome or f"documento_{documento.id}"
                                nome_arquivo_zip_interno = f"{self._sanitizar_nome_arquivo(nome_original)}.pdf"

                                # Adicionar arquivo ao ZIP (compatível com qualquer Storage)
                                try:
                                    zip_file.writestr(nome_arquivo_zip_interno, self._read_fieldfile_bytes(field))
                                except Exception:
                                    stats['arquivos_ignorados'] += 1
                                    stats['erros'].append(f"Arquivo não encontrado: {documento.nome}")
                                    continue

                                # Atualizar estatísticas
                                stats['arquivos_processados'] += 1
                                try:
                                    stats['tamanho_total'] += int(field.size or 0)
                                except Exception:
                                    pass

                                # Adicionar arquivo de metadados
                                metadados = self._gerar_metadados_documento(documento)
                                if metadados:
                                    nome_metadados = f"{self._sanitizar_nome_arquivo(nome_original)}_metadados.txt"
                                    zip_file.writestr(nome_metadados, metadados)
                            else:
                                stats['arquivos_ignorados'] += 1
                                stats['erros'].append(f"Arquivo corrompido: {documento.nome}")
                        else:
                            stats['arquivos_ignorados'] += 1
                            stats['erros'].append(f"Arquivo não encontrado: {documento.nome}")

                    except Exception as e:
                        stats['arquivos_ignorados'] += 1
                        stats['erros'].append(f"Erro ao processar {documento.nome}: {str(e)}")
                        continue

        except Exception as e:
            # Limpar arquivo ZIP se houver erro
            if caminho_zip.exists():
                caminho_zip.unlink()
            raise ValueError(f"Erro ao criar arquivo ZIP: {str(e)}")

        # Verificar se o ZIP foi criado com sucesso
        if not caminho_zip.exists():
            raise ValueError("Falha ao criar arquivo ZIP")

        # Adicionar informações finais
        stats['tamanho_total_mb'] = round(stats['tamanho_total'] / (1024 * 1024), 2)
        stats['sucesso'] = stats['arquivos_processados'] > 0

        return stats

    def _open_fieldfile(self, field):
        """Abre um FieldFile de forma robusta (field.open -> storage.open)."""
        try:
            field.open('rb')
            return field.file
        except Exception:
            return field.storage.open(field.name, 'rb')

    def _read_fieldfile_bytes(self, field):
        """Lê o conteúdo de um FieldFile com fallback para o storage."""
        # 1) Preferir o arquivo já associado ao FieldFile (em testes pode estar em memória)
        try:
            f = getattr(field, 'file', None)
            if f is not None:
                try:
                    f.seek(0)
                except Exception:
                    pass
                data = f.read()
                if data:
                    return data
        except Exception:
            pass

        # 2) Tentar via open/read do FieldFile
        try:
            field.open('rb')
            try:
                field.seek(0)
            except Exception:
                pass
            data = field.read()
            try:
                field.close()
            except Exception:
                pass
            if data:
                return data
        except Exception:
            pass

        # 3) Fallback para storage
        with field.storage.open(field.name, 'rb') as f:
            return f.read()

    def _gerar_metadados_documento(self, documento):
        """
        Gera texto com metadados do documento

        Args:
            documento: Objeto Documento

        Returns:
            str: Texto com metadados formatados
        """
        metadados = f"""METADADOS DO DOCUMENTO
========================
ID: {documento.id}
Nome: {documento.nome}
Assunto: {documento.assunto[:100]}...
Tipo: {documento.tipo_documento.nome}
Departamento: {documento.departamento.nome if documento.departamento else 'Sem departamento'}
Número: {documento.numero_documento}
Data: {documento.data_documento.strftime('%d/%m/%Y')}
Caixa: {documento.caixa.numero if documento.caixa else 'Não atribuída'}
Data de Upload: {documento.data_upload.strftime('%d/%m/%Y %H:%M:%S')}

OCR Processado: {'Sim' if documento.ocr_processado else 'Não'}
Arquivo: {documento.arquivo_pdf.name if documento.arquivo_pdf else 'N/A'}
"""
        return metadados

    def limpar_arquivos_temporarios(self, idade_horas=24):
        """
        Limpa arquivos ZIP temporários mais antigos que idade_horas

        Args:
            idade_horas: Idade máxima dos arquivos em horas

        Returns:
            dict: Quantidade de arquivos removidos e erros encontrados.
        """
        import time
        agora = time.time()
        limite_segundos = idade_horas * 3600
        removidos = 0
        erros = 0

        for arquivo in self.temp_dir.glob('*.zip'):
            if agora - arquivo.stat().st_mtime > limite_segundos:
                try:
                    arquivo.unlink()
                    removidos += 1
                except OSError:
                    erros += 1

        return {'removidos': removidos, 'erros': erros}

    def agendar_limpeza_automatica(self):
        """
        Agenda limpeza automática de arquivos temporários
        """
        import threading
        import time

        def limpar_periodicamente():
            while True:
                time.sleep(3600)  # Esperar 1 hora
                self.limpar_arquivos_temporarios()

        # Iniciar thread em background
        thread = threading.Thread(target=limpar_periodicamente, daemon=True)
        thread.start()

    def _validar_permissao_acesso(self, documento, usuario):
        """
        Valida se o usuário tem permissão para acessar o documento

        Args:
            documento: Objeto Documento
            usuario: Objeto User

        Returns:
            bool: True se tem permissão, False caso contrário
        """
        if not usuario.is_authenticated:
            return False
        if usuario.is_superuser:
            return True
        return usuario.has_perm('documentos.view_documento')

    def _validar_arquivo(self, caminho_arquivo):
        """
        Valida integridade do arquivo

        Args:
            caminho_arquivo: Caminho completo do arquivo

        Returns:
            bool: True se arquivo é válido, False caso contrário
        """
        try:
            # Aceita tanto path (str) quanto FieldFile/File
            if hasattr(caminho_arquivo, 'open'):
                field = caminho_arquivo
                try:
                    if getattr(field, 'size', 0) == 0:
                        return False
                except Exception:
                    pass
                # Alguns storages/ambientes podem retornar header vazio ou variar o início.
                # Para robustez, buscamos a assinatura %PDF no início do arquivo.
                chunk = self._read_fieldfile_bytes(field)[:1024]
                return b'%PDF' in chunk

            # Fallback: path em disco
            if not os.path.exists(caminho_arquivo):
                return False

            tamanho = os.path.getsize(caminho_arquivo)
            if tamanho == 0:
                return False

            with open(caminho_arquivo, 'rb') as f:
                header = f.read(4)
                if not header.startswith(b'%PDF'):
                    return False

            return True
        except Exception:
            return False

    def _sanitizar_nome_arquivo(self, nome):
        """
        Sanitiza nome de arquivo para uso seguro em sistemas de arquivos

        Args:
            nome: Nome original do arquivo

        Returns:
            str: Nome sanitizado
        """
        import re

        # Remover caracteres inválidos
        nome = re.sub(r'[<>:"/\\|?*]', '_', nome)
        nome = re.sub(r'\s+', '_', nome)

        # Limitar tamanho
        if len(nome) > 100:
            nome = nome[:100]

        # Remover underscores duplicados
        nome = re.sub(r'_+', '_', nome)

        # Remover underscores no início/fim
        nome = nome.strip('_')

        return nome or 'documento'

    def gerar_resumo_download(self, documentos):
        """
        Gera um resumo dos documentos que serão baixados

        Args:
            documentos: QuerySet ou lista de objetos Documento

        Returns:
            dict: Resumo estatístico
        """
        tipos = {}
        departamentos = {}
        total_tamanho = 0
        total_arquivos = 0

        for doc in documentos:
            # Contar por tipo
            tipo_nome = doc.tipo_documento.nome
            tipos[tipo_nome] = tipos.get(tipo_nome, 0) + 1

            # Contar por departamento
            dept_nome = doc.departamento.nome if doc.departamento else 'Sem departamento'
            departamentos[dept_nome] = departamentos.get(dept_nome, 0) + 1

            # Calcular tamanho
            if doc.arquivo_pdf and os.path.exists(doc.arquivo_pdf.path):
                total_tamanho += doc.arquivo_pdf.size
                total_arquivos += 1

        return {
            'total_documentos': len(documentos),
            'total_arquivos': total_arquivos,
            'tamanho_total_mb': round(total_tamanho / (1024 * 1024), 2),
            'tipos': tipos,
            'departamentos': departamentos
        }
