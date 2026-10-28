import sys
import os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
from datetime import date
from decimal import Decimal
import saldo_service
import planejamento_service

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('scratch/financas_casa_audit_copy.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

hoje = date(2026, 10, 20)

print("="*80)
print("AUDITORIA COMPLETA DE REGISTROS E INDICADORES - BASE FINANCAS_CASA_AUDIT_COPY")
print("="*80)

# 1. SALDO CONSOLIDADO
saldo_res = saldo_service.calcular_saldo_consolidado(conn, hoje)
print(f"\n1. SALDO CONSOLIDADO ATUAL: R$ {saldo_res['saldo_consolidado']}")
for c in saldo_res['contas']:
    print(f"   Conta: {c['conta_nome']} (ID {c['conta_id']}) -> Saldo: R$ {c['saldo_atual']}")

# 2. TODAS AS TRANSACOES DE DESPESA DE OUTUBRO/2026
print("\n2. TODAS AS DESPESAS DE OUTUBRO/2026 (ID, DATA, DESCRICAO, VALOR, CATEGORIA, PAGO, STATUS_CONCILIACAO):")
cur.execute("""
    SELECT id, data, descricao, valor, categoria, conta, pago, 
           COALESCE(status_conciliacao_fatura, 'normal') as st_conc,
           afeta_saldo_bancario
    FROM transacoes
    WHERE tipo = 'despesa' AND data >= '2026-10-01' AND data <= '2026-10-31'
    ORDER BY data ASC, id ASC
""")
despesas_out = cur.fetchall()

tot_todas_out = Decimal("0.00")
tot_pagas_out = Decimal("0.00")
tot_pend_out_geral = Decimal("0.00")
tot_pend_out_afeta_caixa = Decimal("0.00")

itens_pendentes_antigo = []
for d in despesas_out:
    val = Decimal(str(d["valor"]))
    tot_todas_out += val
    if d["pago"] == 1:
        tot_pagas_out += val
    else:
        tot_pend_out_geral += val
        afeta = d["afeta_saldo_bancario"]
        if afeta == 1 or afeta is None:
            tot_pend_out_afeta_caixa += val
            itens_pendentes_antigo.append(d)
        print(f"   [PENDENTE] ID {d['id']:2d} | Venc: {d['data']} | R$ {val:7.2f} | {d['categoria']:18s} | Conc: {d['st_conc']:20s} | {d['descricao']}")

print(f"\nTotal Despesas Mês: R$ {tot_todas_out:.2f}")
print(f"Total Pagas Mês: R$ {tot_pagas_out:.2f}")
print(f"Total Pendentes Geral: R$ {tot_pend_out_geral:.2f}")
print(f"Total Pendentes que afetam caixa (Obrigações Antigas): R$ {tot_pend_out_afeta_caixa:.2f}")

# 3. VERIFICACAO DE OBRIGACOES ANTIGAS (< 2026-10-01) PENDENTES
cur.execute("""
    SELECT id, data, descricao, valor, categoria, conta, pago
    FROM transacoes
    WHERE tipo = 'despesa' AND data < '2026-10-01' AND (pago IS NULL OR pago != 1)
""")
antigas_pend = cur.fetchall()
print(f"\n3. DESPESAS VENCIDAS ANTES DE OUTUBRO/2026 PENDENTES: {len(antigas_pend)} registros")
for a in antigas_pend:
    print(f"   ID {a['id']} | {a['data']} | R$ {a['valor']} | {a['descricao']}")

# 4. CLASSIFICACAO DETALHADA NO PLANEJAMENTO NOVO
print("\n4. CLASSIFICACAO DAS PENDENCIAS NO PLANEJAMENTO NOVO:")
proj = planejamento_service.calcular_projecao_mensal(conn, hoje)
print(f"   Obrigações Confirmadas: R$ {proj['total_obrigacoes_confirmadas']}")
print(f"   Valores BV sob Conciliação: R$ {proj['total_bv_pendente']}")
print(f"   Soma Confirmadas + BV: R$ {proj['total_obrigacoes_confirmadas'] + proj['total_bv_pendente']}")
print(f"   Variáveis Restantes Estimadas: R$ {proj['total_variaveis_restantes']}")
print(f"   Saldo Atual: R$ {proj['saldo_atual']}")
print(f"   Saldo Final Projetado sem Renda App: R$ {proj['saldo_final_projetado_sem_renda_app']}")

# 5. DETALHAMENTO DE DESPESAS VARIAVEIS
print("\n5. DETALHAMENTO DAS DESPESAS VARIAVEIS (calcular_despesas_variaveis_restantes):")
res_var = planejamento_service.calcular_despesas_variaveis_restantes(conn, "2026-10", hoje)
for item in res_var["detalhe_categorias"]:
    print(f"   Cat: {item['categoria']:15s} | Teto: R$ {item['teto_limite']:7.2f} | Previsto: R$ {item['previsao_futura']:7.2f} | Realizado Pós-Hoje: R$ {item['gasto_posterior_realizado']:7.2f} | Restante: R$ {item['consumo_restante']:7.2f} | Tipo: {item['tipo_previsao']}")
print(f"   TOTAL CONSUMO ESPERADO RESTANTE: R$ {res_var['total_consumo_esperado_restante']}")
print(f"   TOTAL ESSENCIAL SEMANA: R$ {res_var['total_essencial_semana']}")

# 6. CAIXA 7 DIAS DETALHAMENTO
print("\n6. CAIXA DOS PROXIMOS 7 DIAS (20/10 a 27/10):")
caixa = planejamento_service.calcular_necessidade_caixa_7dias(conn, hoje)
print(f"   Data Referencia: {caixa['data_referencia']} | Data Limite: {caixa['data_limite_7d']}")
print(f"   Saldo Livre: R$ {caixa['saldo_livre']}")
print(f"   Total Confirmadas 7d: R$ {caixa['total_confirmadas_7d']}")
for ob in caixa['obrigacoes_confirmadas_7d']:
    print(f"      - ID {ob['id']:2d} | {ob['data']} | R$ {ob['saldo_devedor']:7.2f} | {ob['categoria']:15s} | {ob['descricao']}")
print(f"   Total Vencidas Prioritarias: R$ {caixa['total_vencidas_prioritarias']}")
print(f"   Total Vencidas Reprogramadas: R$ {caixa['total_vencidas_reprogramadas']}")
for rpr in caixa['obrigacoes_vencidas_reprogramadas']:
    print(f"      - [REPROGRAMADA] ID {rpr['id']:2d} | {rpr['data']} | R$ {rpr['saldo_devedor']:7.2f} | {rpr['categoria']:15s} | {rpr['descricao']}")
print(f"   Total BV Pendente de Confirmacao: R$ {caixa['total_pendente_confirmacao']}")
for bv in caixa['valores_pendentes_confirmacao']:
    print(f"      - [BV PENDENTE] ID {bv['id']:2d} | {bv['data']} | R$ {bv['saldo_devedor']:7.2f} | {bv['descricao']}")
print(f"   Gastos Variaveis Semana: R$ {caixa['gastos_variaveis_semana']}")
print(f"   Compromissos Minimos Semana: R$ {caixa['compromissos_minimos_semana']}")
print(f"   Necessidade Adicional Caixa: R$ {caixa['necessidade_adicional_caixa']}")

conn.close()
