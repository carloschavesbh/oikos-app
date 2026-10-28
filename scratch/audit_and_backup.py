import sqlite3
import shutil
import os
from datetime import datetime

# 1. Backup do banco
backup_name = f'financas_casa_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
shutil.copyfile('financas_casa.db', backup_name)
print(f'Backup criado com sucesso: {backup_name}')

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

# 2. Tabelas existentes
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('Tabelas:', tables)

# 3. Colunas de turnos
cur.execute('PRAGMA table_info(turnos)')
cols_t = cur.fetchall()
print('Colunas turnos:', [c[1] for c in cols_t])

# 4. Turnos existentes
cur.execute('SELECT * FROM turnos')
rows_t = cur.fetchall()
print(f'Total de turnos existentes: {len(rows_t)}')
for r in rows_t:
    print('Turno:', r)

# 5. Contas configuradas
cur.execute('SELECT id, nome, tipo, conta_pai_id, incluir_saldo_consolidado FROM contas_config')
rows_cc = cur.fetchall()
print('Contas:')
for r in rows_cc:
    print(' ', r)

# 6. Transacoes de combustível e 99
cur.execute('PRAGMA table_info(transacoes)')
cols_tr = cur.fetchall()
print('Colunas transacoes:', [c[1] for c in cols_tr])

cur.execute("SELECT id, data, tipo, descricao, valor, conta_id, categoria FROM transacoes WHERE categoria LIKE '%Combust%' OR descricao LIKE '%99%' OR descricao LIKE '%Combust%' OR descricao LIKE '%Etanol%' ORDER BY data DESC LIMIT 10")
for r in cur.fetchall():
    print('Transacao Combustivel/99:', r)

