import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_remodelacao.db')

print("--- 1. METAS DE PLANEJAMENTO EXISTENTES ---")
metas = conn.execute("SELECT * FROM planejamento_metas").fetchall()
for m in metas:
    print(m)

print("\n--- 2. DESPESAS COM IPVA, SEGURO, IMPOSTOS OU ANUAIS ---")
txs = conn.execute("SELECT id, data, descricao, valor, categoria, conta FROM transacoes WHERE descricao LIKE '%ipva%' OR descricao LIKE '%seguro%' OR descricao LIKE '%imposto%' OR categoria LIKE '%imposto%' ORDER BY data DESC LIMIT 15").fetchall()
for t in txs:
    print(t)

conn.close()

