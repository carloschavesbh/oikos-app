import sqlite3
import sys
import os

sys.path.insert(0, os.getcwd())
import saldo_service

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("--- REGISTROS ATÉ 02/10/2026 EM FINANCAS_CASA.DB ---")
cur.execute("SELECT id, data, descricao, valor, tipo, conta, pago FROM transacoes WHERE data <= '2026-10-05' ORDER BY id ASC")
for row in cur.fetchall():
    print(row)

print("\n--- SALDOS ATUAIS NO BANCO DE PRODUÇÃO ---")
res_mp = saldo_service.calcular_saldo_conta(conn, 1)
res_cart = saldo_service.calcular_saldo_conta(conn, 2)
res_cons = saldo_service.calcular_saldo_consolidado(conn)
print(f"Mercado Pago: R$ {res_mp['saldo_atual']}")
print(f"Carteira: R$ {res_cart['saldo_atual']}")
print(f"Consolidado: R$ {res_cons['saldo_consolidado']}")

conn.close()
