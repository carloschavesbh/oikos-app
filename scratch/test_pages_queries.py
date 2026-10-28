import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3
import pandas as pd
from datetime import date
from decimal import Decimal

conn = sqlite3.connect('financas_casa.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Testar consulta de Paga Leve com compras e contas
cur.execute("SELECT * FROM pagaleve_contas")
contas_pl = [dict(r) for r in cur.fetchall()]
print("Contas PL:", contas_pl)

cur.execute("SELECT * FROM pagaleve_compras")
compras_pl = [dict(r) for r in cur.fetchall()]
print("Compras PL:", len(compras_pl))

# 2. Testar consulta de dívidas
cur.execute("SELECT * FROM dividas_gerenciamento")
divs = [dict(r) for r in cur.fetchall()]
print("Dívidas:", len(divs))

# 3. Testar consulta de categorias
cur.execute("""
    SELECT g.id, g.nome, count(s.id) as total_subs
    FROM grupos_categoria g
    LEFT JOIN subcategorias s ON s.grupo_id = g.id
    GROUP BY g.id
""")
cats = cur.fetchall()
print("Grupos com subs:", len(cats))

conn.close()
print("✓ Todas as consultas das páginas executadas perfeitamente!")
