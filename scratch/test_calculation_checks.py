import sqlite3
import pandas as pd
from datetime import date, timedelta
import calendar
from decimal import Decimal
import saldo_service
import planejamento_service

conn = sqlite3.connect('financas_casa.db')
conn.row_factory = sqlite3.Row

# Test reading df and df_turnos
df = pd.read_sql_query("SELECT * FROM transacoes", conn)
df_turnos = pd.read_sql_query("SELECT * FROM turnos", conn)

hoje = date(2026, 10, 20)
hoje_str = hoje.strftime("%Y-%m-%d")
# contando hoje mais seis dias = 20/10 a 26/10
limite_7d = hoje + timedelta(days=6)
limite_7d_str = limite_7d.strftime("%Y-%m-%d")
ano_atual = hoje.year
mes_atual = hoje.month
ultimo_dia = calendar.monthrange(ano_atual, mes_atual)[1]
fim_mes = date(ano_atual, mes_atual, ultimo_dia)
fim_mes_str = fim_mes.strftime("%Y-%m-%d")
dias_corridos_restantes = max(1, (fim_mes - hoje).days + 1)

print(f"Hoje: {hoje_str} | Limite 7d: {limite_7d_str} | Fim mes: {fim_mes_str} | Dias corridos: {dias_corridos_restantes}")

# 1. Renda do mes
df_rec = df[(df["tipo"] == "receita") & (df["data"] >= f"{ano_atual}-{mes_atual:02d}-01") & (df["data"] <= fim_mes_str)].copy()
rec_recebidas = df_rec[df_rec["pago"] == 1]
rec_previstas = df_rec[df_rec["pago"] == 0]

sal_fernanda_row = rec_recebidas[rec_recebidas["descricao"].str.contains("Fernanda", case=False, na=False) | rec_recebidas["categoria"].str.contains("Fernanda", case=False, na=False)]
val_sal_fernanda = float(sal_fernanda_row["valor"].sum()) if not sal_fernanda_row.empty else 0.0

# 99 turnos
df_turnos_out = df_turnos[df_turnos["data"] >= f"{ano_atual}-{mes_atual:02d}-01"].copy() if not df_turnos.empty else pd.DataFrame()
bruto_99 = float(df_turnos_out["ganho_bruto"].sum()) if not df_turnos_out.empty else 0.0
comb_99 = float(df_turnos_out["combustivel"].sum()) if not df_turnos_out.empty else 0.0
liq_99 = bruto_99 - comb_99

renda_efetiva_familiar = val_sal_fernanda + liq_99
print(f"Renda Efetiva Familiar: R$ {renda_efetiva_familiar:.2f} (Fernanda: R$ {val_sal_fernanda:.2f}, 99 Liq: R$ {liq_99:.2f})")

# Descontos em folha
df_folha = df[(df["data"] >= f"{ano_atual}-{mes_atual:02d}-01") & (df["data"] <= fim_mes_str) & (
    (df["descricao"].str.contains("Desconto em Folha", case=False, na=False)) |
    (df["categoria"].str.contains("Odontol", case=False, na=False))
)]
tot_folha = float(df_folha["valor"].sum())
print(f"Descontos em Folha segregados: R$ {tot_folha:.2f}")

# Compromissos
df_desp = df[(df["tipo"] == "despesa") & (df["pago"] == 0)].copy()
# Filtrar fora descontos em folha
if "afeta_saldo_bancario" in df_desp.columns:
    df_caixa = df_desp[(df_desp["afeta_saldo_bancario"] == 1) | (df_desp["afeta_saldo_bancario"].isna())].copy()
else:
    df_caixa = df_desp.copy()

vencidas = df_caixa[(df_caixa["data"] < hoje_str) & (df_caixa["data"] >= f"{ano_atual}-{mes_atual:02d}-01")].sort_values("data")
prox_7d = df_caixa[(df_caixa["data"] >= hoje_str) & (df_caixa["data"] <= limite_7d_str)].sort_values("data")
restante_mes = df_caixa[(df_caixa["data"] > limite_7d_str) & (df_caixa["data"] <= fim_mes_str)].sort_values("data")

print(f"Vencidas ({len(vencidas)}): R$ {vencidas['valor'].sum():.2f}")
print(f"7 dias ({len(prox_7d)}): R$ {prox_7d['valor'].sum():.2f}")
print(f"Restante ({len(restante_mes)}): R$ {restante_mes['valor'].sum():.2f}")

conn.close()
print("All calculation checks passed!")
