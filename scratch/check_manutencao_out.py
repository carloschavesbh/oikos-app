import sqlite3

conn = sqlite3.connect('financas_remodelacao.db')
rows = conn.execute("""
    SELECT id, data, descricao, valor, categoria, conta 
    FROM transacoes 
    WHERE tipo='despesa' 
      AND categoria = 'Manutenção Veículo'
      AND data BETWEEN '2026-10-01' AND '2026-10-31'
""").fetchall()
print("Manutenção Veículo em Outubro:", rows)
conn.close()
