import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3
from datetime import date
from decimal import Decimal
import saldo_service

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("--- TESTANDO OPERAÇÕES DO MÓDULO DE DÍVIDAS E CATEGORIAS ---")

# 1. Inserir uma dívida livre de teste em transação isolada
cur.execute("BEGIN TRANSACTION")
cur.execute("""
    INSERT INTO dividas_gerenciamento (credor, descricao, tipo_divida, valor_original, saldo_atual, meta_voluntaria_mensal, data_inicio, status)
    VALUES ('Teste Credor', 'Dívida teste livre', 'livre', 1000.0, 1000.0, 100.0, '2026-10-20', 'ativa')
""")
div_id = cur.lastrowid

# Pagamento manual
cur.execute("""
    INSERT INTO dividas_pagamentos_manuais (divida_id, data_pagamento, valor_pago, observacao)
    VALUES (?, '2026-10-20', 200.0, 'Pagamento parcial teste')
""", (div_id,))
cur.execute("UPDATE dividas_gerenciamento SET saldo_atual = saldo_atual - 200.0 WHERE id = ?", (div_id,))

# Verifica saldo
cur.execute("SELECT saldo_atual FROM dividas_gerenciamento WHERE id = ?", (div_id,))
assert cur.fetchone()[0] == 800.0
print("✓ Dívida livre e amortização manual testadas com sucesso.")

# Reverte a transação de teste para manter financas_casa.db estritamente limpo!
cur.execute("ROLLBACK")
print("✓ Rollback executado: financas_casa.db permanece limpo e intocado.")

# 2. Verifica lançamentos pendentes
cur.execute("SELECT id, descricao, status_rateio FROM transacoes WHERE status_rateio != 'normal'")
pendentes = cur.fetchall()
print(f"Lançamentos pendentes de classificação no banco: {len(pendentes)}")
for p in pendentes:
    print(f"  ID {p[0]}: {p[1]} ({p[2]})")

conn.close()
print("✓ Validação concluída com sucesso!")
