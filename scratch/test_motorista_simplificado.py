import sqlite3
import shutil
import os
import sys
from decimal import Decimal

# Inclui cwd no path
sys.path.insert(0, os.getcwd())
import saldo_service

TEMP_DB = 'test_motorista_simplificado_temp.db'
if os.path.exists(TEMP_DB):
    try:
        os.remove(TEMP_DB)
    except Exception:
        pass

# Copia do backup seguro criado no passo anterior
shutil.copy('financas_casa_backup_urgente_motorista.db', TEMP_DB)
print("=== Banco de teste criado a partir do backup ===")

conn = sqlite3.connect(TEMP_DB)
cur = conn.cursor()

# ------------------------------------------------------------------------------
# 1. AUDITORIA DOS REGISTROS AFETADOS EM 19/10/2026
# ------------------------------------------------------------------------------
print("\n--- 1. AUDITORIA DOS REGISTROS EM 19/10 ---")
cur.execute("SELECT id, data, descricao, valor, tipo, categoria, conta, pago FROM transacoes WHERE id >= 34")
rows_34_36 = cur.fetchall()
for r in rows_34_36:
    print(f"Transação {r[0]}: {r[1]} | {r[2]} | R$ {r[3]:.2f} ({r[4]}) | Conta: {r[6]} | Pago: {r[7]}")

res_mp_antes = saldo_service.calcular_saldo_conta(conn, 1)
res_cons_antes = saldo_service.calcular_saldo_consolidado(conn)
print(f"\nSaldo ANTES do saneamento: Mercado Pago = R$ {res_mp_antes['saldo_atual']} | Consolidado = R$ {res_cons_antes['saldo_consolidado']}")
assert res_mp_antes['saldo_atual'] == Decimal("-15.97")
assert res_cons_antes['saldo_consolidado'] == Decimal("84.03")

# SANEAMENTO DOS REGISTROS INDEVIDOS:
# id=35 (despesa de R$ 60 de combustível padrão indevida) -> Deletar
# id=34 (receita de R$ 17.60 órfã do primeiro lançamento) -> Deletar
# id=36 (receita de R$ 17.60 do segundo lançamento) -> Essa é a receita do turno real de 19/10!
cur.execute("DELETE FROM transacoes WHERE id IN (34, 35)")
conn.commit()

# Verifica se o saldo do Mercado Pago agora reflete o marco inicial (8.83) + o ganho real de R$ 17,60 transferido da 99
res_mp_pos = saldo_service.calcular_saldo_conta(conn, 1)
res_cons_pos = saldo_service.calcular_saldo_consolidado(conn)
print(f"Saldo APÓS sanear id 34 e 35: Mercado Pago = R$ {res_mp_pos['saldo_atual']} | Consolidado = R$ {res_cons_pos['saldo_consolidado']}")
assert res_mp_pos['saldo_atual'] == Decimal("26.43")  # 8.83 + 17.60 = 26.43
assert res_cons_pos['saldo_consolidado'] == Decimal("126.43") # 108.83 + 17.60 = 126.43

# E se os R$ 17,60 já estivessem contemplados no saldo de R$ 8,83 no momento do marco das 17h?
# Se já estavam contemplados, id=36 também é removido e o saldo volta a exatos 8.83 e 108.83!
print("Se o ganho de R$ 17,60 já estava conferido no marco inicial das 17h:")
cur.execute("DELETE FROM transacoes WHERE id = 36")
conn.commit()
res_mp_base = saldo_service.calcular_saldo_conta(conn, 1)
res_cons_base = saldo_service.calcular_saldo_consolidado(conn)
print(f"Saldo base restabelecido: Mercado Pago = R$ {res_mp_base['saldo_atual']} | Consolidado = R$ {res_cons_base['saldo_consolidado']}")
assert res_mp_base['saldo_atual'] == Decimal("8.83")
assert res_cons_base['saldo_consolidado'] == Decimal("108.83")

# ------------------------------------------------------------------------------
# 2. ADIÇÃO DAS COLUNAS DE VÍNCULO E CONCILIAÇÃO
# ------------------------------------------------------------------------------
print("\n--- 2. PREPARAÇÃO DA ESTRUTURA COM VÍNCULO ESTÁVEL ---")
cur.execute("PRAGMA table_info(transacoes)")
cols_transacoes = [c[1] for c in cur.fetchall()]
if "turno_id" not in cols_transacoes:
    cur.execute("ALTER TABLE transacoes ADD COLUMN turno_id INTEGER REFERENCES turnos(id)")
    print("Coluna 'turno_id' adicionada com sucesso em transacoes.")

cur.execute("PRAGMA table_info(turnos)")
cols_turnos = [c[1] for c in cur.fetchall()]
novas_cols_turnos = [
    ("plataforma", "TEXT DEFAULT '99'"),
    ("valor_transferido_banco", "REAL DEFAULT 0"),
    ("dinheiro_fisico_recebido", "REAL DEFAULT 0"),
    ("despesas_diretas_app", "REAL DEFAULT 0"),
    ("combustivel_consumido", "REAL DEFAULT 0"),
    ("status_conciliacao", "TEXT DEFAULT 'conciliado'")
]
for col, c_def in novas_cols_turnos:
    if col not in cols_turnos:
        cur.execute(f"ALTER TABLE turnos ADD COLUMN {col} {c_def}")
print("Colunas de conciliação adicionadas em turnos com sucesso.")
conn.commit()

# ------------------------------------------------------------------------------
# 3. TESTES DOS CENÁRIOS OPERACIONAIS E CONCILIAÇÃO
# ------------------------------------------------------------------------------
print("\n--- 3. TESTE CENÁRIO A: Turno com transferência imediata para Mercado Pago ---")
# Motorista rodou 4h, 75km, ganhou R$ 150 na 99 e transferiu R$ 150 via Pix para o Mercado Pago.
# Não houve dinheiro físico nem combustível no dia.
cur.execute("""
    INSERT INTO turnos (data, horas, km, ganho_bruto, combustivel, plataforma, valor_transferido_banco, dinheiro_fisico_recebido, status_conciliacao)
    VALUES ('2026-10-20', 4.0, 75.0, 150.0, 0.0, '99', 150.0, 0.0, 'conciliado')
""")
t_a_id = cur.lastrowid

# Registra a receita bancária VINCULADA ao turno no Mercado Pago
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-20', 'Repasse 99 (Turno #A)', 150.0, 'receita', 'Renda Corridas (99/Uber)', 'Mercado Pago', 1, 1, 1, ?)
""", (t_a_id,))
conn.commit()

res_a_mp = saldo_service.calcular_saldo_conta(conn, 1)
res_a_cart = saldo_service.calcular_saldo_conta(conn, 2)
print(f"Cenário A: Mercado Pago = R$ {res_a_mp['saldo_atual']} (esperado: 158.83) | Carteira = R$ {res_a_cart['saldo_atual']} (esperado: 100.00)")
assert res_a_mp['saldo_atual'] == Decimal("158.83")
assert res_a_cart['saldo_atual'] == Decimal("100.00")

print("\n--- TESTE CENÁRIO B: Turno com parte em Dinheiro Físico ---")
# Ganho total R$ 100: R$ 70 transferido para Mercado Pago e R$ 30 recebido em mãos (dinheiro físico)
cur.execute("""
    INSERT INTO turnos (data, horas, km, ganho_bruto, combustivel, plataforma, valor_transferido_banco, dinheiro_fisico_recebido, status_conciliacao)
    VALUES ('2026-10-21', 3.0, 50.0, 100.0, 0.0, '99', 70.0, 30.0, 'conciliado')
""")
t_b_id = cur.lastrowid

# Lançamentos vinculados: R$ 70 no Mercado Pago e R$ 30 na Carteira
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-21', 'Repasse 99 (Turno #B)', 70.0, 'receita', 'Renda Corridas (99/Uber)', 'Mercado Pago', 1, 1, 1, ?)
""", (t_b_id,))
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-21', 'Dinheiro de Passageiro (Turno #B)', 30.0, 'receita', 'Renda Corridas (99/Uber)', 'Dinheiro / Carteira', 2, 1, 1, ?)
""", (t_b_id,))
conn.commit()

res_b_mp = saldo_service.calcular_saldo_conta(conn, 1)
res_b_cart = saldo_service.calcular_saldo_conta(conn, 2)
print(f"Cenário B: Mercado Pago = R$ {res_b_mp['saldo_atual']} (esperado: 228.83) | Carteira = R$ {res_b_cart['saldo_atual']} (esperado: 130.00)")
assert res_b_mp['saldo_atual'] == Decimal("228.83")
assert res_b_cart['saldo_atual'] == Decimal("130.00")

print("\n--- TESTE CENÁRIO C: Diferença não confirmada -> Pendente de conciliação ---")
# Ganhou R$ 80, mas transferiu R$ 60 ao Mercado Pago. Não tem certeza sobre os R$ 20.
# REGRA: NÃO alterar a carteira física automaticamente!
cur.execute("""
    INSERT INTO turnos (data, horas, km, ganho_bruto, combustivel, plataforma, valor_transferido_banco, dinheiro_fisico_recebido, status_conciliacao)
    VALUES ('2026-10-22', 2.0, 30.0, 80.0, 0.0, '99', 60.0, 0.0, 'pendente')
""")
t_c_id = cur.lastrowid

# Registra apenas os R$ 60 que entraram no banco!
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-22', 'Repasse 99 (Turno #C)', 60.0, 'receita', 'Renda Corridas (99/Uber)', 'Mercado Pago', 1, 1, 1, ?)
""", (t_c_id,))
conn.commit()

res_c_mp = saldo_service.calcular_saldo_conta(conn, 1)
res_c_cart = saldo_service.calcular_saldo_conta(conn, 2)
print(f"Cenário C: Mercado Pago = R$ {res_c_mp['saldo_atual']} (esperado: 288.83) | Carteira = R$ {res_c_cart['saldo_atual']} (inalterada em 130.00)")
assert res_c_mp['saldo_atual'] == Decimal("288.83")
assert res_c_cart['saldo_atual'] == Decimal("130.00")

print("\n--- TESTE CENÁRIO D: Abastecimento real separado de consumo estimado ---")
# O motorista abasteceu R$ 50 no posto com cartão de débito do Mercado Pago.
# Consumo estimado do turno foi R$ 35 (apenas métrica operacional).
# Movimentação financeira no banco: apenas os R$ 50 do posto!
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario)
    VALUES ('2026-10-22', 'Posto Ipiranga - Abastecimento', 50.0, 'despesa', 'Combustível', 'Mercado Pago', 1, 1, 1)
""")
conn.commit()

res_d_mp = saldo_service.calcular_saldo_conta(conn, 1)
print(f"Cenário D: Mercado Pago após abastecer R$ 50 = R$ {res_d_mp['saldo_atual']} (esperado: 238.83)")
assert res_d_mp['saldo_atual'] == Decimal("238.83")

print("\n--- TESTE CENÁRIO E: Edição Idempotente (Sem duplicar lançamentos) ---")
# Usuário edita o Turno B: o repasse na verdade foi R$ 90 e o dinheiro físico foi R$ 10 (total R$ 100)
# Ação segura: atualiza o turno e substitui as transações vinculadas àquele turno_id
cur.execute("""
    UPDATE turnos 
    SET valor_transferido_banco = 90.0, dinheiro_fisico_recebido = 10.0
    WHERE id = ?
""", (t_b_id,))

# Deleta transações antigas de t_b_id e recria as corrigidas
cur.execute("DELETE FROM transacoes WHERE turno_id = ?", (t_b_id,))
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-21', 'Repasse 99 (Turno #B)', 90.0, 'receita', 'Renda Corridas (99/Uber)', 'Mercado Pago', 1, 1, 1, ?)
""", (t_b_id,))
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-21', 'Dinheiro de Passageiro (Turno #B)', 10.0, 'receita', 'Renda Corridas (99/Uber)', 'Dinheiro / Carteira', 2, 1, 1, ?)
""", (t_b_id,))
conn.commit()

res_e_mp = saldo_service.calcular_saldo_conta(conn, 1)
res_e_cart = saldo_service.calcular_saldo_conta(conn, 2)
print(f"Cenário E (Pós-edição): Mercado Pago = R$ {res_e_mp['saldo_atual']} (esperado: 258.83) | Carteira = R$ {res_e_cart['saldo_atual']} (esperado: 110.00)")
assert res_e_mp['saldo_atual'] == Decimal("258.83")  # subiu 20 no banco
assert res_e_cart['saldo_atual'] == Decimal("110.00") # desceu 20 na carteira

print("\n--- TESTE CENÁRIO F: Exclusão Atômica de Turno ---")
# Se o usuário excluir o Turno A: remove da tabela turnos e remove atomicamente as transações com turno_id = t_a_id
cur.execute("DELETE FROM transacoes WHERE turno_id = ?", (t_a_id,))
cur.execute("DELETE FROM turnos WHERE id = ?", (t_a_id,))
conn.commit()

res_f_mp = saldo_service.calcular_saldo_conta(conn, 1)
print(f"Cenário F (Pós-exclusão do Turno A): Mercado Pago = R$ {res_f_mp['saldo_atual']} (reduziu exatamente os R$ 150 do Turno A para 108.83)")
assert res_f_mp['saldo_atual'] == Decimal("108.83")

conn.close()
try:
    os.remove(TEMP_DB)
except Exception:
    pass

print("\n=======================================================")
print("TODOS OS TESTES DO FLUXO SIMPLIFICADO PASSARAM COM 100% DE SUCESSO!")
print("=======================================================")
