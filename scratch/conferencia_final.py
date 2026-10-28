import sqlite3
import sys
import os

sys.path.insert(0, os.getcwd())
import saldo_service

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("=== VERIFICAÇÃO FINAL DE FINANCAS_CASA.DB ===")
cur.execute("PRAGMA integrity_check")
print("Integridade SQLite:", cur.fetchone()[0])

print("\n--- SALDOS OFICIAIS CALCULADOS VIA SALDO_SERVICE ---")
res_mp = saldo_service.calcular_saldo_conta(conn, 1)
res_cart = saldo_service.calcular_saldo_conta(conn, 2)
res_cons = saldo_service.calcular_saldo_consolidado(conn)
print(f"Mercado Pago (ID 1): R$ {res_mp['saldo_atual']}")
print(f"Dinheiro / Carteira (ID 2): R$ {res_cart['saldo_atual']}")
print(f"Saldo Consolidado Geral: R$ {res_cons['saldo_consolidado']}")

print("\n--- TURNO ID 2 EM TURNOS ---")
cur.execute("SELECT id, data, horas, km, ganho_bruto, combustivel, observacao, periodo, plataforma FROM turnos WHERE id = 2")
print("Turno 2:", cur.fetchone())

print("\n--- AJUSTES DE SALDO ATIVOS (MARCOS INICIAIS) ---")
cur.execute("SELECT * FROM ajustes_saldo")
for a in cur.fetchall():
    print("Ajuste:", a)

print("\n--- CONFERÊNCIA DE TRANSAÇÕES RESTANTES ---")
cur.execute("SELECT COUNT(*) FROM transacoes")
print("Total de transações legítimas:", cur.fetchone()[0])
cur.execute("SELECT id, data, descricao, valor, tipo, conta FROM transacoes WHERE id >= 30")
for t in cur.fetchall():
    print("Transação:", t)

conn.close()
