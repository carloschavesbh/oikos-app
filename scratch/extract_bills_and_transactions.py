import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import re
import json

print("=" * 80)
print("EXTRAÇÃO DE LANÇAMENTOS E CONTAS DO ORGANIZZE (VISÃO GERAL E LANÇAMENTOS)")
print("=" * 80)

# 1. Analisa Organizze _ Visão geral.html
with open("Organizze/Organizze _ Visão geral.html", "r", encoding="utf-8", errors="ignore") as f:
    html_vg = f.read()

print("\n--- 1. CONTAS A PAGAR / CONTAS VENCIDAS EM VISÃO GERAL ---")
# Procura por billToPay ou similares
# Vamos procurar blocos que tenham bill.description ou texto com data e valor
# No HTML salvo pelo navegador, o Angular compilou o DOM, então os valores e textos estão dentro das tags!
# Vamos procurar todos os trechos com classes zze-bill ou bill ou item
bill_blocks = re.findall(r'<li[^>]*class="[^"]*bill[^"]*"[^>]*>(.*?)</li>', html_vg, re.DOTALL)
if not bill_blocks:
    bill_blocks = re.findall(r'<div[^>]*class="[^"]*bill-item[^"]*"[^>]*>(.*?)</div>', html_vg, re.DOTALL)

print(f"Blocos 'bill' encontrados: {len(bill_blocks)}")

# Vamos procurar todos os blocos com datas e valores em Visão Geral
# Padrão: qualquer bloco com data dd/mm/aaaa e R$ valor
items_vg = re.findall(r'([^<>\n]{3,60})\s*(\d{2}/\d{2}/\d{4})\s*[^<>\n]*?(R\$\s*[\d\.,]+)', html_vg)
print(f"Itens com Descrição + Data + Valor em Visão Geral: {len(items_vg)}")
for it in items_vg:
    print(f"  • {it[1]} | {it[0].strip()} | {it[2]}")

# 2. Analisa Organizze _ Lançamentos.html
print("\n--- 2. LANÇAMENTOS EM Organizze _ Lançamentos.html ---")
with open("Organizze/Organizze _ Lançamentos.html", "r", encoding="utf-8", errors="ignore") as f:
    html_lanc = f.read()

items_lanc = re.findall(r'([^<>\n]{3,60})\s*(\d{2}/\d{2}/\d{4})\s*[^<>\n]*?(R\$\s*[\d\.,]+)', html_lanc)
print(f"Itens com Descrição + Data + Valor em Lançamentos.html: {len(items_lanc)}")
for it in items_lanc:
    print(f"  • {it[1]} | {it[0].strip()} | {it[2]}")

# Vamos olhar os blocos da tabela de transações
# No Organizze, a tabela de lançamentos tem datas e descrições
print("\n--- 3. BUSCA POR LINHAS DE LANÇAMENTOS NO DOM ---")
for m in re.finditer(r'(\d{2}/\d{2}/\d{4})', html_lanc):
    start = max(0, m.start() - 200)
    end = min(len(html_lanc), m.end() + 200)
    snip = html_lanc[start:end]
    clean = re.sub(r'<[^>]+>', ' ', snip)
    clean = re.sub(r'\s+', ' ', clean).strip()
    print(f"Linha: {clean[:140]}")
