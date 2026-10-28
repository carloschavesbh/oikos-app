import sys, os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
import shutil
import saldo_service
from decimal import Decimal

TEST_DB = "scratch/test_drivvo_pendencias.db"
shutil.copyfile("financas_casa.db", TEST_DB)

conn = sqlite3.connect(TEST_DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== TESTE 1: Auditoria da Transação 40 com Litros/Hodômetro Pendentes ===")
cur.execute("SELECT * FROM veiculo_abastecimentos WHERE transacao_id = 40")
row = dict(cur.fetchone())
print("Registro de Abastecimento vinculado:", row)

assert row["valor_bruto"] == 100.0, "Valor bruto deve ser R$ 100,00"
assert row["desconto"] == 9.52, "Desconto deve ser R$ 9,52"
assert row["valor_pago"] == 90.48, "Valor pago deve ser R$ 90,48"
assert row["transacao_id"] == 40, "Deve estar vinculado à transação 40"
assert row["litros"] is None, "Litros deve estar pendente (None)"
assert row["hodometro"] is None, "Hodômetro deve estar pendente (None)"
assert row["tanque_cheio"] is None, "Tanque cheio deve estar pendente (None)"
print("✅ Abastecimento #40 auditado com sucesso com dados pendentes preservados!")

print("\n=== TESTE 2: obter_metricas_combustivel com Dados Pendentes ===")
metricas = saldo_service.obter_metricas_combustivel(conn)
print("Metricas Mes:", metricas["mes"])
assert metricas["mes"]["pago_real"] == 90.48, "Total pago no mês deve ser R$ 90,48"
assert metricas["mes"]["litros"] == 0.0, "Litros somados devem ser 0.0 enquanto pendente"
print("✅ obter_metricas_combustivel funciona perfeitamente com valores pendentes (sem TypeError ou divisão por zero)!")

print("\n=== TESTE 3: Atualização dos Dados Reais quando Informados pelo Usuário ===")
count_tr_antes = cur.execute("SELECT count(*) FROM transacoes").fetchone()[0]

dados_confirmar = {
    "id": row["id"],
    "data": "2026-10-20",
    "hodometro": 187295.0,
    "combustivel": "Etanol",
    "litros": 28.0,
    "valor_bruto": 100.0,
    "desconto": 9.52,
    "valor_pago": 90.48,
    "conta": "Dinheiro / Carteira",
    "conta_id": 2,
    "tanque_cheio": 1,
    "posto": "Posto Shell",
    "observacao": "Confirmado pelo motorista",
    "transacao_id": 40
}
ok, msg = saldo_service.salvar_abastecimento_veiculo(conn, dados_confirmar)
assert ok, f"Falha ao salvar: {msg}"

count_tr_depois = cur.execute("SELECT count(*) FROM transacoes").fetchone()[0]
assert count_tr_depois == count_tr_antes, f"Erro! Foram criadas novas transações ao atualizar: antes={count_tr_antes}, depois={count_tr_depois}"

cur.execute("SELECT * FROM veiculo_abastecimentos WHERE id = ?", (row["id"],))
row_atualizado = dict(cur.fetchone())
assert row_atualizado["litros"] == 28.0
assert row_atualizado["hodometro"] == 187295.0
assert row_atualizado["preco_litro"] == round(100.0 / 28.0, 3)
print("✅ Atualização dos dados confirmados pelo motorista realizada sem duplicar transações!")

conn.close()
print("\n🎉 TODOS OS TESTES DE AUDITORIA E PENDÊNCIAS PASSARAM COM SUCESSO!")
