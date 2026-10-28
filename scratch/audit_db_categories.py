import sys
import sqlite3
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('scratch/financas_casa_audit_copy.db')

print("--- CATEGORIAS ATUAIS EM TRANSACOES (HISTÓRICO COMPLETO) ---")
df = pd.read_sql_query("""
    SELECT categoria, tipo, count(*) as total_transacoes, round(sum(valor), 2) as valor_total,
           min(data) as primeira_data, max(data) as ultima_data
    FROM transacoes
    GROUP BY categoria, tipo
    ORDER BY tipo, categoria
""", conn)
print(df.to_string())

print("\n--- TRANSAÇÕES DE OUTUBRO/2026 E SUAS CATEGORIAS ATUAIS ---")
df_out = pd.read_sql_query("""
    SELECT id, data, descricao, valor, categoria, tipo, pago, grupo_parcelamento
    FROM transacoes
    WHERE data >= '2026-10-01'
    ORDER BY data, id
""", conn)
print(df_out.to_string())

conn.close()
