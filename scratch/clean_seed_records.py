import sqlite3

conn = sqlite3.connect('financas_remodelacao.db')
cur = conn.cursor()

# 1. Remover despesas eventuais geradas pelo seed_despesas_eventuais.py
cur.execute("DELETE FROM planejamento_despesas_eventuais WHERE id IN (3, 4, 5, 6, 7)")
removidos_dev = cur.rowcount
print(f"Removidos {removidos_dev} registros de seed da tabela planejamento_despesas_eventuais.")

# 2. Remover ajuste manual de teste em planejamento_cenarios_renda
cur.execute("DELETE FROM planejamento_cenarios_renda WHERE observacoes LIKE '%Ajuste manual para teste%'")
removidos_cen = cur.rowcount
print(f"Removidos {removidos_cen} registros de teste da tabela planejamento_cenarios_renda.")

conn.commit()

# Conferir estado
cur.execute("SELECT COUNT(*) FROM planejamento_despesas_eventuais")
print(f"Total atual em planejamento_despesas_eventuais: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM planejamento_cenarios_renda")
print(f"Total atual em planejamento_cenarios_renda: {cur.fetchone()[0]}")

conn.close()
