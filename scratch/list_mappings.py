import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('scratch/financas_casa_teste_hierarquia.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
    SELECT t.id, t.data, t.descricao, t.valor, t.categoria as cat_antiga,
           g.nome as grupo_novo, s.nome as subcat_nova, t.natureza_gasto, t.pago
    FROM transacoes t
    LEFT JOIN grupos_categoria g ON g.id = t.grupo_id
    LEFT JOIN subcategorias s ON s.id = t.subcategoria_id
    ORDER BY t.data, t.id
""")
rows = cur.fetchall()
print(f"Total de Transações: {len(rows)}")
for r in rows:
    g_str = str(r["grupo_novo"]) if r["grupo_novo"] else "SEM GRUPO"
    s_str = str(r["subcat_nova"]) if r["subcat_nova"] else "SEM SUBCAT"
    print(f"ID {r['id']:2d} | {r['data']} | {r['descricao']:45s} | R$ {r['valor']:7.2f} | Antiga: {r['cat_antiga']:18s} -> Grupo: {g_str:18s} | Subcat: {s_str}")

conn.close()
