import sys
import os
sys.path.insert(0, os.path.abspath("."))
import sqlite3
import datetime
import saldo_service

print("=" * 80)
print("   CONCILIAÇÃO CONTÁBIL DO CONTRACHEQUE DA FERNANDA (MÊS 11/2026)   ")
print("=" * 80)

db_path = "financas_remodelacao.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# -----------------------------------------------------------------------------
# 0. Saldo ANTES da Conciliação
# -----------------------------------------------------------------------------
saldo_antes = saldo_service.calcular_saldo_consolidado(conn)
mp_antes = next((c for c in saldo_antes["contas"] if c["conta_id"] == 1), {})
print(f"Saldo Mercado Pago ANTES: R$ {float(mp_antes.get('saldo_atual', 0)):,.2f}")
print(f"Saldo Consolidado ANTES:  R$ {float(saldo_antes.get('saldo_consolidado', 0)):,.2f}")

# -----------------------------------------------------------------------------
# 1. Ajustar a Receita Salarial (ID 2739)
# -----------------------------------------------------------------------------
print("\n--- 1. AJUSTANDO RECEITA SALARIAL (ID 2739) ---")
cur.execute("SELECT * FROM transacoes WHERE id = 2739")
r2739 = cur.fetchone()
if not r2739:
    raise Exception("Transação ID 2739 não encontrada!")

print(f"Valor anterior: R$ {float(r2739['valor']):,.2f} | Descrição: '{r2739['descricao']}'")

novo_valor_salario = 4483.59
nova_desc_salario = "Salário Fernanda PBH (Bruto Líquido de Previdência)"
novo_motivo_salario = "Vencimento R$ 3.811,43 + Retroativo R$ 752,35 + Vale Cultura R$ 293,24 + Alimentação R$ 356,25 (- BHPrev R$ 638,95 - Greve R$ 90,73)"
data_salario = "2026-11-06"

cur.execute("""
    UPDATE transacoes
    SET valor = ?,
        valor_pago = ?,
        descricao = ?,
        motivo_ajuste = ?,
        pago = 1,
        status_pagamento = 'pago',
        data_liquidacao = ?,
        afeta_saldo_bancario = 1,
        titular = 'Fernanda'
    WHERE id = 2739
""", (novo_valor_salario, novo_valor_salario, nova_desc_salario, novo_motivo_salario, data_salario))

print(f"Valor atualizado: R$ {novo_valor_salario:,.2f}")
print(f"Descrição: '{nova_desc_salario}'")
print(f"Observações: '{novo_motivo_salario}'")

# -----------------------------------------------------------------------------
# 2 e 3. Registrar as Despesas da Folha e o Investimento Cooperativo
# -----------------------------------------------------------------------------
print("\n--- 2 & 3. REGISTRANDO DESPESAS EM FOLHA E INVESTIMENTO COOPERATIVO ---")

despesas_folha = [
    {
        "descricao": "Unimed Mensalidades (Titular + Dependentes)",
        "valor": 576.34,
        "categoria": "Saúde",
        "subcategoria": "Plano de Saúde",
        "tipo": "despesa"
    },
    {
        "descricao": "Unimed Coparticipações (Titular + Dependente B)",
        "valor": 387.07,
        "categoria": "Saúde",
        "subcategoria": "Coparticipação Unimed",
        "tipo": "despesa"
    },
    {
        "descricao": "Odontoprev Mensalidade",
        "valor": 19.94,
        "categoria": "Saúde",
        "subcategoria": "Plano Odonto",
        "tipo": "despesa"
    },
    {
        "descricao": "Crediserv BH - Empréstimo 2",
        "valor": 433.86,
        "categoria": "Dívidas",
        "subcategoria": "Crediserv - Empréstimo",
        "tipo": "despesa"
    },
    {
        "descricao": "Crediserv BH - Capital Social (Sicoob)",
        "valor": 30.00,
        "categoria": "Investimentos",
        "subcategoria": "Conta Capital Sicoob",
        "tipo": "despesa"
    }
]

# Obter IDs de grupo e subcategoria se existirem
for item in despesas_folha:
    cur.execute("SELECT id FROM grupos_categoria WHERE nome = ? LIMIT 1", (item["categoria"],))
    g_row = cur.fetchone()
    grupo_id = g_row["id"] if g_row else None

    cur.execute("SELECT id FROM subcategorias WHERE nome = ? LIMIT 1", (item["subcategoria"],))
    s_row = cur.fetchone()
    sub_id = s_row["id"] if s_row else None

    # Idempotência: verificar se já existe lançamento idêntico em 06/11/2026
    cur.execute("""
        SELECT id FROM transacoes
        WHERE data = '2026-11-06'
          AND descricao = ?
          AND conta_id = 1
    """, (item["descricao"],))
    existe = cur.fetchone()

    if existe:
        print(f"Lançamento já existente (ID {existe['id']}): '{item['descricao']}' - R$ {item['valor']:,.2f}")
    else:
        cur.execute("""
            INSERT INTO transacoes (
                data, descricao, valor, valor_pago, tipo, categoria, subcategoria,
                conta, conta_id, pago, afeta_saldo_bancario, status_pagamento,
                data_liquidacao, titular, grupo_id, subcategoria_id, ref_externa
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Mercado Pago', 1, 1, 1, 'pago', ?, 'Fernanda', ?, ?, 'folha_pbh_2026-11')
        """, (
            "2026-11-06",
            item["descricao"],
            item["valor"],
            item["valor"],
            item["tipo"],
            item["categoria"],
            item["subcategoria"],
            "2026-11-06",
            grupo_id,
            sub_id
        ))
        novo_id = cur.lastrowid
        print(f"Inserido ID {novo_id}: '{item['descricao']}' | R$ {item['valor']:,.2f} | {item['categoria']} > {item['subcategoria']}")

# -----------------------------------------------------------------------------
# 4. Commit e Recálculo de Saldo
# -----------------------------------------------------------------------------
print("\n--- 4. SALVANDO NO BANCO E RECALCULANDO SALDO ---")
conn.commit()

saldo_depois = saldo_service.calcular_saldo_consolidado(conn)
mp_depois = next((c for c in saldo_depois["contas"] if c["conta_id"] == 1), {})
cart_depois = next((c for c in saldo_depois["contas"] if c["conta_id"] == 2), {})
pay_depois = next((c for c in saldo_depois["contas"] if c["conta_id"] == 1779), {})

total_despesas_folha = sum(d["valor"] for d in despesas_folha)
dif_receita = float(r2739["valor"]) - novo_valor_salario

print(f"\nResumo da Conciliação do Contracheque:")
print(f"  * Ajuste Receita Bruta Líquida de Previdência: -R$ {dif_receita:,.2f}")
print(f"  * Despesas e Investimento em Folha Lançados:   -R$ {total_despesas_folha:,.2f}")
print(f"  * Impacto Total no Saldo do Mercado Pago:      -R$ {(dif_receita + total_despesas_folha):,.2f}")

print(f"\nNovas Posições de Saldo em Caixa:")
print(f"  * Mercado Pago:       R$ {float(mp_depois.get('saldo_atual', 0)):,.2f}")
print(f"  * Dinheiro / Carteira: R$ {float(cart_depois.get('saldo_atual', 0)):,.2f}")
print(f"  * 99Pay:              R$ {float(pay_depois.get('saldo_atual', 0)):,.2f}")
print(f"  -------------------------------------------------------------")
print(f"  * SALDO CONSOLIDADO LIVRE: R$ {float(saldo_depois.get('saldo_consolidado', 0)):,.2f}")

conn.close()
print("\n>>> CONCILIAÇÃO FINALIZADA COM SUCESSO! <<<")

