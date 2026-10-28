import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM transacoes")
total_trans = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM transacoes WHERE tipo = 'despesa'")
total_desp = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM transacoes WHERE tipo = 'receita'")
total_rec = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM transacoes WHERE tipo = 'despesa' AND pago = 1")
desp_pagas = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM transacoes WHERE tipo = 'despesa' AND pago = 0")
desp_pend = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM turnos")
total_turnos = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM ajustes_saldo")
total_ajustes = cur.fetchone()[0]

print(f"Total de Transações: {total_trans}")
print(f"Despesas: {total_desp} (Pagas: {desp_pagas}, Pendentes: {desp_pend})")
print(f"Receitas: {total_rec}")
print(f"Turnos: {total_turnos}")
print(f"Ajustes de saldo: {total_ajustes}")

print("\nDespesas atualmente com pago = 1:")
cur.execute("SELECT id, data, descricao, valor, tipo, conta, conta_id, pago, status_pagamento FROM transacoes WHERE tipo = 'despesa' AND pago = 1 ORDER BY data ASC, id ASC")
for r in cur.fetchall():
    print(r)

print("\nDespesas atualmente com pago = 0:")
cur.execute("SELECT id, data, descricao, valor, tipo, conta, conta_id, pago, status_pagamento FROM transacoes WHERE tipo = 'despesa' AND pago = 0 ORDER BY data ASC, id ASC")
for r in cur.fetchall():
    print(r)

conn.close()
