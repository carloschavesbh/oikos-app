import sqlite3

conn = sqlite3.connect('financas_remodelacao.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tabelas no banco:")
for t in sorted(tables):
    cur.execute(f"PRAGMA table_info({t})")
    cols = [c[1] for c in cur.fetchall()]
    print(f"  {t}: {', '.join(cols[:8])}{'...' if len(cols)>8 else ''}")
conn.close()

