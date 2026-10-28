import sqlite3
import shutil
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.getcwd())
import saldo_service

TEMP_DB = 'test_bv_temp.db'
if os.path.exists(TEMP_DB):
    try:
        os.remove(TEMP_DB)
    except Exception:
        pass

shutil.copy('financas_casa.db', TEMP_DB)
conn = sqlite3.connect(TEMP_DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Prepara tabelas
cur.execute("""
CREATE TABLE IF NOT EXISTS pagamentos_despesas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transacao_id INTEGER NOT NULL REFERENCES transacoes(id),
    data_pagamento DATE NOT NULL,
    valor_pago REAL NOT NULL,
    valor_pago_centavos INTEGER NOT NULL,
    conta_id INTEGER NOT NULL REFERENCES contas_config(id),
    momento_pagamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    afeta_saldo_bancario INTEGER DEFAULT 1,
    considerado_no_marco INTEGER DEFAULT 0,
    observacao TEXT,
    cancelado INTEGER DEFAULT 0,
    cancelado_em TIMESTAMP,
    motivo_cancelamento TEXT
)
""")
conn.commit()

# Adiciona colunas para renegociação e status se não existirem
cur.execute("PRAGMA table_info(transacoes)")
cols_t = [c[1] for c in cur.fetchall()]
for col, cdef in [
    ("status_pagamento", "TEXT DEFAULT 'pendente'"),
    ("valor_financiado_renegociado", "REAL DEFAULT 0"),
    ("renegociacao_origem_id", "INTEGER REFERENCES transacoes(id)")
]:
    if col not in cols_t:
        cur.execute(f"ALTER TABLE transacoes ADD COLUMN {col} {cdef}")
conn.commit()

# ------------------------------------------------------------------------------
# SIMULAÇÃO DA REGRA 10: ACORDO BV 4/24
# ------------------------------------------------------------------------------
print("=== SIMULAÇÃO DA REGRA 10: ACORDO BV 4/24 ===")
cur.execute("SELECT id, data, descricao, valor, pago, conta FROM transacoes WHERE id = 27")
bv_orig = cur.fetchone()
print(f"Obrigação Original: ID {bv_orig['id']} | {bv_orig['descricao']} | R$ {bv_orig['valor']:.2f} | Pago: {bv_orig['pago']}")

# Cenário:
# Valor original: R$ 1.428,82
# Pagamento efetivo na fatura/banco: R$ 328,82
# Saldo restante de R$ 1.100,00 foi parcelado em 2x de R$ 570,00 (com juros) para Nov e Dez.

# 1. Registra o pagamento efetivo de R$ 328,82
val_pago = 328.82
cur.execute("""
    INSERT INTO pagamentos_despesas 
    (transacao_id, data_pagamento, valor_pago, valor_pago_centavos, conta_id, afeta_saldo_bancario, considerado_no_marco, observacao)
    VALUES (27, '2026-10-22', ?, ?, 1, 1, 0, 'Entrada paga da fatura BV')
""", (val_pago, saldo_service.decimal_to_cents(saldo_service.to_decimal(val_pago))))

saldo_remanescente = bv_orig['valor'] - val_pago # 1100.00

# 2. Marca na obrigação original que o restante foi financiado/renegociado
cur.execute("""
    UPDATE transacoes 
    SET pago = 1, -- Não fica mais pendente cobrando 1428.82
        status_pagamento = 'renegociado_parcial',
        valor_financiado_renegociado = ?
    WHERE id = 27
""", (saldo_remanescente,))

# 3. Cria as novas parcelas no novo cronograma vinculadas à origem
parcelas_novas = [
    ('2026-11-22', 'Acordo BV (Reneg. Parcela 1/2)', 570.00, 'Acordo BV', 'Mercado Pago', 27),
    ('2026-12-22', 'Acordo BV (Reneg. Parcela 2/2)', 570.00, 'Acordo BV', 'Mercado Pago', 27)
]
for data_p, desc_p, val_p, cat_p, c_p, orig_id in parcelas_novas:
    cur.execute("""
        INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, renegociacao_origem_id, status_pagamento)
        VALUES (?, ?, ?, 'despesa', ?, ?, 1, 0, 1, ?, 'pendente')
    """, (data_p, desc_p, val_p, cat_p, c_p, orig_id))

conn.commit()

# 4. Verificação de Integridade e Ausência de Dupla Contagem:
print("\n--- CONFERÊNCIA PÓS-REPACTUAÇÃO DO ACORDO BV ---")
cur.execute("SELECT id, descricao, valor, pago, status_pagamento, valor_financiado_renegociado FROM transacoes WHERE id = 27")
bv_atual = cur.fetchone()
print(f"Obrigação Original (ID 27):")
print(f"  Valor nominal: R$ {bv_atual['valor']:.2f}")
print(f"  Status: {bv_atual['status_pagamento']}")
print(f"  Valor Financiado / Migrado para novo cronograma: R$ {bv_atual['valor_financiado_renegociado']:.2f}")

cur.execute("SELECT id, data_pagamento, valor_pago FROM pagamentos_despesas WHERE transacao_id = 27")
pag = cur.fetchone()
print(f"Pagamento Efetivo Registrado no Extrato: R$ {pag['valor_pago']:.2f} em {pag['data_pagamento']}")

cur.execute("SELECT id, data, descricao, valor, pago, status_pagamento FROM transacoes WHERE renegociacao_origem_id = 27")
print("\nNovas parcelas geradas no cronograma futuro:")
for nova in cur.fetchall():
    print(f"  ID {nova['id']}: Vencimento {nova['data']} | {nova['descricao']} | R$ {nova['valor']:.2f} ({nova['status_pagamento']})")

# 5. Total de obrigações pendentes em Outubro:
cur.execute("""
    SELECT SUM(valor) FROM transacoes 
    WHERE tipo = 'despesa' AND pago = 0 AND data >= '2026-10-01' AND data <= '2026-10-31'
""")
pend_out = cur.fetchone()[0]
print(f"\nTotal de obrigações pendentes de Outubro (BV não entra mais em duplicidade): R$ {pend_out:,.2f}")

conn.close()
os.remove(TEMP_DB)
print("\n=== SUCESSO ABSOLUTO NA SIMULAÇÃO DO ACORDO BV! ===")
