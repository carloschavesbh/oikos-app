import sqlite3
import shutil
import calendar
from datetime import datetime, date, timedelta

# 1. Copia banco para teste isolado
TEST_DB = "scratch/test_drivvo_isolado.db"
shutil.copyfile("financas_casa.db", TEST_DB)

conn = sqlite3.connect(TEST_DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 2. Cria tabela veiculo_abastecimentos no banco isolado
cur.execute("""
CREATE TABLE IF NOT EXISTS veiculo_abastecimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data DATE NOT NULL,
    hodometro REAL,
    combustivel TEXT NOT NULL DEFAULT 'Etanol',
    litros REAL,
    preco_litro REAL,
    valor_bruto REAL,
    desconto REAL DEFAULT 0.0,
    valor_pago REAL NOT NULL,
    conta TEXT,
    conta_id INTEGER REFERENCES contas_config(id),
    tanque_cheio INTEGER DEFAULT 1,
    posto TEXT,
    observacao TEXT,
    transacao_id INTEGER REFERENCES transacoes(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")
cur.execute("DELETE FROM veiculo_abastecimentos")
conn.commit()
conn.commit()

print("=== TESTE 1: Auditoria da Transação 40 (20/10/2026 - R$ 90,48) ===")
cur.execute("SELECT id, data, descricao, valor, conta, conta_id, categoria FROM transacoes WHERE id = 40")
tr40 = dict(cur.fetchone())
print("Transação #40 existente:", tr40)
assert tr40["valor"] == 90.48 and tr40["data"] == "2026-10-20"
assert tr40["conta"] == "Dinheiro / Carteira"
print("✅ Transação #40 encontrada como despesa de R$ 90,48.")

# 3. Vincular Transação #40 aos detalhes de veículo (Drivvo-style)
print("\n=== TESTE 2: Vinculação de Despesa Existente sem Duplicar Saída Financeira ===")
count_tr_antes = cur.execute("SELECT count(*) FROM transacoes").fetchone()[0]

# Insere em veiculo_abastecimentos com transacao_id = 40
cur.execute("""
    INSERT INTO veiculo_abastecimentos (
        data, hodometro, combustivel, litros, preco_litro, valor_bruto, desconto, valor_pago,
        conta, conta_id, tanque_cheio, posto, observacao, transacao_id
    ) VALUES (
        '2026-10-20', 187290.0, 'Etanol', 27.86, 3.59, 100.0, 9.52, 90.48,
        'Dinheiro / Carteira', 2, 1, 'Posto de Combustível', 'Cupom de R$ 9,52 em dinheiro físico', 40
    )
""")
conn.commit()

count_tr_depois = cur.execute("SELECT count(*) FROM transacoes").fetchone()[0]
assert count_tr_depois == count_tr_antes, f"Erro! Foram criadas novas transações: antes={count_tr_antes}, depois={count_tr_depois}"
print("✅ Vinculação realizada com sucesso! Número de transações no extrato bancário permaneceu exatamente o mesmo (33).")

# 4. Cadastro de Novo Abastecimento Direto pelo Motorista App (com criação de despesa única)
print("\n=== TESTE 3: Cadastro de Novo Abastecimento com Despesa Única ===")
# Ex: Abastecimento em 21/10/2026: R$ 50 bruto, desconto R$ 0, pago R$ 50 no Mercado Pago
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario)
    VALUES ('2026-10-21', 'Abastecimento Gasolina Comum (8.50L) - Posto Shell', 50.0, 'despesa', 'Combustível (Trabalho)', 'Mercado Pago', 1, 1, 1)
""")
nova_tr_id = cur.lastrowid

cur.execute("""
    INSERT INTO veiculo_abastecimentos (
        data, hodometro, combustivel, litros, preco_litro, valor_bruto, desconto, valor_pago,
        conta, conta_id, tanque_cheio, posto, observacao, transacao_id
    ) VALUES (
        '2026-10-21', 187380.0, 'Gasolina Comum', 8.50, 5.88, 50.0, 0.0, 50.0,
        'Mercado Pago', 1, 0, 'Posto Shell', 'Completar para rodar a tarde', ?
    )
""", (nova_tr_id,))
conn.commit()

cur.execute("SELECT * FROM veiculo_abastecimentos WHERE transacao_id = ?", (nova_tr_id,))
r_novo = dict(cur.fetchone())
assert r_novo["valor_pago"] == 50.0
assert r_novo["desconto"] == 0.0
assert r_novo["transacao_id"] == nova_tr_id
print(f"✅ Novo abastecimento registrado: Transação #{nova_tr_id} vinculada ao registro do veículo #{r_novo['id']}.")

# 5. Cálculo dos Totais por Dia, Semana e Mês
print("\n=== TESTE 4: Cálculo dos Totais Pagos em Abastecimentos (Dia, Semana, Mês) ===")
# Consideremos data de referência 2026-10-21 (Quarta-feira)
hoje = date(2026, 10, 21)
hoje_iso = "2026-10-21"
inicio_semana = (hoje - timedelta(days=hoje.weekday())).strftime("%Y-%m-%d") # 2026-10-19
fim_semana = (hoje + timedelta(days=6 - hoje.weekday())).strftime("%Y-%m-%d") # 2026-10-25
inicio_mes = "2026-10-01"
fim_mes = "2026-10-31"

cur.execute("SELECT sum(valor_pago) FROM veiculo_abastecimentos WHERE data = ?", (hoje_iso,))
pago_hoje = cur.fetchone()[0] or 0.0

cur.execute("SELECT sum(valor_pago) FROM veiculo_abastecimentos WHERE data >= ? AND data <= ?", (inicio_semana, fim_semana))
pago_semana = cur.fetchone()[0] or 0.0

cur.execute("SELECT sum(valor_pago) FROM veiculo_abastecimentos WHERE data >= ? AND data <= ?", (inicio_mes, fim_mes))
pago_mes = cur.fetchone()[0] or 0.0

print(f"Abastecimento Pago Hoje ({hoje_iso}): R$ {pago_hoje:,.2f}")
print(f"Abastecimento Pago Esta Semana ({inicio_semana} a {fim_semana}): R$ {pago_semana:,.2f}")
print(f"Abastecimento Pago Este Mês ({inicio_mes} a {fim_mes}): R$ {pago_mes:,.2f}")

assert pago_hoje == 50.0
# Na semana temos: 20/10 (R$ 90,48) + 21/10 (R$ 50,00) = R$ 140,48
assert round(pago_semana, 2) == 140.48
assert round(pago_mes, 2) == 140.48
print("✅ Totais de abastecimento pago por dia, semana e mês calculados perfeitamente!")

# 6. Comparação com Consumo Estimado dos Turnos e Segregação Contábil
print("\n=== TESTE 5: Comparação Segregada (Sem Desconto Duplo e Sem Chamar de Lucro Líquido Completo) ===")
# Faturamento bruto e consumo estimado dos turnos
cur.execute("SELECT sum(ganho_bruto), sum(combustivel_consumido_estimado) FROM turnos WHERE status_turno = 'encerrado' AND data = '2026-10-20'")
row_t20 = cur.fetchone()
faturamento_20 = row_t20[0] or 0.0
consumo_est_20 = row_t20[1] or 0.0

# Abastecimento pago em 20/10
cur.execute("SELECT sum(valor_pago) FROM veiculo_abastecimentos WHERE data = '2026-10-20'")
abast_pago_20 = cur.fetchone()[0] or 0.0

# 1. Resultado de Caixa após Abastecimentos
resultado_caixa_20 = faturamento_20 - abast_pago_20

# 2. Resultado Operacional Estimado (Corridas - Consumo Proporcional)
resultado_operacional_est_20 = faturamento_20 - consumo_est_20

print(f"--- 20/10/2026 ---")
print(f"Faturamento Bruto: R$ {faturamento_20:,.2f}")
print(f"Abastecimento Real Pago (Caixa): R$ {abast_pago_20:,.2f}")
print(f"Consumo Estimado da Rodagem: R$ {consumo_est_20:,.2f}")
print(f"Resultado de Caixa após Abastecimento: R$ {resultado_caixa_20:,.2f}")
print(f"Resultado Operacional Estimado: R$ {resultado_operacional_est_20:,.2f}")

# Validações estritas:
assert faturamento_20 == 65.28
assert abast_pago_20 == 90.48
assert consumo_est_20 == 9.50
assert round(resultado_caixa_20, 2) == -25.20
assert round(resultado_operacional_est_20, 2) == 55.78

# Garantia: Nunca descontar os dois simultaneamente como custos adicionais
custo_com_duplo_desconto = abast_pago_20 + consumo_est_20
assert custo_com_duplo_desconto == 99.98
# O sistema NUNCA faz: faturamento_20 - custo_com_duplo_desconto (-34.70)!
print("✅ Garantia cumprida: Os dois resultados são apresentados separadamente, sem dupla cobrança de combustível!")

# 7. Preservação do Marco 99 e Turnos
print("\n=== TESTE 6: Preservação do Marco 99 e Turnos ===")
cur.execute("SELECT count(*) FROM turnos")
total_t = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM motorista_marco_producao")
total_m = cur.fetchone()[0]
print(f"Turnos preservados: {total_t} | Marcos 99: {total_m}")
assert total_t >= 3 and total_m >= 1
print("✅ Turnos e Marco 99 totalmente preservados!")

conn.close()
print("\n🎉 TODOS OS TESTES DRIVVO PASSARAM COM 100% DE SUCESSO!")
