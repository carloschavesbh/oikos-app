import sqlite3
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_casa.db')

print("--- CONTAS CONFIG ---")
print(pd.read_sql_query('SELECT * FROM contas_config', conn))

print("\n--- PLANEJAMENTO METAS ---")
try:
    print(pd.read_sql_query('SELECT * FROM planejamento_metas', conn))
except Exception as e:
    print("Erro em planejamento_metas:", e)

print("\n--- TRANSAÇÃO IPVA ---")
print(pd.read_sql_query("SELECT id, data, descricao, valor, pago, status_pagamento FROM transacoes WHERE descricao LIKE '%IPVA%'", conn))

print("\n--- TODAS AS TABELAS ---")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([r[0] for r in cursor.fetchall()])

conn.close()
