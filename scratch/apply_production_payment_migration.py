import sqlite3
import sys
import os
import shutil
from decimal import Decimal

sys.path.insert(0, os.getcwd())
import saldo_service

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'financas_casa.db'
BACKUP_PATH = 'financas_casa_backup_pos_auditoria_migracao_16_regras.db'

print("================================================================================")
print("APLICAÇÃO OFICIAL DA MIGRAÇÃO DE PAGAMENTOS EM PRODUÇÃO")
print("================================================================================")

# ------------------------------------------------------------------------------
# CONDIÇÃO 1: Novo Backup Integral e Validação de Integridade
# ------------------------------------------------------------------------------
print(f"1. Criando backup integral em: {BACKUP_PATH}...")
shutil.copy(DB_PATH, BACKUP_PATH)

conn_b = sqlite3.connect(BACKUP_PATH)
cur_b = conn_b.cursor()
cur_b.execute("PRAGMA integrity_check")
check_b = cur_b.fetchone()[0]
conn_b.close()
print(f"   Validação de integridade do backup: {check_b}")
assert check_b == 'ok', "Falha na integridade do arquivo de backup!"

# Conecta ao banco de produção
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ------------------------------------------------------------------------------
# CONDIÇÃO 15 (PARTE 1): Contagens e Saldos ANTES da Migração
# ------------------------------------------------------------------------------
cur.execute("SELECT COUNT(*) FROM transacoes")
trans_total_antes = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM transacoes WHERE tipo = 'despesa'")
desp_total_antes = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM transacoes WHERE tipo = 'despesa' AND pago = 1")
desp_pagas_antes = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM transacoes WHERE tipo = 'despesa' AND pago = 0")
desp_pend_antes = cur.fetchone()[0]

s_mp_antes = saldo_service.calcular_saldo_conta(conn, 1)
s_cart_antes = saldo_service.calcular_saldo_conta(conn, 2)
s_cons_antes = saldo_service.calcular_saldo_consolidado(conn)

print("\n--- SITUAÇÃO ANTES DA MIGRAÇÃO ---")
print(f"Total de Transações: {trans_total_antes}")
print(f"Despesas Pagas: {desp_pagas_antes} | Despesas Pendentes: {desp_pend_antes}")
print(f"Mercado Pago: R$ {s_mp_antes['saldo_atual']}")
print(f"Dinheiro / Carteira: R$ {s_cart_antes['saldo_atual']}")
print(f"Consolidado Geral: R$ {s_cons_antes['saldo_consolidado']}")

# ------------------------------------------------------------------------------
# CONDIÇÃO 16: Verificação da Copasa (id=2, R$ 72,46)
# ------------------------------------------------------------------------------
cur.execute("SELECT id, data, descricao, valor, pago, status_pagamento FROM transacoes WHERE id = 2")
cop_check = cur.fetchone()
print(f"\nCondição 16 - Copasa id=2: pago={cop_check['pago']} | status={cop_check['status_pagamento']}")
if cop_check['pago'] != 0 or cop_check['status_pagamento'] != 'pendente':
    print("   Restaurando Copasa id=2 para rigorosamente pendente...")
    cur.execute("UPDATE transacoes SET pago = 0, status_pagamento = 'pendente' WHERE id = 2")
    conn.commit()
    print("   Copasa id=2 restaurada com sucesso.")
assert cop_check['valor'] == 72.46

# ------------------------------------------------------------------------------
# MIGRAÇÃO DE ESQUEMA E DADOS
# ------------------------------------------------------------------------------
print("\n--- EXECUTANDO MIGRAÇÃO DO ESQUEMA ---")
saldo_service.migrar_esquema(conn)

# Verifica pagamentos já existentes para garantir idempotência
cur.execute("SELECT DISTINCT transacao_id FROM pagamentos_despesas")
pags_existentes_ids = set(r[0] for r in cur.fetchall())

# 1. Migração de despesas históricas pré-marco (Condição 5: data real desconhecida)
cur.execute("""
    SELECT id, data, descricao, valor, conta_id, afeta_saldo_bancario 
    FROM transacoes 
    WHERE tipo = 'despesa' AND pago = 1 AND data < '2026-10-19'
    ORDER BY id ASC
""")
desp_legadas_pre = cur.fetchall()

pags_pre_migrados = 0
for d in desp_legadas_pre:
    d_id = d['id']
    if d_id in pags_existentes_ids:
        continue
    d_val = d['valor']
    d_cents = saldo_service.decimal_to_cents(saldo_service.to_decimal(d_val))
    c_id = d['conta_id'] or 1
    afeta = d['afeta_saldo_bancario'] if d['afeta_saldo_bancario'] is not None else 1
    
    cur.execute("""
        INSERT INTO pagamentos_despesas
        (transacao_id, data_pagamento, data_real_desconhecida, classificacao, valor_pago, valor_pago_centavos, conta_id, afeta_saldo_bancario, considerado_no_marco, forma_pagamento, observacao)
        VALUES (?, NULL, 1, 'historico_pre_marco', ?, ?, ?, ?, 1, 'Histórico', 'Pagamento anterior ao marco de 19/10/2026 - já contemplado no saldo inicial')
    """, (d_id, d_val, d_cents, c_id, afeta))
    pags_pre_migrados += 1

print(f"Pagamentos históricos pré-marco inseridos: {pags_pre_migrados}")

# 2. Migração de despesas legítimas pós-marco (IDs 37 e 38 - Compras Las Casas em 19/10)
cur.execute("""
    SELECT id, data, descricao, valor, conta_id, afeta_saldo_bancario 
    FROM transacoes 
    WHERE tipo = 'despesa' AND pago = 1 AND data >= '2026-10-19'
    ORDER BY id ASC
""")
desp_pos_marco = cur.fetchall()

pags_pos_migrados = 0
for d in desp_pos_marco:
    d_id = d['id']
    if d_id in pags_existentes_ids:
        continue
    d_val = d['valor']
    d_cents = saldo_service.decimal_to_cents(saldo_service.to_decimal(d_val))
    c_id = d['conta_id'] or 2
    afeta = d['afeta_saldo_bancario'] if d['afeta_saldo_bancario'] is not None else 1
    
    cur.execute("""
        INSERT INTO pagamentos_despesas
        (transacao_id, data_pagamento, data_real_desconhecida, classificacao, valor_pago, valor_pago_centavos, conta_id, afeta_saldo_bancario, considerado_no_marco, forma_pagamento, observacao)
        VALUES (?, ?, 0, 'pagamento_efetivo', ?, ?, ?, ?, 0, 'Dinheiro', 'Compra presencial em supermercado após a conciliação')
    """, (d_id, d['data'], d_val, d_cents, c_id, afeta))
    pags_pos_migrados += 1

print(f"Pagamentos efetivos pós-marco inseridos: {pags_pos_migrados}")

# 3. Atualiza status_pagamento em transacoes
cur.execute("UPDATE transacoes SET status_pagamento = 'pago' WHERE pago = 1 AND (status_pagamento IS NULL OR status_pagamento = 'pendente')")
cur.execute("UPDATE transacoes SET status_pagamento = 'pendente' WHERE pago = 0 AND (status_pagamento IS NULL OR status_pagamento != 'pendente')")

conn.commit()

# ------------------------------------------------------------------------------
# CONDIÇÃO 15 (PARTE 2): Contagens e Saldos DEPOIS da Migração
# ------------------------------------------------------------------------------
cur.execute("PRAGMA integrity_check")
check_final = cur.fetchone()[0]
assert check_final == 'ok', "Erro de integridade no banco de dados pós-migração!"

cur.execute("SELECT COUNT(*) FROM transacoes")
trans_total_depois = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM transacoes WHERE tipo = 'despesa'")
desp_total_depois = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM transacoes WHERE tipo = 'despesa' AND pago = 1")
desp_pagas_depois = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM transacoes WHERE tipo = 'despesa' AND pago = 0")
desp_pend_depois = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM pagamentos_despesas")
pags_total_depois = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM pagamentos_despesas WHERE cancelado = 0")
pags_ativos_depois = cur.fetchone()[0]

s_mp_depois = saldo_service.calcular_saldo_conta(conn, 1)
s_cart_depois = saldo_service.calcular_saldo_conta(conn, 2)
s_cons_depois = saldo_service.calcular_saldo_consolidado(conn)

print("\n--- SITUAÇÃO DEPOIS DA MIGRAÇÃO ---")
print(f"Total de Transações: {trans_total_depois} (preservadas: {trans_total_antes == trans_total_depois})")
print(f"Despesas Pagas: {desp_pagas_depois} | Despesas Pendentes: {desp_pend_depois}")
print(f"Total de Pagamentos Registrados em pagamentos_despesas: {pags_total_depois} (Ativos: {pags_ativos_depois})")
print(f"Mercado Pago: R$ {s_mp_depois['saldo_atual']} (esperado: 8.83)")
print(f"Dinheiro / Carteira: R$ {s_cart_depois['saldo_atual']} (esperado: 77.50)")
print(f"Consolidado Geral: R$ {s_cons_depois['saldo_consolidado']} (esperado: 86.33)")

assert s_mp_depois['saldo_atual'] == Decimal("8.83")
assert s_cart_depois['saldo_atual'] == Decimal("77.50")
assert s_cons_depois['saldo_consolidado'] == Decimal("86.33")

conn.close()
print("\n================================================================================")
print("MIGRAÇÃO EM PRODUÇÃO EXECUTADA COM SUCESSO ABSOLUTO!")
print("================================================================================")

