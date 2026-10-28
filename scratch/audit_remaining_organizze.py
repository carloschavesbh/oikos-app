import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import re
import json

print("=" * 80)
print("AUDITORIA COMPLETA DOS 7 ARQUIVOS ORGANIZZE")
print("=" * 80)

# 1. Cartões de Crédito.html
with open("Organizze/Organizze _ Cartões de Crédito.html", "r", encoding="utf-8", errors="ignore") as f:
    html_crd = f.read()
print("\n--- 1. ORGANIZZE _ CARTÕES DE CRÉDITO.HTML ---")
# Procura faturas, limites, parcelas, compras de cartão
matches_crd = re.findall(r'(\b\d{2}/\d{2}/\d{4}\b|\b\d{2}/\d{2}\b).*?(R\$\s*[\d\.,]+)', html_crd)
print(f"Pares data/valor em Cartões de Crédito.html: {len(matches_crd)}")
for m in matches_crd:
    print(m)
# Procura nomes de cartões
print("Nomes de cartões em Cartões de Crédito.html:")
for m in re.finditer(r'class="[^"]*card-name[^"]*"[^>]*>(.*?)<', html_crd):
    print("  Card name tag:", m.group(1))

# 2. Limite de gastos.html
with open("Organizze/Organizze _ Limite de gastos.html", "r", encoding="utf-8", errors="ignore") as f:
    html_lim = f.read()
print("\n--- 2. ORGANIZZE _ LIMITE DE GASTOS.HTML ---")
matches_lim = re.findall(r'([^<>\n]{3,40})\s*.*?(R\$\s*[\d\.,]+)', html_lim)
print(f"Limites de gastos identificados: {len(matches_lim)}")
for m in matches_lim[:10]:
    clean_k = re.sub(r'<[^>]+>', '', m[0]).strip()
    if clean_k:
        print(f"  • {clean_k}: {m[1]}")

# 3. Relatórios.html
with open("Organizze/Organizze _ Relatórios.html", "r", encoding="utf-8", errors="ignore") as f:
    html_rel = f.read()
print("\n--- 3. ORGANIZZE _ RELATÓRIOS.HTML ---")
# Procura números consolidados de relatórios
matches_rel = re.findall(r'class="[^"]*report-[^"]*"[^>]*>(.*?)</div>', html_rel, re.DOTALL)
print(f"Blocos report encontrados: {len(matches_rel)}")
# Procura datas e totais
totais_rel = re.findall(r'(Total de receitas|Total de despesas|Saldo|Resultado).*?(R\$\s*[\d\.,]+)', html_rel, re.I)
print(f"Totais encontrados em Relatórios: {totais_rel}")

conn = sys.modules.get('sqlite3')
