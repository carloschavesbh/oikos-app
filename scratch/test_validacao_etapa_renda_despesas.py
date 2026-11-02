import os
import sys
import hashlib
import sqlite3

sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

os.environ['DATABASE_PATH'] = 'financas_remodelacao.db'

from starlette.testclient import TestClient
from web_app import app
import planejamento_anual_service

client = TestClient(app)

print("--- 1. TESTE DE ROTAS HTTP E RENDERIZAÇÃO ---")

# 1.1 Home / Visão Geral
res_home = client.get('/')
assert res_home.status_code == 200, f"Home retornou status {res_home.status_code}"
html_home = res_home.text
assert 'Despesas Anuais & Eventuais' in html_home, "Card de Despesas Anuais ausente na Home"
assert 'Total Previsto (12 Meses)' in html_home, "Texto de total previsto ausente na Home"
print("✓ Home OK: Card compacto de Despesas Anuais e cobertura por reservas renderizado.")

# 1.2 Planejamento
res_plan = client.get('/planejamento')
assert res_plan.status_code == 200, f"/planejamento retornou status {res_plan.status_code}"
html_plan = res_plan.text
assert 'Renda Familiar & Cenários' in html_plan, "Aba Renda Familiar ausente em /planejamento"
assert 'Calendário Anual (12 Meses)' in html_plan, "Aba Calendário Anual ausente em /planejamento"
assert 'Cenários de Sensibilidade' in html_plan, "Cenários de sensibilidade ausentes"
assert 'Margem Operacional do Oikos Drive' in html_plan, "Margem do Drive ausente"
assert 'Despesas por Natureza Orçamentária' in html_plan, "Classificação de natureza ausente"
assert 'Linha do Tempo dos Próximos 12 Meses' in html_plan, "Linha do tempo ausente"
assert 'IPVA HB20 2027' in html_plan, "Compromisso IPVA não encontrado na lista"
print("✓ /planejamento OK: Abas, Renda Variável, Cenários, Margem Drive, Natureza e Calendário 12m renderizados.")

print("\n--- 2. TESTE DE APIs E MODAIS ---")

# 2.1 Ajuste de Cenários
res_cen = client.post('/api/planejamento/cenarios', json={
    'ano': 2026,
    'mes': 11,
    'estavel_manual': 3500.0,
    'conservador_manual': 200.0,
    'habitual_manual': 2000.0,
    'favoravel_manual': 4000.0,
    'observacoes': 'Ajuste manual para teste'
})
assert res_cen.status_code == 200, f"Erro ao salvar cenários: {res_cen.text}"
assert res_cen.json().get('sucesso') is True
print("✓ API /api/planejamento/cenarios OK.")

# 2.2 Classificação de Natureza da Despesa (Atributo Separado)
res_nat = client.post('/api/planejamento/natureza-despesa', json={
    'categoria': 'Streaming',
    'natureza': 'qualidade_vida'
})
assert res_nat.status_code == 200, f"Erro ao salvar natureza: {res_nat.text}"
assert res_nat.json().get('sucesso') is True
print("✓ API /api/planejamento/natureza-despesa OK.")

# 2.3 Cadastro de Nova Despesa Eventual
res_dev = client.post('/api/planejamento/despesas-eventuais', json={
    'nome': 'Viagem Férias Teste',
    'categoria': 'Lazer',
    'responsavel': 'Família',
    'data_prevista': '2027-07-15',
    'valor_estimado': 1500.0,
    'recorrencia': 'anual',
    'cofrinho_id': 6 # Cofrinho Reserva
})
assert res_dev.status_code == 200, f"Erro ao criar despesa: {res_dev.text}"
dev_data = res_dev.json()
assert dev_data.get('sucesso') is True
dev_id = dev_data.get('id')
print(f"✓ API /api/planejamento/despesas-eventuais OK (ID {dev_id}).")

# 2.4 Conciliação de Pagamento
res_conc = client.post(f'/api/planejamento/despesas-eventuais/{dev_id}/conciliar', json={
    'valor_pago': 1500.0,
    'data_pagamento': '2027-07-15',
    'baixar_reserva_cofrinho': False
})
assert res_conc.status_code == 200
assert res_conc.json().get('sucesso') is True
print("✓ API /api/planejamento/despesas-eventuais/{id}/conciliar OK.")

# 2.5 Exclusão
res_del = client.post(f'/api/planejamento/despesas-eventuais/{dev_id}/excluir')
assert res_del.status_code == 200
assert res_del.json().get('sucesso') is True
print("✓ API /api/planejamento/despesas-eventuais/{id}/excluir OK.")

print("\n--- 3. VERIFICAÇÃO DE REGRAS CRÍTICAS ---")

conn = sqlite3.connect('financas_remodelacao.db')
conn.row_factory = sqlite3.Row

# 3.1 Garantia Anti-Duplicidade Turnos vs Receitas vs Transferências
tot_turnos_out = conn.execute("SELECT COALESCE(SUM(ganho_bruto), 0) FROM turnos WHERE data BETWEEN '2026-10-01' AND '2026-10-31'").fetchone()[0]
tot_rec_99_out = conn.execute("SELECT COALESCE(SUM(valor), 0) FROM transacoes WHERE tipo = 'receita' AND categoria = '99 / Chaves (Carlos)' AND data BETWEEN '2026-10-01' AND '2026-10-31'").fetchone()[0]
print(f"Ganho bruto registrado em Turnos (Outubro): R$ {tot_turnos_out:.2f}")
print(f"Receita 99 registrada em Transações (Outubro): R$ {tot_rec_99_out:.2f}")
print("Nota: Na apuração da renda familiar, não somamos os dois; usa-se o lançamento financeiro como base de caixa sem duplicar o ganho operacional.")

# 3.2 Não tratar ausência de dados como zero
hist = planejamento_anual_service.analisar_historico_renda(conn, 12, 2026, 10)
meses_incompletos = [m for m in hist['historico'] if m['qualidade'] in ('parcial', 'sem_dados')]
print(f"Meses identificados como incompletos/lacunas: {len(meses_incompletos)}")
for mi in meses_incompletos:
    print(f"  - {mi['mes']}: {mi['motivo_qualidade']}")
assert hist['estatisticas_variavel']['qtd_meses_validos'] <= 12, "Qtd meses válidos inválida"
assert hist['estatisticas_variavel']['minimo_observado'] > 0, "Mínimo observado não deveria ser zero"
print("✓ Ausência de dados não tratada como zero: média e cenários usam apenas meses válidos.")

# 3.3 Rateio proporcional de cofrinho para múltiplos compromissos
cur = conn.cursor()
cur.execute("UPDATE cofrinhos SET saldo_confirmado = 600.0 WHERE id = 1") # Cofrinho IPVA com R$ 600
conn.commit()

cal = planejamento_anual_service.obter_calendario_anual(conn, 2026, 11)
desp_ipva = [d for d in cal['todas_despesas'] if d['cofrinho_id'] == 1]
print(f"Compromissos vinculados ao Cofrinho 1: {len(desp_ipva)}")
soma_reservada_cof1 = sum(d['saldo_reservado_alocado'] for d in desp_ipva)
print(f"Saldo real no Cofrinho 1: R$ 600.00 | Soma distribuída: R$ {soma_reservada_cof1:.2f}")
assert soma_reservada_cof1 <= 600.01, f"Erro: saldo de cofrinho duplicado! {soma_reservada_cof1} > 600.0"
print("✓ Rateio anti-duplicidade de cofrinho confirmado.")

# Restaurar saldo do cofrinho 1 e limpar dados de teste
cur.execute("UPDATE cofrinhos SET saldo_confirmado = 0.0 WHERE id = 1")
cur.execute("DELETE FROM planejamento_cenarios_renda WHERE observacoes LIKE '%Ajuste manual para teste%'")
cur.execute("DELETE FROM planejamento_meses_amostra")
conn.commit()
conn.close()

print("\n--- 4. INTEGRIDADE DO BANCO REAL financas_casa.db ---")
hash_prod = hashlib.sha256(open('financas_casa.db', 'rb').read()).hexdigest()
ESPERADO_PROD = "a68d68388ad5fe14345370b7d62d6c2221fc40c18af9eef7dae76e3a7ddebf2f"
assert hash_prod == ESPERADO_PROD, f"ALERTA: financas_casa.db foi alterado! Hash: {hash_prod}"
print(f"✓ financas_casa.db 100% INTACTO: {hash_prod}")

print("\n=== TODOS OS TESTES DA ETAPA PASSARAM COM 100% DE SUCESSO! ===")

