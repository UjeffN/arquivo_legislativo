"""
Serviço de OCR para extração de texto de documentos PDF
"""

import os
import re
from datetime import datetime
from typing import Dict, Optional, Tuple
import logging

# Importar bibliotecas de PDF
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logging.warning("pdfplumber não instalado. Usando modo placeholder.")

try:
    import pytesseract
    from PIL import Image
    import io
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logging.warning("pytesseract não instalado. OCR de imagens não disponível.")

logger = logging.getLogger(__name__)


class OCRProcessor:
    """Processador de OCR para documentos PDF"""

    def __init__(self):
        self.tipos_documento = [
            'ATA', 'ACORDO', 'CONVITE', 'MEMORANDO', 'OFICIO', 'REQUERIMENTO',
            'PORTARIA', 'PRESTAÇÃO', 'PROCESSO', 'RELATÓRIO', 'TERMO', 'ATO',
            'CONVÊNIO', 'DENÚNCIA', 'INSTRUÇÃO', 'PARECER', 'INQUÉRITO',
            'AJUSTAMENTO', 'AUDIÊNCIA', 'COMISSÃO', 'DISCIPLINAR', 'MESA'
        ]

        # Mapeamento de tipos para IDs (baseado nos valores do select)
        self.mapeamento_tipos = {
            'ATA': 'ATA de registro das ocorrências de uma reunião',
            'ACORDO': 'Acordo de Cooperação Técnica',
            'AUDIÊNCIA': 'Ata de Audiência Pública',
            'ATO': 'Ato da Presidência',
            'MESA': 'Atos da Mesa Diretora',
            'CONVITE': 'Convite',
            'CONVÊNIO': 'Convênio',
            'DENÚNCIA': 'Denúncia',
            'INSTRUÇÃO': 'Instrução Normativa',
            'MEMORANDO': 'Memorando',
            'OFICIO': 'Oficio',
            'OFÍCIO': 'Oficio',
            'OUTROS': 'Outros',
            'PARECER': 'Parecer Prévio - Tribunal de Contas dos Municípios',
            'PORTARIA INTERNA': 'Portaria Interna de Unidade Administrativa',
            'PORTARIA EXECUTIVO': 'Portaria do Poder Executivo',
            'PORTARIA CMP': 'Portarias da CMP',
            'PRESTAÇÃO': 'Prestação de Contas',
            'PROCESSO': 'Processo Disciplinar - CEDP',
            'RELATÓRIO': 'Relatório Comissão Parlamentar de Inquérito - CPI',
            'COMISSÃO': 'Relatório da Comissão de Assuntos Relevantes',
            'REQUERIMENTO': 'Requerimento',
            'TERMO': 'Termo de Ajustamento de Conduta',
            'AJUSTAMENTO': 'Termo de Ajustamento de Gestão'
        }

    def extrair_texto_pdf(self, caminho_arquivo: str) -> str:
        """
        Extrai texto de um arquivo PDF usando pdfplumber e OCR

        Args:
            caminho_arquivo: Caminho do arquivo PDF

        Returns:
            Texto extraído do documento
        """
        try:
            logger.info(f"Processando OCR do arquivo: {caminho_arquivo}")

            texto_extraido = ""

            # Método 1: Tentar extrair texto diretamente com pdfplumber
            if PDFPLUMBER_AVAILABLE:
                try:
                    with pdfplumber.open(caminho_arquivo) as pdf:
                        for pagina in pdf.pages:
                            texto_pagina = pagina.extract_text()
                            if texto_pagina:
                                texto_extraido += texto_pagina + "\n"

                    if texto_extraido.strip():
                        logger.info(f"Texto extraído com pdfplumber: {len(texto_extraido)} caracteres")
                        return texto_extraido

                except Exception as e:
                    logger.warning(f"Erro ao extrair texto com pdfplumber: {e}")

            # Método 2: Tentar OCR das imagens se pdfplumber não funcionar
            if TESSERACT_AVAILABLE and texto_extraido.strip() == "":
                try:
                    texto_extraido = self._extrair_com_ocr_imagem(caminho_arquivo)
                    if texto_extraido.strip():
                        logger.info(f"Texto extraído com OCR: {len(texto_extraido)} caracteres")
                        return texto_extraido

                except Exception as e:
                    logger.warning(f"Erro ao extrair texto com OCR: {e}")

            # Método 3: Retornar placeholder se nada funcionar
            if not texto_extraido.strip():
                logger.warning("Não foi possível extrair texto.")
                texto_extraido = ""

            return texto_extraido

        except Exception as e:
            logger.error(f"Erro ao processar OCR: {e}")
            return ""

    def _extrair_com_ocr_imagem(self, caminho_arquivo: str) -> str:
        """Extrai texto usando OCR das imagens do PDF"""
        if not PDFPLUMBER_AVAILABLE or not TESSERACT_AVAILABLE:
            return ""

        texto_extraido = ""

        try:
            with pdfplumber.open(caminho_arquivo) as pdf:
                for pagina_num, pagina in enumerate(pdf.pages):
                    # Converter página para imagem
                    img = pagina.to_image()

                    pil_img = img.original
                    try:
                        # Garantir um modo compatível com o Tesseract
                        if getattr(pil_img, 'mode', None) not in (None, 'RGB'):
                            pil_img = pil_img.convert('RGB')
                    except Exception:
                        pass

                    # Fazer OCR direto na imagem PIL
                    texto_pagina = pytesseract.image_to_string(
                        pil_img,
                        lang='por'  # Português
                    )

                    if texto_pagina.strip():
                        texto_extraido += f"--- Página {pagina_num + 1} ---\n"
                        texto_extraido += texto_pagina + "\n"

        except Exception as e:
            logger.error(f"Erro no OCR da imagem: {e}")

        return texto_extraido

    def _gerar_texto_placeholder(self, caminho_arquivo: str) -> str:
        """Gera texto placeholder para demonstração"""
        nome_arquivo = os.path.basename(caminho_arquivo)
        return f"""
        CONTEÚDO EXTRAÍDO DO ARQUIVO: {nome_arquivo}

        PORTARIA Nº 404/2024

        O PREFEITO MUNICIPAL DE PARAUAPEBAS, ESTADO DO PARÁ, no uso de suas atribuições legais,

        CONSIDERANDO as necessidades de serviços administrativos;

        RESOLVE:

        Art. 1º - Autorizar a contratação de serviços especializados.

        Art. 2º - Esta portaria entra em vigor na data de sua publicação.

        Parauapebas/PA, 05 de agosto de 2024.

        PREFEITO
        """

    def analisar_documento(self, texto: str) -> Dict:
        """
        Analisa o texto extraído e identifica informações do documento

        Args:
            texto: Texto extraído do documento

        Returns:
            Dicionário com informações extraídas
        """
        informacoes = {
            'tipo_documento': None,
            'numero_documento': None,
            'ano_documento': None,
            'data_documento': None,
            'assunto': None,
            'departamento': None,
            'confianca': 0.0
        }

        try:
            # Extrair tipo de documento
            informacoes['tipo_documento'] = self._extrair_tipo_documento(texto)

            # Extrair número e ano
            numero, ano = self._extrair_numero_ano(texto)
            informacoes['numero_documento'] = numero
            informacoes['ano_documento'] = ano

            # Extrair data
            informacoes['data_documento'] = self._extrair_data(texto)

            # Extrair assunto
            informacoes['assunto'] = self._extrair_assunto(texto)

            # Calcular confiança
            informacoes['confianca'] = self._calcular_confianca(informacoes)

        except Exception as e:
            logger.error(f"Erro ao analisar documento: {e}")

        return informacoes

    def _extrair_tipo_documento(self, texto: str) -> Optional[str]:
        """Extrai o tipo de documento do texto"""
        texto_upper = texto.upper()

        # Padrões específicos para identificar tipos
        padroes = [
            # Portarias (prioridade alta)
            (r'PORTARIA.*INTERNA|PORTARIA.*UNIDADE', 'PORTARIA INTERNA'),
            (r'PORTARIA.*EXECUTIVO|PORTARIA.*PREFEITO', 'PORTARIA EXECUTIVO'),
            (r'PORTARIA.*CMP|PORTARIA.*CAMARA', 'PORTARIA CMP'),
            (r'PORTARIA', 'PORTARIA'),

            # Prestação de Contas
            (r'PRESTAÇÃO.*CONTAS|PRESTACAO.*CONTAS', 'PRESTAÇÃO'),

            # Processos
            (r'PROCESSO.*DISCIPLINAR|PROCESSO.*CEDP', 'PROCESSO'),

            # Relatórios
            (r'RELATÓRIO.*CPI|RELATORIO.*CPI', 'RELATÓRIO'),
            (r'RELATÓRIO.*COMISSÃO|RELATORIO.*COMISSAO', 'COMISSÃO'),
            (r'RELATÓRIO|RELATORIO', 'RELATÓRIO'),

            # Atas
            (r'ATA.*REUNIÃO|ATA.*OCORRÊNCIA', 'ATA'),
            (r'ATA.*AUDIÊNCIA|ATA.*AUDIENCIA', 'AUDIÊNCIA'),
            (r'ATA', 'ATA'),

            # Termos
            (r'TERMO.*AJUSTAMENTO.*CONDUTA', 'TERMO'),
            (r'TERMO.*AJUSTAMENTO.*GESTÃO|TERMO.*AJUSTAMENTO.*GESTAO', 'AJUSTAMENTO'),
            (r'TERMO', 'TERMO'),

            # Outros tipos
            (r'ACORDO.*COOPERAÇÃO|ACORDO.*COOPERACAO', 'ACORDO'),
            (r'INSTRUÇÃO.*NORMATIVA|INSTRUCAO.*NORMATIVA', 'INSTRUÇÃO'),
            (r'PARECER.*TCM|PARECER.*TRIBUNAL', 'PARECER'),
            (r'CONVÊNIO|CONVENIO', 'CONVÊNIO'),
            (r'DENÚNCIA|DENUNCIA', 'DENÚNCIA'),
            (r'ATO.*PRESIDÊNCIA|ATO.*PRESIDENCIA', 'ATO'),
            (r'ATOS.*MESA.*DIRETORA', 'MESA'),
            (r'COMISSÃO.*PARLAMENTAR.*INQUÉRITO', 'RELATÓRIO'),
            (r'COMISSÃO.*ASSUNTOS.*RELEVANTES', 'COMISSÃO'),
            (r'INQUÉRITO|INQUERITO', 'INQUÉRITO'),
            (r'AJUSTAMENTO.*GESTÃO|AJUSTAMENTO.*GESTAO', 'AJUSTAMENTO'),
            (r'AJUSTAMENTO.*CONDUTA', 'TERMO'),
            (r'MEMORANDO', 'MEMORANDO'),
            (r'OFÍCIO|OFICIO', 'OFICIO'),
            (r'REQUERIMENTO', 'REQUERIMENTO'),
            (r'CONVITE', 'CONVITE'),
        ]

        # Verificar padrões em ordem de prioridade
        for padrao, tipo in padroes:
            match = re.search(padrao, texto_upper)
            if match:
                return tipo

        # Se não encontrou nenhum padrão específico, busca por palavras-chave
        for tipo in self.tipos_documento:
            if tipo in texto_upper:
                return tipo

        return None

    def _extrair_numero_ano(self, texto: str) -> Tuple[Optional[str], Optional[int]]:
        """Extrai número e ano do documento"""

        # Padrão: PORTARIA Nº 404/2024
        padrao1 = r'Nº\s*(\d+)\/(\d{4})'
        match = re.search(padrao1, texto, re.IGNORECASE)

        if match:
            return match.group(1), int(match.group(2))

        # Padrão alternativo: 404/2024
        padrao2 = r'(\d+)\/(\d{4})'
        matches = re.findall(padrao2, texto)

        if matches:
            return matches[0][0], int(matches[0][1])

        return None, None

    def _extrair_data(self, texto: str) -> Optional[str]:
        """Extrai data do documento"""

        # Padrão: Parauapebas/PA, 05 de agosto de 2024
        padrao1 = r'(\d{1,2})\s+de\s+(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})'
        match = re.search(padrao1, texto, re.IGNORECASE)

        if match:
            dia = match.group(1).zfill(2)
            mes = self._mes_para_numero(match.group(2))
            ano = match.group(3)
            return f"{dia}/{mes}/{ano}"

        # Padrão: 05/08/2024
        padrao2 = r'(\d{2})\/(\d{2})\/(\d{4})'
        match = re.search(padrao2, texto)

        if match:
            return f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

        return None

    def _mes_para_numero(self, mes: str) -> str:
        """Converte nome do mês para número"""
        meses = {
            'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
            'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
            'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
        }
        return meses.get(mes.lower(), '01')

    def _extrair_assunto(self, texto: str) -> Optional[str]:
        """Extrai assunto do documento"""

        # Procura por palavras-chave que indicam assunto
        palavras_chave = [
            'RESOLVE:', 'CONSIDERANDO:', 'AUTORIZAR', 'CONTRATAR', 'NOMEAR',
            'DISPÕE', 'ESTABELECE', 'REGULAMENTA', 'APROVA'
        ]

        linhas = texto.split('\n')
        for i, linha in enumerate(linhas):
            for palavra in palavras_chave:
                if palavra in linha.upper():
                    # Retorna a linha e a próxima linha como assunto
                    assunto = linha.strip()
                    if i + 1 < len(linhas):
                        assunto += " " + linhas[i + 1].strip()
                    return assunto[:200]  # Limita a 200 caracteres

        return None

    def _calcular_confianca(self, informacoes: Dict) -> float:
        """Calcula a confiança da extração"""

        pontos = 0
        total = 5

        if informacoes['tipo_documento']:
            pontos += 1

        if informacoes['numero_documento']:
            pontos += 1

        if informacoes['ano_documento']:
            pontos += 1

        if informacoes['data_documento']:
            pontos += 1

        if informacoes['assunto']:
            pontos += 1

        return (pontos / total) * 100


# Instância global do processador OCR
ocr_processor = OCRProcessor()
