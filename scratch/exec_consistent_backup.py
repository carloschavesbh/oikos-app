# -*- coding: utf-8 -*-
import sqlite3
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

src_path = "financas_casa.db"
dest_dir = r"C:\Users\carlo\Downloads\OIKOS_BACKUP_PRE_REMODELACAO_20261101\database"
os.makedirs(dest_dir, exist_ok=True)
dest_path = os.path.join(dest_dir, "financas_casa_backup_consistente_20261101.db")

print(f"Iniciando backup consistente de '{src_path}' para '{dest_path}'...")

# 1. Conexão e checkpoint WAL para descarregar eventuais transações pendentes
src = sqlite3.connect(src_path)
src.execute("PRAGMA wal_checkpoint(TRUNCATE)")

# 2. Executar SQLite Online Backup API
dst = sqlite3.connect(dest_path)
src.backup(dst)
dst.close()
src.close()

print("Backup consistente via SQLite Online Backup concluído.")

# 3. Verificação de integridade da cópia
check_conn = sqlite3.connect(dest_path)
check_cur = check_conn.cursor()
check_cur.execute("PRAGMA integrity_check")
res = check_cur.fetchone()[0]
print(f"PRAGMA integrity_check na cópia: {res}")

check_cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
table_count = check_cur.fetchone()[0]
print(f"Total de tabelas preservadas: {table_count}")

check_cur.execute("SELECT count(*) FROM transacoes")
tx_count = check_cur.fetchone()[0]
print(f"Total de transações preservadas: {tx_count}")

check_cur.execute("SELECT count(*) FROM contas")
contas_count = check_cur.fetchone()[0]
print(f"Total de contas preservadas: {contas_count}")

check_conn.close()

if res == "ok":
    print("VERIFICAÇÃO DE INTEGRIDADE: SUCESSO ABSOLUTO (ok)")
else:
    print(f"VERIFICAÇÃO DE INTEGRIDADE: FALHA ({res})")
    sys.exit(1)

