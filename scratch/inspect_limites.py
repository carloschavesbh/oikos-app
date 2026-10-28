import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()
cur.execute("SELECT categoria, limite FROM limites_categoria")
print("Limites atuais em limites_categoria:")
for r in cur.fetchall():
    print(r)
conn.close()

with open('app.py', 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f, 1):
        if 'limites_categoria' in line or 'modal_limite_gasto' in line or 'render_limite_gastos' in line:
            print(f"{idx}: {line.strip()}")
