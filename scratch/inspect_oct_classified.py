import json
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('scratch/classified_all_113.json', 'r', encoding='utf-8') as f:
    items = json.load(f)

print("=== OUTUBRO/2026 DETALHADO ===")
oct_items = [i for i in items if '20261001' in i['arquivo']]
for idx, i in enumerate(oct_items):
    print(f"{idx+1:2d}. {i['data']} | {i['valor']:>9.2f} | {i['situacao']:<8} | {i['descricao'][:30]:<30} | {i['classificacao']} | {i['motivo']}")
