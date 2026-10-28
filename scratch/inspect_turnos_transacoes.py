import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("=== TABELA TURNOS ===")
cur.execute("PRAGMA table_info(turnos)")
print("Colunas:", [c[1] for c in cur.fetchall()])
cur.execute("SELECT * FROM turnos")
turnos = cur.fetchall()
for t in turnos:
    print(t)

print("\n=== TRANSACOES RECENTES (data >= '2026-10-18' ou com 'turno' ou 'combustivel' na descricao) ===")
cur.execute("""
    SELECT id, data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario
    FROM transacoes
    WHERE data >= '2026-10-18' 
       OR descricao LIKE '%Turno%' 
       OR descricao LIKE '%Combust%' 
       OR descricao LIKE '%Uber%' 
       OR descricao LIKE '%99%'
    ORDER BY id ASC
""")
for r in cur.fetchall():
    print(r)

print("\n=== TODAS AS TRANSACOES COM ID > 30 ===")
cur.execute("SELECT id, data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario FROM transacoes WHERE id >= 30 ORDER BY id ASC")
for r in cur.fetchall():
    print(r)

print("\n=== AJUSTES DE SALDO ===")
cur.execute("SELECT * FROM ajustes_saldo")
for r in cur.fetchall():
    print(r)

conn.close()
