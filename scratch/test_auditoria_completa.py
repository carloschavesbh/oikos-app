import sqlite3
import shutil
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.getcwd())
import saldo_service

TEMP_DB = 'scratch_temp_test.db'
if os.path.exists(TEMP_DB):
    try:
        os.remove(TEMP_DB)
    except Exception:
        pass

# Copia de financas_casa.db atual
shutil.copy('financas_casa.db', TEMP_DB)
print("=== Banco temporário de teste copiado ===")

conn = sqlite3.connect(TEMP_DB)
cur = conn.cursor()

# 1. Auditoria prévia dos registros 34, 35 e 36
cur.execute("SELECT id, data, descricao, valor, tipo, categoria, conta, pago FROM transacoes WHERE id IN (34, 35, 36) ORDER BY id ASC")
rows = cur.fetchall()
print(f"Encontrados {len(rows)} registros alvo:")
for r in rows:
    print("  ", r)
assert len(rows) == 3
assert rows[0][0] == 34 and rows[0][3] == 17.60 and rows[0][4] == 'receita'
assert rows[1][0] == 35 and rows[1][3] == 60.00 and rows[1][4] == 'despesa'
assert rows[2][0] == 36 and rows[2][3] == 17.60 and rows[2][4] == 'receita'

# 2. Confere turno 2
cur.execute("SELECT id, data, horas, km, ganho_bruto, combustivel, observacao FROM turnos WHERE id = 2")
turno_2 = cur.fetchone()
print(f"Turno id=2: {turno_2}")
assert turno_2 is not None
assert turno_2[0] == 2
assert turno_2[2] == 1.0 # horas
assert turno_2[3] == 15.0 # km
assert turno_2[4] == 17.60 # ganho bruto
assert turno_2[5] == 0.0 # combustivel

# 3. Saldos ANTES do saneamento
res_mp_antes = saldo_service.calcular_saldo_conta(conn, 1)
res_cart_antes = saldo_service.calcular_saldo_conta(conn, 2)
res_cons_antes = saldo_service.calcular_saldo_consolidado(conn)
print(f"Saldos ANTES: MP = R$ {res_mp_antes['saldo_atual']} | Carteira = R$ {res_cart_antes['saldo_atual']} | Consolidado = R$ {res_cons_antes['saldo_consolidado']}")
assert res_mp_antes['saldo_atual'] == Decimal("-15.97")
assert res_cart_antes['saldo_atual'] == Decimal("100.00")
assert res_cons_antes['saldo_consolidado'] == Decimal("84.03")

# 4. Executa saneamento: remoção de 34, 35 e 36
cur.execute("DELETE FROM transacoes WHERE id IN (34, 35, 36)")
conn.commit()

# 5. Saldos APÓS saneamento
res_mp_pos = saldo_service.calcular_saldo_conta(conn, 1)
res_cart_pos = saldo_service.calcular_saldo_conta(conn, 2)
res_cons_pos = saldo_service.calcular_saldo_consolidado(conn)
print(f"Saldos APÓS Saneamento: MP = R$ {res_mp_pos['saldo_atual']} | Carteira = R$ {res_cart_pos['saldo_atual']} | Consolidado = R$ {res_cons_pos['saldo_consolidado']}")
assert res_mp_pos['saldo_atual'] == Decimal("8.83")
assert res_cart_pos['saldo_atual'] == Decimal("100.00")
assert res_cons_pos['saldo_consolidado'] == Decimal("108.83")

# 6. Adiciona colunas necessárias
cur.execute("PRAGMA table_info(transacoes)")
cols_t = [c[1] for c in cur.fetchall()]
if "turno_id" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN turno_id INTEGER REFERENCES turnos(id)")

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
conn.commit()

# 7. Simula NOVO TURNO sem movimentação bancária (caso comum: valor já incluso no saldo ou mantido no app)
cur.execute("""
    INSERT INTO turnos (data, horas, km, ganho_bruto, combustivel, plataforma, valor_transferido_banco, dinheiro_fisico_recebido, status_conciliacao)
    VALUES ('2026-10-20', 3.0, 45.0, 80.0, 0.0, '99', 0.0, 0.0, 'conciliado')
""")
t3_id = cur.lastrowid
conn.commit()

# Verifica se o saldo NÃO foi alterado
res_mp_t3 = saldo_service.calcular_saldo_conta(conn, 1)
res_cons_t3 = saldo_service.calcular_saldo_consolidado(conn)
print(f"Após turno sem movimentação bancária: MP = R$ {res_mp_t3['saldo_atual']} | Consolidado = R$ {res_cons_t3['saldo_consolidado']}")
assert res_mp_t3['saldo_atual'] == Decimal("8.83")
assert res_cons_t3['saldo_consolidado'] == Decimal("108.83")

# 8. Simula NOVO TURNO COM movimentação bancária explícita
cur.execute("""
    INSERT INTO turnos (data, horas, km, ganho_bruto, combustivel, plataforma, valor_transferido_banco, dinheiro_fisico_recebido, status_conciliacao)
    VALUES ('2026-10-21', 4.0, 60.0, 120.0, 0.0, '99', 120.0, 0.0, 'conciliado')
""")
t4_id = cur.lastrowid
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-21', 'Repasse 99 (Turno #4)', 120.0, 'receita', 'Renda Corridas (99/Uber)', 'Mercado Pago', 1, 1, 1, ?)
""", (t4_id,))
conn.commit()

res_mp_t4 = saldo_service.calcular_saldo_conta(conn, 1)
print(f"Após repasse bancário real do Turno 4: MP = R$ {res_mp_t4['saldo_atual']} (esperado: R$ 128.83)")
assert res_mp_t4['saldo_atual'] == Decimal("128.83")

# 9. Simula EXCLUSÃO DO TURNO 4: garantir que a movimentação bancária legítima NÃO é excluída
cur.execute("UPDATE transacoes SET turno_id = NULL WHERE turno_id = ?", (t4_id,))
cur.execute("DELETE FROM turnos WHERE id = ?", (t4_id,))
conn.commit()

cur.execute("SELECT id, descricao, valor FROM transacoes WHERE data = '2026-10-21'")
transacao_legitima = cur.fetchone()
print(f"Transação legítima preservada no extrato após exclusão do turno: {transacao_legitima}")
assert transacao_legitima is not None
assert transacao_legitima[2] == 120.0

res_mp_pos_del = saldo_service.calcular_saldo_conta(conn, 1)
print(f"Saldo bancário legítimo mantido intacto: MP = R$ {res_mp_pos_del['saldo_atual']}")
assert res_mp_pos_del['saldo_atual'] == Decimal("128.83")

conn.close()
os.remove(TEMP_DB)
print("\n=== TODOS OS TESTES PASSARAM COM SUCESSO! ===")
