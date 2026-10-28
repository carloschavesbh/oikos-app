import sqlite3
import shutil
import os

db_path = 'financas_casa.db'
backup_path = 'financas_casa_backup_urgente_motorista.db'

# 1. Consistent backup using sqlite backup API
source = sqlite3.connect(db_path)
dest = sqlite3.connect(backup_path)
source.backup(dest)
dest.close()
source.close()

print(f"Backup created successfully at: {backup_path}")
print(f"Source size: {os.path.getsize(db_path)} bytes, Backup size: {os.path.getsize(backup_path)} bytes")

# 2. Check integrity of backup
conn_b = sqlite3.connect(backup_path)
cur_b = conn_b.cursor()
cur_b.execute("PRAGMA integrity_check")
print("Integrity check on backup:", cur_b.fetchall())
conn_b.close()
