import sys, os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
import pandas as pd

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("=== TABELA PAGALEVE_COMPRAS ===")
cur.execute("SELECT * FROM pagaleve_compras")
col_names = [d[0] for d in cur.description]
compras = cur.fetchall()
for c in compras:
    row_dict = dict(zip(col_names, c))
    print(row_dict)

print("\n=== TRANSACOES VINCULADAS AO PAGA LEVE OU COM GRUPO_PARCELAMENTO PAGALEVE ===")
cur.execute("""
    SELECT id, data, descricao, valor, pago, grupo_parcelamento, numero_parcela, total_parcelas_compra, status_rateio
    FROM transacoes
    WHERE grupo_parcelamento LIKE '%pagaleve%' OR descricao LIKE '%Paga Leve%' OR descricao LIKE '%pagaleve%'
    ORDER BY id ASC
""")
col_t = [d[0] for d in cur.description]
trans = cur.fetchall()
df_pl = pd.DataFrame(trans, columns=col_t)
print(df_pl.to_string())

print("\n--- RESUMO DE PARCELAS POR STATUS (PAGO VS PENDENTE) ---")
print("Total de transacoes Paga Leve:", len(df_pl))
print("Pagas (pago = 1):")
print(df_pl[df_pl['pago'] == 1][['id', 'data', 'descricao', 'valor']])
print("Soma pagas:", df_pl[df_pl['pago'] == 1]['valor'].sum())

print("\nPendentes (pago != 1 ou 0):")
print(df_pl[df_pl['pago'] != 1][['id', 'data', 'descricao', 'valor']])
print("Soma pendentes:", df_pl[df_pl['pago'] != 1]['valor'].sum())

conn.close()
