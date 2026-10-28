import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("--- BUSCA POR BV / 1428 ---")
cur.execute("SELECT id, data, descricao, valor, tipo, categoria, conta, pago, afeta_saldo_bancario FROM transacoes WHERE descricao LIKE '%BV%' OR (valor >= 1400 AND valor <= 1500)")
rows = cur.fetchall()
if not rows:
    print("Nenhum registro encontrado com '%BV%' ou valor entre 1400 e 1500.")
else:
    for row in rows:
        print(row)

print("\n--- TODAS AS TRANSAÇÕES NO BANCO ATUAL ---")
cur.execute("SELECT id, data, descricao, valor, tipo, categoria, conta, pago, afeta_saldo_bancario FROM transacoes ORDER BY data ASC, id ASC")
for row in cur.fetchall():
    print(row)

print("\n--- SCHEMA DA TABELA TRANSACOES ---")
cur.execute("PRAGMA table_info(transacoes)")
for col in cur.fetchall():
    print(col)

print("\n--- OUTRAS TABELAS EXISTENTES ---")
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
for t in cur.fetchall():
    print(t[0])

conn.close()
