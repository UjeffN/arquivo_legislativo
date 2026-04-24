import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import authenticate

senhas_para_testar = [
    "suportedti@1",
    "camara@1", 
    "administrator",
    "admin",
    "123456",
    "password"
]

print("🔍 Testando senhas para o usuário admin:")
for senha in senhas_para_testar:
    user = authenticate(username="admin", password=senha)
    if user:
        print(f"✅ SENHA CORRETA: {senha}")
        break
    else:
        print(f"❌ {senha} - incorreta")
else:
    print("🔴 Nenhuma senha funcionou!")
