import sqlite3
import sys
import os
from decimal import Decimal
import pandas as pd

sys.path.insert(0, os.getcwd())
import saldo_service

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("=== VERIFICAÇÃO FINAL DE INTEGRAÇÃO EM FINANCAS_CASA.DB ===")

# 1. Integridade SQLite
cur.execute("PRAGMA integrity_check")
check = cur.fetchone()[0]
print(f"Integridade SQLite: {check}")
assert check == 'ok'

# 2. Saldos Oficiais
res_mp = saldo_service.calcular_saldo_conta(conn, 1)
res_cart = saldo_service.calcular_saldo_conta(conn, 2)
res_cons = saldo_service.calcular_saldo_consolidado(conn)

print(f"\nSaldos Calculados Oficialmente:")
print(f"  Mercado Pago (ID 1): R$ {res_mp['saldo_atual']}")
print(f"  Dinheiro / Carteira (ID 2): R$ {res_cart['saldo_atual']}")
print(f"  Saldo Consolidado Geral: R$ {res_cons['saldo_consolidado']}")

assert res_mp['saldo_atual'] == Decimal("8.83")
assert res_cart['saldo_atual'] == Decimal("77.50")
assert res_cons['saldo_consolidado'] == Decimal("86.33")

# 3. Estado da Copasa (id=2)
cur.execute("SELECT id, data, descricao, valor, pago, status_pagamento FROM transacoes WHERE id = 2")
cop = cur.fetchone()
print(f"\nCopasa (id=2) em produção: {cop}")
assert cop[4] == 0 # pago = 0
assert cop[5] == 'pendente'

# 4. Tabela pagamentos_despesas pronta e vazia
cur.execute("SELECT COUNT(*) FROM pagamentos_despesas")
pags_count = cur.fetchone()[0]
print(f"Total de pagamentos em pagamentos_despesas: {pags_count}")
assert pags_count == 0

# 5. Simulação temporária de pagamento da Copasa pelo novo motor
print("\n--- TESTE EM MEMÓRIA: Pagamento da Copasa em 20/10 pelo Mercado Pago ---")
mem_conn = sqlite3.connect(':memory:')
conn.backup(mem_conn)
res_pag = saldo_service.registrar_pagamento(
    conn=mem_conn,
    transacao_id=2,
    data_pagamento='2026-10-20',
    valor_pago=72.46,
    conta_id=1,
    considerado_no_marco=0,
    observacao="Teste em memória"
)
mp_mem = saldo_service.calcular_saldo_conta(mem_conn, 1)
print(f"Resultado do registro de pagamento: {res_pag}")
print(f"Saldo Mercado Pago após pagamento em 20/10: R$ {mp_mem['saldo_atual']} (esperado: -63.63)")
assert mp_mem['saldo_atual'] == Decimal("-63.63")

# Estorno em memória
saldo_service.estornar_pagamento(mem_conn, res_pag['pagamento_id'], "Estorno de teste")
mp_mem_estorno = saldo_service.calcular_saldo_conta(mem_conn, 1)
print(f"Saldo Mercado Pago após estorno: R$ {mp_mem_estorno['saldo_atual']} (esperado: 8.83)")
assert mp_mem_estorno['saldo_atual'] == Decimal("8.83")
mem_conn.close()

conn.close()
print("\n=== TODOS OS SISTEMAS 100% OPERACIONAIS E VALIDADOS ===")
