# -*- coding: utf-8 -*-
import os
import sys
import sqlite3
import hashlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD_DB = os.path.join(BASE_DIR, "financas_casa.db")
BACKUP_DB = r"C:\Users\carlo\Downloads\OIKOS_BACKUP_PRE_REMODELACAO_20261101\database\financas_casa_backup_consistente_20261101.db"

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

prod_hash_before = sha256(PROD_DB)

print("--- 1. VERIFICAÇÃO DO BANCO DE DADOS DE BACKUP ---")
assert os.path.exists(BACKUP_DB), "Arquivo de backup não encontrado!"
conn = sqlite3.connect(BACKUP_DB)
cur = conn.cursor()
cur.execute("PRAGMA integrity_check")
status = cur.fetchone()[0]
print(f"PRAGMA integrity_check no backup: {status}")
assert status == "ok", f"Falha de integridade: {status}"

cur.execute("SELECT count(*) FROM transacoes")
print(f"Transações no backup: {cur.fetchone()[0]}")
cur.execute("SELECT count(*) FROM contas")
print(f"Contas no backup: {cur.fetchone()[0]}")
cur.execute("SELECT count(*) FROM cartoes")
print(f"Cartões no backup: {cur.fetchone()[0]}")
conn.close()

print("\n--- 2. VERIFICAÇÃO DE INICIALIZAÇÃO DO CÓDIGO PRESERVADO ---")
sys.path.insert(0, BASE_DIR)
import web_app
from starlette.testclient import TestClient

# Apontar servidor estritamente para uma cópia temporária de teste
test_temp_db = os.path.join(BASE_DIR, "scratch", "temp_iso_check.db")
import shutil
shutil.copy2(BACKUP_DB, test_temp_db)
web_app.DB_PATH = test_temp_db

client = TestClient(web_app.app)
resp_home = client.get("/")
print(f"GET / (Visão Geral): HTTP {resp_home.status_code}")
resp_drive = client.get("/motorista")
print(f"GET /motorista (Oikos Drive): HTTP {resp_drive.status_code}")
resp_lancamentos = client.get("/lancamentos")
print(f"GET /lancamentos: HTTP {resp_lancamentos.status_code}")

assert resp_home.status_code == 200, "Erro ao carregar Home"
assert resp_drive.status_code == 200, "Erro ao carregar Drive"
assert resp_lancamentos.status_code == 200, "Erro ao carregar Lançamentos"

if os.path.exists(test_temp_db):
    os.remove(test_temp_db)

print("\n--- 3. VERIFICAÇÃO DE INTANGIBILIDADE DO BANCO REAL ---")
prod_hash_after = sha256(PROD_DB)
print(f"SHA256 financas_casa.db antes:  {prod_hash_before}")
print(f"SHA256 financas_casa.db depois: {prod_hash_after}")
assert prod_hash_before == prod_hash_after, "ALERTA: Banco real foi modificado!"
print("Banco real de produção: 100% INTACTO.")

print("\n>>> PONTO DE RETORNO VALIDADO COM SUCESSO ABSOLUTO! <<<")

