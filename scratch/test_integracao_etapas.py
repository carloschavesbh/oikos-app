import sqlite3
import pandas as pd
import sys
import os
from decimal import Decimal

sys.path.insert(0, os.getcwd())
import app
import saldo_service

sys.stdout.reconfigure(encoding='utf-8')

print("================================================================================")
print("TESTE DE INTEGRAÇÃO DAS ETAPAS 1 A 5")
print("================================================================================")

# 1. Verifica título e constantes
print(f"1. APP_TITLE: '{app.APP_TITLE}'")
assert app.APP_TITLE == "Central Financeira"
assert app.APP_SUBTITLE == "Gestão Pessoal & Motorista"
print("   ✅ Constantes de cabeçalho verificadas.")

# 2. Conecta ao banco e valida integridade
conn = sqlite3.connect('financas_casa.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("PRAGMA integrity_check")
assert cur.fetchone()[0] == 'ok'

s_mp = saldo_service.calcular_saldo_conta(conn, 1)['saldo_atual']
s_cart = saldo_service.calcular_saldo_conta(conn, 2)['saldo_atual']
s_tot = saldo_service.calcular_saldo_consolidado(conn)['saldo_consolidado']

print(f"\n2. Saldos em produção:")
print(f"   Mercado Pago: R$ {s_mp} (esperado: 8.83)")
print(f"   Carteira:     R$ {s_cart} (esperado: 77.50)")
print(f"   Consolidado:  R$ {s_tot} (esperado: 86.33)")

assert s_mp == Decimal("8.83")
assert s_cart == Decimal("77.50")
assert s_tot == Decimal("86.33")

# 3. Verifica dados preservados
cur.execute("SELECT id, descricao, valor, pago, status_pagamento FROM transacoes WHERE id = 2")
cop = dict(cur.fetchone())
print(f"\n3. Copasa id=2: {cop}")
assert cop['pago'] == 0
assert cop['status_pagamento'] == 'pendente'
assert cop['valor'] == 72.46

cur.execute("SELECT id, ganho_bruto, combustivel FROM turnos WHERE id = 2")
tur = dict(cur.fetchone())
print(f"   Turno 99 id=2: {tur}")
assert tur['ganho_bruto'] == 17.60
assert tur['combustivel'] == 0.0

# 4. Testa agrupamento da página Paga Leve com dados reais
df_trans = pd.read_sql_query("SELECT * FROM transacoes", conn)
df_pl = df_trans[(df_trans["grupo_parcelamento"].str.startswith("pagaleve", na=False)) | (df_trans["descricao"].str.contains("Paga Leve", case=False, na=False))].copy()
print(f"\n4. Parcelas Paga Leve no banco: {len(df_pl)}")
assert len(df_pl) == 9

# Contagem de compras ativas vs quitadas
grupos = set(df_pl['grupo_parcelamento'].dropna().unique())
print(f"   Grupos Paga Leve: {grupos}")
assert 'pagaleve_raia' in grupos
assert 'pagaleve_whey' in grupos
assert 'pagaleve_99food' in grupos

conn.close()

print("\n================================================================================")
print("TODAS AS ETAPAS ESTÃO ÍNTEGRAS, VALIDADAS E FUNCIONANDO COM SUCESSO!")
print("================================================================================")
