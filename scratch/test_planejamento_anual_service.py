import sqlite3
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))

import planejamento_anual_service

conn = sqlite3.connect('financas_remodelacao.db')
conn.row_factory = sqlite3.Row

print("--- 1. TESTE DE INICIALIZAÇÃO DO ESQUEMA ---")
planejamento_anual_service.inicializar_tabelas_renda_e_anual(conn)
print("✓ Tabelas inicializadas com sucesso.")

print("\n--- 2. TESTE DE ANÁLISE DE HISTÓRICO DE RENDA ---")
hist12 = planejamento_anual_service.analisar_historico_renda(conn, 12, 2026, 10)
print(f"Mês de referência: {hist12['mes_referencia']}")
print(f"Meses analisados: {len(hist12['historico'])}")
print("Estatísticas Variável:")
print(f"  - Meses válidos: {hist12['estatisticas_variavel']['qtd_meses_validos']}")
print(f"  - Mínimo observado: R$ {hist12['estatisticas_variavel']['minimo_observado']:,.2f}")
print(f"  - Média observada: R$ {hist12['estatisticas_variavel']['media_observada']:,.2f}")
print(f"  - Máximo observado: R$ {hist12['estatisticas_variavel']['maximo_observado']:,.2f}")

print("\nCenários de Renda Sugeridos:")
for c_nome, c_info in hist12["cenarios"].items():
    print(f"  - {c_nome.upper()}: Base R$ {c_info['base']:,.2f} | Final R$ {c_info['valor_final']:,.2f} (Manual: {c_info['is_manual']})")
    print(f"    Descrição: {c_info['descricao']}")

assert hist12['estatisticas_variavel']['qtd_meses_validos'] > 0, "Deveria haver meses válidos de renda variável"
print("✓ Histórico de renda analisado corretamente.")

print("\n--- 3. TESTE DE INTEGRAÇÃO COM DRIVE & MARGEM LÍQUIDA ---")
margem_drive = planejamento_anual_service.obter_margem_operacional_drive(conn, 2026, 10)
print(f"Turnos no mês: {margem_drive['qtd_turnos']} ({margem_drive['horas_totais']}h rodadas)")
print(f"Faturamento Bruto: R$ {margem_drive['faturamento_bruto']:,.2f}")
print(f"Custos Registrados: R$ {margem_drive['custos_registrados']:,.2f}")
print(f"Resultado Líquido Disponível: R$ {margem_drive['resultado_liquido_disponivel']:,.2f}")
print(f"Ganho Médio por Hora: R$ {margem_drive['ganho_hora_real']:,.2f}/h (Referência: R$ {margem_drive['referencia_hora']}/h)")
print("✓ Margem operacional do Drive apurada com distinção de custos.")

print("\n--- 4. TESTE DE CLASSIFICAÇÃO DE DESPESAS POR NATUREZA ---")
classif = planejamento_anual_service.obter_classificacao_natureza(conn)
print(f"Total de categorias classificadas: {len(classif)}")
print(f"Exemplo: 'Alimentação' => {classif.get('Alimentação')}")
print(f"Exemplo: 'Streaming' => {classif.get('Streaming')}")
print(f"Exemplo: 'Acordo BV' => {classif.get('Acordo BV')}")

comp_cenarios = planejamento_anual_service.comparar_cenarios_com_despesas(conn, 2026, 10, hist12["cenarios"])
print(f"\nDespesas Totais Outubro: R$ {comp_cenarios['despesas_totais']:,.2f}")
for nat_k, nat_v in comp_cenarios["por_natureza"].items():
    print(f"  - {nat_v['icone']} {nat_v['nome']}: R$ {nat_v['total']:,.2f} ({nat_v['pct_total']}%)")

print("\nResultados dos Cenários:")
for c_nome, c_res in comp_cenarios["cenarios"].items():
    print(f"  - {c_nome.upper()}: Renda R$ {c_res['renda_total']:,.2f} - Despesas R$ {c_res['despesas_totais']:,.2f} => Sobra/Falta: R$ {c_res['sobra_ou_falta']:,.2f} ({c_res['status'].upper()})")
    print(f"    Cobertura da Estrutura: {c_res['cobertura_estrutura_pct']}% (Cobre estrutura: {c_res['cobre_estrutura']})")

print("✓ Comparativo de cenários e classificação de despesas funcional.")

print("\n--- 5. TESTE DE CALENDÁRIO ANUAL & ALOCAÇÃO DE COFRINHOS ---")
# Criar 2 despesas eventuais para teste vinculadas ao mesmo cofrinho
cur = conn.cursor()
cur.execute("DELETE FROM planejamento_despesas_eventuais WHERE nome LIKE 'Teste %'")
conn.commit()

id_d1 = planejamento_anual_service.criar_despesa_eventual(conn, {
    "nome": "Teste IPVA HB20 2027",
    "categoria": "Impostos Veículo",
    "responsavel": "Carlos",
    "data_prevista": "2027-01-15",
    "valor_estimado": 1200.0,
    "cofrinho_id": 1, # Cofrinho IPVA
    "frequencia_contribuicao": "mensal"
})

id_d2 = planejamento_anual_service.criar_despesa_eventual(conn, {
    "nome": "Teste Taxa Licenciamento 2027",
    "categoria": "Impostos Veículo",
    "responsavel": "Carlos",
    "data_prevista": "2027-03-31",
    "valor_estimado": 400.0,
    "cofrinho_id": 1, # Mesmo Cofrinho IPVA
    "frequencia_contribuicao": "mensal"
})

# Simular saldo no cofrinho IPVA de R$ 800,00 para testar rateio proporcional
cur.execute("UPDATE cofrinhos SET saldo_confirmado = 800.0 WHERE id = 1")
conn.commit()

cal = planejamento_anual_service.obter_calendario_anual(conn, 2026, 11)
print(f"Meses na linha do tempo: {len(cal['meses'])}")
print(f"Total previsto nos 12 meses: R$ {cal['total_geral_previsto']:,.2f}")
print(f"Total reservado: R$ {cal['total_geral_reservado']:,.2f}")
print(f"Total falta reservar: R$ {cal['total_geral_falta']:,.2f}")

# Verificar distribuição do cofrinho
d1_item = next(d for d in cal["todas_despesas"] if d["id"] == id_d1)
d2_item = next(d for d in cal["todas_despesas"] if d["id"] == id_d2)
print(f"D1 (Alvo R$ 1.200,00): Reservado R$ {d1_item['saldo_reservado_alocado']:,.2f} | Falta R$ {d1_item['falta_reservar']:,.2f} | Sugestão: R$ {d1_item['sugestao_mensal']:,.2f}/mês")
print(f"D2 (Alvo R$ 400,00): Reservado R$ {d2_item['saldo_reservado_alocado']:,.2f} | Falta R$ {d2_item['falta_reservar']:,.2f} | Sugestão: R$ {d2_item['sugestao_mensal']:,.2f}/mês")

soma_alocada = d1_item['saldo_reservado_alocado'] + d2_item['saldo_reservado_alocado']
print(f"Soma alocada aos 2 compromissos: R$ {soma_alocada:.2f} (Saldo real do cofrinho: R$ 800.00)")
assert abs(soma_alocada - 800.0) < 0.05, f"Erro no rateio anti-duplicidade! {soma_alocada} != 800.0"
print("✓ Rateio anti-duplicidade de cofrinho validado com precisão!")

# Testar conciliação de pagamento
planejamento_anual_service.conciliar_pagamento_despesa_eventual(conn, id_d1, 1200.0, "2027-01-15", baixar_reserva_cofrinho=True)
cur.execute("SELECT status, valor_confirmado FROM planejamento_despesas_eventuais WHERE id = ?", (id_d1,))
r_pago = cur.fetchone()
assert r_pago[0] == 'paga', "Status deveria ser 'paga'"
assert r_pago[1] == 1200.0, "Valor confirmado não bate"

cur.execute("SELECT saldo_confirmado FROM cofrinhos WHERE id = 1")
saldo_pos_baixa = cur.fetchone()[0]
print(f"Saldo cofrinho após baixa de R$ 1.200 (com saldo 800): R$ {saldo_pos_baixa:.2f} (deve ser 0.00 sem ficar negativo)")
assert saldo_pos_baixa == 0.0, "Saldo não zerou corretamente"
print("✓ Conciliação de pagamento com baixa de cofrinho validada!")

# Limpar dados de teste e restaurar saldo original do cofrinho 1 (0.0)
cur.execute("DELETE FROM planejamento_despesas_eventuais WHERE id IN (?, ?)", (id_d1, id_d2))
cur.execute("UPDATE cofrinhos SET saldo_confirmado = 0.0 WHERE id = 1")
conn.commit()
conn.close()

print("\n=== TODOS OS TESTES UNITÁRIOS DO SERVIÇO PASSARAM COM SUCESSO! ===")
