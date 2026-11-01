# Script para criar backup seguro do banco de remodelacao antes da migracao de Patrimonio e Bens
import sqlite3
import hashlib
import shutil
import os

origem = "financas_remodelacao.db"
destino = "financas_remodelacao_backup_pre_patrimonio.db"

assert os.path.exists(origem), f"Arquivo de origem nao encontrado: {origem}"

# Backup consistente com sqlite3 API
con_orig = sqlite3.connect(origem)
con_dest = sqlite3.connect(destino)
with con_dest:
    con_orig.backup(con_dest)
con_dest.close()
con_orig.close()

with open(destino, "rb") as f:
    h = hashlib.sha256(f.read()).hexdigest()

print(f"Backup consistente criado em: {destino}")
print(f"Tamanho: {os.path.getsize(destino)} bytes")
print(f"SHA-256: {h}")

