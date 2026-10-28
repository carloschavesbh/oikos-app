import sqlite3
import pandas as pd
from datetime import date, timedelta
import calendar
import sys
sys.path.append('.')
import saldo_service
import planejamento_service

conn = sqlite3.connect('financas_casa.db')
conn.row_factory = sqlite3.Row

df = pd.read_sql_query("SELECT * FROM transacoes", conn)
df_turnos = pd.read_sql_query("SELECT * FROM turnos", conn)

hoje = date(2026, 10, 20)
hoje_str = hoje.strftime("%Y-%m-%d")
limite_7d = hoje + timedelta(days=6)
limite_7d_str = limite_7d.strftime("%Y-%m-%d")
ano_atual = hoje.year
mes_atual = hoje.month
inicio_mes_str = f"{ano_atual}-{mes_atual:02d}-01"
ultimo_dia = calendar.monthrange(ano_atual, mes_atual)[1]
fim_mes = date(ano_atual, mes_atual, ultimo_dia)
fim_mes_str = fim_mes.strftime("%Y-%m-%d")
dias_corridos_restantes = max(1, (fim_mes - hoje).days + 1)

# Saldos
saldo_info = saldo_service.calcular_saldo_consolidado(conn)
saldo_total = float(saldo_info["saldo_consolidado"])
mp_val = float(saldo_service.calcular_saldo_conta(conn, 1)["saldo_atual"])
cart_val = float(saldo_service.calcular_saldo_conta(conn, 2)["saldo_atual"])

# Contas
df_desp = df[(df["tipo"] == "despesa") & (df["pago"] == 0)].copy()
if "afeta_saldo_bancario" in df_desp.columns:
    df_caixa = df_desp[(df_desp["afeta_saldo_bancario"] == 1) | (df_desp["afeta_saldo_bancario"].isna())].copy()
else:
    df_caixa = df_desp.copy()

vencidas = df_caixa[(df_caixa["data"] < hoje_str) & (df_caixa["data"] >= inicio_mes_str)].sort_values("data")
prox_7d = df_caixa[(df_caixa["data"] >= hoje_str) & (df_caixa["data"] <= limite_7d_str)].sort_values("data")
restante_mes = df_caixa[(df_caixa["data"] > limite_7d_str) & (df_caixa["data"] <= fim_mes_str)].sort_values("data")

tot_vencidas = float(vencidas["valor"].sum())
tot_7d = float(prox_7d["valor"].sum())
tot_restante = float(restante_mes["valor"].sum())
tot_pendente = tot_vencidas + tot_7d + tot_restante

print(f"Total Pendente Outubro: R$ {tot_pendente:.2f}")
print(f"Saldo Total Disponível: R$ {saldo_total:.2f}")
deficit = max(0.0, tot_pendente - saldo_total)
print(f"Déficit Líquido Consistente: R$ {deficit:.2f}")

# Simulação com 8 dias e 5h/dia, margem 65%
dias_disp = 8
horas_dia = 5.0
margem = 0.65
tot_horas_disp = dias_disp * horas_dia
meta_liq_dia = deficit / dias_disp
meta_liq_hora = meta_liq_dia / horas_dia
meta_bruta_total = deficit / margem
meta_bruta_dia = meta_liq_dia / margem
meta_bruta_hora = meta_liq_hora / margem
horas_nec = meta_bruta_total / 35.0
dif_horas = tot_horas_disp - horas_nec

print(f"Total Horas Disp: {tot_horas_disp}h | Horas Necessárias: {horas_nec:.1f}h")
if dif_horas < 0:
    print(f"🚨 Meta acima da capacidade informada (+{abs(dif_horas):.1f}h necessárias)")
else:
    print(f"✅ Dentro da capacidade informada (Folga {dif_horas:.1f}h)")

conn.close()
print("Draft check OK!")
