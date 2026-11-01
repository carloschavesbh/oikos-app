# Suite de testes abrangente para a Etapa 1 da Remodelacao Oikos Pessoal
import sys
import os
import hashlib
sys.path.insert(0, os.path.abspath("."))

from starlette.testclient import TestClient
from web_app import app, DB_PATH

client = TestClient(app)

print(f"Banco ativo no web_app: {DB_PATH}")
assert "financas_remodelacao.db" in str(DB_PATH), f"ERRO: Banco nao e o de remodelacao! {DB_PATH}"

# 1. Teste de todas as rotas do sistema
rotas = [
    ('/', 'Visão Geral'),
    ('/planejamento', 'Planejamento'),
    ('/lancamentos', 'Lançamentos'),
    ('/contas', 'Contas'),
    ('/cartoes', 'Cartões'),
    ('/pagaleve', 'Paga Leve'),
    ('/motorista', 'Oikos Drive'),
    ('/drive', 'Oikos Drive'),
    ('/missoes', 'Missões')
]

for url, nome in rotas:
    r = client.get(url, follow_redirects=True)
    assert r.status_code == 200, f"Falha na rota {url} ({nome}): status {r.status_code}"
    # Verificar presença dos componentes estruturais da navegação
    assert 'id="app-sidebar"' in r.text, f"Sidebar ausente na rota {url}"
    assert 'id="mobile-drawer"' in r.text, f"Mobile drawer ausente na rota {url}"
    assert 'toggleSidebar()' in r.text, f"Funcao toggleSidebar ausente na rota {url}"
    print(f"  [OK] Rota {url:<15} ({nome}): 200 OK - Sidebar e Drawer presentes")

# 2. Teste da API de Meta de Horas (/api/meta-horas)
r_horas = client.post('/api/meta-horas', json={'horas': 6.0})
assert r_horas.status_code == 200, f"Falha ao salvar meta horas: {r_horas.status_code}"
data_horas = r_horas.json()
assert data_horas.get('sucesso') is True, f"Resposta sem sucesso: {data_horas}"
assert data_horas.get('meta_bruta_hoje') == 210.0, f"Meta não calculada a R$ 35/h: {data_horas}"
print("  [OK] Rota /api/meta-horas: 200 OK - 6.0h x R$ 35 = R$ 210,00 gravada com sucesso")

# 3. Teste do resumo de Foco de Hoje na Visão Geral
r_index = client.get('/')
assert 'Foco de Hoje' in r_index.text
assert 'Meta Alvo' in r_index.text
assert 'Faturado' in r_index.text
assert 'Restante' in r_index.text
assert 'Abrir Oikos Drive' in r_index.text
print("  [OK] Resumo compacto de Foco de Hoje na Visão Geral validado com sucesso")

# 4. Teste de integridade de financas_casa.db (banco de produção original não deve ter sido tocado)
with open("financas_casa.db", "rb") as f:
    hash_prod = hashlib.sha256(f.read()).hexdigest()
assert hash_prod == "a68d68388ad5fe14345370b7d62d6c2221fc40c18af9eef7dae76e3a7ddebf2f", f"ALERTA CRÍTICO: financas_casa.db foi alterado! Hash: {hash_prod}"
print(f"  [OK] financas_casa.db 100% preservado (SHA256: {hash_prod[:12]}...)")

print("\nTODOS OS TESTES AUTOMATIZADOS PASSARAM COM SUCESSO!")
