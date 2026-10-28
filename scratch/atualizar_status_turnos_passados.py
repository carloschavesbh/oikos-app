import sys
import os
import shutil
import sqlite3
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
BACKUP_FILE = f"financas_casa_backup_turnos_incorporados_{TIMESTAMP}.db"

print("=" * 65)
print("EXECUÇÃO AUTÔNOMA: INCORPORAÇÃO DE TURNOS PASSADOS AO MARCO")
print("=" * 65)

# 1. Backup de Segurança
shutil.copy2(DB_FILE, BACKUP_FILE)
print(f"1. Backup de segurança criado: {BACKUP_FILE}")

# 2. Conexão ao banco principal
conn = sqlite3.connect(DB_FILE)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 3. Atualização de status dos turnos anteriores ao marco de 21/10/2026
print("\n2. Atualizando turnos passados para status_conciliacao = 'incorporado_marco'...")
cur.execute("""
    UPDATE turnos
    SET status_conciliacao = 'incorporado_marco'
    WHERE data < '2026-10-21'
""")
linhas_afetadas = cur.rowcount
conn.commit()
print(f"   ✅ {linhas_afetadas} turnos atualizados para 'incorporado_marco' com sucesso!")

# 4. Auditoria individual dos turnos
print("\n3. Auditoria detalhada dos turnos operacionais:")
cur.execute("SELECT id, data, ganho_bruto, status_conciliacao FROM turnos ORDER BY data ASC, id ASC")
turnos_rows = cur.fetchall()

for t in turnos_rows:
    t_id = t["id"]
    t_dt = t["data"]
    t_bruto = t["ganho_bruto"]
    info_rec = saldo_service.obter_recebimentos_turno(conn, t_id)
    print(f"   - Turno #{t_id} ({t_dt}) • Bruto: R$ {t_bruto:,.2f}")
    print(f"     Status Contábil: {info_rec['status']}")
    print(f"     Incorporado ao Marco: {info_rec.get('eh_incorporado_marco')}")
    print(f"     Restante Elegível: R$ {info_rec['restante_elegivel']:,.2f}")
    print(f"     Transações Vinculadas: {[tr['id'] for tr in info_rec['transacoes']]}")

# 5. Teste de bloqueio de segurança contra geração de entrada indevida
print("\n4. Testando tentativa de gerar nova movimentação para turno incorporado:")
ok_tentativa, msg_tentativa = saldo_service.registrar_recebimento_turno(
    conn,
    turno_id=2,
    config_recebimento={"modo": "conta_unica", "conta_id": 1, "valor": 17.60}
)
print(f"   - Bloqueio ativo: ok={ok_tentativa}")
print(f"   - Mensagem: {msg_tentativa}")
assert ok_tentativa is False, "A tentativa de gerar receita para turno incorporado DEVE ser bloqueada!"
print("   ✅ Bloqueio de duplicidade para turnos passados validado com 100% de sucesso!")

# 6. Verificação de integridade dos saldos bancários
print("\n5. Verificando saldos bancários consolidados:")
res_cons = saldo_service.calcular_saldo_consolidado(conn)
saldo_mp = None
saldo_cart = None
for c in res_cons["contas"]:
    if c["conta_id"] == 1:
        saldo_mp = c["saldo_atual"]
    elif c["conta_id"] == 2:
        saldo_cart = c["saldo_atual"]

saldo_livre = res_cons["saldo_consolidado"]

print(f"   - Mercado Pago: R$ {saldo_mp:,.2f}")
print(f"   - Dinheiro / Carteira: R$ {saldo_cart:,.2f}")
print(f"   - Saldo Livre Disponível: R$ {saldo_livre:,.2f}")

assert float(saldo_mp) == 40.00, f"Saldo do Mercado Pago deve ser R$ 40,00, obtido {saldo_mp}"
assert float(saldo_cart) == 7.00, f"Saldo da Carteira deve ser R$ 7,00, obtido {saldo_cart}"
assert float(saldo_livre) == 47.00, f"Saldo Livre deve ser R$ 47,00, obtido {saldo_livre}"

print("\n   🎯 TODOS OS SALDOS E REGRAS PERMANECEM PERFEITAMENTE CONCILIADOS E INTACTOS!")

conn.close()
print("\n" + "=" * 65)
print("INCORPORAÇÃO DE TURNOS FINALIZADA COM SUCESSO!")
print("=" * 65)
