import sqlite3
import shutil
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.getcwd())
import saldo_service

TEMP_DB = 'test_correcao_motorista_temp.db'
if os.path.exists(TEMP_DB):
    try:
        os.remove(TEMP_DB)
    except Exception:
        pass

# Copia do backup antes de qualquer coisa
shutil.copy('financas_casa_backup_urgente_motorista.db', TEMP_DB)
print("=== Banco de teste temporário criado a partir do backup ===")

conn = sqlite3.connect(TEMP_DB)
cur = conn.cursor()

# 1. Verifica estado das transações no banco temporário
print("\n--- TRANSACOES 34, 35, 36 NO BANCO TEMPORÁRIO ---")
cur.execute("SELECT id, data, descricao, valor, tipo, categoria, conta, pago FROM transacoes WHERE id >= 34")
for r in cur.fetchall():
    print(r)

# Saldo atual com os lançamentos indevidos
res_mp_antes = saldo_service.calcular_saldo_conta(conn, 1)
res_cons_antes = saldo_service.calcular_saldo_consolidado(conn)
print(f"Saldo Mercado Pago ANTES da correção: R$ {res_mp_antes['saldo_atual']}")
print(f"Saldo Consolidado ANTES da correção: R$ {res_cons_antes['saldo_consolidado']}")
assert res_mp_antes['saldo_atual'] == Decimal("-15.97")
assert res_cons_antes['saldo_consolidado'] == Decimal("84.03")
print("Confirmado matematicamente: o saldo de R$ 84,03 decorre exatamente de id=34 (+17.60), id=35 (-60.00) e id=36 (+17.60)!")

# 2. Simula a correção pontual e cirúrgica dos registros indevidos:
# O que o usuário fez em 19/10:
# Turno com Ganho Bruto R$ 17,60 e Combustível R$ 0,00.
# O id=35 (-60.00) foi um combustível preenchido indevidamente por valor padrão e que já foi zerado no turno.
# O id=34 (+17.60) foi duplicado pelo id=36 (+17.60).
# Portanto: id=35 deve ser REMOVIDO (ou anulado) e id=34 deve ser REMOVIDO (duplicata de id=36), mantendo id=36 (+17.60) como o ganho real do turno 2.
# OU se o ganho de R$ 17,60 ainda está na 99 Pay (e não caiu no Mercado Pago):
# se caiu no Mercado Pago: saldo = 8.83 + 17.60 = 26.43 (Consolidado: 126.43).
# se foi desfeito: volta a 8.83 e 108.83.
print("\n--- TESTE DE REMOÇÃO DOS LANÇAMENTOS INDEVIDOS 34 E 35 ---")
cur.execute("DELETE FROM transacoes WHERE id IN (34, 35)")
conn.commit()

res_mp_corrigido = saldo_service.calcular_saldo_conta(conn, 1)
res_cons_corrigido = saldo_service.calcular_saldo_consolidado(conn)
print(f"Saldo Mercado Pago mantendo apenas o turno real (id=36 R$ 17,60): R$ {res_mp_corrigido['saldo_atual']}")
print(f"Saldo Consolidado: R$ {res_cons_corrigido['saldo_consolidado']}")
assert res_mp_corrigido['saldo_atual'] == Decimal("8.83") + Decimal("17.60")
assert res_cons_corrigido['saldo_consolidado'] == Decimal("108.83") + Decimal("17.60")

# E se o ganho de R$ 17,60 tiver sido registrado antes do marco de conciliação das 17h?
# Se o marco das 17h já contemplava os R$ 17,60, id=36 também não deveria somar:
# Bastaria ter inserido id=36 em transacoes_contempladas_ids do marco de 19/10, o que manteria R$ 8,83 e R$ 108,83!
print("\n--- TESTE SE O TURNO JÁ ESTAVA CONTEMPLADO NO MARCO INICIAL ---")
# Se removermos id=36 também (revertendo ao estado puro de 19/10 antes de qualquer turno):
cur.execute("DELETE FROM transacoes WHERE id = 36")
conn.commit()
res_mp_puro = saldo_service.calcular_saldo_conta(conn, 1)
res_cons_puro = saldo_service.calcular_saldo_consolidado(conn)
print(f"Saldo Mercado Pago revertido ao marco original: R$ {res_mp_puro['saldo_atual']}")
print(f"Saldo Consolidado revertido ao marco original: R$ {res_cons_puro['saldo_consolidado']}")
assert res_mp_puro['saldo_atual'] == Decimal("8.83")
assert res_cons_puro['saldo_consolidado'] == Decimal("108.83")

# 3. Teste da Nova Arquitetura com Vínculo Estável e Idempotência:
print("\n--- TESTE DA NOVA ARQUITETURA DE TURNOS VINCULADOS ---")
# Adiciona coluna turno_id em transacoes se não existir
cur.execute("PRAGMA table_info(transacoes)")
cols = [c[1] for c in cur.fetchall()]
if "turno_id" not in cols:
    cur.execute("ALTER TABLE transacoes ADD COLUMN turno_id INTEGER REFERENCES turnos(id)")
    conn.commit()

# Cenário A: Criar turno 10 com ganho R$ 100 e combustível abastecido R$ 40
cur.execute("""
    INSERT INTO turnos (data, horas, km, ganho_bruto, combustivel, observacao, periodo)
    VALUES ('2026-10-20', 4.0, 60.0, 100.0, 40.0, 'Turno teste com vínculo', 'Noite')
""")
t10_id = cur.lastrowid

# Insere transações COM turno_id vinculado
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-20', 'Ganhos Corridas (Turno #10)', 100.0, 'receita', 'Renda Corridas (99/Uber)', 'Mercado Pago', 1, 1, 1, ?)
""", (t10_id,))
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-20', 'Abastecimento Turno #10', 40.0, 'despesa', 'Combustível', 'Mercado Pago', 1, 1, 1, ?)
""", (t10_id,))
conn.commit()

res_apos_t10 = saldo_service.calcular_saldo_conta(conn, 1)
print(f"Saldo Mercado Pago após turno #10 (+100 -40 = +60): R$ {res_apos_t10['saldo_atual']} (esperado: 68.83)")
assert res_apos_t10['saldo_atual'] == Decimal("68.83")

# Cenário B: Editar turno 10 (combustível foi R$ 0 na verdade, ganho R$ 100)
# Idempotência: Deleta transações vinculadas a turno_id=10 e recria somente o necessário
cur.execute("UPDATE turnos SET combustivel = 0 WHERE id = ?", (t10_id,))
cur.execute("DELETE FROM transacoes WHERE turno_id = ?", (t10_id,))
# Recria apenas a receita (já que combustível é 0)
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-20', 'Ganhos Corridas (Turno #10)', 100.0, 'receita', 'Renda Corridas (99/Uber)', 'Mercado Pago', 1, 1, 1, ?)
""", (t10_id,))
conn.commit()

res_apos_edit = saldo_service.calcular_saldo_conta(conn, 1)
print(f"Saldo Mercado Pago após EDITAR turno #10 (combustível zerado): R$ {res_apos_edit['saldo_atual']} (esperado: 108.83)")
assert res_apos_edit['saldo_atual'] == Decimal("108.83")

# Cenário C: Excluir turno 10
# Deleta da tabela turnos e deleta atomicamente de transacoes
cur.execute("DELETE FROM transacoes WHERE turno_id = ?", (t10_id,))
cur.execute("DELETE FROM turnos WHERE id = ?", (t10_id,))
conn.commit()

res_apos_del = saldo_service.calcular_saldo_conta(conn, 1)
print(f"Saldo Mercado Pago após EXCLUIR turno #10: R$ {res_apos_del['saldo_atual']} (revertido para 8.83)")
assert res_apos_del['saldo_atual'] == Decimal("8.83")

# Cenário D: Carteira 99 Pay isolada
# Cadastra a conta '99 Pay' em contas_config
cur.execute("INSERT INTO contas_config (nome, tipo, cor) VALUES ('99 Pay', 'digital', '#ffaa00')")
conta_99_id = cur.lastrowid

# Turno recebido na 99 Pay (R$ 150)
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario)
    VALUES ('2026-10-20', 'Ganhos Corridas 99 Pay', 150.0, 'receita', 'Renda Corridas (99/Uber)', '99 Pay', ?, 1, 1)
""", (conta_99_id,))
conn.commit()

saldo_99 = saldo_service.calcular_saldo_conta(conn, conta_99_id)["saldo_atual"]
saldo_mp = saldo_service.calcular_saldo_conta(conn, 1)["saldo_atual"]
print(f"Ganhos na 99 Pay: Saldo 99 Pay = R$ {saldo_99} | Mercado Pago = R$ {saldo_mp} (inalterado)")
assert saldo_99 == Decimal("150.00")
assert saldo_mp == Decimal("8.83")

# Gasto doméstico pago direto pela 99 Pay (ex: Farmácia R$ 35)
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario)
    VALUES ('2026-10-20', 'Farmácia paga com 99 Pay', 35.0, 'despesa', 'Medicamentos', '99 Pay', ?, 1, 1)
""", (conta_99_id,))
conn.commit()

saldo_99_pos_gasto = saldo_service.calcular_saldo_conta(conn, conta_99_id)["saldo_atual"]
print(f"Após gasto doméstico na 99 Pay: Saldo 99 Pay = R$ {saldo_99_pos_gasto} (esperado: 115.00)")
assert saldo_99_pos_gasto == Decimal("115.00")

# Transferência / Repasse de R$ 100 da 99 Pay para o Mercado Pago
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, conta_destino_id, pago, afeta_saldo_bancario)
    VALUES ('2026-10-20', 'Repasse 99 Pay para Mercado Pago', 100.0, 'transferencia', 'Transferência', '99 Pay', ?, 1, 1, 1)
""", (conta_99_id,))
conn.commit()

saldo_99_pos_transf = saldo_service.calcular_saldo_conta(conn, conta_99_id)["saldo_atual"]
saldo_mp_pos_transf = saldo_service.calcular_saldo_conta(conn, 1)["saldo_atual"]
print(f"Após Repasse: 99 Pay = R$ {saldo_99_pos_transf} (R$ 15.00) | Mercado Pago = R$ {saldo_mp_pos_transf} (R$ 108.83)")
assert saldo_99_pos_transf == Decimal("15.00")
assert saldo_mp_pos_transf == Decimal("108.83")

conn.close()
try:
    os.remove(TEMP_DB)
except Exception:
    pass

print("\n=======================================================")
print("TODOS OS TESTES DE VALIDAÇÃO E CORREÇÃO FORAM APROVADOS!")
print("=======================================================")
