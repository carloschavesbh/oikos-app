import sqlite3
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_casa.db')
df = pd.read_sql_query("SELECT id, data, descricao, valor, tipo, categoria, conta, pago, afeta_saldo_bancario, grupo_parcelamento FROM transacoes ORDER BY data ASC, id ASC", conn)
conn.close()

print(f"Total de lançamentos em transacoes: {len(df)}")
print("\n--- RECEITAS ---")
print(df[df["tipo"] == "receita"][["id", "data", "descricao", "valor", "pago"]])

print("\n--- DESPESAS JÁ PAGAS ---")
print(df[(df["tipo"] == "despesa") & (df["pago"] == 1)][["id", "data", "descricao", "valor", "categoria", "conta"]])

print("\n--- OBRIGAÇÕES PENDENTES (pago == 0) ---")
pend = df[(df["tipo"] == "despesa") & (df["pago"] == 0)][["id", "data", "descricao", "valor", "categoria", "conta"]]
print(pend.to_string())
print(f"\nTotal Obrigações Pendentes: R$ {pend['valor'].sum():.2f}")
