# Sistema de Arquivo Digital

Sistema Django para gestão de documentos digitais e caixas físicas da Câmara Municipal de Parauapebas. O projeto permite cadastrar, importar, pesquisar, revisar e organizar documentos PDF, com OCR, auditoria, departamentos, categorias/tipos de documento, caixas, movimentações e ações em lote.

## Sumário

- [Visão geral](#visão-geral)
- [Requisitos](#requisitos)
- [Instalação em ambiente novo](#instalação-em-ambiente-novo)
- [Configuração do `.env`](#configuração-do-env)
- [Banco de dados, migrações e usuário administrador](#banco-de-dados-migrações-e-usuário-administrador)
- [Arquivos estáticos, mídia e logs](#arquivos-estáticos-mídia-e-logs)
- [Como executar](#como-executar)
- [OCR e importação de PDFs](#ocr-e-importação-de-pdfs)
- [Comandos úteis](#comandos-úteis)
- [Testes e qualidade](#testes-e-qualidade)
- [Deploy com Gunicorn, WhiteNoise e proxy reverso](#deploy-com-gunicorn-whitenoise-e-proxy-reverso)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Solução de problemas](#solução-de-problemas)

## Visão geral

Funcionalidades principais:

- Autenticação via Django e controle de permissões por app/modelo.
- Dashboard administrativo.
- Upload de documentos PDF com leitura de texto por OCR.
- Confirmação/revisão de dados extraídos.
- Listagem, pesquisa textual, filtros e paginação de documentos.
- Download individual e download em lote.
- Organização por departamentos, categorias/tipos e caixas físicas.
- Movimentação de documentos entre caixas.
- Histórico de movimentações.
- Auditoria de operações críticas.
- Importação em lote de PDFs existentes no servidor.
- Geração de dados simulados para testes funcionais e de carga.

## Requisitos

Versões recomendadas:

- Ubuntu/Debian recente.
- Python 3.12.
- SQLite 3 para o banco padrão.
- Tesseract OCR com idioma português.
- Git.
- Acesso à internet no primeiro carregamento da interface, pois alguns templates usam CDNs para Tailwind, Font Awesome, jQuery e Bootstrap.

Pacotes de sistema no Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y \
  git \
  python3 \
  python3-venv \
  python3-dev \
  build-essential \
  pkg-config \
  sqlite3 \
  tesseract-ocr \
  tesseract-ocr-por \
  poppler-utils \
  libjpeg-dev \
  zlib1g-dev
```

Observações:

- `tesseract-ocr-por` é necessário para OCR em português (`lang='por'`).
- `poppler-utils` ajuda no ecossistema de PDFs e diagnóstico, embora a extração principal use `pdfplumber`.
- O projeto usa SQLite por padrão. Para PostgreSQL/MySQL seria necessário alterar `DATABASES` em `config/settings.py` e instalar o driver apropriado.

## Instalação em ambiente novo

Clone ou copie o projeto para o servidor:

```bash
cd /opt
git clone <URL_DO_REPOSITORIO> sistema_arquivos
cd /opt/sistema_arquivos/arquivo_digital
```

Crie e ative o ambiente virtual:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

Se o projeto foi copiado sem Git, basta entrar na pasta que contém `manage.py` e executar os mesmos comandos de ambiente virtual.

## Configuração do `.env`

Crie o arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

Gere uma `SECRET_KEY` segura:

```bash
python - <<'PY'
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
PY
```

Edite o `.env`:

```bash
nano .env
```

Variáveis usadas pelo projeto:

| Variável | Obrigatória | Exemplo | Uso |
|---|---:|---|---|
| `SECRET_KEY` | Sim | `uma-chave-longa` | Chave criptográfica do Django. Nunca versionar. |
| `DEBUG` | Não | `True` ou `False` | Modo de debug. Use `False` em produção. |
| `ALLOWED_HOSTS` | Sim | `localhost,127.0.0.1` | Hosts aceitos pelo Django. |
| `CSRF_TRUSTED_ORIGINS` | Não | `https://dominio.gov.br` | Origens HTTPS confiáveis para POST. |
| `FORCE_SCRIPT_NAME` | Não | `/arquivo` | Prefixo da aplicação quando publicada em subcaminho. |
| `USE_X_FORWARDED_HOST` | Não | `True` | Uso de headers do proxy. |
| `SECURE_SSL_REDIRECT` | Não | `True` | Redirecionar HTTP para HTTPS. |
| `SECURE_HSTS_SECONDS` | Não | `31536000` | HSTS em produção. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | Não | `True` | HSTS para subdomínios. |
| `SECURE_HSTS_PRELOAD` | Não | `True` | HSTS preload. |
| `SECURE_REFERRER_POLICY` | Não | `same-origin` | Política do header Referrer-Policy. |

Ambiente local com `runserver` direto:

```dotenv
SECRET_KEY=<sua-chave>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
FORCE_SCRIPT_NAME=
SECURE_SSL_REDIRECT=False
USE_X_FORWARDED_HOST=False
```

Produção publicada em `https://sistemas.parauapebas.pa.leg.br/arquivo/`:

```dotenv
SECRET_KEY=<sua-chave-de-producao>
DEBUG=False
ALLOWED_HOSTS=sistemas.parauapebas.pa.leg.br
CSRF_TRUSTED_ORIGINS=https://sistemas.parauapebas.pa.leg.br
FORCE_SCRIPT_NAME=/arquivo
SECURE_SSL_REDIRECT=True
USE_X_FORWARDED_HOST=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

## Banco de dados, migrações e usuário administrador

O banco padrão é SQLite em:

```text
arquivo_digital/db.sqlite3
```

Em ambiente novo, crie as tabelas:

```bash
python manage.py migrate
```

Crie um superusuário pelo comando padrão:

```bash
python manage.py createsuperuser
```

Ou use o script do projeto:

```bash
DJANGO_SUPERUSER_PASSWORD='senha-forte-aqui' \
python criar_admin.py --username admin --email admin@example.com
```

Depois, acesse o Admin:

- Local sem prefixo: `http://127.0.0.1:8000/admin/`
- Produção com prefixo: `https://sistemas.parauapebas.pa.leg.br/arquivo/admin/`

Permissões:

- Usuários comuns precisam receber permissões Django (`view`, `add`, `change`, `delete`) nos modelos de documentos, caixas, departamentos e tipos.
- O superusuário acessa todas as telas.

## Arquivos estáticos, mídia e logs

Diretórios importantes:

```text
static/       arquivos CSS/JS/imagens mantidos no projeto
staticfiles/  saída do collectstatic em produção
media/        uploads de documentos PDF
logs/         logs do Django e auditoria
temp/         arquivos temporários, incluindo downloads em lote
```

Crie diretórios esperados se necessário:

```bash
mkdir -p logs media staticfiles temp
```

Em produção, colete estáticos:

```bash
python manage.py collectstatic --noinput
```

O projeto usa WhiteNoise quando `DEBUG=False`, então os estáticos podem ser servidos pelo próprio Django/Gunicorn. Em instalações com Nginx, também é possível servir `staticfiles/` diretamente pelo proxy.

## Como executar

Desenvolvimento local:

```bash
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

Acesse:

```text
http://127.0.0.1:8000/accounts/login/
```

Se `FORCE_SCRIPT_NAME=/arquivo`, a aplicação deve estar atrás de um proxy que publique o subcaminho `/arquivo`. Para rodar diretamente pelo `runserver`, deixe `FORCE_SCRIPT_NAME=` no `.env`.

Produção com Gunicorn:

```bash
source venv/bin/activate
gunicorn config.wsgi:application \
  --bind 127.0.0.1:8001 \
  --workers 3 \
  --timeout 120
```

## OCR e importação de PDFs

O serviço de OCR fica em `services/ocr.py`.

Fluxo:

1. Tenta extrair texto diretamente do PDF com `pdfplumber`.
2. Se não houver texto, tenta OCR da imagem com `pytesseract` e idioma `por`.
3. O texto extraído é analisado para sugerir tipo, número, ano, data e assunto.

Teste rápido do Tesseract:

```bash
tesseract --version
tesseract --list-langs | grep por
```

Importar PDFs existentes:

```bash
python manage.py importar_pdfs_ocr \
  --root /caminho/para/pdfs \
  --recursive \
  --csv-relatorio relatorio_importacao_documentos.csv \
  --caixa-numero 1 \
  --tipo-nome IMPORTADO \
  --departamento-nome IMPORTACAO
```

Simular antes de gravar:

```bash
python manage.py importar_pdfs_ocr --root /caminho/para/pdfs --recursive --dry-run
```

Processar em lotes:

```bash
python manage.py importar_pdfs_ocr --root /caminho/para/pdfs --recursive --offset 0 --limit 100
python manage.py importar_pdfs_ocr --root /caminho/para/pdfs --recursive --offset 100 --limit 100
```

## Comandos úteis

Verificar configuração:

```bash
python manage.py check
```

Criar dados simulados:

```bash
python manage.py gerar_dados_teste --usuarios 20 --caixas 100 --documentos 5000 --seed 42
```

Limpar downloads temporários:

```bash
python manage.py limpar_downloads_temporarios --idade-horas 24
```

Abrir shell Django:

```bash
python manage.py shell
```

Criar migrações após alterar modelos:

```bash
python manage.py makemigrations
python manage.py migrate
```

## Testes e qualidade

Rodar todos os testes:

```bash
python manage.py test
```

Rodar testes por app:

```bash
python manage.py test apps.documentos
python manage.py test apps.caixas
python manage.py test apps.departamentos
python manage.py test apps.auditoria
```

Testes úteis já usados no projeto:

```bash
python manage.py test apps.core.tests_sidebar
python manage.py test apps.documentos.tests.MovimentacaoDocumentosLoteTests
```

Formatação e lint:

```bash
black .
flake8 .
```

Configuração do Black está em `pyproject.toml` na raiz superior do workspace.

## Deploy com Gunicorn, WhiteNoise e proxy reverso

Exemplo de serviço systemd:

```ini
[Unit]
Description=Arquivo Digital Gunicorn
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/sistema_arquivos/arquivo_digital
EnvironmentFile=/opt/sistema_arquivos/arquivo_digital/.env
ExecStart=/opt/sistema_arquivos/arquivo_digital/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8001 --workers 3 --timeout 120
Restart=always

[Install]
WantedBy=multi-user.target
```

Exemplo de Nginx publicando em `/arquivo/`:

```nginx
location /arquivo/static/ {
    alias /opt/sistema_arquivos/arquivo_digital/staticfiles/;
}

location /arquivo/media/ {
    alias /opt/sistema_arquivos/arquivo_digital/media/;
}

location /arquivo/ {
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Script-Name /arquivo;
    proxy_pass http://127.0.0.1:8001/;
}
```

Checklist de deploy:

```bash
source venv/bin/activate
python manage.py check
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py test apps.documentos apps.caixas apps.departamentos apps.auditoria
```

Depois reinicie o serviço:

```bash
sudo systemctl restart arquivo-digital
sudo systemctl status arquivo-digital
```

## Estrutura do projeto

```text
arquivo_digital/
├── apps/
│   ├── auditoria/       logs, retenção, estatísticas e alertas
│   ├── caixas/          caixas físicas e movimentações
│   ├── core/            dashboard, layout, helpers e template tags
│   ├── departamentos/   departamentos organizacionais
│   └── documentos/      upload, OCR, pesquisa, categorias e downloads
├── config/              settings, URLs e WSGI
├── docs/                documentação auxiliar de testes e segurança
├── media/               PDFs enviados pelos usuários
├── services/            serviços compartilhados de OCR e caixas
├── static/              CSS/JS/imagens do sistema
├── staticfiles/         arquivos coletados para produção
├── templates/           templates HTML
├── tests/               testes de carga/performance
├── manage.py
├── requirements.txt
└── .env.example
```

## Solução de problemas

Erro `SECRET_KEY deve ser definida no ambiente`:

- Crie o `.env`.
- Defina `SECRET_KEY`.
- Execute comandos a partir da pasta que contém `manage.py`.

Erro `ALLOWED_HOSTS é obrigatória`:

- Defina `ALLOWED_HOSTS` no `.env`, separado por vírgulas.

CSS/JS não carregam:

- Em desenvolvimento, confira `DEBUG=True`.
- Em produção, rode `python manage.py collectstatic --noinput`.
- Verifique `FORCE_SCRIPT_NAME`, `STATIC_URL` e a configuração do proxy.

Login redireciona para caminho errado:

- Se estiver rodando direto com `runserver`, use `FORCE_SCRIPT_NAME=`.
- Se estiver em produção sob `/arquivo`, use `FORCE_SCRIPT_NAME=/arquivo` e publique a aplicação com proxy reverso nesse subcaminho.

OCR não extrai texto:

- Verifique `tesseract --version`.
- Verifique `tesseract --list-langs | grep por`.
- Confirme que o PDF não está corrompido.
- PDFs com texto nativo usam `pdfplumber`; PDFs escaneados dependem do Tesseract.

Uploads falham por permissão:

- Garanta escrita em `media/`, `logs/`, `temp/` e `staticfiles/` para o usuário que executa o Gunicorn.

Banco novo sem dados:

- Execute `python manage.py migrate`.
- Crie superusuário.
- Cadastre categorias, departamentos e caixas, ou rode `gerar_dados_teste`.

## Segurança operacional

- Nunca versionar `.env`, `db.sqlite3`, `media/`, `logs/`, `temp/` ou `staticfiles/`.
- Em produção, manter `DEBUG=False`.
- Usar HTTPS no proxy reverso.
- Fazer backup regular de `db.sqlite3` e `media/`.
- Testar restauração de backup periodicamente.
- Revisar permissões de usuários no Django Admin.
