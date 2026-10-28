import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import re

with open("Organizze/Organizze _ Lançamentos.html", "r", encoding="utf-8", errors="ignore") as f:
    html = f.read()

# Procura o trecho onde aparecem as transações
# Vamos achar o container das transações
print("--- LENDO TABELA DE TRANSAÇÕES EM LANÇAMENTOS.HTML ---")
# Procura todas as ocorrências de data e pega os próximos 500 caracteres
matches = list(re.finditer(r'(\d{2}/\d{2}/\d{4})', html))
for m in matches:
    dt = m.group(1)
    chunk = html[m.start(): m.start() + 600]
    # Extrai texto limpo
    txt = re.sub(r'<[^>]+>', ' ', chunk)
    txt = re.sub(r'\s+', ' ', txt).strip()
    print(f"Data: {dt} | Trecho: {txt[:160]}")
