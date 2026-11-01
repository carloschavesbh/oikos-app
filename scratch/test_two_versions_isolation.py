# -*- coding: utf-8 -*-
import os
import sys
import hashlib
import sqlite3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_PESSOAL = r"C:\Users\carlo\Downloads\Gerenciador financeiro"
BASE_GERAL = r"C:\Users\carlo\Downloads\Oikos-Geral"

DB_ORIGINAL = os.path.join(BASE_PESSOAL, "financas_casa.db")
DB_PESSOAL = os.path.join(BASE_PESSOAL, "financas_remodelacao.db")
DB_GERAL = os.path.join(BASE_GERAL, "financas_geral.db")

def get_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

hash_original_antes = get_hash(DB_ORIGINAL)
hash_geral_antes = get_hash(DB_GERAL)
hash_pessoal_antes = get_hash(DB_PESSOAL)

print("--- 1. VERIFICAÇÃO DE CAMINHOS E EXISTÊNCIA DOS BANCOS ---")
print(f"Banco Original (Preservado): {DB_ORIGINAL} [Existe: {os.path.exists(DB_ORIGINAL)}]")
print(f"Banco Oikos Pessoal:         {DB_PESSOAL} [Existe: {os.path.exists(DB_PESSOAL)}]")
print(f"Banco Oikos Geral:           {DB_GERAL} [Existe: {os.path.exists(DB_GERAL)}]")

assert os.path.exists(DB_ORIGINAL), "Banco original não encontrado!"
assert os.path.exists(DB_PESSOAL), "Banco pessoal não encontrado!"
assert os.path.exists(DB_GERAL), "Banco geral não encontrado!"

print("\n--- 2. VERIFICAÇÃO DE CONFIGURAÇÃO DO BACKEND EM AMBAS AS PASTAS ---")
# Importar web_app do Oikos Pessoal
sys.path.insert(0, BASE_PESSOAL)
import web_app as web_app_pessoal
from starlette.testclient import TestClient

print(f"Oikos Pessoal DB_PATH: {web_app_pessoal.DB_PATH}")
assert web_app_pessoal.DB_PATH == DB_PESSOAL, f"DB_PATH inesperado no Pessoal: {web_app_pessoal.DB_PATH}"

client_pessoal = TestClient(web_app_pessoal.app)
resp_pessoal = client_pessoal.get("/")
print(f"Oikos Pessoal GET / -> HTTP {resp_pessoal.status_code}")
assert resp_pessoal.status_code == 200
assert "Pessoal" in resp_pessoal.text, "Badge 'Pessoal' não encontrado no HTML do Oikos Pessoal"

# Testar Oikos Geral em subprocesso/módulo isolado
import importlib.util
spec = importlib.util.spec_from_file_location("web_app_geral", os.path.join(BASE_GERAL, "web_app.py"))
web_app_geral = importlib.util.module_from_spec(spec)
# Configura contexto de diretório para templates de Oikos Geral
old_cwd = os.getcwd()
os.chdir(BASE_GERAL)
spec.loader.exec_module(web_app_geral)
os.chdir(old_cwd)

print(f"Oikos Geral DB_PATH: {web_app_geral.DB_PATH}")
assert web_app_geral.DB_PATH == DB_GERAL, f"DB_PATH inesperado no Geral: {web_app_geral.DB_PATH}"

client_geral = TestClient(web_app_geral.app)
resp_geral = client_geral.get("/")
print(f"Oikos Geral GET / -> HTTP {resp_geral.status_code}")
assert resp_geral.status_code == 200
assert "Uso Geral" in resp_geral.text, "Badge 'Uso Geral' não encontrado no HTML do Oikos Geral"

print("\n--- 3. TESTE DE ISOLAMENTO DE ESCRITA ENTRE OS BANCOS ---")
# Inserir um registro teste exclusivo no banco da remodelação pessoal
conn_pessoal = sqlite3.connect(DB_PESSOAL)
cur_p = conn_pessoal.cursor()
cur_p.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, pago)
    VALUES ('2026-11-01', 'TESTE_ISOLAMENTO_PESSOAL_EXCLUSIVO', 99.99, 'DESPESA', 'Outros', 'Carteira', 1)
""")
conn_pessoal.commit()
conn_pessoal.close()

# Verificar que o registro NÃO existe no banco geral nem no original
conn_geral = sqlite3.connect(DB_GERAL)
cur_g = conn_geral.cursor()
cur_g.execute("SELECT count(*) FROM transacoes WHERE descricao='TESTE_ISOLAMENTO_PESSOAL_EXCLUSIVO'")
qtd_no_geral = cur_g.fetchone()[0]
conn_geral.close()

conn_orig = sqlite3.connect(DB_ORIGINAL)
cur_o = conn_orig.cursor()
cur_o.execute("SELECT count(*) FROM transacoes WHERE descricao='TESTE_ISOLAMENTO_PESSOAL_EXCLUSIVO'")
qtd_no_orig = cur_o.fetchone()[0]
conn_orig.close()

print(f"Registro no banco Pessoal: 1")
print(f"Registro no banco Geral:   {qtd_no_geral} (Esperado: 0)")
print(f"Registro no banco Orig:    {qtd_no_orig} (Esperado: 0)")

assert qtd_no_geral == 0, "FALHA DE ISOLAMENTO: Registro vazou para o banco Geral!"
assert qtd_no_orig == 0, "FALHA DE ISOLAMENTO: Registro vazou para o banco Original!"

# Limpar o registro de teste do banco pessoal
conn_pessoal = sqlite3.connect(DB_PESSOAL)
conn_pessoal.execute("DELETE FROM transacoes WHERE descricao='TESTE_ISOLAMENTO_PESSOAL_EXCLUSIVO'")
conn_pessoal.commit()
conn_pessoal.close()

# Verificar que financas_casa.db permaneceu 100% íntegro
hash_original_depois = get_hash(DB_ORIGINAL)
print(f"\nSHA256 financas_casa.db antes:  {hash_original_antes}")
print(f"SHA256 financas_casa.db depois: {hash_original_depois}")
assert hash_original_antes == hash_original_depois, "ALERTA: financas_casa.db foi alterado!"

print("\n>>> SUCESSO: AMBOS OS AMBIENTES ESTÃO COMPLETAMENTE DESACOPLADOS E FUNCIONANDO! <<<")

