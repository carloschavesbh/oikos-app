import sqlite3
import shutil
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.getcwd())
import saldo_service

sys.stdout.reconfigure(encoding='utf-8')

TEMP_DB = 'test_obrigatorio_temp.db'
if os.path.exists(TEMP_DB):
    try:
        os.remove(TEMP_DB)
    except Exception:
        pass

shutil.copy('financas_casa.db', TEMP_DB)
conn = sqlite3.connect(TEMP_DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Estrutura relacional e auditável de pagamentos
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
    considerado_no_marco INTEGER DEFAULT 0, -- 1 se o valor já integrava o saldo conciliado do marco
    observacao TEXT,
    cancelado INTEGER DEFAULT 0,
    cancelado_em TIMESTAMP,
    motivo_cancelamento TEXT
)
""")

# Coluna de controle de status na tabela transacoes
cur.execute("PRAGMA table_info(transacoes)")
cols_t = [c[1] for c in cur.fetchall()]
if "status_pagamento" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN status_pagamento TEXT DEFAULT 'pendente'")
conn.commit()

# ==============================================================================
# MOTOR CONTÁBIL CENTRALIZADO (Compatível com saldo_service)
# ==============================================================================
def obter_saldo_conta(conn: sqlite3.Connection, conta_id: int) -> Decimal:
    """
    Calcula o saldo exato da conta considerando:
    1. Marco inicial de conciliação.
    2. Receitas posteriores ao marco.
    3. Transferências posteriores ao marco.
    4. Pagamentos efetivos de despesas:
       - Pagamento pós-marco (considerado_no_marco = 0 e cancelado = 0): DEBITA a conta utilizada.
       - Pagamento pré-marco (considerado_no_marco = 1): NÃO altera saldo (já contemplado no marco).
       - Pagamento cancelado (cancelado = 1): IGNORADO (estornado).
    5. Transações legadas pós-marco não migradas para pagamentos_despesas.
    """
    res_base = saldo_service.calcular_saldo_conta(conn, conta_id)
    saldo_cents = res_base["saldo_centavos"]
    
    # Subtrai pagamentos ativos realizados pós-marco através de pagamentos_despesas
    cur = conn.cursor()
    cur.execute("""
        SELECT SUM(valor_pago_centavos) 
        FROM pagamentos_despesas 
        WHERE conta_id = ? 
          AND cancelado = 0 
          AND afeta_saldo_bancario = 1 
          AND considerado_no_marco = 0
    """, (conta_id,))
    total_debitos_cents = cur.fetchone()[0] or 0
    saldo_final_cents = saldo_cents - total_debitos_cents
    return saldo_service.cents_to_decimal(saldo_final_cents)

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
    cur.execute("SELECT id, valor, data FROM transacoes WHERE id = ?", (transacao_id,))
    t = cur.fetchone()
    if not t:
        raise ValueError(f"Transação {transacao_id} não encontrada.")
    
    val_orig = t["valor"]
    val_cents = saldo_service.decimal_to_cents(saldo_service.to_decimal(valor_pago))
    
    cur.execute("""
        INSERT INTO pagamentos_despesas 
        (transacao_id, data_pagamento, valor_pago, valor_pago_centavos, conta_id, afeta_saldo_bancario, considerado_no_marco, observacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (transacao_id, data_pagamento, valor_pago, val_cents, conta_id, afeta_saldo_bancario, considerado_no_marco, observacao))
    pag_id = cur.lastrowid
    
    # Atualiza status da obrigação
    cur.execute("SELECT SUM(valor_pago) FROM pagamentos_despesas WHERE transacao_id = ? AND cancelado = 0", (transacao_id,))
    total_pago = cur.fetchone()[0] or 0.0
    saldo_devedor = max(0.0, val_orig - total_pago)
    
    if total_pago >= val_orig - 0.001:
        st_pag = "pago"
        pago_flag = 1
    elif total_pago > 0:
        st_pag = "parcial"
        pago_flag = 2
    else:
        st_pag = "pendente"
        pago_flag = 0
        
    cur.execute("UPDATE transacoes SET pago = ?, status_pagamento = ? WHERE id = ?", (pago_flag, st_pag, transacao_id))
    conn.commit()
    return pag_id, total_pago, saldo_devedor

def estornar_pagamento(conn: sqlite3.Connection, pagamento_id: int, motivo: str):
    cur = conn.cursor()
    cur.execute("SELECT transacao_id FROM pagamentos_despesas WHERE id = ?", (pagamento_id,))
    p = cur.fetchone()
    if not p:
        raise ValueError("Pagamento não encontrado")
    t_id = p["transacao_id"]
    
    cur.execute("""
        UPDATE pagamentos_despesas 
        SET cancelado = 1, cancelado_em = CURRENT_TIMESTAMP, motivo_cancelamento = ?
        WHERE id = ?
    """, (motivo, pagamento_id))
    
    # Recalcula obrigação
    cur.execute("SELECT valor FROM transacoes WHERE id = ?", (t_id,))
    val_orig = cur.fetchone()["valor"]
    cur.execute("SELECT SUM(valor_pago) FROM pagamentos_despesas WHERE transacao_id = ? AND cancelado = 0", (t_id,))
    total_pago = cur.fetchone()[0] or 0.0
    saldo_devedor = max(0.0, val_orig - total_pago)
    
    if total_pago >= val_orig - 0.001:
        st_pag = "pago"
        pago_flag = 1
    elif total_pago > 0:
        st_pag = "parcial"
        pago_flag = 2
    else:
        st_pag = "pendente"
        pago_flag = 0
        
    cur.execute("UPDATE transacoes SET pago = ?, status_pagamento = ? WHERE id = ?", (pago_flag, st_pag, t_id))
    conn.commit()
    return t_id, total_pago, saldo_devedor

# ==============================================================================
# EXECUÇÃO DOS TESTES OBRIGATÓRIOS DO USUÁRIO
# ==============================================================================

print("=== ESTADO INICIAL RECONCILIADO EM 19/10/2026 ===")
mp_ini = obter_saldo_conta(conn, 1)
cart_ini = obter_saldo_conta(conn, 2)
print(f"Mercado Pago: R$ {mp_ini} | Carteira: R$ {cart_ini}")
assert mp_ini == Decimal("8.83")
assert cart_ini == Decimal("77.50")

print("\n--- TESTE OBRIGATÓRIO 1: Conta de setembro vencida e pendente, paga em 20/10 pelo Mercado Pago ---")
# Cadastra uma conta de setembro que venceu em 25/09/2026 (R$ 150,00) e continuava pendente:
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, status_pagamento)
    VALUES ('2026-09-25', 'Conta Antiga de Setembro', 150.00, 'despesa', 'Outros', 'Mercado Pago', 1, 0, 1, 'pendente')
""")
id_set = cur.lastrowid
conn.commit()

# Saldo antes de pagar em 20/10:
mp_antes_t1 = obter_saldo_conta(conn, 1)
print(f"Saldo Mercado Pago ANTES do pagamento: R$ {mp_antes_t1}")
assert mp_antes_t1 == Decimal("8.83")

# Paga em 20/10/2026 pelo Mercado Pago:
pag_t1_id, tot_pago_t1, dev_t1 = registrar_pagamento(
    conn=conn,
    transacao_id=id_set,
    data_pagamento='2026-10-20',
    valor_pago=150.00,
    conta_id=1,
    considerado_no_marco=0, # Ocorreu pós-marco
    observacao="Pagamento em 20/10 da conta pendente de setembro"
)

# Verifica se o vencimento original de setembro foi PRESERVADO:
cur.execute("SELECT data, valor, pago, status_pagamento FROM transacoes WHERE id = ?", (id_set,))
t_set_pos = cur.fetchone()
print(f"Obrigação ID {id_set}: Vencimento preservado={t_set_pos['data']} | Valor={t_set_pos['valor']:.2f} | Status={t_set_pos['status_pagamento']}")
assert t_set_pos['data'] == '2026-09-25'
assert t_set_pos['pago'] == 1
assert dev_t1 == 0.0

# Saldo pós-pagamento:
mp_pos_t1 = obter_saldo_conta(conn, 1)
print(f"Saldo Mercado Pago APÓS pagamento em 20/10: R$ {mp_pos_t1} (esperado: 8.83 - 150.00 = -141.17)")
assert mp_pos_t1 == Decimal("-141.17")
print("✅ Teste Obrigatório 1 passou com 100% de sucesso!")

print("\n--- TESTE OBRIGATÓRIO 2: Conta de outubro paga ANTES da conciliação de 19/10 ---")
# Cemig SIM (id=15, R$ 132,92, vencimento 09/10). Foi paga no dia 10/10, antes do marco das 17h de 19/10.
# O usuário marca retroativamente seu status como pago:
pag_t2_id, tot_pago_t2, dev_t2 = registrar_pagamento(
    conn=conn,
    transacao_id=15,
    data_pagamento='2026-10-10',
    valor_pago=132.92,
    conta_id=1,
    considerado_no_marco=1, # Já fazia parte da conciliação do marco
    observacao="Conta paga antes do marco de 19/10"
)

mp_pos_t2 = obter_saldo_conta(conn, 1)
print(f"Cemig SIM quitada retroativamente! Saldo devedor: R$ {dev_t2:.2f}")
print(f"Saldo Mercado Pago APÓS marcação retroativa: R$ {mp_pos_t2} (esperado: inalterado em -141.17)")
assert mp_pos_t2 == Decimal("-141.17")
print("✅ Teste Obrigatório 2 passou com 100% de sucesso (sem desconto duplo)!")

print("\n--- TESTE OBRIGATÓRIO 3: Desfazer status de conta paga ANTES do marco ---")
# Se uma conta de antes do marco tiver seu status desmarcado/estornado:
# REGRA: "Ao desfazer o status de uma conta paga antes do marco, não criar artificialmente dinheiro na conta."
estornar_pagamento(conn, pag_t2_id, "Desmarcado pelo usuário para revisão")
cur.execute("SELECT pago, status_pagamento FROM transacoes WHERE id = 15")
t15 = cur.fetchone()
mp_pos_t3 = obter_saldo_conta(conn, 1)
print(f"Cemig SIM desmarcada: status={t15['status_pagamento']} | pago flag={t15['pago']}")
print(f"Saldo Mercado Pago: R$ {mp_pos_t3} (inalterado em -141.17, sem criação artificial de dinheiro!)")
assert mp_pos_t3 == Decimal("-141.17")
assert t15['pago'] == 0
print("✅ Teste Obrigatório 3 passou com 100% de sucesso!")

print("\n--- TESTE OBRIGATÓRIO 4: Pagamento Parcial de Obrigação ---")
# Copasa (id=2, vencimento 01/10, valor R$ 72,46). Paga R$ 30,00 em dinheiro físico (Carteira) em 20/10.
cart_antes_t4 = obter_saldo_conta(conn, 2)
print(f"Carteira ANTES do pagamento parcial: R$ {cart_antes_t4}")
assert cart_antes_t4 == Decimal("77.50")

pag_t4_id, tot_pago_t4, dev_t4 = registrar_pagamento(
    conn=conn,
    transacao_id=2,
    data_pagamento='2026-10-20',
    valor_pago=30.00,
    conta_id=2, # Carteira
    considerado_no_marco=0,
    observacao="Pagamento parcial de Copasa em dinheiro"
)

cart_pos_t4 = obter_saldo_conta(conn, 2)
cur.execute("SELECT valor, pago, status_pagamento FROM transacoes WHERE id = 2")
t_cop = cur.fetchone()
print(f"Copasa pós-pagamento parcial:")
print(f"  Valor original: R$ {t_cop['valor']:.2f}")
print(f"  Pago até agora: R$ {tot_pago_t4:.2f}")
print(f"  Saldo devedor restante: R$ {dev_t4:.2f} (esperado: 72.46 - 30.00 = 42.46)")
print(f"  Status da obrigação: {t_cop['status_pagamento']} (pago flag: {t_cop['pago']})")
print(f"  Saldo Carteira DEPOIS: R$ {cart_pos_t4} (esperado: 77.50 - 30.00 = 47.50)")

assert t_cop['status_pagamento'] == "parcial"
assert t_cop['pago'] == 2 # 2 = parcial
assert round(dev_t4, 2) == 42.46
assert cart_pos_t4 == Decimal("47.50")
print("✅ Teste Obrigatório 4 passou com 100% de sucesso!")

print("\n--- TESTE OBRIGATÓRIO 5: Estorno de Pagamento Posterior ao Marco com Rastreabilidade ---")
# Estorna o pagamento parcial de R$ 30,00 da Carteira:
estornar_pagamento(conn, pag_t4_id, "Estorno solicitado pelo usuário - nota cancelada")
cart_pos_t5 = obter_saldo_conta(conn, 2)
cur.execute("SELECT cancelado, cancelado_em, motivo_cancelamento FROM pagamentos_despesas WHERE id = ?", (pag_t4_id,))
audit_estorno = cur.fetchone()
cur.execute("SELECT pago, status_pagamento FROM transacoes WHERE id = 2")
t_cop_pos_estorno = cur.fetchone()

print(f"Rastreabilidade do estorno no banco: cancelado={audit_estorno['cancelado']}, motivo='{audit_estorno['motivo_cancelamento']}'")
print(f"Copasa retornou a: status={t_cop_pos_estorno['status_pagamento']} | pago flag={t_cop_pos_estorno['pago']}")
print(f"Saldo Carteira recomposto para: R$ {cart_pos_t5} (retornou a 77.50!)")
assert cart_pos_t5 == Decimal("77.50")
assert t_cop_pos_estorno['pago'] == 0
print("✅ Teste Obrigatório 5 passou com 100% de sucesso!")

print("\n--- TESTE OBRIGATÓRIO 6: Reedição de Pagamento ---")
# Usuário registra novo pagamento de R$ 50,00 no Mercado Pago para a Copasa em 20/10,
# mas depois percebe que o valor correto era R$ 40,00.
# A reedição cancela o lançamento de R$ 50,00 com motivo e registra o corrigido de R$ 40,00:
pag_edit1_id, _, _ = registrar_pagamento(conn, 2, '2026-10-20', 50.00, 1, 1, 0, "Valor inicial digitado")
mp_com_50 = obter_saldo_conta(conn, 1)
print(f"Saldo MP com R$ 50 pagos: R$ {mp_com_50} (-141.17 - 50 = -191.17)")
assert mp_com_50 == Decimal("-191.17")

# Reedição segura: estorna com rastreabilidade e grava o valor correto
estornar_pagamento(conn, pag_edit1_id, "Correção de digitação: valor correto era 40.00")
pag_edit2_id, tot_edit, dev_edit = registrar_pagamento(conn, 2, '2026-10-20', 40.00, 1, 1, 0, "Valor corrigido")

mp_com_40 = obter_saldo_conta(conn, 1)
print(f"Saldo MP após reedição para R$ 40: R$ {mp_com_40} (esperado: -181.17)")
print(f"Saldo devedor restante da Copasa: R$ {dev_edit:.2f} (72.46 - 40 = 32.46)")
assert mp_com_40 == Decimal("-181.17")
assert round(dev_edit, 2) == 32.46
print("✅ Teste Obrigatório 6 passou com 100% de sucesso!")

conn.close()
os.remove(TEMP_DB)
print("\n================================================================================")
print("TODAS AS REGRAS E CENÁRIOS EXIGIDOS PELO USUÁRIO FORAM 100% HOMOLOGADOS!")
print("================================================================================")
