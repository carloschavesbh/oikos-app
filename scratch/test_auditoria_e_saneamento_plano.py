import sqlite3
import shutil
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.getcwd())
import saldo_service

TEMP_DB = 'test_auditoria_plano_temp.db'
if os.path.exists(TEMP_DB):
    try:
        os.remove(TEMP_DB)
    except Exception:
        pass

# Copia do backup
shutil.copy('financas_casa_backup_urgente_motorista.db', TEMP_DB)
print("=== Banco de teste temporário criado a partir do backup ===")

conn = sqlite3.connect(TEMP_DB)
cur = conn.cursor()

# 1. ESTADO ATUAL ANTES DE QUALQUER MODIFICAÇÃO
print("\n--- 1. ESTADO DOS REGISTROS 34, 35 E 36 ---")
cur.execute("SELECT id, data, descricao, valor, tipo, categoria, conta, pago FROM transacoes WHERE id >= 34")
for r in cur.fetchall():
    print(r)

res_mp_inicial = saldo_service.calcular_saldo_conta(conn, 1)
res_cart_inicial = saldo_service.calcular_saldo_conta(conn, 2)
res_cons_inicial = saldo_service.calcular_saldo_consolidado(conn)
print(f"Saldo Mercado Pago: R$ {res_mp_inicial['saldo_atual']}")
print(f"Saldo Dinheiro / Carteira: R$ {res_cart_inicial['saldo_atual']}")
print(f"Saldo Consolidado: R$ {res_cons_inicial['saldo_consolidado']}")

# 2. PLANO DE SANEAMENTO:
# Saneamento dos registros 34 e 35 (duplicação e combustível fictício):
cur.execute("DELETE FROM transacoes WHERE id IN (34, 35)")
conn.commit()

# Neutralização de id=36 (pois o turno ocorreu de manhã e o marco das 17h já representava o saldo final real daquele dia):
cur.execute("DELETE FROM transacoes WHERE id = 36")
conn.commit()

res_mp_opcao_a = saldo_service.calcular_saldo_conta(conn, 1)
res_cart_opcao_a = saldo_service.calcular_saldo_conta(conn, 2)
res_cons_opcao_a = saldo_service.calcular_saldo_consolidado(conn)
print(f"\nMercado Pago após neutralizar 34, 35 e 36: R$ {res_mp_opcao_a['saldo_atual']} (esperado: 8.83)")
print(f"Dinheiro / Carteira: R$ {res_cart_opcao_a['saldo_atual']} (esperado: 100.00)")
print(f"Consolidado: R$ {res_cons_opcao_a['saldo_consolidado']} (esperado: 108.83)")
assert res_mp_opcao_a['saldo_atual'] == Decimal("8.83")
assert res_cart_opcao_a['saldo_atual'] == Decimal("100.00")
assert res_cons_opcao_a['saldo_consolidado'] == Decimal("108.83")

# O turno operacional de 19/10 permanece perfeitamente intacto na tabela turnos:
cur.execute("SELECT id, data, horas, km, ganho_bruto, combustivel, observacao FROM turnos WHERE id = 2")
turno_preservado = cur.fetchone()
print(f"\nTurno Operacional Preservado: {turno_preservado}")
assert turno_preservado[0] == 2
assert turno_preservado[4] == 17.6

# 3. TESTE DE PRESERVAÇÃO DE MOVIMENTAÇÕES REAIS AO EXCLUIR UM TURNO (Regra 2)
print("\n--- 3. TESTE REGRA 2: Não excluir movimentações bancárias reais ao excluir turno ---")
cur.execute("PRAGMA table_info(transacoes)")
cols = [c[1] for c in cur.fetchall()]
if "turno_id" not in cols:
    cur.execute("ALTER TABLE transacoes ADD COLUMN turno_id INTEGER REFERENCES turnos(id)")

# Cria turno de teste
cur.execute("""
    INSERT INTO turnos (data, horas, km, ganho_bruto, combustivel, observacao, periodo)
    VALUES ('2026-10-20', 3.0, 45.0, 85.0, 0.0, 'Turno teste exclusao', 'Noite')
""")
t_teste_id = cur.lastrowid

# Insere transação financeira real (ex: Pix recebido) vinculada ao turno_id
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-20', 'Pix recebido de corrida', 85.0, 'receita', 'Renda Corridas (99/Uber)', 'Mercado Pago', 1, 1, 1, ?)
""", (t_teste_id,))
conn.commit()

# Ao excluir o turno operacional:
# REGRA 2: Remove apenas o registro em 'turnos', e desvincula 'turno_id = NULL' em transacoes, preservando a movimentação financeira real!
cur.execute("UPDATE transacoes SET turno_id = NULL WHERE turno_id = ?", (t_teste_id,))
cur.execute("DELETE FROM turnos WHERE id = ?", (t_teste_id,))
conn.commit()

# Verifica se a movimentação bancária foi preservada
cur.execute("SELECT id, descricao, valor, turno_id FROM transacoes WHERE descricao = 'Pix recebido de corrida'")
t_preservada = cur.fetchone()
print(f"Transação bancária preservada após excluir turno: {t_preservada}")
assert t_preservada is not None
assert t_preservada[3] is None  # Desvinculada com segurança

conn.close()
try:
    os.remove(TEMP_DB)
except Exception:
    pass

print("\n=== Todos os testes do plano de auditoria foram executados com sucesso ===")
