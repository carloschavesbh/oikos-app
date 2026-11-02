"""
=============================================================================
TESTES DE VALIDAÇÃO DOS DOIS AJUSTES FINAIS:
1. Histórico de renda: sugestão automática vs confirmação do usuário; não exclusão automática de renda baixa.
2. Contribuições para reservas: cálculo exato por datas reais, tratamento de dia 31, vencimento hoje,
   antes da 1ª contribuição e exatamente em data de contribuição.
3. Validação de teto: soma de reservas atribuídas não pode ultrapassar o saldo do cofrinho.
=============================================================================
"""

import sys
import os
import sqlite3
import datetime
import decimal

sys.path.insert(0, os.path.abspath("."))
import planejamento_anual_service
import saldo_service
from fastapi.testclient import TestClient
import web_app

client = TestClient(web_app.app)
conn = sqlite3.connect("financas_remodelacao.db")

print("--- INICIANDO TESTES DOS AJUSTES FINAIS ---")

# -----------------------------------------------------------------------------
# 1. TESTE DO HISTÓRICO DE RENDA: SUGESTÃO VS CONFIRMAÇÃO DO USUÁRIO
# -----------------------------------------------------------------------------
print("\n[TESTE 1] Histórico de Renda:")
hist = planejamento_anual_service.analisar_historico_renda(conn, 12, 2026, 10)
m_abr = next(m for m in hist["historico"] if m["mes"] == "2026-04")
m_jan = next(m for m in hist["historico"] if m["mes"] == "2026-01")

print(f"  Janeiro (R$ {m_jan['variavel']}): qualidade = '{m_jan['qualidade']}', label = '{m_jan['qualidade_label']}', eh_sugestao = {m_jan['eh_sugestao']}")
print(f"  Abril (R$ {m_abr['variavel']}): qualidade = '{m_abr['qualidade']}', label = '{m_abr['qualidade_label']}', eh_sugestao = {m_abr['eh_sugestao']}")

assert "Sugestão" in m_jan["qualidade_label"], "Janeiro deve ser apresentado como sugestão automática do sistema!"
assert "Sugestão" in m_abr["qualidade_label"], "Abril deve ser apresentado como sugestão automática do sistema!"
assert "greve" not in m_abr["motivo_qualidade"].lower(), "Não deve haver menção infundada a greve/paralisação!"
assert "greve" not in m_jan["motivo_qualidade"].lower()
assert m_abr["incluir_na_amostra"] is True, "Mês com renda baixa não deve ser excluído automaticamente dos cenários!"

# Testa confirmação pelo usuário via API
res_conf = client.post("/api/planejamento/meses-amostra", json={
    "meses_ativos": ["2026-01", "2026-02", "2026-03", "2026-04"],
    "meses_confirmados": ["2026-01"],
    "qualidade_map": {"2026-01": "confirmado_usuario"}
})
assert res_conf.status_code == 200 and res_conf.json()["sucesso"] is True

hist_pos_conf = planejamento_anual_service.analisar_historico_renda(conn, 12, 2026, 10)
m_jan_conf = next(m for m in hist_pos_conf["historico"] if m["mes"] == "2026-01")
assert m_jan_conf["confirmado_usuario"] is True, "Janeiro deve constar como confirmado pelo usuário!"
assert "Confirmado pelo Usuário" in m_jan_conf["qualidade_label"]
print("  ✓ Confirmação explícita de cobertura pelo usuário funcionando perfeitamente.")

# Limpa configuração de teste do histórico
planejamento_anual_service.salvar_selecao_meses_amostra(conn, [
    "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-07", "2026-08", "2026-09", "2026-10"
])

# -----------------------------------------------------------------------------
# 2. TESTE DE CÁLCULO DE DATAS E OPORTUNIDADES REAIS DE CONTRIBUIÇÃO
# -----------------------------------------------------------------------------
print("\n[TESTE 2] Cálculo de Datas Efetivas de Contribuição:")

hoje = datetime.date(2026, 11, 2)

# Caso A: Vencimento hoje
datas_hoje = planejamento_anual_service.calcular_datas_contribuicao_efetivas(hoje, hoje, "mensal")
assert len(datas_hoje) == 1 and datas_hoje[0] == hoje, "Vencimento hoje deve gerar exatamente 1 oportunidade (hoje)!"
print("  ✓ Caso A (Vencimento hoje): 1 oportunidade confirmada.")

# Caso B: Vencimento antes da primeira contribuição
dt_antes = hoje - datetime.timedelta(days=1)
datas_antes = planejamento_anual_service.calcular_datas_contribuicao_efetivas(hoje, dt_antes, "mensal")
assert len(datas_antes) == 0, "Vencimento antes da 1ª contribuição deve gerar 0 oportunidades futuras!"
print("  ✓ Caso B (Vencimento antes da 1ª contribuição): 0 oportunidades confirmadas.")

# Caso C: Vencimento exatamente numa data de contribuição mensal
# Ex: início 02/11/2026, vencimento 02/02/2027 -> 4 oportunidades (02/11, 02/12, 02/01, 02/02)
dt_exata = datetime.date(2027, 2, 2)
datas_exata = planejamento_anual_service.calcular_datas_contribuicao_efetivas(hoje, dt_exata, "mensal")
assert len(datas_exata) == 4, f"Esperado 4 oportunidades, obtido {len(datas_exata)}"
assert datas_exata[-1] == dt_exata, "Última contribuição deve cair exatamente na data de vencimento!"
print(f"  ✓ Caso C (Vencimento em data exata): {len(datas_exata)} oportunidades: {[d.strftime('%Y-%m-%d') for d in datas_exata]}")

# Caso D: Dia 31 em meses com menos dias
dt_31 = datetime.date(2026, 1, 31)
dt_fim = datetime.date(2026, 5, 31)
datas_31 = planejamento_anual_service.calcular_datas_contribuicao_efetivas(dt_31, dt_fim, "mensal")
dias_meses = [d.strftime("%Y-%m-%d") for d in datas_31]
assert dias_meses == ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30", "2026-05-31"], f"Datas incorretas: {dias_meses}"
print(f"  ✓ Caso D (Dia 31 em meses curtos): ajustado corretamente ({dias_meses})")

# -----------------------------------------------------------------------------
# 3. TESTE DE TETO DE RESERVAS: SOMA NÃO PODE ULTRAPASSAR SALDO DO COFRINHO
# -----------------------------------------------------------------------------
print("\n[TESTE 3] Validação de Teto do Cofrinho (Criação, Edição e Resgate):")

cur = conn.cursor()
# Vamos usar o Cofrinho IPVA (id 1, conta 1271)
cur.execute("SELECT id, saldo_confirmado FROM cofrinhos WHERE id = 1")
r_cof = cur.fetchone()
print(f"  Saldo inicial do Cofrinho IPVA: R$ {r_cof[1]}")

# Alimenta temporariamente o cofrinho com R$ 100,00 para os testes
ok_dep, msg_dep = saldo_service.transferir_para_cofrinho(conn, 1, 100.0, "2026-11-02", "Depósito teste")
assert ok_dep is True
s_disp = planejamento_anual_service.obter_saldo_disponivel_cofrinho(conn, 1)
assert s_disp == 100.0, f"Saldo esperado R$ 100.00, obtido R$ {s_disp}"
print(f"  Saldo disponível pós depósito: R$ {s_disp:.2f}")

# 3.1 Teste: cadastrar compromisso com reserva manual de R$ 70,00 (Válido, <= 100)
id_comp1 = planejamento_anual_service.criar_despesa_eventual(conn, {
    "nome": "Compromisso Teste A",
    "categoria": "Impostos Veículo",
    "responsavel": "Família",
    "data_prevista": "2027-02-02",
    "valor_estimado": 200.0,
    "cofrinho_id": 1,
    "valor_reservado_manual": 70.0,
    "frequencia_contribuicao": "mensal"
})
assert id_comp1 > 0
print("  ✓ Compromisso 1 criado com R$ 70,00 de reserva manual atribuída.")

# 3.2 Teste: cadastrar segundo compromisso com reserva manual de R$ 40,00 (70 + 40 = 110 > 100 -> DEVE FALHAR)
falhou_como_esperado = False
try:
    planejamento_anual_service.criar_despesa_eventual(conn, {
        "nome": "Compromisso Teste B",
        "categoria": "Impostos Veículo",
        "responsavel": "Família",
        "data_prevista": "2027-03-02",
        "valor_estimado": 150.0,
        "cofrinho_id": 1,
        "valor_reservado_manual": 40.0,
        "frequencia_contribuicao": "mensal"
    })
except ValueError as e:
    falhou_como_esperado = True
    print(f"  ✓ Bloqueio esperado na criação: {e}")
assert falhou_como_esperado is True, "Criação de reserva excedendo saldo do cofrinho deveria ter falhado!"

# 3.3 Teste: editar compromisso 1 para R$ 120,00 (> 100 -> DEVE FALHAR)
falhou_edicao = False
try:
    planejamento_anual_service.atualizar_despesa_eventual(conn, id_comp1, {
        "nome": "Compromisso Teste A",
        "categoria": "Impostos Veículo",
        "responsavel": "Família",
        "data_prevista": "2027-02-02",
        "valor_estimado": 200.0,
        "cofrinho_id": 1,
        "valor_reservado_manual": 120.0,
        "frequencia_contribuicao": "mensal"
    })
except ValueError as e:
    falhou_edicao = True
    print(f"  ✓ Bloqueio esperado na edição: {e}")
assert falhou_edicao is True, "Edição de reserva excedendo saldo do cofrinho deveria ter falhado!"

# 3.4 Teste: resgatar valor do cofrinho que comprometa a reserva atribuída (R$ 70 atribuído, tenta resgatar R$ 50 -> sobra 50 < 70 -> DEVE FALHAR)
ok_res, msg_res = saldo_service.retirar_de_cofrinho(conn, 1, 50.0, "2026-11-02", "Tentativa de resgate excessivo")
assert ok_res is False, "Resgate violando reserva comprometida deveria ser recusado!"
print(f"  ✓ Bloqueio esperado no resgate de cofrinho: {msg_res}")

# 3.5 Teste: resgatar valor livre (R$ 30 livre, resgata R$ 20 -> DEVE TER SUCESSO)
ok_res_livre, msg_res_livre = saldo_service.retirar_de_cofrinho(conn, 1, 20.0, "2026-11-02", "Resgate de saldo livre")
assert ok_res_livre is True, f"Resgate de saldo livre falhou: {msg_res_livre}"
print(f"  ✓ Resgate de saldo livre permitido: {msg_res_livre}")

# -----------------------------------------------------------------------------
# LIMPEZA ISOLADA DOS DADOS DE TESTE
# -----------------------------------------------------------------------------
print("\n[LIMPEZA] Removendo dados de teste e restaurando cofrinho...")
cur.execute("DELETE FROM planejamento_despesas_eventuais WHERE id = ?", (id_comp1,))
# Remove transferências de teste criadas
cur.execute("DELETE FROM transacoes WHERE descricao IN ('Depósito teste', 'Resgate de saldo livre')")
# Recompõe saldo do cofrinho para R$ 0,00
cur.execute("UPDATE cofrinhos SET saldo_confirmado = 0.0 WHERE id = 1")
conn.commit()

cur.execute("SELECT COUNT(*) FROM planejamento_despesas_eventuais")
c_dev = cur.fetchone()[0]
cur.execute("SELECT saldo_confirmado FROM cofrinhos WHERE id = 1")
s_final = cur.fetchone()[0]
assert c_dev == 0, "Tabela de compromissos deve retornar a 0!"
assert s_final == 0.0, "Saldo do cofrinho deve retornar a 0.0!"
print("  ✓ Limpeza concluída com sucesso! Banco totalmente preservado.")

print("\n=======================================================")
print(" TODOS OS TESTES PASSARAM COM 100% DE SUCESSO! ")
print("=======================================================")
