import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3
import saldo_service
from decimal import Decimal

conn = sqlite3.connect('scratch/financas_casa_teste_preflight.db')
c = conn.cursor()

c.execute("PRAGMA integrity_check")
assert c.fetchone()[0] == 'ok'

res_cons = saldo_service.calcular_saldo_consolidado(conn)
print(f"Saldo Consolidado Preflight: {res_cons['saldo_consolidado']}")
assert res_cons['saldo_consolidado'] == Decimal('86.33')

c.execute("SELECT COUNT(*) FROM transacoes")
cnt_t = c.fetchone()[0]
assert cnt_t == 32

c.execute("SELECT COUNT(*) FROM pagamentos_despesas")
cnt_p = c.fetchone()[0]
assert cnt_p == 14

c.execute("SELECT COUNT(*) FROM turnos")
cnt_turn = c.fetchone()[0]
assert cnt_turn == 1

c.execute("SELECT COUNT(*) FROM grupos_categoria")
cnt_g = c.fetchone()[0]
assert cnt_g == 16

c.execute("SELECT COUNT(*) FROM subcategorias")
cnt_sub = c.fetchone()[0]
assert cnt_sub == 63

c.execute("SELECT COUNT(*) FROM pagaleve_compras")
cnt_plc = c.fetchone()[0]
assert cnt_plc == 6

c.execute("SELECT COUNT(*) FROM pagaleve_contas")
cnt_pla = c.fetchone()[0]
assert cnt_pla == 2

print("✓ TODOS OS CRITÉRIOS DE INTEGRIDADE NO PREFLIGHT PASSARAM 100%!")
conn.close()
