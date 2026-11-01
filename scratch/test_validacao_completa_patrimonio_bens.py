import os
import sys
import hashlib
import sqlite3

sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

os.environ['DATABASE_PATH'] = 'financas_remodelacao.db'

from starlette.testclient import TestClient
from web_app import app
import patrimonio_service

client = TestClient(app)

print("--- 1. TESTE DE ROTAS E STATUS HTTP ---")

# Testar /
res_home = client.get('/')
assert res_home.status_code == 200, f"Home retornou {res_home.status_code}"
html_home = res_home.text
assert '/patrimonio' in html_home, "Link /patrimonio não encontrado na Home"
assert '/bens' in html_home, "Link /bens não encontrado na Home"
assert 'Meu Patrimônio' in html_home, "'Meu Patrimônio' não encontrado na Home"
assert 'Meus Bens' in html_home, "'Meus Bens' não encontrado na Home"
print("✓ Home OK: links /patrimonio e /bens presentes na navegação e card de resumo.")

# Testar /patrimonio
res_patr = client.get('/patrimonio')
assert res_patr.status_code == 200, f"/patrimonio retornou {res_patr.status_code}"
html_patr = res_patr.text
assert 'Meu Patrimônio' in html_patr, "'Meu Patrimônio' não encontrado em /patrimonio"
assert 'Patrimônio Líquido' in html_patr, "'Patrimônio Líquido' não encontrado em /patrimonio"
assert 'Como este cálculo é composto' in html_patr, "Explicação de composição ausente em /patrimonio"
assert 'saldo devedor' in html_patr.lower(), "Explicação de saldo devedor ausente"
print("✓ /patrimonio OK: tela analítica de balanço, metodologia e anti-duplicidade.")

# Testar /bens
res_bens = client.get('/bens')
assert res_bens.status_code == 200, f"/bens retornou {res_bens.status_code}"
html_bens = res_bens.text
assert 'Meus Bens' in html_bens, "'Meus Bens' não encontrado em /bens"
assert 'Novo Bem' in html_bens or 'Cadastrar' in html_bens, "Modal/botão de cadastro não encontrado em /bens"
assert 'Oikos Drive' in html_bens, "Vínculo com Drive ausente em /bens"
print("✓ /bens OK: tela cadastral e operacional de bens com vínculo Drive.")

print("\n--- 2. TESTE DE AUDITORIA MATEMÁTICA E ANTI-DUPLICIDADE ---")
conn = sqlite3.connect('financas_remodelacao.db')
conn.row_factory = sqlite3.Row
resumo = patrimonio_service.obter_resumo_patrimonial(conn)
conn.close()

print(f"Total Bens: R$ {resumo['total_bens']:,.2f}")
print(f"Saldo Caixa: R$ {resumo['saldo_caixa']:,.2f}")
print(f"Total Ativos: R$ {resumo['total_ativos']:,.2f}")
print(f"Total Passivos: R$ {resumo['total_passivos']:,.2f}")
print(f"  - Cartões a vencer: R$ {resumo['total_cartao']:,.2f}")
print(f"  - Paga Leve a vencer: R$ {resumo['total_pagaleve']:,.2f}")
print(f"  - Outros Parcelamentos: R$ {resumo['total_outros_parc']:,.2f}")
print(f"  - Dívidas Formais: R$ {resumo['total_dividas_formais']:,.2f}")
print(f"Patrimônio Líquido: R$ {resumo['patrimonio_liquido']:,.2f}")

esperado_liq = round(resumo['total_ativos'] - resumo['total_passivos'], 2)
assert round(resumo['patrimonio_liquido'], 2) == esperado_liq, f"Divergência matemática: {resumo['patrimonio_liquido']} != {esperado_liq}"
soma_passivos = round(
    resumo['total_cartao'] +
    resumo['total_pagaleve'] +
    resumo['total_outros_parc'] +
    resumo['total_dividas_formais'], 2
)
assert round(resumo['total_passivos'], 2) == soma_passivos, f"Passivos não batem: {resumo['total_passivos']} != {soma_passivos}"
print("✓ Matemática patrimonial íntegra e sem divergências.")

print("\n--- 3. TESTE DE CRUD E FLUXO DE REAVALIAÇÃO DE BENS ---")
# Criar um bem de teste via API JSON
res_create = client.post('/api/patrimonio/bens', json={
    'nome': 'Bicicleta Caloi Aro 29',
    'tipo': 'Outros',
    'proprietario': 'Familiar',
    'valor_atual': '1200.00',
    'data_aquisicao': '2026-05-10',
    'valor_aquisicao': '1500.00',
    'observacoes': 'Teste unitário automatizado'
})
assert res_create.status_code == 200, f"Erro ao criar bem: {res_create.text}"
data_created = res_create.json()
assert data_created.get('sucesso') is True, "Sucesso não foi retornado true"
bem_id = data_created.get('id')
print(f"✓ Bem criado com sucesso via API: ID {bem_id}")

conn = sqlite3.connect('financas_remodelacao.db')
conn.row_factory = sqlite3.Row
bem_caloi = patrimonio_service.obter_bem(conn, bem_id)
assert bem_caloi is not None, "Bem não encontrado no banco!"
print(f"✓ Bem consultado no banco: {bem_caloi['nome']} - R$ {bem_caloi['valor_atual_estimado']:,.2f}")

# Reavaliar bem via API JSON
res_av = client.post(f'/api/patrimonio/bens/{bem_id}/avaliacoes', json={
    'valor_estimado': '1100.00',
    'observacoes': 'Depreciação de uso'
})
assert res_av.status_code == 200, f"Erro ao reavaliar bem: {res_av.text}"
assert res_av.json().get('sucesso') is True

historico = patrimonio_service.listar_historico_avaliacoes(conn, bem_id)
assert len(historico) >= 2, f"Histórico deve ter ao menos 2 avaliações, tem {len(historico)}"
print(f"✓ Reavaliação registrada no histórico: {len(historico)} registros.")

# Arquivar bem via API JSON
res_arq = client.post(f'/api/patrimonio/bens/{bem_id}/status', json={'status': 'arquivado'})
assert res_arq.status_code == 200
assert res_arq.json().get('sucesso') is True
bens_ativos = patrimonio_service.listar_bens(conn, incluir_arquivados=False)
assert not any(b['id'] == bem_id for b in bens_ativos), "Bem arquivado não deveria constar na lista de ativos!"
print("✓ Arquivamento funcionando corretamente.")

# Desarquivar bem via API JSON
res_desarq = client.post(f'/api/patrimonio/bens/{bem_id}/status', json={'status': 'ativo'})
assert res_desarq.status_code == 200
assert res_desarq.json().get('sucesso') is True
bens_ativos_pos = patrimonio_service.listar_bens(conn, incluir_arquivados=False)
assert any(b['id'] == bem_id for b in bens_ativos_pos), "Bem desarquivado deveria constar na lista de ativos!"
print("✓ Desarquivamento funcionando corretamente.")

# Remover o bem de teste criado para manter o banco limpo
cur = conn.cursor()
cur.execute("DELETE FROM bens_avaliacoes WHERE bem_id = ?", (bem_id,))
cur.execute("DELETE FROM bens WHERE id = ?", (bem_id,))
conn.commit()
conn.close()
print("✓ Limpeza do registro de teste concluída.")

print("\n--- 4. VERIFICAÇÃO DE INTEGRIDADE DO BANCO REAL financas_casa.db ---")
hash_prod = hashlib.sha256(open('financas_casa.db', 'rb').read()).hexdigest()
ESPERADO_PROD = "a68d68388ad5fe14345370b7d62d6c2221fc40c18af9eef7dae76e3a7ddebf2f"
assert hash_prod == ESPERADO_PROD, f"ALERTA: Banco de produção foi modificado! Hash: {hash_prod}"
print(f"✓ financas_casa.db PERFEITAMENTE INTACTO: {hash_prod}")

print("\n=== TODOS OS TESTES PASSARAM COM SUCESSO! ===")
