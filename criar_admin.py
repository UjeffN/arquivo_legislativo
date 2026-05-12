#!/usr/bin/env python3
"""
Cria ou redefine um superusuário de forma segura.

Uso:
  python criar_admin.py --username admin --email admin@example.com

Senha:
  - Define por variável de ambiente DJANGO_SUPERUSER_PASSWORD
  - Ou solicita de forma interativa via terminal.
"""

import argparse
import getpass
import os
import sys

import django


def _parse_args():
    parser = argparse.ArgumentParser(description='Cria ou redefine superusuário Django.')
    parser.add_argument('--username', default='admin', help='Nome de usuário (padrão: admin)')
    parser.add_argument(
        '--email',
        default='admin@camara.parauapebas.pa.leg.br',
        help='Email do superusuário',
    )
    return parser.parse_args()


def _obter_senha():
    senha_env = os.getenv('DJANGO_SUPERUSER_PASSWORD')
    if senha_env:
        return senha_env
    senha = getpass.getpass('Senha do superusuário: ').strip()
    if not senha:
        raise ValueError('Senha não pode ser vazia.')
    return senha


def main():
    args = _parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    senha = _obter_senha()
    user, created = user_model.objects.get_or_create(
        username=args.username,
        defaults={'email': args.email, 'is_staff': True, 'is_superuser': True},
    )

    if not created:
        user.email = args.email
        user.is_staff = True
        user.is_superuser = True

    user.set_password(senha)
    user.save()

    status = 'criado' if created else 'atualizado'
    print(f'Superusuário {args.username} {status} com sucesso.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Erro: {exc}', file=sys.stderr)
        sys.exit(1)
