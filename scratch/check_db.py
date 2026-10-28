import sqlite3

conn = sqlite3.connect('financas_casa.db')
c = conn.cursor()
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

for t in ["turnos", "motorista_turnos", "abastecimentos", "motorista"]:
    if t in tables:
        print(f"\n--- {t} ---")
        row = c.execute(f"SELECT sql FROM sqlite_master WHERE name='{t}'").fetchone()
        print(row[0] if row else "None")
        print("Sample row:")
        sample = c.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 3").fetchall()
        for s in sample:
            print(s)
