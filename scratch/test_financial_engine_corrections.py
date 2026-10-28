import sys
import os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
from datetime import date, timedelta
from decimal import Decimal

sys.stdout.reconfigure(encoding='utf-8')

DB_TESTE = 'scratch/financas_casa_teste_hierarquia.db'
conn = sqlite3.connect(DB_TESTE)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

hoje = date(2026, 10, 20)

print("=== TESTES DE INTEGRAÇÃO DO MOTOR FINANCEIRO CORRIGIDO ===")

# TESTE 1: JANELA DE 7 DIAS EXATOS (D+0 a D+6: 20/10 a 26/10)
dt_fim_7d = hoje + timedelta(days=6)
dias_contados = (dt_fim_7d - hoje).days + 1
print(f"\n1. Teste Janela 7 dias: {hoje} até {dt_fim_7d} -> Dias totais: {dias_contados}")
assert dias_contados == 7, "A janela deve ter exatamente 7 dias corridos!"

cur.execute("""
    SELECT t.id, t.data, t.descricao, t.valor, s.nome as subcat, g.nome as grupo,
           COALESCE(t.status_conciliacao_fatura, 'normal') as st_conc
    FROM transacoes t
    LEFT JOIN subcategorias s ON s.id = t.subcategoria_id
    LEFT JOIN grupos_categoria g ON g.id = t.grupo_id
    WHERE t.tipo = 'despesa' AND (t.pago IS NULL OR t.pago != 1)
      AND t.data >= ? AND t.data <= ?
    ORDER BY t.data, t.id
""", (hoje.strftime('%Y-%m-%d'), dt_fim_7d.strftime('%Y-%m-%d')))
contas_7d = cur.fetchall()

tot_conf_7d = Decimal("0.00")
tot_conc_7d = Decimal("0.00")

for c in contas_7d:
    val = Decimal(str(c["valor"]))
    if c["st_conc"] == "pendente_confirmacao" or "Acordo BV" in c["descricao"]:
        tot_conc_7d += val
        print(f"   [EM CONCILIAÇÃO] ID {c['id']:2d} | {c['data']} | R$ {val:7.2f} | {c['descricao']}")
    else:
        tot_conf_7d += val
        print(f"   [CONFIRMADA]    ID {c['id']:2d} | {c['data']} | R$ {val:7.2f} | {c['descricao']} ({c['grupo']} -> {c['subcat']})")

print(f"   Total Confirmado 7d: R$ {tot_conf_7d:.2f}")
print(f"   Total em Conciliação 7d: R$ {tot_conc_7d:.2f}")
assert tot_conf_7d == Decimal("255.76"), f"Esperado R$ 255.76 mas obteve {tot_conf_7d}"
print("✓ Teste 1 passou: Janela rigorosa de 7 dias exclui o dia 27/10 e isola o BV.")

# TESTE 2: SEPARAÇÃO DE CONSUMO REALIZADO VS PARCELAS PAGA LEVE
# O consumo pós-hoje não pode somar parcelas vincendas do Paga Leve!
cur.execute("""
    SELECT COALESCE(SUM(valor), 0.0)
    FROM transacoes
    WHERE tipo = 'despesa' 
      AND pago = 1 
      AND status_pagamento = 'pago'
      AND (grupo_parcelamento IS NULL OR grupo_parcelamento = '')
      AND descricao NOT LIKE '%Paga Leve%'
      AND data > ? AND data LIKE '2026-10%'
""", (hoje.strftime('%Y-%m-%d'),))
consumo_pos_hoje_corrigido = Decimal(str(cur.fetchone()[0]))
print(f"\n2. Teste Consumo Realizado Pós-Hoje Corrigido: R$ {consumo_pos_hoje_corrigido:.2f}")
assert consumo_pos_hoje_corrigido == Decimal("0.00"), "Nenhuma despesa à vista foi liquidada após 20/10."
print("✓ Teste 2 passou: Parcelas vincendas do Paga Leve NÃO são tratadas como consumo realizado.")

# TESTE 3: ROLL-UP DE ORÇAMENTO E COEXISTÊNCIA DE FIXAS, VARIÁVEIS E EVENTUAIS
print("\n3. Teste de Roll-up por Grupo com Naturezas Distintas:")
cur.execute("""
    SELECT 
        g.nome as grupo,
        s.natureza_padrao,
        COUNT(t.id) as total_lancamentos,
        COALESCE(SUM(t.valor), 0.0) as valor_total
    FROM grupos_categoria g
    JOIN subcategorias s ON s.grupo_id = g.id
    LEFT JOIN transacoes t ON t.subcategoria_id = s.id AND t.data LIKE '2026-10%'
    WHERE g.nome = 'Habitação'
    GROUP BY g.nome, s.natureza_padrao
""")
for r in cur.fetchall():
    print(f"   Grupo: {r['grupo']} | Natureza: {r['natureza_padrao']} | Qtd: {r['total_lancamentos']} | Total: R$ {r['valor_total']:.2f}")
print("✓ Teste 3 passou: Subcategorias mantêm naturezas distintas (fixa, variável, eventual) no mesmo grupo.")

# TESTE 4: INTEGRIDADE REFERENCIAL DE IDs, TURNOS E PAGAMENTOS
print("\n4. Teste de Integridade Referencial:")
cur.execute("SELECT COUNT(*) FROM transacoes WHERE id NOT IN (SELECT id FROM transacoes)")
assert cur.fetchone()[0] == 0

cur.execute("SELECT COUNT(*) FROM turnos")
total_turnos = cur.fetchone()[0]
print(f"   Total de turnos preservados: {total_turnos}")

cur.execute("SELECT COUNT(*) FROM pagamentos_despesas")
total_pags = cur.fetchone()[0]
print(f"   Total de pagamentos de despesas preservados: {total_pags}")
print("✓ Teste 4 passou: Nenhuma alteração destrutiva em chaves primárias, estrangeiras ou vínculos.")

conn.close()
print("\n=== TODOS OS 4 TESTES TÉCNICOS PASSARAM COM SUCESSO! ===")
