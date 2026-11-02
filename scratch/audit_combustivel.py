import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_remodelacao.db')

# 1. Abastecimentos reais em transacoes em Outubro
txs_comb = conn.execute("""
    SELECT id, data, descricao, valor, categoria, conta 
    FROM transacoes 
    WHERE tipo='despesa' 
      AND categoria IN ('Combustível', 'Combustível (Trabalho)')
      AND data BETWEEN '2026-10-01' AND '2026-10-31'
    ORDER BY data
""").fetchall()

print(f"--- TRANSAÇÕES DE COMBUSTÍVEL EM OUTUBRO ({len(txs_comb)} lançamentos) ---")
tot_txs_comb = sum(t[3] for t in txs_comb)
for t in txs_comb:
    print(f"  Tx #{t[0]}: {t[1]} | {t[2]} | R$ {t[3]:.2f} | {t[5]}")
print(f"Total pago no posto (transações): R$ {tot_txs_comb:.2f}")

# 2. Consumo estimado nos turnos em Outubro
turnos_comb = conn.execute("""
    SELECT id, data, km, ganho_bruto, combustivel, observacao
    FROM turnos
    WHERE data BETWEEN '2026-10-01' AND '2026-10-31'
    ORDER BY data
""").fetchall()

print(f"\n--- CONSUMO ESTIMADO NOS TURNOS EM OUTUBRO ({len(turnos_comb)} turnos) ---")
tot_turnos_comb = sum(t[4] for t in turnos_comb)
tot_turnos_bruto = sum(t[3] for t in turnos_comb)
for t in turnos_comb:
    print(f"  Turno #{t[0]}: {t[1]} | {t[2]} km | Bruto R$ {t[3]:.2f} | Combustível Estimado R$ {t[4]:.2f}")
print(f"Total combustível estimado nos turnos: R$ {tot_turnos_comb:.2f}")

# 3. Abastecimentos na tabela veiculo_abastecimentos em Outubro
abast_tbl = conn.execute("""
    SELECT id, data, combustivel, litros, preco_litro, valor_bruto, desconto, valor_pago
    FROM veiculo_abastecimentos
    WHERE data BETWEEN '2026-10-01' AND '2026-10-31'
""").fetchall()
print(f"\n--- TABELA veiculo_abastecimentos EM OUTUBRO ({len(abast_tbl)} registros) ---")
for a in abast_tbl:
    print(a)

conn.close()
