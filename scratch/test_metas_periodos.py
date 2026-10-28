import sqlite3
import pandas as pd
from datetime import date, timedelta
import sys
sys.path.append('.')
import saldo_service

conn = sqlite3.connect('financas_casa.db')
conn.row_factory = sqlite3.Row

df = pd.read_sql_query("SELECT * FROM transacoes", conn)
df_turnos = pd.read_sql_query("SELECT * FROM turnos", conn)

hoje = date(2026, 10, 20)
hoje_str = hoje.strftime("%Y-%m-%d")
limite_7d = hoje + timedelta(days=6)
limite_7d_str = limite_7d.strftime("%Y-%m-%d")
inicio_mes_str = "2026-10-01"
fim_mes_str = "2026-10-31"

# 1. Base Financeira Unica
saldo_info = saldo_service.calcular_saldo_consolidado(conn)
saldo_disp = float(saldo_info["saldo_consolidado"])

df_desp = df[(df["tipo"] == "despesa") & (df["pago"] == 0)].copy()
df_caixa = df_desp[(df_desp["afeta_saldo_bancario"] == 1) | (df_desp["afeta_saldo_bancario"].isna())].copy()

vencidas = df_caixa[(df_caixa["data"] < hoje_str) & (df_caixa["data"] >= inicio_mes_str)]
prox_7d = df_caixa[(df_caixa["data"] >= hoje_str) & (df_caixa["data"] <= limite_7d_str)]
restante_mes = df_caixa[(df_caixa["data"] > limite_7d_str) & (df_caixa["data"] <= fim_mes_str)]

tot_vencidas = float(vencidas["valor"].sum())
tot_7d = float(prox_7d["valor"].sum())
tot_restante_mes = float(restante_mes["valor"].sum())
tot_pendente_mes = tot_vencidas + tot_7d + tot_restante_mes
deficit_mes = max(0.0, tot_pendente_mes - saldo_disp)

# Semana: vencidas + 7 dias
tot_semana = tot_vencidas + tot_7d
deficit_semana = max(0.0, tot_semana - saldo_disp)

print(f"Saldo Disp: R$ {saldo_disp:.2f}")
print(f"Total Mes Pendente: R$ {tot_pendente_mes:.2f} | Deficit Mes: R$ {deficit_mes:.2f}")
print(f"Total Semana: R$ {tot_semana:.2f} | Deficit Semana: R$ {deficit_semana:.2f}")

# Parametros configurados
dias_disp_mes = 8
horas_hoje = 5.0
dias_semana = 5
horas_dia_semana = 5.0
margem_liq = 0.65
taxa_mercado = 35.0

# 1. HOJE
meta_liq_hoje = deficit_mes / dias_disp_mes
meta_bruta_hoje = meta_liq_hoje / margem_liq
meta_liq_hora_hoje = meta_liq_hoje / horas_hoje
meta_bruta_hora_hoje = meta_bruta_hoje / horas_hoje
horas_nec_hoje = meta_bruta_hoje / taxa_mercado
dif_horas_hoje = horas_hoje - horas_nec_hoje

# Turnos de hoje
df_turnos_hoje = df_turnos[df_turnos["data"] == hoje_str]
liq_hoje_real = float(df_turnos_hoje["ganho_bruto"].sum() - df_turnos_hoje["combustivel"].sum()) if not df_turnos_hoje.empty else 0.0

print("\n--- HOJE ---")
print(f"Meta Liq Hoje: R$ {meta_liq_hoje:.2f} | Meta Bruta Hoje: R$ {meta_bruta_hoje:.2f}")
print(f"Meta Liq/h: R$ {meta_liq_hora_hoje:.2f}/h | Meta Bruta/h: R$ {meta_bruta_hora_hoje:.2f}/h")
print(f"Horas Nec Hoje: {horas_nec_hoje:.1f}h | Dif Horas: {dif_horas_hoje:.1f}h")
print(f"Realizado Hoje: R$ {liq_hoje_real:.2f}")

# 2. SEMANA
meta_liq_semana = deficit_semana
meta_bruta_semana = meta_liq_semana / margem_liq
meta_liq_dia_semana = meta_liq_semana / dias_semana
meta_bruta_dia_semana = meta_bruta_semana / dias_semana
horas_nec_semana = meta_bruta_semana / taxa_mercado
horas_disp_semana = dias_semana * horas_dia_semana
dif_horas_semana = horas_disp_semana - horas_nec_semana

# Turnos da semana
df_turnos_semana = df_turnos[(df_turnos["data"] >= hoje_str) & (df_turnos["data"] <= limite_7d_str)]
liq_semana_real = float(df_turnos_semana["ganho_bruto"].sum() - df_turnos_semana["combustivel"].sum()) if not df_turnos_semana.empty else 0.0

print("\n--- SEMANA ---")
print(f"Meta Liq Semana: R$ {meta_liq_semana:.2f} | Meta Bruta Semana: R$ {meta_bruta_semana:.2f}")
print(f"Meta Liq/Dia: R$ {meta_liq_dia_semana:.2f} | Meta Bruta/Dia: R$ {meta_bruta_dia_semana:.2f}")
print(f"Horas Nec Semana: {horas_nec_semana:.1f}h | Disp: {horas_disp_semana:.1f}h | Dif: {dif_horas_semana:.1f}h")
print(f"Realizado Semana: R$ {liq_semana_real:.2f}")

# 3. MES
meta_liq_mes = deficit_mes
meta_bruta_mes = meta_liq_mes / margem_liq
meta_liq_dia_mes = meta_liq_mes / dias_disp_mes
meta_bruta_dia_mes = meta_bruta_mes / dias_disp_mes
horas_disp_mes = dias_disp_mes * horas_dia_semana
horas_nec_mes = meta_bruta_mes / taxa_mercado
dif_horas_mes = horas_disp_mes - horas_nec_mes

# Turnos do mes
df_turnos_mes = df_turnos[df_turnos["data"] >= inicio_mes_str]
liq_mes_real = float(df_turnos_mes["ganho_bruto"].sum() - df_turnos_mes["combustivel"].sum()) if not df_turnos_mes.empty else 0.0

print("\n--- MES ---")
print(f"Meta Liq Mes: R$ {meta_liq_mes:.2f} | Meta Bruta Mes: R$ {meta_bruta_mes:.2f}")
print(f"Meta Liq/Dia: R$ {meta_liq_dia_mes:.2f} | Meta Bruta/Dia: R$ {meta_bruta_dia_mes:.2f}")
print(f"Horas Nec Mes: {horas_nec_mes:.1f}h | Disp: {horas_disp_mes:.1f}h | Dif: {dif_horas_mes:.1f}h")
print(f"Realizado Mes: R$ {liq_mes_real:.2f}")

conn.close()
print("\nChecks OK!")
