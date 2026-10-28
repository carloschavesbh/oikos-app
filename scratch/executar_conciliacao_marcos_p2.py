import sys
import os
import shutil
import sqlite3
from decimal import Decimal
from datetime import datetime

# Configure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import saldo_service

DB_FILE = "financas_casa.db"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_FILE = f"financas_casa_backup_conciliacao_p2_{TIMESTAMP}.db"

print("=" * 65)
print("EXECUÇÃO AUTÔNOMA: CONCILIAÇÃO DEFINITIVA DE SALDOS (21/10/2026)")
print("=" * 65)

# 1. Backup de Segurança
shutil.copy2(DB_FILE, BACKUP_FILE)
print(f"1. Backup de segurança criado: {BACKUP_FILE}")

# 2. Conexão com o banco principal
conn = sqlite3.connect(DB_FILE)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 3. Cancelamento contábil dos marcos anteriores de 19/10/2026
print("\n2. Atualizando histórico: cancelando marcos anteriores de 19/10/2026...")
cur.execute("SELECT id, conta_id, data, saldo_informado_centavos FROM ajustes_saldo WHERE status = 'ativo'")
marcos_antigos = cur.fetchall()
for m in marcos_antigos:
    m_id, m_cid, m_dt, m_cents = m
    saldo_service.cancelar_ajuste(
        conn, 
        ajuste_id=m_id, 
        motivo_cancelamento="Substituído pela conciliação definitiva de corte em 21/10/2026"
    )
    print(f"   - Marco #{m_id} (Conta {m_cid} • {m_dt} • R$ {m_cents/100:,.2f}) marcado como substituído.")

# 4. Registro dos novos marcos de corte em 21/10/2026
print("\n3. Registrando novos marcos de corte oficiais para 21/10/2026:")

# 4.1. Mercado Pago: R$ 40,00
# Contempla transações #42 (Receita 99: R$ 55,05) e #46 (Despesa Raia: R$ 6,89) realizadas hoje
id_marco_mp = saldo_service.registrar_ajuste(
    conn,
    conta_id=1,
    data_ajuste="2026-10-21",
    saldo_informado=Decimal("40.00"),
    tipo="marco_inicial",
    motivo="Marco definitivo de saldo conciliado - Extrato oficial Mercado Pago (R$ 40,00)",
    transacoes_contempladas_ids=[42, 46]
)
print(f"   ✅ Novo Marco Mercado Pago registrado (ID #{id_marco_mp}): R$ 40,00 em 21/10/2026")

# 4.2. Dinheiro / Carteira: R$ 7,00
# Transações anteriores (R$ 90,48 combustível e R$ 9,15 padaria de 20/10) ficam antes do corte
id_marco_cart = saldo_service.registrar_ajuste(
    conn,
    conta_id=2,
    data_ajuste="2026-10-21",
    saldo_informado=Decimal("7.00"),
    tipo="marco_inicial",
    motivo="Marco definitivo de saldo conciliado - Dinheiro físico em mãos (R$ 7,00)",
    transacoes_contempladas_ids=[]
)
print(f"   ✅ Novo Marco Carteira registrado (ID #{id_marco_cart}): R$ 7,00 em 21/10/2026")

# 5. Blindagem contra pagamentos prévios
print("\n4. Blindando pagamentos da tabela pagamentos_despesas anteriores/contemplados...")
cur.execute("""
    UPDATE pagamentos_despesas
    SET considerado_no_marco = 1
    WHERE data_pagamento <= '2026-10-21' AND cancelado = 0
""")
conn.commit()
print(f"   ✅ {cur.rowcount} registros de pagamentos marcados como já refletidos no saldo bancário.")

# 6. Verificação e Asserções de Integridade
print("\n5. Validando saldos calculados pelo saldo_service:")
res_mp = saldo_service.calcular_saldo_conta(conn, 1)
res_cart = saldo_service.calcular_saldo_conta(conn, 2)
res_cons = saldo_service.calcular_saldo_consolidado(conn)

saldo_mp = res_mp["saldo_atual"]
saldo_cart = res_cart["saldo_atual"]
saldo_livre = res_cons["saldo_consolidado"]
saldo_reservas = res_cons["saldo_reservas"]
saldo_total = res_cons["saldo_total_com_reservas"]

print(f"   - Mercado Pago: R$ {saldo_mp:,.2f} (esperado: R$ 40.00)")
print(f"   - Dinheiro / Carteira: R$ {saldo_cart:,.2f} (esperado: R$ 7.00)")
print(f"   - Saldo Livre Disponível: R$ {saldo_livre:,.2f} (esperado: R$ 47.00)")
print(f"   - Reservas / Cofrinhos: R$ {saldo_reservas:,.2f} (esperado: R$ 0.00)")
print(f"   - Total Consolidado: R$ {saldo_total:,.2f} (esperado: R$ 47.00)")

assert saldo_mp == Decimal("40.00"), f"Erro no Mercado Pago: obtido {saldo_mp}"
assert saldo_cart == Decimal("7.00"), f"Erro na Carteira: obtido {saldo_cart}"
assert saldo_livre == Decimal("47.00"), f"Erro no Saldo Livre: obtido {saldo_livre}"
assert saldo_reservas == Decimal("0.00"), f"Erro nas Reservas: obtido {saldo_reservas}"
assert saldo_total == Decimal("47.00"), f"Erro no Total: obtido {saldo_total}"

print("\n   🎯 TODAS AS REGRAS E ASSERÇÕES FORAM ATENDIDAS COM PRECISÃO ABSOLUTA!")

conn.close()
print("\n" + "=" * 65)
print("CONCILIAÇÃO FINALIZADA COM SUCESSO NO BANCO REAL!")
print("=" * 65)
