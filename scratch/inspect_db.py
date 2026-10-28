import sqlite3

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM transacoes')
print('transacoes:', cur.fetchone()[0])
cur.execute('SELECT * FROM turnos')
print('turnos:', cur.fetchall())
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('tables:', [r[0] for r in cur.fetchall()])
conn.close()
