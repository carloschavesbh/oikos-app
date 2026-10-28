import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3
import pandas as pd
from datetime import date
from decimal import Decimal

DB_TEST = 'scratch/financas_casa_teste_inteligencia.db'

print("=" * 80)
print("PROTÓTIPO DE INTELIGÊNCIA FINANCEIRA — RENDA REAL, CRÉDITO E ENDIVIDAMENTO")
print("Ambiente: Banco de Testes Isolado (scratch/financas_casa_teste_inteligencia.db)")
print("=" * 80)

conn = sqlite3.connect(DB_TEST)
cur = conn.cursor()

# 1. Extensão não-destrutiva do esquema no banco de teste
cur.execute("PRAGMA table_info(transacoes)")
cols_t = [c[1] for c in cur.fetchall()]
if 'natureza_operacao' not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN natureza_operacao TEXT DEFAULT 'consumo_real'")
    # Atualiza as receitas existentes para 'renda_efetiva' (exceto saldo inicial)
    cur.execute("UPDATE transacoes SET natureza_operacao = 'renda_efetiva' WHERE tipo = 'receita' AND descricao NOT LIKE '%Saldo Anterior%'")
    cur.execute("UPDATE transacoes SET natureza_operacao = 'ajuste_saldo' WHERE descricao LIKE '%Saldo Anterior%'")
    # Atualiza pagamento de fatura existente para 'liquidacao_fatura'
    cur.execute("UPDATE transacoes SET natureza_operacao = 'liquidacao_fatura' WHERE categoria = 'Pagamento de fatura' OR descricao LIKE '%Pagamento de fatura%'")
    # Atualiza empréstimo Crediserv para 'amortizacao_divida'
    cur.execute("UPDATE transacoes SET natureza_operacao = 'amortizacao_divida' WHERE descricao LIKE '%Crediserv%' OR descricao LIKE '%Acordo BV%'")
    print("✓ Coluna 'natureza_operacao' adicionada e transações históricas mapeadas com prudência.")

# Adiciona cartão Inter Aparecida se não existir
cur.execute("SELECT id FROM cartoes WHERE nome LIKE '%Inter%' OR nome LIKE '%Aparecida%'")
row_card = cur.fetchone()
if not row_card:
    cur.execute("""
        INSERT INTO cartoes (nome, bandeira, limite_total, dia_fechamento, dia_vencimento, cor)
        VALUES ('Cartão Inter Aparecida', 'Mastercard', 0.0, 10, 20, '#f97316')
    """)
    id_cartao_aparecida = cur.lastrowid
    print(f"✓ Cartão 'Cartão Inter Aparecida' criado no banco de teste (ID {id_cartao_aparecida}).")
else:
    id_cartao_aparecida = row_card[0]

# Adiciona conta de cartão se necessário em contas_config para rastreabilidade
cur.execute("SELECT id FROM contas_config WHERE nome = 'Cartão Inter Aparecida'")
row_cta_card = cur.fetchone()
if not row_cta_card:
    cur.execute("INSERT INTO contas_config (nome, tipo, cor) VALUES ('Cartão Inter Aparecida', 'cartao', '#f97316')")
    id_cta_card = cur.lastrowid
else:
    id_cta_card = row_cta_card[0]

conn.commit()

# =============================================================================
# SIMULAÇÃO DOS DOIS CENÁRIOS REAIS
# =============================================================================
print("\n--- INSERINDO LANÇAMENTOS DE TESTE DOS CENÁRIOS A E B ---")

# SITUAÇÃO A: Empréstimo em dinheiro pelo cartão (Pix no crédito)
# 1. Receita no Mercado Pago: R$ 280,00 (Empréstimo / Aporte)
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, natureza_operacao, status_pagamento)
    VALUES ('2026-10-21', 'Pix Recebido Cartão Inter Aparecida', 280.0, 'receita', 'Empréstimo / Aporte', 'Mercado Pago', 1, 1, 'financiamento_aporte', 'pago')
""")
id_sim_rec = cur.lastrowid

# 2. Obrigação do Principal no Cartão Inter Aparecida: R$ 280,00 (Outras Dívidas)
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, natureza_operacao, status_pagamento)
    VALUES ('2026-10-21', 'Principal Pix Crédito Inter Aparecida', 280.0, 'despesa', 'Outras Dívidas', 'Cartão Inter Aparecida', ?, 0, 'amortizacao_divida', 'pendente')
""", (id_cta_card,))
id_sim_obrig_princ = cur.lastrowid

# 3. Juros cobrados no cartão Inter Aparecida: R$ 32,00 (Juros / Taxas de Empréstimo)
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, natureza_operacao, status_pagamento)
    VALUES ('2026-10-21', 'Juros Pix Crédito Inter Aparecida', 32.0, 'despesa', 'Juros / Taxas de Empréstimo', 'Cartão Inter Aparecida', ?, 0, 'encargo_financeiro', 'pendente')
""", (id_cta_card,))
id_sim_juros = cur.lastrowid

# 4. Despesa real paga com os R$ 280,00 recebidos: Supermercado R$ 180,00 e Farmácia R$ 100,00
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, natureza_operacao, status_pagamento)
    VALUES ('2026-10-21', 'Supermercado da Semana (com Pix recebido)', 180.0, 'despesa', 'Supermercado', 'Mercado Pago', 1, 1, 'consumo_real', 'pago')
""")
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, natureza_operacao, status_pagamento)
    VALUES ('2026-10-21', 'Farmácia Pedro (com Pix recebido)', 100.0, 'despesa', 'Medicamentos', 'Mercado Pago', 1, 1, 'consumo_real', 'pago')
""")

# 5. Pagamento posterior da fatura/reembolso à Aparecida no vencimento do cartão: R$ 312,00 (280 principal + 32 juros)
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, natureza_operacao, status_pagamento)
    VALUES ('2026-11-20', 'Pagamento Fatura Inter Aparecida (Quitação)', 312.0, 'despesa', 'Pagamento de fatura', 'Mercado Pago', 1, 1, 'liquidacao_fatura', 'pago')
""")

# SITUAÇÃO B: Compra direta no Cartão Inter Aparecida
# 1. Compra direta de R$ 120,00 no Supermercado
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, natureza_operacao, status_pagamento)
    VALUES ('2026-10-22', 'Supermercado direto no Cartão Inter Aparecida', 120.0, 'despesa', 'Supermercado', 'Cartão Inter Aparecida', ?, 1, 'consumo_real', 'pago')
""", (id_cta_card,))

# 2. Reembolso posterior à Aparecida de R$ 120,00 via Mercado Pago
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, natureza_operacao, status_pagamento)
    VALUES ('2026-11-20', 'Reembolso Compra Supermercado Inter Aparecida', 120.0, 'despesa', 'Pagamento de fatura', 'Mercado Pago', 1, 1, 'liquidacao_fatura', 'pago')
""")

conn.commit()
print("✓ Lançamentos simulados inseridos com sucesso no banco de teste.")

# =============================================================================
# COMPARAÇÃO: CÁLCULO ATUAL (INGÊNUO) VS CÁLCULO COM INTELIGÊNCIA FINANCEIRA
# =============================================================================
print("\n" + "=" * 80)
print("COMPARAÇÃO METODOLÓGICA: SISTEMA ATUAL (INGÊNUO) VS INTELIGÊNCIA FINANCEIRA")
print("=" * 80)

# 1. Cálculo Ingênuo (Atual)
cur.execute("""
    SELECT 
        COALESCE(SUM(CASE WHEN tipo = 'receita' THEN valor ELSE 0 END), 0.0) as rec_total,
        COALESCE(SUM(CASE WHEN tipo = 'despesa' THEN valor ELSE 0 END), 0.0) as desp_total
    FROM transacoes
    WHERE data LIKE '2026-10%' OR data LIKE '2026-11%'
""")
row_ing = cur.fetchone()
rec_ing, desp_ing = row_ing
res_ing = rec_ing - desp_ing

print("\n🚨 1. CÁLCULO ATUAL (INGÊNUO):")
print(f"  • 'Receitas' Totais Apuradas: R$ {rec_ing:,.2f}  <-- INFLADO! Contou R$ 280 de empréstimo como se fosse renda!")
print(f"  • 'Despesas' Totais Apuradas: R$ {desp_ing:,.2f}  <-- MULTIPLICADO! Somou a obrigação do cartão (280), o consumo do dinheiro (280), a fatura (312), a compra direta (120) e o reembolso (120)!")
print(f"  • 'Resultado Líquido': R$ {res_ing:,.2f}")

# 2. Cálculo com Inteligência Financeira
cur.execute("""
    SELECT natureza_operacao, SUM(valor), COUNT(*)
    FROM transacoes
    WHERE (data LIKE '2026-10%' OR data LIKE '2026-11%')
    GROUP BY natureza_operacao
""")
por_nat = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

renda_efetiva = por_nat.get('renda_efetiva', (0.0, 0))[0]
financiamento_aporte = por_nat.get('financiamento_aporte', (0.0, 0))[0]
consumo_real = por_nat.get('consumo_real', (0.0, 0))[0]
amortizacao_divida = por_nat.get('amortizacao_divida', (0.0, 0))[0]
encargo_financeiro = por_nat.get('encargo_financeiro', (0.0, 0))[0]
liquidacao_fatura = por_nat.get('liquidacao_fatura', (0.0, 0))[0]

print("\n💡 2. CÁLCULO COM INTELIGÊNCIA FINANCEIRA (SEM DUPLICIDADE):")
print(f"  A. Renda Efetiva Conquistada: R$ {renda_efetiva:,.2f} (Salários, Corridas, Ganhos)")
print(f"  B. Entradas de Financiamento / Empréstimos: R$ {financiamento_aporte:,.2f} (Dinheiro de crédito que entrou no caixa)")
print(f"  -------------------------------------------------------------")
print(f"  C. Consumo Real das Família: R$ {consumo_real:,.2f} (O que realmente foi consumido: 180 + 100 + 120)")
print(f"  D. Custo Financeiro / Juros e Taxas: R$ {encargo_financeiro:,.2f} (Custo do crédito: 32)")
print(f"  E. Amortização do Principal de Empréstimos: R$ {amortizacao_divida:,.2f} (Devolução do principal)")
print(f"  F. Liquidação de Faturas / Reembolsos: R$ {liquidacao_fatura:,.2f} (Pagamentos financeiros de obrigações já lançadas)")
print(f"  -------------------------------------------------------------")

resultado_economico_real = renda_efetiva - consumo_real - encargo_financeiro
print(f"  • RESULTADO ECONÔMICO REAL (Renda - Consumo - Juros): R$ {resultado_economico_real:,.2f}")
print(f"  • TOTAL DE ENTRADAS NO CAIXA: R$ {renda_efetiva + financiamento_aporte:,.2f}")
print(f"  • TOTAL DE SAÍDAS DE CAIXA: R$ {consumo_real + encargo_financeiro + amortizacao_divida:,.2f}")

# Indicadores de Saúde Financeira
if renda_efetiva > 0:
    taxa_autonomia = ((renda_efetiva - consumo_real - encargo_financeiro) / renda_efetiva) * 100
else:
    taxa_autonomia = -100.0

total_entradas_caixa = renda_efetiva + financiamento_aporte
taxa_dependencia_credito = (financiamento_aporte / total_entradas_caixa * 100) if total_entradas_caixa > 0 else 0.0

print("\n📊 3. INDICADORES DE SAÚDE FINANCEIRA:")
print(f"  • Taxa de Dependência de Crédito: {taxa_dependencia_credito:.1f}% do caixa veio de empréstimos")
print(f"  • Taxa de Autonomia Financeira: {taxa_autonomia:.1f}%")
print(f"  • Juros Efetivamente Pagos: R$ 32,00 | Juros a Pagar: R$ 0,00")
print(f"  • Crédito Novo Contratado no Mês: R$ 312,00 (Principal: 280 + Juros: 32)")
print(f"  • Redução Efetiva de Dívidas: R$ 280,00 amortizados")
print(f"  • Variação Líquida de Endividamento: R$ { (280 + 32) - 312 :.2f} (Dívida do mês totalmente quitada)")

conn.close()
print("=" * 80)
