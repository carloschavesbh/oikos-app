import sqlite3
import pandas as pd

conn = sqlite3.connect('financas_casa.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print("Tabelas no banco:", tables)

print("\n=== ESTRUTURA DE TRANSAÇÕES ===")
if 'transacoes' in tables:
    cursor.execute("PRAGMA table_info(transacoes)")
    for col in cursor.fetchall():
        print(f"  {col[1]} ({col[2]})")

print("\n=== TRANSAÇÕES REAIS ===")
if 'transacoes' in tables:
    df_tx = pd.read_sql_query("SELECT * FROM transacoes", conn)
    print(f"Total: {len(df_tx)}")
    for _, r in df_tx.iterrows():
        print(f"  [{r['id']}] {r.get('data')} | {r.get('tipo')} | R$ {r.get('valor')} | {r.get('descricao')} | status: {r.get('status')} | conta_id: {r.get('conta_id')}")

if 'contas_bancarias' in tables:
    print("\n=== CONTAS BANCÁRIAS ===")
    df_c = pd.read_sql_query("SELECT * FROM contas_bancarias", conn)
    print(df_c)

if 'cartoes' in tables:
    print("\n=== CARTÕES ===")
    df_cartoes = pd.read_sql_query("SELECT * FROM cartoes", conn)
    print(df_cartoes)

if 'dividas' in tables:
    print("\n=== DÍVIDAS ===")
    df_div = pd.read_sql_query("SELECT * FROM dividas", conn)
    print(df_div)

if 'pagaleve_compras' in tables:
    print("\n=== PAGALEVE COMPRAS ===")
    df_plc = pd.read_sql_query("SELECT * FROM pagaleve_compras", conn)
    print(df_plc)

conn.close()
