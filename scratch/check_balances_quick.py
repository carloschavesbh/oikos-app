import sys, os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3, saldo_service

conn = sqlite3.connect('financas_casa.db')
c1 = saldo_service.calcular_saldo_conta(conn, 1)
c2 = saldo_service.calcular_saldo_conta(conn, 2)
cons = saldo_service.calcular_saldo_consolidado(conn)
print(f"Antes: Mercado Pago = R$ {c1['saldo_atual']}, Carteira = R$ {c2['saldo_atual']}, Consolidado = R$ {cons['saldo_consolidado']}")
conn.close()
