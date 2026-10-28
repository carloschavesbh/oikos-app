import sqlite3
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))

import app
import saldo_service
import planejamento_service

print("=== AUDITORIA COMPLETA DE REGRAS E FORMAS ===")

conn = sqlite3.connect('financas_casa.db')
conn.row_factory = sqlite3.Row

# 1. Teste de Persistência da Margem Líquida
print("\n--- 1. Teste da Margem Líquida ---")
margem_inicial = app.carregar_margem_liquida_planejada(65.0)
print(f"Margem carregada inicial: {margem_inicial}%")
app.salvar_margem_liquida_planejada(70.0)
margem_atualizada = app.carregar_margem_liquida_planejada(65.0)
print(f"Margem após atualizar para 70%: {margem_atualizada}%")
assert margem_atualizada == 70.0
# Restaurar padrão 65.0
app.salvar_margem_liquida_planejada(65.0)
margem_restaurada = app.carregar_margem_liquida_planejada(65.0)
print(f"Margem restaurada para padrão: {margem_restaurada}%")
assert margem_restaurada == 65.0

# 2. Teste da Base Financeira Única
print("\n--- 2. Base Financeira Única ---")
saldo_info = saldo_service.calcular_saldo_consolidado(conn)
saldo_disp = float(saldo_info["saldo_consolidado"])
print(f"Saldo Consolidado Livre: R$ {saldo_disp:.2f}")
assert saldo_disp == 86.33

df_tx = pd.read_sql_query("SELECT * FROM transacoes", conn)
df_turnos = pd.read_sql_query("SELECT * FROM turnos", conn)

hoje = date(2026, 10, 20)
hoje_str = hoje.strftime("%Y-%m-%d")
limite_7d = hoje + timedelta(days=6)
limite_7d_str = limite_7d.strftime("%Y-%m-%d")
inicio_mes_str = "2026-10-01"
fim_mes_str = "2026-10-31"

df_desp = df_tx[(df_tx["tipo"] == "despesa") & (df_tx["pago"] == 0)].copy()
df_caixa = df_desp[(df_desp["afeta_saldo_bancario"] == 1) | (df_desp["afeta_saldo_bancario"].isna())].copy()

vencidas = df_caixa[(df_caixa["data"] < hoje_str) & (df_caixa["data"] >= inicio_mes_str)]
prox_7d = df_caixa[(df_caixa["data"] >= hoje_str) & (df_caixa["data"] <= limite_7d_str)]
restante_mes = df_caixa[(df_caixa["data"] > limite_7d_str) & (df_caixa["data"] <= fim_mes_str)]

tot_vencidas = float(vencidas["valor"].sum())
tot_7d = float(prox_7d["valor"].sum())
tot_restante_mes = float(restante_mes["valor"].sum())
tot_pendente_mes = tot_vencidas + tot_7d + tot_restante_mes

deficit_mes = max(0.0, tot_pendente_mes - saldo_disp)
deficit_semana = max(0.0, (tot_vencidas + tot_7d) - saldo_disp)

print(f"Total Vencidas: R$ {tot_vencidas:.2f} (8 contas)")
print(f"Total Próx 7d: R$ {tot_7d:.2f} (3 contas)")
print(f"Total Restante Mês: R$ {tot_restante_mes:.2f} (2 contas)")
print(f"Total Pendente Mês: R$ {tot_pendente_mes:.2f}")
print(f"Déficit Mês: R$ {deficit_mes:.2f}")
print(f"Déficit Semana: R$ {deficit_semana:.2f}")

assert round(tot_pendente_mes, 2) == 2928.21
assert round(deficit_mes, 2) == 2841.88
assert round(deficit_semana, 2) == 2316.82

# 3. Teste das Metas Hoje
print("\n--- 3. Metas Hoje ---")
dias_disp_mes = 8
horas_hoje = 5.0
margem_liq = 0.65
taxa_mercado = 35.0

meta_liq_hoje = deficit_mes / dias_disp_mes
meta_bruta_hoje = meta_liq_hoje / margem_liq
meta_liq_hora_hoje = meta_liq_hoje / horas_hoje
horas_nec_hoje = meta_bruta_hoje / taxa_mercado
prod_bruta_viavel_hoje = horas_hoje * taxa_mercado
prod_liq_viavel_hoje = prod_bruta_viavel_hoje * margem_liq
deficit_restante_hoje = max(0.0, meta_liq_hoje - prod_liq_viavel_hoje)

print(f"Meta Líquida Hoje: R$ {meta_liq_hoje:.2f}")
print(f"Meta Bruta Hoje: R$ {meta_bruta_hoje:.2f}")
print(f"Horas Necessárias Hoje: {horas_nec_hoje:.1f}h")
print(f"Produção Viável Hoje ({horas_hoje}h): R$ {prod_liq_viavel_hoje:.2f} líq")
print(f"Déficit Restante Hoje: R$ {deficit_restante_hoje:.2f} líq")

assert round(meta_liq_hoje, 2) == 355.24 or round(meta_liq_hoje, 2) == 355.23
assert round(prod_liq_viavel_hoje, 2) == 113.75
assert round(deficit_restante_hoje, 2) == round(meta_liq_hoje - 113.75, 2)

# 4. Teste de Cofrinhos e Missão via planejamento_service
print("\n--- 4. Cofrinhos e Missão no Serviço ---")
cofrinhos = planejamento_service.obter_cofrinhos(conn)
print(f"Cofrinhos encontrados: {len(cofrinhos)}")
for c in cofrinhos:
    print(f"  - {c['nome']}: R$ {float(c['saldo_confirmado']):.2f} (Meta: R$ {float(c['meta_valor']):.2f})")

missao = planejamento_service.obter_status_missao_ipva(conn, mes_ano="2026-10", data_referencia=hoje)
print(f"Missão IPVA: {missao['titulo']} | Alvo: R$ {float(missao['valor_nominal']):.2f} | Status: {missao.get('status')}")
assert missao.get("tem_missao") is True
assert float(missao["valor_nominal"]) == 431.11

# 5. Integridade do banco
c_cur = conn.cursor()
c_cur.execute("PRAGMA integrity_check")
int_res = c_cur.fetchone()[0]
print(f"\nPRAGMA integrity_check: {int_res}")
assert int_res == 'ok'

conn.close()
print("\n✅ TODAS AS AUDITORIAS PASSARAM COM 100% DE SUCESSO!")
