# Sistema de Arquivo Digital - Câmara Municipal de Parauapebas

## 📋 Contexto do Sistema

O Departamento de Arquivo da Câmara Municipal utilizava anteriormente um sistema para registro e organização de documentos digitalizados. O sistema foi descontinuado após o cancelamento do contrato, impossibilitando o acesso às telas, formulários e estrutura anterior.

Diante disso, surgiu a necessidade de desenvolver um novo sistema interno para:
- Armazenar documentos digitalizados
- Registrar metadados
- Organizar documentos de acordo com o armazenamento físico
- Permitir pesquisa rápida
- Gerar etiquetas para identificação das caixas físicas

## 🎯 Objetivo do Sistema

Criar um Sistema de Arquivo Digital que permita:
- Upload de documentos digitalizados
- Registro de informações do documento
- Organização por caixas físicas
- Pesquisa avançada de documentos
- Impressão de etiqueta para caixas
- Automação do preenchimento de dados usando OCR

## 🔄 Fluxo Atual do Departamento de Arquivo

Fluxo que o setor utiliza atualmente:
1. Escanear o documento
2. Salvar o PDF
3. Subir o documento no sistema
4. Preencher formulário com dados do documento
5. Guardar o documento físico em uma caixa

Organização física atual: Documentos são organizados por **CAIXAS**

## 🚀 Estado Atual do Sistema

### ✅ **FUNCIONALIDADES IMPLEMENTADAS:**
- ✅ Django 4.2+ configurado e funcionando
- ✅ Upload de documentos PDF
- ✅ Registro de metadados
- ✅ Organização por caixas físicas
- ✅ Pesquisa de documentos
- ✅ OCR com Tesseract
- ✅ Geração de etiquetas (ReportLab)
- ✅ Sistema em produção com HTTPS
- ✅ Servidor configurado com Nginx + Gunicorn

### 🌐 **ACESSO AO SISTEMA:**
- **HTTPS Seguro:** `https://192.168.1.20/admin/`
- **Domínio:** `https://sistemas.parauapebas.pa.leg.br/admin/`
- **HTTP:** Redireciona automaticamente para HTTPS

## 🏗️ Estrutura do Projeto (ATUAL)

```
arquivo_digital/
├── manage.py                     # Gerenciador Django
├── requirements.txt              # Dependências Python
├── .env                         # Variáveis de ambiente
├── .gitignore                   # Arquivos ignorados no Git
├── config/                      # Configurações Django
│   ├── settings.py              # Configurações principais
│   ├── urls.py                  # URLs do projeto
│   └── wsgi.py                  # WSGI para produção
├── apps/                        # Aplicações Django
│   ├── core/                    # Sistema principal
│   ├── documentos/              # Gestão de documentos
│   ├── caixas/                  # Gestão de caixas
│   └── departamentos/           # Departamentos
├── services/                    # Lógica de negócio
│   ├── ocr.py                   # Serviço OCR
│   └── caixa_service.py         # Serviço de caixas
├── staticfiles/                 # Arquivos estáticos (via Whitenoise)
├── templates/                   # Templates HTML
├── media/                       # Uploads de documentos
├── logs/                        # Logs do sistema
└── venv/                        # Ambiente virtual
```

## 🛠️ Tecnologias Utilizadas

### **Backend:**
- **Python 3.12+**
- **Django 4.2+**
- **SQLite** (banco de dados atual)
- **Gunicorn** (servidor WSGI)
- **Whitenoise** (servir estáticos)

### **Automação:**
- **Tesseract OCR** (extração de texto)
- **pdfplumber** (processamento de PDF)
- **Pillow** (processamento de imagem)
- **ReportLab** (geração de etiquetas)

### **Infraestrutura:**
- **Nginx** (proxy reverso + SSL)
- **Systemd** (gerenciamento de serviço)
- **HTTPS** (certificado SSL autoassinado)
- **python-dotenv** (variáveis de ambiente)

## 🔧 Configuração de Produção

### **Serviços Ativos:**
```bash
# Serviço Django
sudo systemctl status arquivo_digital

# Servidor Nginx
sudo systemctl status nginx

# Portas ativas
# 80  -> HTTP (redireciona para HTTPS)
# 443 -> HTTPS (Nginx)
# 8000 -> Django direto (interno)
```

### **Variáveis de Ambiente (.env):**
```bash
# Servidor
HOST=192.168.1.20
PORT=8000
DEBUG=False

# Domínio
ALLOWED_HOSTS=192.168.1.20,sistemas.parauapebas.pa.leg.br
DOMAIN_NAME=sistemas.parauapebas.pa.leg.br

# Segurança
SECRET_KEY=django-insecure-XXXXXXXXXXXXXXXX
```

## 📦 Instalação e Deploy

### **1. Clonar o Projeto:**
```bash
git clone <repositório>
cd arquivo_digital
```

### **2. Ambiente Virtual:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### **3. Configurar Ambiente:**
```bash
cp .env.example .env
# Editar .env com suas configurações
```

### **4. Banco de Dados:**
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### **5. Coletar Estáticos:**
```bash
python manage.py collectstatic --noinput
```

### **6. Instalar Serviço:**
```bash
sudo chmod +x scripts/install_service.sh
sudo ./scripts/install_service.sh
```

## 🔒 Segurança Implementada

### **✅ Medidas de Segurança:**
- ✅ **SECRET_KEY** segura no .env
- ✅ **DEBUG = False** em produção
- ✅ **HTTPS** configurado com SSL
- ✅ **Headers de segurança** (HSTS, XSS, etc)
- ✅ **Permissões restritas** em arquivos sensíveis
- ✅ **.env** no .gitignore

### **🔐 Configurações de Segurança:**
```python
SECURE_SSL_REDIRECT = False  # Nginx já redireciona
SECURE_HSTS_SECONDS = 31536000
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
```

## 📊 Fluxo de Trabalho do Sistema

### **Fluxo Ideal:**
1. **Escanear documento** → PDF
2. **Upload no sistema** → OCR automático
3. **Extração automática:**
   - Tipo de documento
   - Número
   - Data
   - Assunto
4. **Formulário preenchido** → Usuário revisa
5. **Vincular à caixa física** → Salvar
6. **Pesquisa rápida** → Visualizar PDF

### **Organização Física:**
```
Caixa 01
├── Portaria 12/2023
├── Lei 55/2023
└── Memorando 04/2023

Caixa 02
├── Portaria 101/2024
└── Moção 15/2024
```

## 🎯 MVP - Funcionalidades Mínimas

### **✅ Já Implementadas:**
1. ✅ Upload de documento PDF
2. ✅ Cadastro de metadados
3. ✅ Organização por caixas
4. ✅ Pesquisa simples
5. ✅ Visualização do PDF
6. ✅ OCR básico
7. ✅ Geração de etiquetas

### **🔮 Funcionalidades Futuras:**
- OCR completo e avançado
- Busca por texto dentro do documento
- QR Code nas caixas
- Relatórios estatísticos
- Controle de empréstimo de documentos
- Histórico de alterações
- Integração com outros sistemas

## 🐛 Troubleshooting

### **Problemas Comuns:**

#### **Serviço não inicia:**
```bash
sudo systemctl status arquivo_digital
sudo journalctl -u arquivo_digital -f
```

#### **HTTPS não funciona:**
```bash
sudo nginx -t
sudo systemctl reload nginx
```

#### **Permissões de arquivos:**
```bash
sudo chown -R www-data:www-data media/ staticfiles/ logs/
sudo chmod 640 .env db.sqlite3
```

#### **OCR não funciona:**
```bash
# Verificar se Tesseract está instalado
which tesseract
tesseract --version
```

## 📞 Suporte

Para suporte ou dúvidas:
- Verificar logs em `/opt/sistema_arquivos/arquivo_digital/logs/`
- Status do serviço: `sudo systemctl status arquivo_digital`
- Documentação Django: https://docs.djangoproject.com/

---

**Última atualização:** 23/04/2026  
**Versão:** 1.0 (Produção)  
**Status:** ✅ Funcionando
