import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('scratch/all_5_xls_records.json', encoding='utf-8') as f:
    d = json.load(f)

print("=== BUSCA POR CARTÃO / FATURA / EMPRÉSTIMO NAS 5 PLANILHAS ===")
for fname, rows in d.items():
    for r in rows:
        tags = str(r.get('Tags', ''))
        info = str(r.get('Informações adicionais', ''))
        desc = str(r.get('Descrição', ''))
        cat = str(r.get('Categoria', ''))
        val = r.get('Valor')
        dt = r.get('Data')
        
        lower_all = f"{desc} {cat} {tags} {info}".lower()
        if any(k in lower_all for k in ['fatura', 'cartão', 'cartao', 'inter', 'aparecida', 'empréstimo', 'emprestimo']):
            print(f"{fname[:30]} | {dt} | R$ {val:>9.2f} | Desc: {desc:<32} | Cat: {cat:<25} | Tags: {tags} | Info: {info}")
