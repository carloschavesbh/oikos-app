import sqlite3
import shutil
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.getcwd())
import saldo_service

sys.stdout.reconfigure(encoding='utf-8')

PROD_DB = 'financas_casa.db'
BACKUP_DB = 'financas_casa_backup_etapa1.db'
TEMP_DB = 'test_etapa1_temp.db'

print("================================================================================")
print("ETAPA 1 — BATERIA DE TESTES DE VALIDAÇÃO DO SISTEMA DE PAGAMENTOS")
print("================================================================================")

# ------------------------------------------------------------------------------
# 1. Backup do banco de produção e validação de integridade
# ------------------------------------------------------------------------------
print("1. Criando backup do banco de produção...")
shutil.copy(PROD_DB, BACKUP_DB)
conn_bkp = sqlite3.connect(BACKUP_DB)
cur_bkp = conn_bkp.cursor()
cur_bkp.execute("PRAGMA integrity_check")
bkp_check = cur_bkp.fetchone()[0]
conn_bkp.close()
print(f"   Integridade do backup {BACKUP_DB}: {bkp_check}")
assert bkp_check == 'ok', "Integridade do backup falhou!"

# ------------------------------------------------------------------------------
# 2. Configura banco de teste temporário
# ------------------------------------------------------------------------------
if os.path.exists(TEMP_DB):
    os.remove(TEMP_DB)
shutil.copy(PROD_DB, TEMP_DB)

conn = sqlite3.connect(TEMP_DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("PRAGMA integrity_check")
assert cur.fetchone()[0] == 'ok'

# Saldos de referência iniciais
s_mp_ini = saldo_service.calcular_saldo_conta(conn, 1)['saldo_atual']
s_cart_ini = saldo_service.calcular_saldo_conta(conn, 2)['saldo_atual']
s_tot_ini = saldo_service.calcular_saldo_consolidado(conn)['saldo_consolidado']

print(f"\nSaldos iniciais no banco de teste:")
print(f"  Mercado Pago (1): R$ {s_mp_ini}")
print(f"  Carteira (2):     R$ {s_cart_ini}")
print(f"  Consolidado:      R$ {s_tot_ini}")

assert s_mp_ini == Decimal("8.83")
assert s_cart_ini == Decimal("77.50")
assert s_tot_ini == Decimal("86.33")

# ------------------------------------------------------------------------------
# 3. Teste: Despesa vencida em Setembro e paga pós-marco (20/10/2026)
# ------------------------------------------------------------------------------
print("\n--- TESTE 1: Despesa de Setembro paga pós-marco em Outubro ---")
# Cadastra uma despesa vencida em setembro (ex: 2026-09-15, R$ 100,00, pendente)
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, status_pagamento, afeta_saldo_bancario)
    VALUES ('2026-09-15', 'Conta de Energia Setembro Atrasada', 100.00, 'despesa', 'ENERGIA', 'Mercado Pago', 1, 0, 'pendente', 1)
""")
desp_set_id = cur.lastrowid
conn.commit()

# Verifica que o simples cadastro da conta atrasada de setembro NÃO altera o saldo bancário
s_mp_pos_cad = saldo_service.calcular_saldo_conta(conn, 1)['saldo_atual']
assert s_mp_pos_cad == Decimal("8.83"), "Erro: cadastrar conta atrasada alterou o saldo bancário!"
print("   Cadastro de despesa atrasada de setembro preservou o saldo de R$ 8.83 com sucesso.")

# ------------------------------------------------------------------------------
# 4. Pagamento Parcial (R$ 40,00 em 20/10 via Mercado Pago)
# ------------------------------------------------------------------------------
print("\n--- TESTE 2: Pagamento Parcial (R$ 40,00 em 20/10) ---")
res_p1 = saldo_service.registrar_pagamento(
    conn=conn,
    transacao_id=desp_set_id,
    data_pagamento='2026-10-20',
    valor_pago=40.00,
    conta_id=1,
    considerado_no_marco=0,
    forma_pagamento='Pix',
    observacao='1º pagamento parcial da conta de setembro'
)

# Verifica a obrigação
cur.execute("SELECT data, valor, pago, status_pagamento FROM transacoes WHERE id = ?", (desp_set_id,))
obrig_p1 = cur.fetchone()
print(f"   Vencimento da obrigação: {obrig_p1['data']} (Setembro preservado!)")
print(f"   Status da obrigação: {obrig_p1['status_pagamento']} (flag: {obrig_p1['pago']})")
print(f"   Saldo devedor restante: R$ {res_p1['saldo_devedor']}")

assert obrig_p1['data'] == '2026-09-15'
assert obrig_p1['pago'] == 2 # parcial
assert res_p1['saldo_devedor'] == Decimal("60.00")

# Verifica saldo Mercado Pago: 8.83 - 40.00 = -31.17
s_mp_p1 = saldo_service.calcular_saldo_conta(conn, 1)['saldo_atual']
print(f"   Saldo Mercado Pago pós-débito de R$ 40: R$ {s_mp_p1} (esperado: -31.17)")
assert s_mp_p1 == Decimal("-31.17")

# ------------------------------------------------------------------------------
# 5. Quitação Complementar (R$ 60,00 em 21/10 via Carteira - conta diferente!)
# ------------------------------------------------------------------------------
print("\n--- TESTE 3: Quitação Complementar (R$ 60,00 via Carteira) ---")
res_p2 = saldo_service.registrar_pagamento(
    conn=conn,
    transacao_id=desp_set_id,
    data_pagamento='2026-10-21',
    valor_pago=60.00,
    conta_id=2, # Carteira
    considerado_no_marco=0,
    forma_pagamento='Dinheiro Físico',
    observacao='Quitação do restante em dinheiro'
)

cur.execute("SELECT data, valor, pago, status_pagamento FROM transacoes WHERE id = ?", (desp_set_id,))
obrig_p2 = cur.fetchone()
print(f"   Vencimento da obrigação: {obrig_p2['data']}")
print(f"   Status da obrigação: {obrig_p2['status_pagamento']} (flag: {obrig_p2['pago']})")
print(f"   Saldo devedor restante: R$ {res_p2['saldo_devedor']}")

assert obrig_p2['data'] == '2026-09-15'
assert obrig_p2['pago'] == 1 # pago
assert res_p2['saldo_devedor'] == Decimal("0.00")

# Carteira: 77.50 - 60.00 = 17.50
s_cart_p2 = saldo_service.calcular_saldo_conta(conn, 2)['saldo_atual']
print(f"   Saldo Carteira pós-débito de R$ 60: R$ {s_cart_p2} (esperado: 17.50)")
assert s_cart_p2 == Decimal("17.50")
# Mercado Pago permanece em -31.17
assert saldo_service.calcular_saldo_conta(conn, 1)['saldo_atual'] == Decimal("-31.17")

# ------------------------------------------------------------------------------
# 6. Estorno do pagamento complementar (R$ 60,00)
# ------------------------------------------------------------------------------
print("\n--- TESTE 4: Estorno com recomposição de saldo ---")
res_est = saldo_service.estornar_pagamento(conn, res_p2['pagamento_id'], "Estorno de teste")
s_cart_est = saldo_service.calcular_saldo_conta(conn, 2)['saldo_atual']
cur.execute("SELECT pago, status_pagamento FROM transacoes WHERE id = ?", (desp_set_id,))
obrig_est = cur.fetchone()

print(f"   Após estorno: Carteira recomposta para R$ {s_cart_est} (esperado: 77.50)")
print(f"   Obrigação retornou para: {obrig_est['status_pagamento']} (flag: {obrig_est['pago']})")
print(f"   Saldo devedor reaberto: R$ {res_est['saldo_devedor']}")

assert s_cart_est == Decimal("77.50")
assert obrig_est['pago'] == 2 # volta para parcial
assert res_est['saldo_devedor'] == Decimal("60.00")

# ------------------------------------------------------------------------------
# 7. Estorno de Pagamento Histórico Pré-Marco (Condição 5)
# ------------------------------------------------------------------------------
print("\n--- TESTE 5: Estorno de pagamento histórico pré-marco (não afeta saldo) ---")
# Busca um pagamento histórico pré-marco (ex: transacao_id = 14 YouCine R$ 24,90)
cur.execute("""
    SELECT p.id, p.transacao_id, p.valor_pago, p.conta_id, p.considerado_no_marco
    FROM pagamentos_despesas p
    WHERE p.classificacao = 'historico_pre_marco' AND p.cancelado = 0
    LIMIT 1
""")
pag_hist = cur.fetchone()
print(f"   Pagamento histórico selecionado: ID {pag_hist['id']}, Obrigação #{pag_hist['transacao_id']}, R$ {pag_hist['valor_pago']}")

s_mp_antes_hist = saldo_service.calcular_saldo_conta(conn, 1)['saldo_atual']
s_cart_antes_hist = saldo_service.calcular_saldo_conta(conn, 2)['saldo_atual']

saldo_service.estornar_pagamento(conn, pag_hist['id'], "Estorno histórico de teste")

s_mp_depois_hist = saldo_service.calcular_saldo_conta(conn, 1)['saldo_atual']
s_cart_depois_hist = saldo_service.calcular_saldo_conta(conn, 2)['saldo_atual']

print(f"   Saldo MP antes: {s_mp_antes_hist} | depois: {s_mp_depois_hist}")
print(f"   Saldo Cart antes: {s_cart_antes_hist} | depois: {s_cart_depois_hist}")
assert s_mp_antes_hist == s_mp_depois_hist
assert s_cart_antes_hist == s_cart_depois_hist
print("   Sucesso: Estornar pagamento histórico NÃO gerou movimentação indevida de saldo!")

# ------------------------------------------------------------------------------
# 8. Verificação de Dados Reais Preservados
# ------------------------------------------------------------------------------
print("\n--- TESTE 6: Verificação de Copasa e Turno 99 ---")
cur.execute("SELECT id, data, descricao, valor, pago, status_pagamento FROM transacoes WHERE id = 2")
cop = dict(cur.fetchone())
print(f"   Copasa id=2: {cop['descricao']} | R$ {cop['valor']} | pago={cop['pago']} | status={cop['status_pagamento']}")
assert cop['pago'] == 0
assert cop['status_pagamento'] == 'pendente'
assert cop['valor'] == 72.46

cur.execute("SELECT id, data, ganho_bruto, combustivel, horas, km, status_conciliacao FROM turnos WHERE id = 2")
tur = dict(cur.fetchone())
print(f"   Turno 99 id=2: R$ {tur['ganho_bruto']} | comb: R$ {tur['combustivel']} | horas: {tur['horas']}h | {tur['status_conciliacao']}")
assert tur['ganho_bruto'] == 17.60
assert tur['combustivel'] == 0.0

conn.close()
os.remove(TEMP_DB)

print("\n================================================================================")
print("TODOS OS TESTES DA ETAPA 1 FORAM EXECUTADOS E APROVADOS COM 100% DE SUCESSO!")
print("================================================================================")
