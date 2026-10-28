import json
import pandas as pd
from collections import defaultdict
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('scratch/classified_all_113.json', 'r', encoding='utf-8') as f:
    items = json.load(f)

future_items = [i for i in items if i['data'] > '2026-10-31']
print(f"Total lançamentos futuros (Nov/26 a Fev/27): {len(future_items)}")

# Agrupar por descrição base
recurrences = defaultdict(list)
for i in future_items:
    desc = i['descricao']
    # Normalizar parcelas ex: "Crediserv - Empréstimo 2 5/42" -> "Crediserv - Empréstimo 2"
    # "Acordo BV 5/24" -> "Acordo BV"
    # "Fatura Novembro 2026" -> "Fatura Cartão Inter"
    if "Fatura" in desc:
        base_desc = "Fatura Cartão Inter Aparecida"
    elif "Crediserv" in desc:
        base_desc = "Crediserv - Empréstimo 2"
    elif "Acordo BV" in desc:
        base_desc = "Acordo BV"
    elif "Almoço Domingo 99 Food" in desc:
        base_desc = "Paga Leve - Almoço 99 Food"
    else:
        base_desc = desc
        
    recurrences[base_desc].append(i)

print("\n=== RECORRÊNCIAS E OBRIGAÇÕES IDENTIFICADAS (NOV/26 A FEV/27) ===")
for base_desc, rows in sorted(recurrences.items()):
    val_sample = rows[0]['valor']
    count = len(rows)
    months = [r['data'][:7] for r in rows]
    print(f"\n📌 {base_desc} (Aparece {count}x: {', '.join(months)})")
    for r in rows:
        print(f"     - Data: {r['data']} | Valor: R$ {r['valor']:>9.2f} | Categoria: {r['categoria']} | Desc original: {r['descricao']}")
