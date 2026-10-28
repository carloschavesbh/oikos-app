import sys
import os
import shutil
import sqlite3
from datetime import datetime

# Configure UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import saldo_service

DB_FILE = "financas_casa.db"
BACKUP_FILE = f"financas_casa_backup_execucao_p1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

print("=" * 60)
print("EXECUÇÃO AUTÔNOMA DA CORREÇÃO DA PRIORIDADE 1 NO BANCO REAL")
print("=" * 60)

# 1. Criação de Backup de Segurança
shutil.copy2(DB_FILE, BACKUP_FILE)
print(f"1. Backup de segurança criado com sucesso: {BACKUP_FILE}")

# 2. Conexão ao banco principal
conn = sqlite3.connect(DB_FILE)
conn.row_factory = sqlite3.Row

# Auditoria antes da correção
print("\n2. Estado do Turno #3 antes da correção:")
info_antes = saldo_service.obter_recebimentos_turno(conn, 3)
print(f"   - Faturamento bruto: R$ {info_antes['ganho_bruto']:,.2f}")
print(f"   - Total contabilizado: R$ {info_antes['total_contabilizado']:,.2f}")
print(f"   - Excedente: R$ {info_antes['excedente']:,.2f}")
print(f"   - Transações vinculadas: {[t['id'] for t in info_antes['transacoes']]}")

# Saldos antes
res_antes = saldo_service.calcular_saldo_consolidado(conn)
saldo_cart_antes = None
saldo_mp_antes = None
for c in res_antes["contas"]:
    if c["conta_id"] == 2:
        saldo_cart_antes = float(c["saldo_atual"])
    elif c["conta_id"] == 1:
        saldo_mp_antes = float(c["saldo_atual"])
print(f"   - Saldo Carteira antes: R$ {saldo_cart_antes:,.2f}")
print(f"   - Saldo Mercado Pago antes: R$ {saldo_mp_antes:,.2f}")
print(f"   - Saldo Livre disponível antes: R$ {float(res_antes['saldo_consolidado']):,.2f}")

# 3. Estorno da Transação #41 (Dinheiro/Pix duplicado)
print("\n3. Estornando Transação #41 (R$ 55,05 indevido em Carteira)...")
ok_estorno, msg_estorno = saldo_service.estornar_recebimento_turno(conn, transacao_id=41, turno_id=3)
if not ok_estorno:
    print(f"❌ ERRO ao estornar transação #41: {msg_estorno}")
    conn.close()
    sys.exit(1)
print(f"   ✅ {msg_estorno}")

# 4. Verificação de Integridade pós-correção
print("\n4. Verificação do Turno #3 pós-correção:")
info_depois = saldo_service.obter_recebimentos_turno(conn, 3)
print(f"   - Faturamento bruto: R$ {info_depois['ganho_bruto']:,.2f}")
print(f"   - Total contabilizado: R$ {info_depois['total_contabilizado']:,.2f}")
print(f"   - Restante elegível: R$ {info_depois['restante_elegivel']:,.2f}")
print(f"   - Excedente: R$ {info_depois['excedente']:,.2f}")
print(f"   - Status: {info_depois['status']}")
print(f"   - Transações vinculadas restantes: {[t['id'] for t in info_depois['transacoes']]}")

assert len(info_depois['transacoes']) == 1, "Deveria haver exatamente 1 transação vinculada!"
assert info_depois['transacoes'][0]['id'] == 42, "A transação vinculada deve ser a #42!"
assert info_depois['total_contabilizado'] == 55.05, "O total contabilizado deve ser R$ 55,05!"
assert info_depois['status'] == "integral", "O status deve ser 'integral'!"
print("   ✅ Validação do Turno #3: 100% íntegro e perfeitamente equilibrado!")

# 5. Recálculo dos Saldos Consolidados
print("\n5. Recálculo Oficial dos Saldos Consolidados:")
res_depois = saldo_service.calcular_saldo_consolidado(conn)
saldo_cart_depois = None
saldo_mp_depois = None

for c in res_depois["contas"]:
    if c["conta_id"] == 2:
        saldo_cart_depois = float(c["saldo_atual"])
    elif c["conta_id"] == 1:
        saldo_mp_depois = float(c["saldo_atual"])

saldo_livre_depois = float(res_depois["saldo_consolidado"])
saldo_reservas_depois = float(res_depois["saldo_reservas"])
saldo_total_depois = float(res_depois["saldo_total_com_reservas"])

print(f"   - 💵 Saldo Atual da Carteira: R$ {saldo_cart_depois:,.2f}")
print(f"   - 💳 Saldo Atual do Mercado Pago: R$ {saldo_mp_depois:,.2f}")
print(f"   - 🌐 Saldo Total Disponível (Livre): R$ {saldo_livre_depois:,.2f}")
print(f"   - 🐖 Saldo em Reservas / Cofrinhos: R$ {saldo_reservas_depois:,.2f}")
print(f"   - 🏛️ Saldo Total Consolidado: R$ {saldo_total_depois:,.2f}")

conn.close()
print("\n" + "=" * 60)
print("CORREÇÃO CONCLUÍDA COM SUCESSO NO BANCO REAL!")
print("=" * 60)
