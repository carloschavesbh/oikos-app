import sqlite3
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_casa.db')
hoje = '2026-10-20'

df = pd.read_sql_query('''
    SELECT id, data, descricao, valor, tipo, pago, status_pagamento, 
           afeta_saldo_bancario, categoria, conta, conta_id 
    FROM transacoes 
    WHERE tipo = 'despesa' AND pago = 0
    ORDER BY data, id
''', conn)

print(f"Total despesas pendentes no banco: {len(df)}")
for _, r in df.iterrows():
    print(f"[{r['id']}] {r['data']} | R$ {r['valor']:>8.2f} | {r['descricao']} | afeta_banco={r['afeta_saldo_bancario']} | status={r['status_pagamento']}")

# Turnos realizados
df_turnos = pd.read_sql_query("SELECT * FROM turnos", conn)
print(f"\nTotal turnos: {len(df_turnos)}")
print(df_turnos.to_string())

conn.close()
