# -*- coding: utf-8 -*-
import os
import re

path = r"C:\Users\carlo\Downloads\Oikos-Geral\templates\base.html"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()

# Substituir o badge do mobile
c = re.sub(
    r'(<div class="flex items-center gap-1\.5 md:hidden">.*?<span [^>]*>)\s*PWA\s*(</span>)',
    r'\1\n              {{ OIKOS_EDICAO_NOME | default("Uso Geral") }}\n            \2',
    c,
    flags=re.DOTALL
)

# Substituir o badge do desktop
c = re.sub(
    r'(<div class="hidden md:flex items-center gap-2">.*?<span [^>]*>)\s*PWA\s*(</span>)',
    r'\1\n              {{ OIKOS_EDICAO_NOME | default("Uso Geral") }}\n            \2',
    c,
    flags=re.DOTALL
)

with open(path, "w", encoding="utf-8") as f:
    f.write(c)

print("Patch em base.html de Oikos-Geral aplicado com sucesso!")

# Atualizar .gitignore de Oikos-Geral
git_ignore_path = r"C:\Users\carlo\Downloads\Oikos-Geral\.gitignore"
with open(git_ignore_path, "a", encoding="utf-8") as f:
    f.write("\nfinancas_geral.db\n*.db-wal\n*.db-shm\ntemp_*.db\n")

print("Patch em .gitignore de Oikos-Geral aplicado com sucesso!")

