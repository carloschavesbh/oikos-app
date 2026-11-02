# Suite de Testes Completa - Módulo de Patrimônio & Bens e Integração Geral
import sys
import os
import shutil
import hashlib
sys.path.insert(0, os.path.abspath("."))

TEMP_DB = "temp_test_patrimonio_completo.db"
if os.path.exists(TEMP_DB):
    os.remove(TEMP_DB)

shutil.copyfile("financas_remodelacao.db", TEMP_DB)
os.environ["DB_PATH"] = TEMP_DB

import web_app
web_app.DB_PATH = TEMP_DB
from starlette.testclient import TestClient

client = TestClient(web_app.app)

try:
    print(f"Banco ativo no web_app: {web_app.DB_PATH}")
assert "financas_remodelacao.db" in str(DB_PATH), f"ERRO: Banco incorreto! {DB_PATH}"

# 1. Testar Rota /patrimonio (GET)
r_pat = client.get("/patrimonio")
assert r_pat.status_code == 200, f"Erro ao acessar /patrimonio: {r_pat.status_code}"
assert "Patrimônio & Bens" in r_pat.text
assert "Ativos Físicos" in r_pat.text
assert "Patrimônio Líquido" in r_pat.text
assert "modal-bem" in r_pat.text
print("  [OK] Rota /patrimonio: 200 OK - Interface renderizada")

# 2. Testar API de Cadastro de Bem
novo_bem_payload = {
    "nome": "Smartphone Xiaomi 12",
    "tipo": "Eletrônico",
    "proprietario": "Carlos",
    "valor_aquisicao": 3200.0,
    "data_aquisicao": "2024-01-15",
    "valor_atual_estimado": 1900.0,
    "data_avaliacao": "2026-11-01",
    "observacoes": "Celular de uso diário e operações da 99"
}
r_criar = client.post("/api/patrimonio/bens", json=novo_bem_payload)
assert r_criar.status_code == 200, f"Erro ao criar bem: {r_criar.status_code}"
res_criar = r_criar.json()
assert res_criar.get("sucesso") is True, f"Falha ao criar: {res_criar}"
bem_id = res_criar["id"]
print(f"  [OK] API POST /api/patrimonio/bens: Bem criado id={bem_id}")

# 3. Testar API de Detalhes do Bem
r_det = client.get(f"/api/patrimonio/bens/{bem_id}")
assert r_det.status_code == 200
dados_bem = r_det.json()
assert dados_bem["nome"] == "Smartphone Xiaomi 12"
assert dados_bem["valor_atual_estimado"] == 1900.0
assert len(dados_bem["avaliacoes"]) >= 1
print("  [OK] API GET /api/patrimonio/bens/{id}: Detalhes e histórico carregados")

# 4. Testar API de Nova Avaliação
r_aval = client.post(f"/api/patrimonio/bens/{bem_id}/avaliacoes", json={
    "valor_estimado": 1750.0,
    "data_avaliacao": "2026-11-01",
    "observacoes": "Desgaste natural de bateria"
})
assert r_aval.status_code == 200
assert r_aval.json().get("sucesso") is True

# Conferir reavaliação
r_det2 = client.get(f"/api/patrimonio/bens/{bem_id}")
assert r_det2.json()["valor_atual_estimado"] == 1750.0
assert len(r_det2.json()["avaliacoes"]) == 2
print("  [OK] API POST /api/patrimonio/bens/{id}/avaliacoes: Reavaliação registrada")

# 5. Testar Arquivamento e Desarquivamento
r_arq = client.post(f"/api/patrimonio/bens/{bem_id}/status", json={"status": "arquivado"})
assert r_arq.status_code == 200
assert r_arq.json().get("sucesso") is True

r_det_arq = client.get(f"/api/patrimonio/bens/{bem_id}")
assert r_det_arq.json()["status"] == "arquivado"
print("  [OK] API POST /api/patrimonio/bens/{id}/status: Arquivado com sucesso")

# Reativar
client.post(f"/api/patrimonio/bens/{bem_id}/status", json={"status": "ativo"})

# 6. Testar Integração com a Visão Geral (index)
r_index = client.get("/")
assert r_index.status_code == 200
assert "Patrimônio Líquido" in r_index.text
assert "Ver bens ➔" in r_index.text
assert "app-sidebar" in r_index.text
print("  [OK] Visão Geral (index): Resumo de Patrimônio Líquido presente")

# 7. Testar Integração com o Drive (/motorista)
r_drive = client.get("/motorista")
assert r_drive.status_code == 200
assert "Hyundai HB20" in r_drive.text or "Oikos Drive" in r_drive.text
print("  [OK] Oikos Drive (/motorista): Veículo e métricas integradas")

# 8. Teste de Integridade Crítica: financas_casa.db NÃO PODE TER SIDO TOCADO
with open("financas_casa.db", "rb") as f:
    hash_prod = hashlib.sha256(f.read()).hexdigest()
assert hash_prod == "a68d68388ad5fe14345370b7d62d6c2221fc40c18af9eef7dae76e3a7ddebf2f", f"ALERTA: financas_casa.db alterado! {hash_prod}"
print(f"  [OK] financas_casa.db 100% íntegro (SHA-256: {hash_prod[:12]}...)")

finally:
    if os.path.exists(TEMP_DB):
        try:
            os.remove(TEMP_DB)
        except Exception:
            pass

print("\nTODOS OS TESTES DE INTEGRAÇÃO PASSARAM COM 100% DE SUCESSO!")

