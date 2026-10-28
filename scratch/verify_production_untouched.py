import sys, os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3, saldo_service

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()
cur.execute('PRAGMA integrity_check')
print('Integridade financas_casa.db:', cur.fetchone()[0])
cur.execute('PRAGMA table_info(transacoes)')
cols = [c[1] for c in cur.fetchall()]
print('natureza_operacao existe em producao?:', 'natureza_operacao' in cols)
c1 = saldo_service.calcular_saldo_conta(conn, 1)
c2 = saldo_service.calcular_saldo_conta(conn, 2)
cons = saldo_service.calcular_saldo_consolidado(conn)
print(f"Saldos producao: MP = {c1['saldo_atual']}, Carteira = {c2['saldo_atual']}, Consolidado = {cons['saldo_consolidado']}")
cur.execute("SELECT COUNT(*) FROM transacoes")
print("Total transacoes producao:", cur.fetchone()[0])
conn.close()
