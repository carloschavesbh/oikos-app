import sys
import os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import shutil
import sqlite3
import hashlib

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

# 1. Backups
db_prod = 'financas_casa.db'
db_bkp = 'financas_casa_backup_20261020_pre_integracao.db'
shutil.copy2(db_prod, db_bkp)

app_py = 'app.py'
app_bkp = 'app_backup_20261020_pre_integracao.py'
shutil.copy2(app_py, app_bkp)

plan_py = 'planejamento_service.py'
plan_bkp = 'planejamento_service_backup_20261020_pre_integracao.py'
shutil.copy2(plan_py, plan_bkp)

print('Backups criados com sucesso:')
print(f'  - {db_bkp} (Tamanho: {os.path.getsize(db_bkp)} bytes, SHA256: {sha256_file(db_bkp)[:12]}...)')
print(f'  - {app_bkp} (Tamanho: {os.path.getsize(app_bkp)} bytes)')
print(f'  - {plan_bkp} (Tamanho: {os.path.getsize(plan_bkp)} bytes)')

# 2. Baseline de Produção
conn = sqlite3.connect(db_prod)
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM transacoes')
cnt_trans = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM pagamentos_despesas')
cnt_pags = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM turnos')
cnt_turnos = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM contas_config')
cnt_contas = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM cartoes')
cnt_cartoes = cur.fetchone()[0]

import saldo_service
saldo_info = saldo_service.calcular_saldo_consolidado(conn)
saldo_total = saldo_info['saldo_consolidado']

conn.close()

print('\nBaseline de Produção Pré-Integração:')
print(f'  - Transações: {cnt_trans}')
print(f'  - Pagamentos de Despesas: {cnt_pags}')
print(f'  - Turnos Motorista: {cnt_turnos}')
print(f'  - Contas: {cnt_contas}')
print(f'  - Cartões: {cnt_cartoes}')
print(f'  - Saldo Consolidado: R$ {saldo_total}')
