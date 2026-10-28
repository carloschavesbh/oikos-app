import sqlite3
import json
import re

conn = sqlite3.connect('scratch/financas_casa_teste_migracao.db')
cursor = conn.cursor()

cursor.execute("SELECT id, data, descricao, valor, tipo FROM transacoes WHERE valor = 50.0")
rows = cursor.fetchall()
print("Transações com R$ 50,00 no banco:", rows)

with open('scratch/organizze_lancamentos_extracted.json', 'r', encoding='utf-8') as f:
    org_txs = json.load(f)

print("\nTransações com R$ 50,00 no Organizze:")
for ot in org_txs:
    val = ot['valor']
    if '50,00' in val:
        print(f"  Org ID: {ot['id']} | Linhas: {ot['lines'][:5]}")

conn.close()
