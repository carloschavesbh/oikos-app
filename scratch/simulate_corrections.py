import sys
import os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
from datetime import date, timedelta
from decimal import Decimal
import saldo_service
import planejamento_service

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('scratch/financas_casa_audit_copy.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

hoje = date(2026, 10, 20)

print("--- SIMULACAO NO BANCO DE TESTES DAS CORRECOES PROPOSTAS ---")

# 1. Regra de 7 dias estrita: D+0 a D+6 (20/10 a 26/10)
dt_limite_7d_estrito = hoje + timedelta(days=6) # 26/10
print(f"Janela 7 dias estrita: {hoje} a {dt_limite_7d_estrito}")

cur.execute("""
    SELECT t.id, t.data, t.descricao, t.valor, t.categoria, COALESCE(t.status_conciliacao_fatura, 'normal') as st
    FROM transacoes t
    WHERE t.tipo = 'despesa' AND (t.pago IS NULL OR t.pago != 1)
      AND t.data >= ? AND t.data <= ?
    ORDER BY t.data, t.id
""", (hoje.strftime('%Y-%m-%d'), dt_limite_7d_estrito.strftime('%Y-%m-%d')))
obs_7d_estrito = cur.fetchall()

tot_conf_7d_estrito = Decimal("0.00")
print("Obrigações na janela estrita de 7 dias (20/10 a 26/10):")
for r in obs_7d_estrito:
    if r['st'] != 'pendente_confirmacao' and 'Acordo BV' not in r['descricao']:
        tot_conf_7d_estrito += Decimal(str(r['valor']))
        print(f"  ID {r['id']:2d} | {r['data']} | R$ {r['valor']:7.2f} | {r['descricao']}")
    else:
        print(f"  [ISOLADO BV] ID {r['id']:2d} | {r['data']} | R$ {r['valor']:7.2f} | {r['descricao']}")

print(f"Total Confirmadas 7d Estrito: R$ {tot_conf_7d_estrito:.2f}")

# Comparação com janela D+7 (20/10 a 27/10):
cur.execute("""
    SELECT t.id, t.data, t.descricao, t.valor
    FROM transacoes t
    WHERE t.tipo = 'despesa' AND (t.pago IS NULL OR t.pago != 1) AND t.data = '2026-10-27'
""")
d_27 = cur.fetchall()
print(f"Contas que caem exatamente no dia 27/10: {[dict(x) for x in d_27]}")

# 2. Despesas variáveis sem duplicação
# Habitação: 0 (já é fixa)
# Streaming: 0 (já é assinatura)
# Supermercado: 350.00
# Medicamentos: 80.00 (sem abater parcela Paga Leve)
# Restaurante: 100.00 (sem abater parcela Paga Leve)
# Combustível: se estritamente pessoal: ex 100.00, se 100% trabalho: 0.00
# Outros: 60.00
print("\nDespesas Variáveis Corrigidas (sem duplicação):")
variaveis_corrigidas = {
    "Supermercado": Decimal("350.00"),
    "Medicamentos": Decimal("80.00"),
    "Restaurante": Decimal("100.00"),
    "Outros": Decimal("60.00"),
    "Combustível": Decimal("0.00"), # assumindo 100% app
    "Habitação": Decimal("0.00"), # fixo já nas contas
    "Streaming": Decimal("0.00")   # assinatura já nas contas
}
tot_var_corrigido = sum(variaveis_corrigidas.values())
print(f"Total Consumo Variável Restante Corrigido: R$ {tot_var_corrigido:.2f} (era R$ 1.391,84)")

# 3. Projeção Mensal Corrigida
saldo_atual = Decimal("86.33")
obrig_confirmadas_mes = Decimal("1499.39") # sem BV
saidas_projetadas_corrigidas = obrig_confirmadas_mes + tot_var_corrigido
saldo_final_projetado_corrigido = saldo_atual - saidas_projetadas_corrigidas
print(f"\nProjeção Mensal Corrigida:")
print(f"  Saldo Atual: R$ {saldo_atual:.2f}")
print(f"  Obrigações Confirmadas Mês: R$ {obrig_confirmadas_mes:.2f}")
print(f"  Variáveis Restantes Corrigidas: R$ {tot_var_corrigido:.2f}")
print(f"  Total Saídas: R$ {saidas_projetadas_corrigidas:.2f}")
print(f"  Saldo Final Projetado (sem renda app): R$ {saldo_final_projetado_corrigido:.2f}")
print(f"  Déficit Operacional Projetado: R$ {abs(saldo_final_projetado_corrigido):.2f}")
print(f"  Acordo BV isolado sob conciliação: R$ 1.428,82")

conn.close()
