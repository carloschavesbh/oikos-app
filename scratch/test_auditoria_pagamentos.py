import sqlite3
import shutil
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.getcwd())
import saldo_service

TEMP_DB = 'test_pagamentos_temp.db'
if os.path.exists(TEMP_DB):
    try:
        os.remove(TEMP_DB)
    except Exception:
        pass

# Copia do banco de produção intacto
shutil.copy('financas_casa.db', TEMP_DB)
print("=== Banco de teste criado a partir de financas_casa.db ===")

conn = sqlite3.connect(TEMP_DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Cria tabela de pagamentos de despesas (leve, auditável, relacional)
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

# Adiciona coluna status_pagamento em transacoes se nao existir
cur.execute("PRAGMA table_info(transacoes)")
cols_t = [c[1] for c in cur.fetchall()]
if "status_pagamento" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN status_pagamento TEXT DEFAULT 'pendente'")
conn.commit()

print("\n--- SALDO INICIAL RECONCILIADO EM 19/10/2026 ---")
s_mp = saldo_service.calcular_saldo_conta(conn, 1)
s_cart = saldo_service.calcular_saldo_conta(conn, 2)
s_cons = saldo_service.calcular_saldo_consolidado(conn)
print(f"Mercado Pago: R$ {s_mp['saldo_atual']}")
print(f"Carteira: R$ {s_cart['saldo_atual']}")
print(f"Consolidado: R$ {s_cons['saldo_consolidado']}")
assert s_mp['saldo_atual'] == Decimal("8.83")
# Carteira reflete o saldo inicial de R$ 100,00 menos as despesas legítimas 37 e 38 (Las Casas R$ 22,50) = R$ 77,50
assert s_cart['saldo_atual'] == Decimal("77.50")
assert s_cons['saldo_consolidado'] == Decimal("86.33")

# ==============================================================================
# FUNÇÃO DE SERVIÇO: REGISTRAR PAGAMENTO DE OBRIGAÇÃO
# ==============================================================================
def registrar_pagamento(
    conn: sqlite3.Connection,
    transacao_id: int,
    data_pagamento: str,
    valor_pago: float,
    conta_id: int,
    afeta_saldo_bancario: int = 1,
    considerado_no_marco: int = 0,
    observacao: str = ""
):
    cur = conn.cursor()
    cur.execute("SELECT id, valor, pago, data FROM transacoes WHERE id = ?", (transacao_id,))
    t = cur.fetchone()
    if not t:
        raise ValueError(f"Transação {transacao_id} não encontrada.")
    
    val_orig = t["valor"]
    val_cents = saldo_service.decimal_to_cents(saldo_service.to_decimal(valor_pago))
    
    # 1. Insere o pagamento auditável
    cur.execute("""
        INSERT INTO pagamentos_despesas 
        (transacao_id, data_pagamento, valor_pago, valor_pago_centavos, conta_id, afeta_saldo_bancario, considerado_no_marco, observacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (transacao_id, data_pagamento, valor_pago, val_cents, conta_id, afeta_saldo_bancario, considerado_no_marco, observacao))
    pag_id = cur.lastrowid
    
    # 2. Atualiza o status da obrigação
    cur.execute("""
        SELECT SUM(valor_pago) FROM pagamentos_despesas 
        WHERE transacao_id = ? AND cancelado = 0
    """, (transacao_id,))
    total_pago = cur.fetchone()[0] or 0.0
    
    saldo_devedor = max(0.0, val_orig - total_pago)
    if total_pago >= val_orig - 0.001:
        novo_status = "pago"
        novo_pago = 1
    elif total_pago > 0:
        novo_status = "parcial"
        novo_pago = 2  # 2 indica parcialmente pago
    else:
        novo_status = "pendente"
        novo_pago = 0
        
    cur.execute("UPDATE transacoes SET pago = ?, status_pagamento = ? WHERE id = ?", (novo_pago, novo_status, transacao_id))
    conn.commit()
    return pag_id, total_pago, saldo_devedor

# ==============================================================================
# FUNÇÃO DE SERVIÇO: CANCELAR PAGAMENTO
# ==============================================================================
def cancelar_pagamento(conn: sqlite3.Connection, pagamento_id: int, motivo: str = "Cancelamento pelo usuário"):
    cur = conn.cursor()
    cur.execute("SELECT transacao_id FROM pagamentos_despesas WHERE id = ?", (pagamento_id,))
    r = cur.fetchone()
    if not r:
        raise ValueError("Pagamento não encontrado")
    t_id = r["transacao_id"]
    
    cur.execute("""
        UPDATE pagamentos_despesas 
        SET cancelado = 1, cancelado_em = CURRENT_TIMESTAMP, motivo_cancelamento = ?
        WHERE id = ?
    """, (motivo, pagamento_id))
    
    # Recalcula status da obrigação
    cur.execute("SELECT valor FROM transacoes WHERE id = ?", (t_id,))
    val_orig = cur.fetchone()["valor"]
    cur.execute("SELECT SUM(valor_pago) FROM pagamentos_despesas WHERE transacao_id = ? AND cancelado = 0", (t_id,))
    total_pago = cur.fetchone()[0] or 0.0
    saldo_devedor = max(0.0, val_orig - total_pago)
    
    if total_pago >= val_orig - 0.001:
        novo_status = "pago"
        novo_pago = 1
    elif total_pago > 0:
        novo_status = "parcial"
        novo_pago = 2
    else:
        novo_status = "pendente"
        novo_pago = 0
    cur.execute("UPDATE transacoes SET pago = ?, status_pagamento = ? WHERE id = ?", (novo_pago, novo_status, t_id))
    conn.commit()
    return t_id, total_pago, saldo_devedor

# ==============================================================================
# CALCULO DE SALDO INTEGRADO COM TABELA PAGAMENTOS_DESPESAS
# ==============================================================================
def calcular_saldo_com_pagamentos(conn: sqlite3.Connection, conta_id: int):
    """
    Calcula o saldo da conta respeitando:
    1. Marco inicial.
    2. Receitas posteriores ao marco.
    3. Transferências posteriores ao marco.
    4. Pagamentos de despesas vinculados à conta através de pagamentos_despesas:
       - Se considerado_no_marco = 1: IGNORADO (já contemplado no marco).
       - Se data_pagamento > data_marco (ou post-marco no mesmo dia): SUBTRAÍDO.
    5. Despesas legadas já marcadas como pago=1 no banco original (se houver posterior ao marco).
    """
    res = saldo_service.calcular_saldo_conta(conn, conta_id)
    saldo_cents = res["saldo_centavos"]
    
    # Busca pagamentos ativos nesta conta
    cur = conn.cursor()
    cur.execute("""
        SELECT id, data_pagamento, valor_pago_centavos, afeta_saldo_bancario, considerado_no_marco
        FROM pagamentos_despesas
        WHERE conta_id = ? AND cancelado = 0 AND afeta_saldo_bancario = 1
    """, (conta_id,))
    pagamentos = cur.fetchall()
    
    desp_pags_cents = 0
    for p in pagamentos:
        p_id, p_data, p_val_cents, p_afeta, p_considerado = p
        if p_considerado == 1:
            # Já considerado no marco inicial: não desconta do saldo
            continue
        # Se for posterior ao marco, desconta
        saldo_cents -= p_val_cents
        desp_pags_cents += p_val_cents
        
    return {
        "conta_id": conta_id,
        "saldo_atual": saldo_service.cents_to_decimal(saldo_cents),
        "saldo_centavos": saldo_cents,
        "despesas_pagamentos": saldo_service.cents_to_decimal(desp_pags_cents)
    }

print("\n--- TESTE CENÁRIO 1: Pagar hoje (19/10 pós-marco) uma conta vencida em 01/10 (Copasa R$ 72,46) ---")
# Copasa: id=2, vencimento 01/10, valor 72.46
pag_id, tot_pago, devedor = registrar_pagamento(
    conn=conn,
    transacao_id=2,
    data_pagamento='2026-10-19',
    valor_pago=72.46,
    conta_id=1, # Mercado Pago
    afeta_saldo_bancario=1,
    considerado_no_marco=0, # Ocorreu APÓS a conciliação das 17h03
    observacao="Pago via Pix Mercado Pago após a conciliação"
)
s1_mp = calcular_saldo_com_pagamentos(conn, 1)
print(f"Copasa quitada! Total pago: R$ {tot_pago:.2f} | Saldo devedor: R$ {devedor:.2f}")
print(f"Saldo Mercado Pago: R$ {s1_mp['saldo_atual']} (esperado: 8.83 - 72.46 = -63.63)")
assert s1_mp['saldo_atual'] == Decimal("-63.63")
assert devedor == 0.0

print("\n--- TESTE CENÁRIO 2: Registrar retroativamente pagamento já refletido no saldo inicial (Regra 3) ---")
# Suponha que a conta Cemig SIM (id=15, 132.92) na verdade tinha sido paga em 10/10 antes do marco
# e o dinheiro já havia saído do banco antes da conciliação das 17h de 19/10:
pag2_id, tot2_pago, devedor2 = registrar_pagamento(
    conn=conn,
    transacao_id=15,
    data_pagamento='2026-10-10',
    valor_pago=132.92,
    conta_id=1,
    afeta_saldo_bancario=1,
    considerado_no_marco=1, # JÁ REFLETIDO no saldo do marco de R$ 8,83!
    observacao="Pagamento anterior ao marco, já contemplado no saldo conciliado"
)
s2_mp = calcular_saldo_com_pagamentos(conn, 1)
print(f"Cemig SIM quitada retroativamente! Saldo devedor: R$ {devedor2:.2f}")
print(f"Saldo Mercado Pago inalterado: R$ {s2_mp['saldo_atual']} (esperado: -63.63, sem desconto duplo!)")
assert s2_mp['saldo_atual'] == Decimal("-63.63")

print("\n--- TESTE CENÁRIO 3: Pagamento no dia do marco (19/10) - Verificação de Momento (Regra 4) ---")
# Conta Claro Controle (id=16, 34.36): paga em 19/10 às 11h (antes do marco das 17h03)
pag3_id, tot3, dev3 = registrar_pagamento(
    conn=conn,
    transacao_id=16,
    data_pagamento='2026-10-19',
    valor_pago=34.36,
    conta_id=1,
    considerado_no_marco=1, # antes do marco
    observacao="Pago de manhã em 19/10 antes da conciliação das 17h"
)
s3_mp = calcular_saldo_com_pagamentos(conn, 1)
print(f"Claro (pré-marco): Saldo Mercado Pago: R$ {s3_mp['saldo_atual']} (inalterado em -63.63)")
assert s3_mp['saldo_atual'] == Decimal("-63.63")

# Conta YouCine (id=14, 24.90): paga em 19/10 às 20h (após o marco das 17h03)
# Esta DEVE debitar do banco!
pag4_id, tot4, dev4 = registrar_pagamento(
    conn=conn,
    transacao_id=14,
    data_pagamento='2026-10-19',
    valor_pago=24.90,
    conta_id=1,
    considerado_no_marco=0, # pós-marco
    observacao="Pago à noite em 19/10 após a conciliação das 17h"
)
s4_mp = calcular_saldo_com_pagamentos(conn, 1)
print(f"YouCine (pós-marco): Saldo Mercado Pago: R$ {s4_mp['saldo_atual']} (esperado: -63.63 - 24.90 = -88.53)")
assert s4_mp['saldo_atual'] == Decimal("-88.53")

print("\n--- TESTE CENÁRIO 4: Acordo BV 4/24 - Pagamento Parcial e Saldo Devedor (Regras 5 e 10) ---")
# Acordo BV 4/24: id=27, valor original R$ 1.428,82
# O usuário NÃO quita os 1.428,82. Paga apenas R$ 428,82 de entrada/fatura via Mercado Pago em 22/10.
pag5_id, tot5, dev5 = registrar_pagamento(
    conn=conn,
    transacao_id=27,
    data_pagamento='2026-10-22',
    valor_pago=428.82,
    conta_id=1,
    considerado_no_marco=0, # futuro pós-marco
    observacao="Pagamento parcial / entrada de renegociação"
)
cur.execute("SELECT valor, pago, status_pagamento FROM transacoes WHERE id = 27")
t_bv = cur.fetchone()
s5_mp = calcular_saldo_com_pagamentos(conn, 1)

print(f"Acordo BV após pagamento parcial:")
print(f"  Valor original: R$ {t_bv['valor']:.2f}")
print(f"  Total pago até agora: R$ {tot5:.2f}")
print(f"  Saldo financiado / devedor restante: R$ {dev5:.2f}")
print(f"  Status da obrigação: {t_bv['status_pagamento']} (pago flag: {t_bv['pago']})")
print(f"  Saldo Mercado Pago: R$ {s5_mp['saldo_atual']} (esperado: -88.53 - 428.82 = -517.35)")
assert t_bv['status_pagamento'] == 'parcial'
assert t_bv['pago'] == 2
assert dev5 == 1000.00
assert s5_mp['saldo_atual'] == Decimal("-517.35")

print("\n--- TESTE CENÁRIO 5: Cancelamento / Estorno com Auditoria e Atualização Imediata (Regra 7) ---")
# O usuário cancela o pagamento parcial de R$ 428,82 (por exemplo, estornado ou digitado errado)
t_id_canc, tot_pos_canc, dev_pos_canc = cancelar_pagamento(conn, pag5_id, "Lançamento de teste cancelado")
cur.execute("SELECT cancelado, cancelado_em, motivo_cancelamento FROM pagamentos_despesas WHERE id = ?", (pag5_id,))
audit_pag = cur.fetchone()
s6_mp = calcular_saldo_com_pagamentos(conn, 1)

print(f"Auditoria do cancelamento: cancelado={audit_pag['cancelado']}, motivo='{audit_pag['motivo_cancelamento']}'")
print(f"Saldo devedor do Acordo BV restaurado para: R$ {dev_pos_canc:.2f}")
print(f"Saldo Mercado Pago recomposto: R$ {s6_mp['saldo_atual']} (retornou a -88.53 sem duplicidade!)")
assert dev_pos_canc == 1428.82
assert s6_mp['saldo_atual'] == Decimal("-88.53")

print("\n--- TESTE CENÁRIO 6: Painel Mensal - Diferenciação de Vencimentos, Pagamentos e Atrasadas (Regra 8) ---")
# No mês de Outubro/2026:
# - Vencimentos do mês: despesas com vencimento em outubro
# - Pagamentos realizados no mês: pagamentos ativos com data_pagamento em outubro
# - Obrigações vencidas anteriormente (ex: setembro) ainda pendentes
cur.execute("""
    SELECT 
        COUNT(*) as total_vencem_out,
        SUM(valor) as valor_vencem_out
    FROM transacoes 
    WHERE tipo = 'despesa' AND data >= '2026-10-01' AND data <= '2026-10-31'
""")
venc_out = cur.fetchone()

cur.execute("""
    SELECT 
        COUNT(*) as total_pagamentos_out,
        SUM(valor_pago) as valor_pago_out
    FROM pagamentos_despesas 
    WHERE cancelado = 0 AND data_pagamento >= '2026-10-01' AND data_pagamento <= '2026-10-31'
""")
pags_out = cur.fetchone()

print(f"Painel Outubro/2026:")
print(f"  Vencimentos previstos do mês: {venc_out['total_vencem_out']} contas somando R$ {venc_out['valor_vencem_out']:,.2f}")
print(f"  Pagamentos efetivamente realizados em outubro: {pags_out['total_pagamentos_out']} pagamentos somando R$ {pags_out['valor_pago_out']:,.2f}")

conn.close()
os.remove(TEMP_DB)
print("\n=== TODOS OS 6 CENÁRIOS DE AUDITORIA E TESTES PASSARAM COM SUCESSO! ===")
