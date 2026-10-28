import sys
sys.path.insert(0, '.')
import sqlite3

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("TABELAS:", tables)

for t in ["ajustes_saldo", "saldo_marcos", "saldo_ajustes", "motorista_marco_producao"]:
    if t in tables:
        print(f"\n=== {t} ===")
        cur.execute(f"SELECT * FROM {t}")
        for r in cur.fetchall():
            print(r)

print('\n=== TRANSACOES CARTEIRA ===')
cur.execute("SELECT id, data, descricao, valor, tipo, pago, turno_id FROM transacoes WHERE conta_id = 2 OR conta LIKE '%Carteira%'")
for t in cur.fetchall():
    print(t)

print('\n=== TRANSACOES MERCADO PAGO RECENTES ===')
cur.execute("SELECT id, data, descricao, valor, tipo, pago, turno_id FROM transacoes WHERE conta_id = 1 OR conta LIKE '%Mercado Pago%' ORDER BY data DESC LIMIT 10")
for t in cur.fetchall():
    print(t)

conn.close()
