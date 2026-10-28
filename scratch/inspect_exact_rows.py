import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import re

print("=" * 80)
print("INSPEÇÃO DETALHADA DAS TRANSAÇÕES E CONTAS A PAGAR")
print("=" * 80)

# 1. Visão Geral - 13 Blocos 'bill'
with open("Organizze/Organizze _ Visão geral.html", "r", encoding="utf-8", errors="ignore") as f:
    html_vg = f.read()

bill_blocks = re.findall(r'<li[^>]*class="[^"]*bill[^"]*"[^>]*>(.*?)</li>', html_vg, re.DOTALL)
print(f"\n--- 13 CONTAS ENCONTRADAS NA VISÃO GERAL (bill-items) ---")
for i, b in enumerate(bill_blocks):
    clean = re.sub(r'<[^>]+>', ' ', b)
    clean = re.sub(r'\s+', ' ', clean).strip()
    print(f"[{i+1}] {clean}")

# 2. Lançamentos.html - Linhas de Lançamentos
with open("Organizze/Organizze _ Lançamentos.html", "r", encoding="utf-8", errors="ignore") as f:
    html_lanc = f.read()

# Procura as tags que envolvem cada transação em Lançamentos.html
# No trecho acima vimos que tem a data 01/08/2026, etc.
# Vamos encontrar os containers
trans_chunks = re.findall(r'(<div[^>]*class="[^"]*transaction-row[^"]*"[^>]*>.*?)(?=<div[^>]*class="[^"]*transaction-row[^"]*"|$)', html_lanc, re.DOTALL)
if not trans_chunks:
    trans_chunks = re.findall(r'(<div[^>]*class="[^"]*transaction-cell[^"]*"[^>]*>.*?)(?=<div[^>]*class="[^"]*transaction-cell[^"]*"|$)', html_lanc, re.DOTALL)
if not trans_chunks:
    # Procura por elementos que contêm data no formato dd/mm/aaaa
    trans_chunks = []
    for m in re.finditer(r'(\d{2}/\d{2}/\d{4})', html_lanc):
        start = max(0, m.start() - 250)
        end = min(len(html_lanc), m.end() + 350)
        trans_chunks.append(html_lanc[start:end])

print(f"\n--- LANÇAMENTOS IDENTIFICADOS EM Lançamentos.html ({len(trans_chunks)}) ---")
for i, t in enumerate(trans_chunks):
    clean = re.sub(r'<[^>]+>', ' ', t)
    clean = re.sub(r'\s+', ' ', clean).strip()
    print(f"[{i+1}] {clean}")
