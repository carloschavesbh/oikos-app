import sqlite3

conn = sqlite3.connect('financas_casa.db')
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM transacoes")
t_cnt = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM pagamentos_despesas")
p_cnt = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM turnos")
turn_cnt = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM cartoes")
card_cnt = c.fetchone()[0]

c.execute("SELECT COUNT(*), SUM(saldo_inicial) FROM contas_config")
acc_cnt, saldo_ini = c.fetchone()

# Let's check how app.py calculates saldo consolidado
print(f"Transacoes: {t_cnt}")
print(f"Pagamentos Despesas: {p_cnt}")
print(f"Turnos: {turn_cnt}")
print(f"Cartoes: {card_cnt}")
print(f"Contas: {acc_cnt}, Saldo Inicial: {saldo_ini}")

# Check transacoes sum or balance
c.execute("SELECT tipo, SUM(valor) FROM transacoes GROUP BY tipo")
for row in c.fetchall():
    print(f"Tipo {row[0]}: {row[1]}")

conn.close()
