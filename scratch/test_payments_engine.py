import sqlite3
import json
from decimal import Decimal
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Importar saldo_service
import saldo_service

test_db = 'scratch/financas_casa_teste_migracao.db'
conn = sqlite3.connect(test_db)
saldo_service.migrar_esquema(conn)

cursor = conn.cursor()

print("=== BATERIA DE TESTES DE PAGAMENTOS EM BANCO ISOLADO ===")

# Saldo inicial Mercado Pago (conta_id = 1)
s_ini = saldo_service.calcular_saldo_conta(conn, 1)
print(f"1. Saldo Inicial Mercado Pago: R$ {s_ini['saldo_atual']}")
assert s_ini['saldo_atual'] == Decimal("8.83"), f"Esperado 8.83, obteve {s_ini['saldo_atual']}"

# Teste A: Criar obrigação futura com afeta_saldo_bancario = 0, pago = 0
cursor.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, status_pagamento)
    VALUES ('2026-11-15', 'Conta Teste Futura Provedor', 100.00, 'despesa', 'Habitação', 'Mercado Pago', 1, 0, 0, 'pendente')
""")
conn.commit()
t_id = cursor.lastrowid
print(f"2. Obrigação criada: ID #{t_id} | Valor: R$ 100.00 | afeta_saldo_bancario=0 | pago=0")

# Verificar se saldo mudou antes do pagamento
s_pos_criacao = saldo_service.calcular_saldo_conta(conn, 1)
print(f"   Saldo após criação da obrigação pendente: R$ {s_pos_criacao['saldo_atual']}")
assert s_pos_criacao['saldo_atual'] == Decimal("8.83"), "Saldo não deveria mudar com obrigação pendente!"

# Teste B: Pagamento parcial de R$ 40,00 via Mercado Pago em 2026-10-25
res_p1 = saldo_service.registrar_pagamento(
    conn=conn,
    transacao_id=t_id,
    valor_pago=40.00,
    conta_id=1,
    data_pagamento='2026-10-25',
    forma_pagamento='Pix',
    observacao='Pagamento parcial 1'
)
print(f"3. Pagamento parcial registrado: ID #{res_p1['pagamento_id']} | Pago: R$ {res_p1['valor_pago']} | Saldo Devedor: R$ {res_p1['saldo_devedor']} | Status: {res_p1['status_pagamento']}")
assert res_p1['status_pagamento'] == 'parcial'
assert res_p1['saldo_devedor'] == Decimal("60.00")

# Conferir saldo bancário
s_pos_p1 = saldo_service.calcular_saldo_conta(conn, 1)
print(f"   Saldo Mercado Pago após pagamento parcial (R$ 40,00): R$ {s_pos_p1['saldo_atual']}")
# 8.83 - 40.00 = -31.17
assert s_pos_p1['saldo_atual'] == Decimal("-31.17"), f"Esperado -31.17, obteve {s_pos_p1['saldo_atual']}"

# Teste C: Pagamento do restante de R$ 60,00
res_p2 = saldo_service.registrar_pagamento(
    conn=conn,
    transacao_id=t_id,
    valor_pago=60.00,
    conta_id=1,
    data_pagamento='2026-10-26',
    forma_pagamento='Pix',
    observacao='Pagamento parcial 2 (quitação)'
)
print(f"4. Segundo pagamento registrado: ID #{res_p2['pagamento_id']} | Pago: R$ {res_p2['valor_pago']} | Saldo Devedor: R$ {res_p2['saldo_devedor']} | Status: {res_p2['status_pagamento']}")
assert res_p2['status_pagamento'] == 'pago'
assert res_p2['saldo_devedor'] == Decimal("0.00")

# Conferir saldo bancário
s_pos_p2 = saldo_service.calcular_saldo_conta(conn, 1)
print(f"   Saldo Mercado Pago após quitação total: R$ {s_pos_p2['saldo_atual']}")
# 8.83 - 100.00 = -91.17
assert s_pos_p2['saldo_atual'] == Decimal("-91.17"), f"Esperado -91.17, obteve {s_pos_p2['saldo_atual']}"

# Teste D: Estorno do segundo pagamento de R$ 60,00
res_estorno = saldo_service.estornar_pagamento(conn, res_p2['pagamento_id'], motivo="Teste de estorno")
print(f"5. Estorno efetuado: Pagamento #{res_p2['pagamento_id']} cancelado. Novo status obrigação: {res_estorno['status_pagamento']} | Saldo Devedor: R$ {res_estorno['saldo_devedor']}")
assert res_estorno['status_pagamento'] == 'parcial'
assert res_estorno['saldo_devedor'] == Decimal("60.00")

s_pos_estorno = saldo_service.calcular_saldo_conta(conn, 1)
print(f"   Saldo Mercado Pago após estorno: R$ {s_pos_estorno['saldo_atual']}")
assert s_pos_estorno['saldo_atual'] == Decimal("-31.17"), f"Esperado -31.17, obteve {s_pos_estorno['saldo_atual']}"

# Teste E: Edição de pagamento (atualizar p1 de 40 para 50)
cursor.execute("UPDATE pagamentos_despesas SET valor_pago = 50.00, valor_pago_centavos = 5000 WHERE id = ?", (res_p1['pagamento_id'],))
conn.commit()
s_pos_edit = saldo_service.calcular_saldo_conta(conn, 1)
print(f"6. Saldo Mercado Pago após edição do pagamento para R$ 50,00: R$ {s_pos_edit['saldo_atual']}")
# 8.83 - 50.00 = -41.17
assert s_pos_edit['saldo_atual'] == Decimal("-41.17"), f"Esperado -41.17, obteve {s_pos_edit['saldo_atual']}"

# Teste F: Estorno do primeiro pagamento (zerar tudo)
saldo_service.estornar_pagamento(conn, res_p1['pagamento_id'], motivo="Cancelando teste")
s_final = saldo_service.calcular_saldo_conta(conn, 1)
print(f"7. Saldo Mercado Pago após estornar todos os pagamentos: R$ {s_final['saldo_atual']}")
assert s_final['saldo_atual'] == Decimal("8.83"), f"Esperado 8.83, obteve {s_final['saldo_atual']}"

# Teste G: Desconto em folha (sem saída de conta bancária)
cursor.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, status_pagamento)
    VALUES ('2026-11-07', 'Plano de Saúde Família Desconto em Folha', 578.17, 'despesa', 'Saúde', 'Mercado Pago', 1, 0, 0, 'pendente')
""")
conn.commit()
t_folha_id = cursor.lastrowid

# Liquidação de desconto em folha (afeta_saldo_bancario = 0)
res_folha = saldo_service.registrar_pagamento(
    conn=conn,
    transacao_id=t_folha_id,
    valor_pago=578.17,
    conta_id=1,
    data_pagamento='2026-11-07',
    forma_pagamento='Desconto em Folha',
    observacao='Descontado no contracheque',
    afeta_saldo_bancario=0 # NÃO AFETA O SALDO BANCÁRIO!
)
print(f"8. Desconto em Folha registrado: ID #{res_folha['pagamento_id']} | Status: {res_folha['status_pagamento']} | Saldo Devedor: R$ {res_folha['saldo_devedor']}")
assert res_folha['status_pagamento'] == 'pago'
assert res_folha['saldo_devedor'] == Decimal("0.00")

s_folha = saldo_service.calcular_saldo_conta(conn, 1)
print(f"   Saldo Mercado Pago após liquidação em folha: R$ {s_folha['saldo_atual']}")
assert s_folha['saldo_atual'] == Decimal("8.83"), f"Saldo bancário NÃO pode ser debitado por desconto em folha! Obteve: {s_folha['saldo_atual']}"

print("\n>>> TODOS OS TESTES PASSARAM COM 100% DE SUCESSO! <<<")
conn.close()
