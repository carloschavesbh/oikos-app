import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_remodelacao.db')

print("--- 1. CATEGORIAS DE DESPESA EXISTENTES ---")
cats = conn.execute("SELECT categoria, COUNT(*), SUM(valor) FROM transacoes WHERE tipo='despesa' GROUP BY categoria ORDER BY SUM(valor) DESC").fetchall()
for c in cats:
    print(f"{c[0]}: {c[1]} lançamentos, Total: R$ {c[2]:,.2f}")

print("\n--- 2. SUBCATEGORIAS E GRUPOS SE EXISTIREM ---")
grupos = conn.execute("SELECT * FROM grupos_categoria").fetchall()
print("Grupos:", grupos)
subcats = conn.execute("SELECT id, grupo_id, nome, natureza_padrao, finalidade FROM subcategorias LIMIT 15").fetchall()
print("Subcategorias:", subcats)

conn.close()

