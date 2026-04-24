"""
Serviço para gerenciamento automático de caixas e pastas
"""

import os
import calendar
from datetime import datetime
from django.conf import settings
from django.db import transaction
from apps.caixas.models import Caixa
from apps.documentos.models import TipoDocumento
from apps.departamentos.models import Departamento


class CaixaManager:
    """Gerenciador automático de caixas e pastas"""
    
    def __init__(self):
        self.capacidade_padrao = 100
    
    def criar_ou_obter_caixa(self, departamento, tipo_documento, data_documento):
        """
        Cria ou obtém uma caixa para o documento
        
        Args:
            departamento: Departamento do documento
            tipo_documento: Tipo do documento
            data_documento: Data do documento (datetime.date)
            
        Returns:
            Caixa: Caixa criada ou existente
        """
        ano = data_documento.year
        mes = data_documento.month
        
        # Buscar caixas existentes para o mesmo período
        caixas_existentes = Caixa.objects.filter(
            departamento=departamento,
            tipo_documento=tipo_documento,
            ano=ano,
            mes=mes
        ).order_by('numero_caixa')
        
        # Procurar caixa com espaço disponível
        for caixa in caixas_existentes:
            if not caixa.esta_cheia:
                return caixa
        
        # Criar nova caixa
        numero_caixa = caixas_existentes.count() + 1
        
        caixa = Caixa.objects.create(
            departamento=departamento,
            tipo_documento=tipo_documento,
            ano=ano,
            mes=mes,
            numero_caixa=numero_caixa,
            capacidade_maxima=self.capacidade_padrao,
            status='ABERTA'
        )
        
        # Criar estrutura de pastas
        self.criar_estrutura_pastas(caixa)
        
        return caixa
    
    def criar_estrutura_pastas(self, caixa):
        """
        Cria a estrutura de pastas para a caixa
        
        Args:
            caixa: Objeto Caixa
        """
        caminho_base = settings.MEDIA_ROOT
        caminho_caixa = os.path.join(caminho_base, caixa.gerar_caminho_pasta())
        
        try:
            # Criar diretório da caixa se não existir
            os.makedirs(caminho_caixa, exist_ok=True)
            
            # Criar arquivo README com informações da caixa
            readme_path = os.path.join(caminho_caixa, 'README.txt')
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(self.gerar_readme_caixa(caixa))
            
            # Criar arquivo de índice
            indice_path = os.path.join(caminho_caixa, 'INDICE.txt')
            with open(indice_path, 'w', encoding='utf-8') as f:
                f.write("ÍNDICE DE DOCUMENTOS\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Código: {caixa.codigo}\n")
                f.write(f"Departamento: {caixa.departamento.nome}\n")
                f.write(f"Tipo: {caixa.tipo_documento.nome}\n")
                f.write(f"Período: {calendar.month_name[caixa.mes].title()}/{caixa.ano}\n")
                f.write(f"Capacidade: {caixa.capacidade_maxima} documentos\n")
                f.write(f"Status: {caixa.status}\n")
                f.write(f"Criada em: {caixa.data_criacao.strftime('%d/%m/%Y')}\n\n")
                f.write("DOCUMENTOS:\n")
                f.write("-" * 50 + "\n")
            
            return True
            
        except Exception as e:
            print(f"Erro ao criar estrutura de pastas para caixa {caixa.codigo}: {str(e)}")
            return False
    
    def gerar_readme_caixa(self, caixa):
        """Gera conteúdo README para a caixa"""
        mes_nome = calendar.month_name[caixa.mes].title()
        
        readme = f"""
CAIXA DE ARQUIVO DIGITAL
{'=' * 50}

INFORMAÇÕES DA CAIXA:
- Código: {caixa.codigo}
- Departamento: {caixa.departamento.nome}
- Tipo de Documento: {caixa.tipo_documento.nome}
- Período: {mes_nome}/{caixa.ano}
- Capacidade Máxima: {caixa.capacidade_maxima} documentos
- Status: {caixa.status}
- Data de Criação: {caixa.data_criacao.strftime('%d/%m/%Y')}

DESCRIÇÃO COMPLETA:
{caixa.descricao_completa}

LOCALIZAÇÃO FÍSICA:
{caixa.localizacao_fisica or 'Não definida'}

OBSERVAÇÕES:
{caixa.observacao or 'Nenhuma observação'}

ESTRUTURA DE PASTAS:
- Esta pasta contém todos os documentos da caixa {caixa.codigo}
- Cada documento é nomeado seguindo o padrão: TIPO_ANO_MES_SEQUENCIAL.pdf
- Exemplo: MEMORANDO_2024_01_001.pdf

INSTRUÇÕES:
1. Mantenha os documentos organizados
2. Não ultrapasse a capacidade máxima
3. Atualize o índice ao adicionar novos documentos
4. Feche a caixa quando atingir a capacidade máxima

---
Sistema de Arquivo Digital - Câmara Municipal de Parauapebas
Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
"""
        return readme
    
    def gerar_nome_arquivo(self, documento, caixa):
        """
        Gera nome padronizado para o arquivo
        
        Args:
            documento: Objeto Documento
            caixa: Objeto Caixa
            
        Returns:
            str: Nome do arquivo padronizado
        """
        # Extrair sigla do tipo
        tipo_sigla = caixa.tipo_documento.nome.split()[0].upper()
        
        # Contar documentos na caixa para gerar sequencial
        sequencial = caixa.quantidade_documentos + 1
        
        # Formatar: TIPO_YYYY_MM_XXX.pdf
        nome_arquivo = f"{tipo_sigla}_{caixa.ano}_{caixa.mes:02d}_{sequencial:03d}.pdf"
        
        return nome_arquivo
    
    def mover_arquivo_para_caixa(self, arquivo_temp, caixa, nome_arquivo):
        """
        Move arquivo para a pasta da caixa
        
        Args:
            arquivo_temp: Caminho temporário do arquivo
            caixa: Objeto Caixa
            nome_arquivo: Nome padronizado do arquivo
            
        Returns:
            str: Caminho final do arquivo
        """
        caminho_base = settings.MEDIA_ROOT
        caminho_caixa = os.path.join(caminho_base, caixa.gerar_caminho_pasta())
        caminho_final = os.path.join(caminho_caixa, nome_arquivo)
        
        try:
            # Mover arquivo
            import shutil
            shutil.move(arquivo_temp, caminho_final)
            
            # Atualizar índice
            self.atualizar_indice_caixa(caixa, nome_arquivo)
            
            return caminho_final
            
        except Exception as e:
            print(f"Erro ao mover arquivo para caixa {caixa.codigo}: {str(e)}")
            return arquivo_temp
    
    def atualizar_indice_caixa(self, caixa, nome_arquivo):
        """
        Atualiza o arquivo de índice da caixa
        
        Args:
            caixa: Objeto Caixa
            nome_arquivo: Nome do arquivo adicionado
        """
        caminho_base = settings.MEDIA_ROOT
        caminho_caixa = os.path.join(caminho_base, caixa.gerar_caminho_pasta())
        indice_path = os.path.join(caminho_caixa, 'INDICE.txt')
        
        try:
            with open(indice_path, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                f.write(f"{timestamp} - {nome_arquivo}\n")
                
        except Exception as e:
            print(f"Erro ao atualizar índice da caixa {caixa.codigo}: {str(e)}")
    
    def listar_estrutura_pastas(self, departamento=None):
        """
        Lista a estrutura de pastas existente
        
        Args:
            departamento: Filtro por departamento (opcional)
            
        Returns:
            list: Lista de pastas organizadas
        """
        caminho_base = settings.MEDIA_ROOT
        estrutura = []
        
        if departamento:
            caminho_depto = os.path.join(caminho_base, f"{departamento.sigla}_{departamento.nome.replace(' ', '_')}")
            if os.path.exists(caminho_depto):
                estrutura = self._listar_pastas_recursivo(caminho_depto)
        else:
            if os.path.exists(caminho_base):
                estrutura = self._listar_pastas_recursivo(caminho_base)
        
        return estrutura
    
    def _listar_pastas_recursivo(self, caminho, nivel=0):
        """Lista pastas recursivamente com indentação"""
        pastas = []
        try:
            itens = sorted(os.listdir(caminho))
            for item in itens:
                caminho_completo = os.path.join(caminho, item)
                if os.path.isdir(caminho_completo):
                    indent = "  " * nivel
                    pastas.append(f"{indent}📁 {item}")
                    pastas.extend(self._listar_pastas_recursivo(caminho_completo, nivel + 1))
                else:
                    indent = "  " * nivel
                    pastas.append(f"{indent}📄 {item}")
        except PermissionError:
            pass
        
        return pastas
    
    def fechar_caixa(self, caixa):
        """
        Fecha uma caixa automaticamente
        
        Args:
            caixa: Objeto Caixa
        """
        if caixa.esta_cheia:
            caixa.status = 'FECHADA'
            caixa.data_fechamento = datetime.now().date()
            caixa.save()
            
            # Criar próxima caixa automaticamente
            proxima_caixa = self.criar_proxima_caixa(caixa)
            if proxima_caixa:
                print(f"Nova caixa criada automaticamente: {proxima_caixa.codigo}")
    
    def criar_proxima_caixa(self, caixa):
        """
        Cria a próxima caixa sequencial
        
        Args:
            caixa: Caixa atual
            
        Returns:
            Caixa: Nova caixa criada ou None
        """
        try:
            numero_caixa = caixa.numero_caixa + 1
            
            nova_caixa = Caixa.objects.create(
                departamento=caixa.departamento,
                tipo_documento=caixa.tipo_documento,
                ano=caixa.ano,
                mes=caixa.mes,
                numero_caixa=numero_caixa,
                capacidade_maxima=self.capacidade_padrao,
                status='ABERTA'
            )
            
            # Criar estrutura de pastas
            self.criar_estrutura_pastas(nova_caixa)
            
            return nova_caixa
            
        except Exception as e:
            print(f"Erro ao criar próxima caixa: {str(e)}")
            return None


# Instância global do gerenciador
caixa_manager = CaixaManager()
