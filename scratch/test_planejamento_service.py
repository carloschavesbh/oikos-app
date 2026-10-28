"""
=============================================================================
SUÍTE DE TESTES AUTOMATIZADOS: PLANEJAMENTO FINANCEIRO INTELIGENTE
Validação em banco de teste isolado (financas_teste_planejamento.db).
Garante não duplicação, exatidão contábil e preservação do banco de produção.
=============================================================================
"""

import os
import sys
import sqlite3
import shutil
from decimal import Decimal
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath('.'))
import saldo_service
import planejamento_service

TEST_DB = "financas_teste_planejamento.db"
PROD_DB = "financas_casa.db"

def setup_test_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    # Copia o banco de produção para o banco de teste isolado
    shutil.copy2(PROD_DB, TEST_DB)
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    return conn

def executar_testes_planejamento():
    print("=== INICIANDO TESTES DO PLANEJAMENTO SERVICE EM BANCO ISOLADO ===")
    conn = setup_test_db()
    
    # 0. Verifica integridade do saldo inicial no banco de teste
    s_ini = saldo_service.calcular_saldo_consolidado(conn)["saldo_consolidado"]
    print(f"0. Saldo Consolidado Inicial: R$ {s_ini:.2f} (Esperado R$ 86.33)")
    assert s_ini == Decimal("86.33"), f"Esperado 86.33, obtido {s_ini}"

    # TESTE 1: Inicialização do Esquema de Planejamento
    planejamento_service.inicializar_esquema_planejamento(conn)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'planejamento_%'")
    tabelas_criadas = [r[0] for r in cur.fetchall()]
    print(f"1. Tabelas criadas no banco de teste: {tabelas_criadas}")
    assert "planejamento_metas" in tabelas_criadas
    assert "planejamento_previsao_variaveis" in tabelas_criadas
    assert "planejamento_prioridades_atrasados" in tabelas_criadas
    assert "planejamento_simulacao_trabalho" in tabelas_criadas

    # TESTE 2: Acordo BV tratado como pendente de confirmação
    cur.execute("UPDATE transacoes SET status_conciliacao_fatura = 'pendente_confirmacao' WHERE descricao LIKE '%Acordo BV%'")
    conn.commit()

    caixa_7d = planejamento_service.calcular_necessidade_caixa_7dias(conn, date(2026, 10, 19))
    print(f"2. BV em Conciliação: Total Pendente = R$ {caixa_7d['total_pendente_confirmacao']:.2f}")
    assert caixa_7d["total_pendente_confirmacao"] == Decimal("1428.82"), "O valor do BV deve ser isolado como pendente de confirmação!"
    assert caixa_7d["status_bv_pendente"] is True
    # O BV de R$ 1.428,82 NÃO pode estar somado nas obrigações confirmadas da semana
    for item in caixa_7d["obrigacoes_confirmadas_7d"]:
        assert "Acordo BV" not in item["descricao"], "BV não confirmado não pode estar na lista de confirmados!"

    # TESTE 3: Priorização de Atrasados
    # Selecionamos apenas Copasa (R$ 72,46) como prioridade da semana
    cur.execute("SELECT id FROM transacoes WHERE descricao LIKE '%Copasa%'")
    copasa_id = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO planejamento_prioridades_atrasados (semana_ref, transacao_id, prioritaria, valor_alocado)
        VALUES ('2026-W42', ?, 1, 72.46)
    """, (copasa_id,))
    conn.commit()

    caixa_priorizado = planejamento_service.calcular_necessidade_caixa_7dias(conn, date(2026, 10, 19), semana_ref='2026-W42')
    print(f"3. Atrasadas Prioritárias = R$ {caixa_priorizado['total_vencidas_prioritarias']:.2f} (Copasa)")
    print(f"   Atrasadas Reprogramadas = R$ {caixa_priorizado['total_vencidas_reprogramadas']:.2f}")
    assert caixa_priorizado["total_vencidas_prioritarias"] == Decimal("72.46")
    # As outras atrasadas (R$ 718,57 - 72,46 = 646,11) continuam rastreadas sem sumir
    assert caixa_priorizado["total_vencidas_reprogramadas"] == Decimal("646.11")

    # TESTE 4: Cálculo da Necessidade Adicional de Caixa Líquida
    # Confirmadas 7d (R$ 255,76) + Copasa (R$ 72,46) + Variáveis Semana (R$ 150,00) = R$ 478,22
    # Abate saldo livre R$ 86,33 -> Necessidade líquida = R$ 391,89
    nec_calc = caixa_priorizado["necessidade_adicional_caixa"]
    comp_calc = caixa_priorizado["compromissos_minimos_semana"]
    print(f"4. Compromissos da Semana: R$ {comp_calc:.2f} | Necessidade Líquida: R$ {nec_calc:.2f}")
    assert comp_calc == Decimal("478.22"), f"Esperado 478.22, obtido {comp_calc}"
    assert nec_calc == Decimal("391.89"), f"Esperado 391.89, obtido {nec_calc}"

    # TESTE 5: Missão IPVA e Reserva Virtual (sem movimentar contas bancárias)
    cur.execute("SELECT id FROM transacoes WHERE descricao LIKE '%IPVA%'")
    ipva_id = cur.fetchone()[0]
    # Reserva virtualmente R$ 50,00 do saldo
    sucesso_res, msg_res = planejamento_service.atualizar_reserva_missao(conn, ipva_id, Decimal("50.00"), "2026-10")
    assert sucesso_res is True, msg_res
    
    # Confere que o saldo bancário consolidado continua intacto em R$ 86,33
    saldo_apos_reserva = saldo_service.calcular_saldo_consolidado(conn)["saldo_consolidado"]
    print(f"5. Saldo Bancário após Reserva Virtual: R$ {saldo_apos_reserva:.2f} (INALTERADO)")
    assert saldo_apos_reserva == Decimal("86.33"), "Reserva virtual não pode alterar saldo bancário!"

    # Confere que o saldo livre caiu de R$ 86,33 para R$ 36,33
    caixa_com_reserva = planejamento_service.calcular_necessidade_caixa_7dias(conn, date(2026, 10, 19), semana_ref='2026-W42')
    print(f"   Saldo Livre após Reserva: R$ {caixa_com_reserva['saldo_livre']:.2f} (Esperado 36.33)")
    assert caixa_com_reserva["saldo_livre"] == Decimal("36.33")
    # A necessidade de caixa sobe exatamente os R$ 50 carimbados para o IPVA: R$ 391,89 + R$ 50,00 = R$ 441,89
    assert caixa_com_reserva["necessidade_adicional_caixa"] == Decimal("441.89")

    # TESTE 6: Proteção contra reserva maior que o saldo
    sucesso_inv, msg_inv = planejamento_service.atualizar_reserva_missao(conn, ipva_id, Decimal("500.00"), "2026-10")
    print(f"6. Tentativa de reserva excessiva (R$ 500): Rejeitada com sucesso ({msg_inv})")
    assert sucesso_inv is False, "Não pode permitir reserva maior que o saldo em conta!"

    # TESTE 7: Não Duplicação nas Despesas Variáveis
    # Previsão manual de supermercado de 19/10 a 31/10 = R$ 350,00
    cur.execute("""
        INSERT INTO planejamento_previsao_variaveis (mes_ano, categoria, tipo_previsao, data_inicio, valor_previsto, essencial_semanal)
        VALUES ('2026-10', 'Supermercado', 'a_partir_de_hoje', '2026-10-19', 350.00, 120.00)
    """)
    conn.commit()
    res_var_1 = planejamento_service.calcular_despesas_variaveis_restantes(conn, '2026-10', date(2026, 10, 19))
    sup_1 = next(item for item in res_var_1["detalhe_categorias"] if item["categoria"] == "Supermercado")
    assert sup_1["consumo_restante"] == Decimal("350.00")

    # Lança uma nova compra real de supermercado no dia 20/10 de R$ 100,00
    cur.execute("""
        INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario)
        VALUES ('2026-10-20', 'Supermercado Teste', 100.00, 'despesa', 'Supermercado', 'Mercado Pago', 1, 1, 1)
    """)
    conn.commit()
    # Verifica que a nova compra ABATE a previsão, ficando R$ 250 restantes (NÃO soma 350 + 100 = 450)
    res_var_2 = planejamento_service.calcular_despesas_variaveis_restantes(conn, '2026-10', date(2026, 10, 19))
    sup_2 = next(item for item in res_var_2["detalhe_categorias"] if item["categoria"] == "Supermercado")
    print(f"7. Variáveis: Previsão R$ 350 - Compra Nova R$ 100 = Consumo Restante R$ {sup_2['consumo_restante']:.2f}")
    assert sup_2["consumo_restante"] == Decimal("250.00"), "A despesa real deve substituir a previsão sem duplicar!"

    # TESTE 8: Viabilidade Operacional do Motorista (Regra de Rigor)
    # Cenário solicitado: Preciso de 21 horas, mas tenho apenas 20 disponíveis
    # Meta financeira: R$ 525,00 | Ganho líquido/h: R$ 25,00 -> 525 / 25 = 21,0 horas
    viab_deficit = planejamento_service.calcular_viabilidade_metas_trabalho(
        necessidade_financeira=Decimal("525.00"),
        dias_disponiveis=5,
        horas_disponiveis_dia=4.0, # Total 20h
        ganho_bruto_hora=35.0,
        combustivel_hora=10.0      # Líquido = R$ 25,00/h
    )
    print(f"8. Viabilidade (21h necessárias vs 20h disponíveis): Status = {viab_deficit['status_viabilidade']}")
    print(f"   Rótulo: {viab_deficit['rotulo_viabilidade']}")
    assert viab_deficit["status_viabilidade"] == "deficit", "21h necessárias com 20h disponíveis deve ser déficit!"
    assert viab_deficit["diferenca_horas"] == -1.0, f"Déficit esperado de -1.0h, obtido {viab_deficit['diferenca_horas']}"
    assert viab_deficit["cor_badge"] == "red"

    # Cenário com folga: 18h necessárias com 20h disponíveis
    viab_ok = planejamento_service.calcular_viabilidade_metas_trabalho(
        necessidade_financeira=Decimal("450.00"),
        dias_disponiveis=5,
        horas_disponiveis_dia=4.0,
        ganho_bruto_hora=35.0,
        combustivel_hora=10.0
    )
    print(f"   Viabilidade com Folga: Status = {viab_ok['status_viabilidade']} (Folga de {viab_ok['diferenca_horas']}h)")
    assert viab_ok["status_viabilidade"] == "coberta"
    assert viab_ok["diferenca_horas"] == 2.0

    # TESTE 9: Preservação do Banco de Produção
    conn.close()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    # Conecta no banco de produção oficial e valida saldos e registros
    conn_prod = sqlite3.connect(PROD_DB)
    s_prod = saldo_service.calcular_saldo_consolidado(conn_prod)["saldo_consolidado"]
    cur_p = conn_prod.cursor()
    cur_p.execute("SELECT COUNT(*) FROM transacoes")
    cnt_trans = cur_p.fetchone()[0]
    cur_p.execute("SELECT COUNT(*) FROM turnos")
    cnt_turnos = cur_p.fetchone()[0]
    conn_prod.close()

    print(f"\n9. Conferência do Banco de Produção ({PROD_DB}):")
    print(f"   Saldo Oficial: R$ {s_prod:.2f} (Mercado Pago: R$ 8,83 + Carteira: R$ 77,50)")
    print(f"   Total Transações: {cnt_trans} | Total Turnos: {cnt_turnos}")
    assert s_prod == Decimal("86.33"), "O saldo de produção não pode ter sofrido nenhuma alteração!"
    assert cnt_trans == 32, "Total de transações de produção deve ser rigorosamente 32!"
    assert cnt_turnos == 1, "Total de turnos de produção deve ser rigorosamente 1!"

    print("\n[SUCESSO] TODOS OS 9 TESTES DE PLANEJAMENTO FORAM APROVADOS COM 100% DE EXATIDÃO!")

if __name__ == "__main__":
    executar_testes_planejamento()
