import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3
import saldo_service
from decimal import Decimal

conn = sqlite3.connect('financas_casa.db')
c = conn.cursor()

c.execute("PRAGMA integrity_check")
check = c.fetchone()[0]
print(f"Integridade SQLite: {check}")
assert check == 'ok'

res_cons = saldo_service.calcular_saldo_consolidado(conn)
res_mp = saldo_service.calcular_saldo_conta(conn, 1)
res_cart = saldo_service.calcular_saldo_conta(conn, 2)

print(f"Saldo Consolidado: R$ {res_cons['saldo_consolidado']}")
print(f"Mercado Pago: R$ {res_mp['saldo_atual']}")
print(f"Dinheiro/Carteira: R$ {res_cart['saldo_atual']}")

assert res_cons['saldo_consolidado'] == Decimal('86.33')
assert res_mp['saldo_atual'] == Decimal('8.83')
assert res_cart['saldo_atual'] == Decimal('77.50')

c.execute("SELECT COUNT(*) FROM transacoes")
cnt_t = c.fetchone()[0]
print(f"Transacoes: {cnt_t}")
assert cnt_t == 32

c.execute("SELECT COUNT(*) FROM pagamentos_despesas")
cnt_p = c.fetchone()[0]
print(f"Pagamentos Despesas: {cnt_p}")
assert cnt_p == 14

c.execute("SELECT COUNT(*) FROM turnos")
cnt_turn = c.fetchone()[0]
print(f"Turnos: {cnt_turn}")
assert cnt_turn == 1

c.execute("SELECT COUNT(*) FROM cartoes")
cnt_card = c.fetchone()[0]
print(f"Cartoes: {cnt_card}")
assert cnt_card == 1

c.execute("SELECT COUNT(*) FROM contas_config")
cnt_acc = c.fetchone()[0]
print(f"Contas Config: {cnt_acc}")
assert cnt_acc == 2

c.execute("SELECT COUNT(*) FROM grupos_categoria")
cnt_g = c.fetchone()[0]
print(f"Grupos Categoria: {cnt_g}")
assert cnt_g == 16

c.execute("SELECT COUNT(*) FROM subcategorias")
cnt_sub = c.fetchone()[0]
print(f"Subcategorias: {cnt_sub}")
assert cnt_sub == 63

c.execute("SELECT COUNT(*) FROM pagaleve_compras")
cnt_plc = c.fetchone()[0]
print(f"Paga Leve Compras: {cnt_plc}")
assert cnt_plc == 6

c.execute("SELECT COUNT(*) FROM pagaleve_contas")
cnt_pla = c.fetchone()[0]
print(f"Paga Leve Contas: {cnt_pla}")
assert cnt_pla == 2

c.execute("SELECT COUNT(*) FROM dividas_gerenciamento")
print(f"Dívidas Gerenciamento criadas: {c.fetchone()[0]}")

# Ambiguous checks:
c.execute("SELECT id, descricao, status_rateio FROM transacoes WHERE status_rateio != 'normal'")
amb = c.fetchall()
print(f"Transações ambíguas preservadas como pendentes/especiais: {len(amb)}")
for r in amb:
    print(f"  - ID {r[0]}: {r[1]} -> status_rateio={r[2]}")

print("\n✓ BANCO DE PRODUÇÃO financas_casa.db MIGRADO E 100% PRESERVADO!")
conn.close()
