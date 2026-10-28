import sys
import os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('scratch/financas_casa_audit_copy.db')
conn.row_factory = sqlite3.Row

import saldo_service
import planejamento_service

# Date today is 2026-10-20
hoje = date(2026, 10, 20)
print(f"Data de auditoria: {hoje}")

# 1. Saldo consolidado
res_saldo = saldo_service.calcular_saldo_consolidado(conn, hoje)
print(f"Saldo Consolidado: {res_saldo['saldo_consolidado']}")

# Let's check Visão Geral metrics (the 'old' planning indicators)
inicio_mes_str = "2026-10-01"
fim_mes_str = "2026-10-31"

df = pd.read_sql_query("SELECT * FROM transacoes", conn)

df_outubro = df[(df["data"] >= inicio_mes_str) & (df["data"] <= fim_mes_str)]
if "afeta_saldo_bancario" in df_outubro.columns:
    df_outubro_caixa = df_outubro[(df_outubro["afeta_saldo_bancario"] == 1) | (df_outubro["afeta_saldo_bancario"].isna())]
else:
    df_outubro_caixa = df_outubro

obrigacoes_outubro_pendentes = df_outubro_caixa[(df_outubro_caixa["tipo"] == "despesa") & (df_outubro_caixa["pago"] == 0)]["valor"].sum()
receitas_outubro_pendentes = df_outubro[(df_outubro["tipo"] == "receita") & (df_outubro["pago"] == 0)]["valor"].sum()
saldo_atual = float(res_saldo["saldo_consolidado"])
saldo_previsto_fim_mes = saldo_atual + receitas_outubro_pendentes - obrigacoes_outubro_pendentes

print("\n--- VISÃO GERAL (INDICADORES 'ANTIGOS') ---")
print(f"obrigacoes_outubro_pendentes: {obrigacoes_outubro_pendentes:.2f}")
print(f"receitas_outubro_pendentes: {receitas_outubro_pendentes:.2f}")
print(f"saldo_atual: {saldo_atual:.2f}")
print(f"saldo_previsto_fim_mes: {saldo_previsto_fim_mes:.2f}")

# Check dívidas antigas
df_antigas_pend = df[(df["tipo"] == "despesa") & (df["pago"] == 0) & (df["data"] < inicio_mes_str)]
print(f"Total dívidas antigas (< 2026-10-01) pendentes: {df_antigas_pend['valor'].sum():.2f}")

# Check dias restantes:
ultimo_dia_mes = 31
dias_calendario_restantes = max(1, ultimo_dia_mes - hoje.day + 1)
print(f"dias_calendario_restantes (de 20/10 a 31/10): {dias_calendario_restantes}")

# Check meta_dia if dias_trabalho = dias_calendario_restantes or default
for dt in [12, 11, 10, 8, 5]:
    falta_cobrir = max(0.0, -saldo_previsto_fim_mes)
    m_dia = falta_cobrir / dt if dt > 0 else 0
    print(f"Se dias_trabalho = {dt}: meta_dia = {m_dia:.2f}/dia (falta_cobrir = {falta_cobrir:.2f})")

# If 2841.88 / 12 = 236.82333333333332 !!!
print(f"2841.88 / 12 = {2841.88 / 12:.2f}")
print(f"2841.88 / 236.82 = {2841.88 / 236.82}")

# What is 2841.88?
# Let's check:
print(f"saldo_previsto_fim_mes = {saldo_previsto_fim_mes:.2f}")

# Now let's check Planejamento Novo:
print("\n--- PLANEJAMENTO NOVO (planejamento_service) ---")
proj_novo = planejamento_service.calcular_projecao_mensal(conn, hoje)
for k, v in proj_novo.items():
    if k != "resumo_variaveis":
        print(f"  {k}: {v}")
    else:
        print(f"  resumo_variaveis.total_consumo_esperado_restante: {v['total_consumo_esperado_restante']}")
        print(f"  resumo_variaveis.total_essencial_semana: {v['total_essencial_semana']}")

print("\n--- CAIXA 7 DIAS ---")
caixa_7d = planejamento_service.calcular_necessidade_caixa_7dias(conn, hoje)
for k, v in caixa_7d.items():
    if not isinstance(v, list):
        print(f"  {k}: {v}")

conn.close()
