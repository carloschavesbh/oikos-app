import sqlite3

conn = sqlite3.connect('financas_casa.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT id, data, descricao, valor, tipo, categoria, conta, pago FROM transacoes WHERE data >= '2026-10-01' ORDER BY data")
rows = cur.fetchall()
print(f"Total transacoes em Outubro: {len(rows)}")
for r in rows:
    print(dict(r))

print("\n--- TURNOS ---")
cur.execute("SELECT * FROM turnos WHERE data >= '2026-10-01' ORDER BY data")
t_rows = cur.fetchall()
for t in t_rows:
    print(dict(t))
conn.close()
