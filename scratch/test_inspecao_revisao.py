import os
import sys

sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

os.environ['DATABASE_PATH'] = 'financas_remodelacao.db'

from starlette.testclient import TestClient
from web_app import app
import sqlite3

client = TestClient(app)

print("--- 1. VERIFICAÇÃO DE REGISTROS DE TESTE NO BANCO ---")
conn = sqlite3.connect('financas_remodelacao.db')
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM planejamento_despesas_eventuais")
qtd_dev = cur.fetchone()[0]
print(f"Total em planejamento_despesas_eventuais: {qtd_dev} (Esperado: 0 após limpeza de seeds)")
assert qtd_dev == 0, f"Ainda existem registros de seed! Qtd: {qtd_dev}"

cur.execute("SELECT COUNT(*) FROM planejamento_cenarios_renda WHERE observacoes LIKE '%Ajuste manual para teste%'")
qtd_cen_teste = cur.fetchone()[0]
print(f"Total de cenários de teste: {qtd_cen_teste} (Esperado: 0)")
assert qtd_cen_teste == 0, "Ainda existe cenário de teste!"

print("\n--- 2. RENDERIZAÇÃO DA PÁGINA /planejamento ---")
res_plan = client.get('/planejamento')
assert res_plan.status_code == 200
html_plan = res_plan.text

# Verificar correções de texto e conceitos
assert 'Sua referência média informada: R$ 35,00/h' in html_plan, "Correção de referência informada ausente"
assert 'oficial da 99' not in html_plan.lower(), "Menção a 'oficial da 99' ainda presente!"
assert 'Após Custos Registrados' in html_plan, "Termo 'Após Custos Registrados' ausente"
assert 'Abastecimentos Pagos no Posto (Caixa Real)' in html_plan, "Decomposição de abastecimentos ausente"
assert 'Consumo Estimado nos Turnos' in html_plan, "Consumo estimado nos turnos ausente"
assert 'chk-amostra-mes' in html_plan, "Controle de seleção de amostra de meses ausente"
assert 'Entradas Externas / Aportes' in html_plan, "Coluna de aportes ausente na tabela"
print("✓ /planejamento renderizado com todas as correções textuais e conceituais!")

print("\n--- 3. TESTE DA API DE SELEÇÃO DE MESES NA AMOSTRA ---")
res_meses = client.post('/api/planejamento/meses-amostra', json={
    'meses_ativos': ['2026-01', '2026-02', '2026-03', '2026-07', '2026-10']
})
assert res_meses.status_code == 200
assert res_meses.json().get('sucesso') is True
print("✓ API /api/planejamento/meses-amostra funcionando perfeitamente.")

# Recarregar página para ver cenários com a amostra revisada
res_plan_pos = client.get('/planejamento')
assert res_plan_pos.status_code == 200
print("✓ Página /planejamento recalcula normalmente com seleção personalizada de meses.")

# Limpar tabela de seleção para teste não poluir o banco
cur.execute("DELETE FROM planejamento_meses_amostra")
conn.commit()
conn.close()

print("\n--- 4. INTEGRIDADE DE PRODUÇÃO (financas_casa.db) ---")
import hashlib
hash_prod = hashlib.sha256(open('financas_casa.db', 'rb').read()).hexdigest()
ESPERADO_PROD = "a68d68388ad5fe14345370b7d62d6c2221fc40c18af9eef7dae76e3a7ddebf2f"
assert hash_prod == ESPERADO_PROD, f"ALERTA: financas_casa.db foi modificado! Hash: {hash_prod}"
print(f"✓ financas_casa.db 100% INTACTO: {hash_prod}")

print("\n=== TODAS AS VALIDAÇÕES PASSARAM COM SUCESSO! ===")
