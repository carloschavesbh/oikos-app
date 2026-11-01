# -*- coding: utf-8 -*-
import os
import sys
import hashlib
import sqlite3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
import web_app
import app

PROD_DB = os.path.join(BASE_DIR, "financas_casa.db")
REMOD_DB = os.path.join(BASE_DIR, "financas_remodelacao.db")

def get_hash(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while c := f.read(65536):
            h.update(c)
    return h.hexdigest()

hash_prod_inicial = get_hash(PROD_DB)

print("--- VERIFICAÇÃO DE CONFIGURAÇÃO DE BANCOS ---")
print(f"web_app.DB_PATH configurado: {web_app.DB_PATH}")
print(f"app.DB_NAME configurado:     {app.DB_NAME}")

assert "financas_remodelacao.db" in web_app.DB_PATH, "ERRO: web_app.py não está apontando para financas_remodelacao.db"
assert "financas_remodelacao.db" in app.DB_NAME, "ERRO: app.py não está apontando para financas_remodelacao.db"

# Testar conexão real de web_app.conectar_db()
conn = web_app.conectar_db()
cur = conn.cursor()
cur.execute("SELECT count(*) FROM transacoes")
tx_remod = cur.fetchone()[0]
conn.close()

print(f"Transações lidas via web_app.conectar_db(): {tx_remod}")
assert tx_remod == 1098, "ERRO: quantidade inesperada de transações em financas_remodelacao.db"

# Verificação de intangibilidade de financas_casa.db
hash_prod_final = get_hash(PROD_DB)
print(f"SHA256 financas_casa.db inicial: {hash_prod_inicial}")
print(f"SHA256 financas_casa.db final:   {hash_prod_final}")
assert hash_prod_inicial == hash_prod_final, "ERRO CRÍTICO: financas_casa.db foi alterado!"

print("ISOLAMENTO CONFIRMADO COM SUCESSO!")

