import os
import shutil
import sqlite3
import sys
sys.path.insert(0, '.')
import saldo_service

TEST_DB = "scratch/test_isolado_recebimentos.db"
SRC_DB = "financas_casa_backup_prioridades_20261021_182300.db"
shutil.copy(SRC_DB, TEST_DB)

conn = sqlite3.connect(TEST_DB)

print("--- TESTE 1: Diagnóstico de Turno #3 ---")
info = saldo_service.obter_recebimentos_turno(conn, 3)
print("Info Turno 3:", info)
assert info["status"] == "excedente", f"Esperado excedente, obteve {info['status']}"
assert info["total_contabilizado"] == 110.10
assert info["ganho_bruto"] == 55.05
assert info["excedente"] == 55.05
assert len(info["transacoes"]) == 2
print("Teste 1 OK: Excedente de R$ 55,05 detectado corretamente!")

print("\n--- TESTE 2: Tentativa de registrar mais valor além do teto ---")
ok, msg = saldo_service.registrar_recebimento_turno(conn, 3, {"modo": "conta_unica", "conta_id": 1, "valor": 10.0})
print(f"Tentativa com turno já excedido: ok={ok}, msg={msg}")
assert not ok, "Deveria ter bloqueado nova contabilização!"
print("Teste 2 OK: Bloqueio de valor além do teto funcionou!")

print("\n--- TESTE 3: Estorno da transação duplicada #41 (Dinheiro/Pix indevido) ---")
# Saldo da Carteira antes do estorno
s_cart_antes = saldo_service.calcular_saldo_conta(conn, 2)["saldo_atual"]
print(f"Saldo Carteira antes do estorno de #41: R$ {s_cart_antes:.2f}")
ok, msg = saldo_service.estornar_recebimento_turno(conn, 41, turno_id=3)
assert ok, f"Falha no estorno: {msg}"
print("Estorno executado:", msg)

# Saldo da Carteira após estorno
s_cart_depois = saldo_service.calcular_saldo_conta(conn, 2)["saldo_atual"]
print(f"Saldo Carteira após estorno de #41: R$ {s_cart_depois:.2f}")
from decimal import Decimal
assert s_cart_depois == s_cart_antes - Decimal("55.05"), f"Esperado {s_cart_antes - Decimal('55.05')}, obteve {s_cart_depois}"

info_pos_estorno = saldo_service.obter_recebimentos_turno(conn, 3)
print("Info Turno 3 após estorno:", info_pos_estorno)
assert info_pos_estorno["total_contabilizado"] == 55.05
assert info_pos_estorno["restante_elegivel"] == 0.0
assert info_pos_estorno["status"] == "integral"
print("Teste 3 OK: Estorno de #41 corrigiu o turno para 'integral' e ajustou o saldo da Carteira perfeitamente!")

print("\n--- TESTE 4: Edição de transação vinculada #42 ---")
# Transação 42 está com 55.05 no Mercado Pago. Vamos editar para 30.00
ok, msg = saldo_service.editar_recebimento_turno(conn, 42, 30.0, 1)
assert ok, f"Falha na edição: {msg}"
print("Edição executada:", msg)
info_pos_edicao = saldo_service.obter_recebimentos_turno(conn, 3)
assert info_pos_edicao["total_contabilizado"] == 30.0
assert info_pos_edicao["restante_elegivel"] == 25.05
assert info_pos_edicao["status"] == "parcial"
print("Teste 4 OK: Edição para R$ 30,00 deixou R$ 25,05 restante elegível!")

print("\n--- TESTE 5: Tentativa de editar para valor acima do bruto ---")
ok, msg = saldo_service.editar_recebimento_turno(conn, 42, 60.0, 1)
assert not ok, "Deveria bloquear edição que excede o bruto!"
print(f"Tentativa de exceder bruto bloqueada: ok={ok}, msg={msg}")
print("Teste 5 OK: Edição acima do faturamento bruto bloqueada!")

print("\n--- TESTE 6: Novo turno limpo, divisão entre contas e idempotência ---")
cur = conn.cursor()
cur.execute("""
    INSERT INTO turnos (data, hora_inicio, hora_fim, ganho_bruto, ganho_dinheiro_pix, ganho_online, km, horas)
    VALUES ('2026-10-22', '08:00', '12:00', 100.0, 50.0, 50.0, 50.0, 4.0)
""")
t_novo_id = cur.lastrowid
conn.commit()

# Contabilizar com divisão: 40 em Mercado Pago (1) e 60 em Carteira (2)
ok, msg = saldo_service.registrar_recebimento_turno(conn, t_novo_id, {
    "modo": "divisao",
    "divisoes": [
        {"conta_id": 1, "valor": 40.0},
        {"conta_id": 2, "valor": 60.0}
    ]
})
assert ok, f"Erro na divisão: {msg}"
print("Divisão registrada:", msg)

info_t_novo = saldo_service.obter_recebimentos_turno(conn, t_novo_id)
assert info_t_novo["status"] == "integral"
assert info_t_novo["restante_elegivel"] == 0.0
assert len(info_t_novo["transacoes"]) == 2

# Testar clique duplo / repetição
ok_dup, msg_dup = saldo_service.registrar_recebimento_turno(conn, t_novo_id, {
    "modo": "conta_unica", "conta_id": 1, "valor": 10.0
})
assert not ok_dup, "Deveria bloquear clique repetido!"
print(f"Clique repetido bloqueado com sucesso: {msg_dup}")

print("\n--- TESTE 7: Desvincular movimentação ---")
tr_id_teste = info_t_novo["transacoes"][0]["id"]
ok_desv, msg_desv = saldo_service.desvincular_recebimento_turno(conn, tr_id_teste)
assert ok_desv
print("Desvinculação:", msg_desv)
# Verifica se a transação ainda existe no extrato com turno_id NULL
cur.execute("SELECT id, turno_id FROM transacoes WHERE id = ?", (tr_id_teste,))
row_desv = cur.fetchone()
assert row_desv[1] is None, "turno_id deveria ser NULL"
print("Teste 7 OK: Transação permanece no extrato com turno_id NULL!")

conn.close()
print("\n>>> TODOS OS TESTES DE SEGURANÇA E CONTABILIZAÇÃO PASSARAM COM 100% DE SUCESSO! <<<")
