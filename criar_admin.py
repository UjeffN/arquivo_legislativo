import os
import sys
import django
from django.conf import settings

# Configuração mínima sem logs
settings.configure(
    DEBUG=True,
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": "db.sqlite3",
        }
    },
    INSTALLED_APPS=[
        "django.contrib.auth",
        "django.contrib.contenttypes",
    ],
    SECRET_KEY="temp-key-for-reset"
)
django.setup()

from django.contrib.auth.models import User

# Criar ou resetar usuário admin
try:
    user = User.objects.get(username="admin")
    user.set_password("camara@1")
    user.save()
    print("✅ Senha do usuário admin resetada para: camara@1")
except User.DoesNotExist:
    user = User.objects.create_superuser("admin", "admin@camara.parauapebas.pa.leg.br", "camara@1")
    print("✅ Novo usuário admin criado com senha: camara@1")

print("🎯 Acesse: https://sistemas.parauapebas.pa.leg.br/arquivo/admin/")
print("🔑 Usuário: admin")
print("🔑 Senha: camara@1")
