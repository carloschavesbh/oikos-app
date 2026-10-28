import sqlite3
import sys
sys.path.append('.')
import app

# Run app.inicializar_banco()
app.inicializar_banco()
print("inicializar_banco executed successfully on production DB.")

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()
cur.execute("PRAGMA integrity_check")
print("Integrity check:", cur.fetchone()[0])

cur.execute("SELECT count(*) FROM transacoes")
print("Transacoes:", cur.fetchone()[0])

cur.execute("SELECT count(*) FROM turnos")
print("Turnos:", cur.fetchone()[0])

cur.execute("SELECT count(*) FROM cofrinhos")
print("Cofrinhos:", cur.fetchone()[0])

cur.execute("PRAGMA table_info(planejamento_metas)")
print("Colunas planejamento_metas:", [c[1] for c in cur.fetchall()])

conn.close()
