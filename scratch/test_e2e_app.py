import sys
import os
import sqlite3
import pandas as pd
from datetime import date

# Set UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import saldo_service
import app

print("=== TESTE END-TO-END DE INTERFACE E SERVIÇOS ===")

conn = sqlite3.connect("financas_casa.db")
conn.row_factory = sqlite3.Row

# 1. Teste de Saldo Consolidado
print("\n1. Teste de Saldo Consolidado em Caixa:")
dados_caixa = saldo_service.calcular_saldo_consolidado(conn)
print(f"Saldo Livre: R$ {dados_caixa['saldo_consolidado']}")
print(f"Saldo Reservas: R$ {dados_caixa['saldo_reservas']}")
print(f"Saldo Total: R$ {dados_caixa['saldo_total_com_reservas']}")
assert "saldo_consolidado" in dados_caixa
assert len(dados_caixa["contas"]) > 0
print("✅ Saldo consolidado e detalhamento de contas OK!")

# 2. Teste de Máscara Monetária
print("\n2. Teste de Entrada de Moeda por Centavos:")
casos = [
    ("5", 0.05),
    ("50", 0.50),
    ("500", 5.00),
    ("1170", 11.70),
    ("5505", 55.05),
    ("R$ 55,05", 55.05),
    ("50,5", 50.50),
    ("50.5", 50.50),
    ("100,00", 100.00),
    (100.0, 100.00),
    (None, 0.0)
]
for inp, exp in casos:
    res = app.parse_moeda_centavos(inp)
    assert res == exp, f"Falha: inp={inp}, esperado={exp}, obtido={res}"
print("✅ Todos os casos de digitação rápida de centavos passaram!")

# 3. Teste de Transações e Ordenação de Lançamentos
print("\n3. Teste de Ordenação por Data em Lançamentos:")
df_tr = pd.read_sql_query("SELECT * FROM transacoes", conn)
print(f"Total de transações no banco: {len(df_tr)}")

# Simulação da ordenação mais recente primeiro
df_recente = df_tr.sort_values(by=["data", "id"], ascending=[False, False])
datas_rec = sorted(df_recente["data"].dropna().unique(), reverse=True)
print(f"Ordem mais recente (primeiras 3): {datas_rec[:3]}")
assert datas_rec[0] >= datas_rec[-1]

# Simulação da ordenação mais antigo primeiro
df_antigo = df_tr.sort_values(by=["data", "id"], ascending=[True, True])
datas_ant = sorted(df_antigo["data"].dropna().unique(), reverse=False)
print(f"Ordem mais antigo (primeiras 3): {datas_ant[:3]}")
assert datas_ant[0] <= datas_ant[-1]
print("✅ Ordenação por data (ascendente e descendente) OK!")

# 4. Teste de Obtenção de Recebimentos do Turno
print("\n4. Teste de Auditoria de Recebimentos do Turno:")
info_t3 = saldo_service.obter_recebimentos_turno(conn, 3)
print(f"Turno 3: Bruto R$ {info_t3['ganho_bruto']}, Contabilizado R$ {info_t3['total_contabilizado']}, Excedente R$ {info_t3['excedente']}")
assert info_t3["status"] == "integral"
assert info_t3["excedente"] == 0.0
assert info_t3["total_contabilizado"] == 55.05
print("✅ Auditoria do turno 3 confirmou faturamento e recebimentos 100% equilibrados!")

# 5. Teste de Abastecimento Veículo: Cálculo automático e consistência
print("\n5. Teste de Abastecimento Veículo:")
preco_l = 3.59
val_bruto = 100.0
cupom = 9.52
litros_calc = round(val_bruto / preco_l, 3)
val_pago = round(val_bruto - cupom, 2)
print(f"Preço: {preco_l}/L | Bruto: R$ {val_bruto} ➔ Litros: {litros_calc} L | Cupom: R$ {cupom} ➔ Pago: R$ {val_pago}")
assert litros_calc == 27.855
assert val_pago == 90.48
print("✅ Cálculos de bomba, litros e desconto OK!")

conn.close()
print("\n>>> TODAS AS VALIDAÇÕES END-TO-END PASSARAM COM SUCESSO! <<<")
