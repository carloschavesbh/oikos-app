"""
=============================================================================
TESTE DE INTEGRAÇÃO COMPLETA: PLANEJAMENTO SERVICE & REGRAS VISUAIS
Testa todas as funções em ambiente isolado antes de alterar o app.py.
=============================================================================
"""

import os
import sys
import sqlite3
import shutil
from decimal import Decimal
from datetime import date

sys.path.insert(0, os.path.abspath('.'))
import saldo_service
import planejamento_service

TEST_DB = "financas_teste_planejamento.db"
PROD_DB = "financas_casa.db"

def test_full_flow():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    shutil.copy2(PROD_DB, TEST_DB)
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row

    print("=== TESTE DE FLUXO INTEGRADO: REGRAS VISUAIS E CÁLCULOS ===")

    # 1. Inicializa o esquema de planejamento
    planejamento_service.inicializar_esquema_planejamento(conn)
    cur = conn.cursor()

    # 2. Marca o Acordo BV como pendente de confirmação
    cur.execute("UPDATE transacoes SET status_conciliacao_fatura = 'pendente_confirmacao' WHERE descricao LIKE '%Acordo BV%'")
    conn.commit()

    # 3. Teste da Missão IPVA
    missao = planejamento_service.obter_status_missao_ipva(conn, "2026-10", date(2026, 10, 19))
    print(f"Missao IPVA encontrada: {missao['titulo']}, Valor: R$ {missao['valor_nominal']:.2f}")
    assert missao["tem_missao"] is True
    assert missao["valor_nominal"] == Decimal("431.11")
    assert missao["valor_ja_pago"] == Decimal("0.00")
    assert missao["valor_reservado"] == Decimal("0.00")
    assert missao["saldo_devedor_restante"] == Decimal("431.11")

    # 4. Atualiza reserva virtual para R$ 30,00
    ok_res, msg_res = planejamento_service.atualizar_reserva_missao(conn, missao["transacao_id"], Decimal("30.00"), "2026-10")
    assert ok_res is True, msg_res
    missao_apos = planejamento_service.obter_status_missao_ipva(conn, "2026-10", date(2026, 10, 19))
    print(f"Apos Reserva: Reservado = R$ {missao_apos['valor_reservado']:.2f}, Falta = R$ {missao_apos['saldo_devedor_restante']:.2f}")
    assert missao_apos["valor_reservado"] == Decimal("30.00")
    assert missao_apos["saldo_devedor_restante"] == Decimal("401.11")

    # 5. Caixa 7 dias com reserva
    caixa = planejamento_service.calcular_necessidade_caixa_7dias(conn, date(2026, 10, 19))
    print(f"Saldo Total: R$ {caixa['saldo_total_disponivel']:.2f} | Saldo Livre: R$ {caixa['saldo_livre']:.2f}")
    assert caixa["saldo_total_disponivel"] == Decimal("86.33")
    assert caixa["saldo_livre"] == Decimal("56.33") # 86.33 - 30.00

    # 6. Variáveis esperadas
    cur.execute("""
        INSERT OR REPLACE INTO planejamento_previsao_variaveis (mes_ano, categoria, tipo_previsao, data_inicio, valor_previsto, essencial_semanal)
        VALUES ('2026-10', 'Supermercado', 'a_partir_de_hoje', '2026-10-19', 300.00, 100.00)
    """)
    conn.commit()
    var_res = planejamento_service.calcular_despesas_variaveis_restantes(conn, "2026-10", date(2026, 10, 19))
    item_sup = next(i for i in var_res["detalhe_categorias"] if i["categoria"] == "Supermercado")
    assert item_sup["consumo_restante"] == Decimal("300.00")

    # 7. Viabilidade
    viab = planejamento_service.calcular_viabilidade_metas_trabalho(
        necessidade_financeira=Decimal("500.00"),
        dias_disponiveis=5,
        horas_disponiveis_dia=4.0, # 20h
        ganho_bruto_hora=35.0,
        combustivel_hora=10.0      # liq 25 -> 20h necessarias -> exatamente coberta
    )
    print(f"Viabilidade Exata: {viab['rotulo_viabilidade']}")
    assert viab["status_viabilidade"] == "coberta"
    assert viab["horas_necessarias"] == 20.0

    conn.close()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    print("[TESTE INTEGRADO CONCLUÍDO COM SUCESSO]")

if __name__ == "__main__":
    test_full_flow()
