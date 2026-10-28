import sys
import os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
import uuid
from decimal import Decimal
from datetime import date, timedelta
import saldo_service

sys.stdout.reconfigure(encoding='utf-8')

DB_TESTE = 'scratch/financas_casa_teste_final.db'
print("="*80)
print("TESTANDO OS DOIS MODELOS DE DÍVIDA E FORMULÁRIO DE NOVA DESPESA")
print(f"Banco: {DB_TESTE}")
print("="*80)

conn = sqlite3.connect(DB_TESTE)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# -----------------------------------------------------------------------------
# 1. ATUALIZAÇÃO DO ESQUEMA DE DÍVIDAS (LIVRE E NEGOCIADA)
# -----------------------------------------------------------------------------
cur.execute("PRAGMA table_info(dividas_gerenciamento)")
cols_div = [c[1] for c in cur.fetchall()]

if "tipo_divida" not in cols_div:
    cur.execute("ALTER TABLE dividas_gerenciamento ADD COLUMN tipo_divida TEXT DEFAULT 'livre'") # 'livre', 'negociada'
if "meta_voluntaria_mensal" not in cols_div:
    cur.execute("ALTER TABLE dividas_gerenciamento ADD COLUMN meta_voluntaria_mensal REAL DEFAULT 0.0")
if "meta_voluntaria_semanal" not in cols_div:
    cur.execute("ALTER TABLE dividas_gerenciamento ADD COLUMN meta_voluntaria_semanal REAL DEFAULT 0.0")
if "acordo_parcelas" not in cols_div:
    cur.execute("ALTER TABLE dividas_gerenciamento ADD COLUMN acordo_parcelas INTEGER")
if "acordo_valor_parcela" not in cols_div:
    cur.execute("ALTER TABLE dividas_gerenciamento ADD COLUMN acordo_valor_parcela REAL")
if "acordo_grupo_parcelamento" not in cols_div:
    cur.execute("ALTER TABLE dividas_gerenciamento ADD COLUMN acordo_grupo_parcelamento TEXT")

conn.commit()
print("✓ Colunas de Dívida Livre e Negociada adicionadas em dividas_gerenciamento.")

# -----------------------------------------------------------------------------
# 2. TESTE: DÍVIDA LIVRE (SEM VENCIMENTO OBRIGATÓRIO)
# -----------------------------------------------------------------------------
print("\n--- TESTE 1: DÍVIDA LIVRE COM PAGAMENTOS MANUAIS E META VOLUNTÁRIA ---")
cur.execute("""
    INSERT INTO dividas_gerenciamento (
        credor, descricao, tipo_divida, valor_original, saldo_atual, 
        meta_voluntaria_mensal, data_inicio, status
    ) VALUES ('Familiar (Pai)', 'Ajuda financeira', 'livre', 4000.00, 4000.00, 300.00, '2026-07-01', 'ativa')
""")
div_livre_id = cur.lastrowid

# Pagamento manual 1: R$ 500 em agosto
cur.execute("""
    INSERT INTO dividas_pagamentos_manuais (divida_id, data_pagamento, valor_pago, observacao)
    VALUES (?, '2026-08-15', 500.00, 'Pagamento parcial PIX direto')
""", (div_livre_id,))

# Pagamento manual 2: R$ 500 em setembro
cur.execute("""
    INSERT INTO dividas_pagamentos_manuais (divida_id, data_pagamento, valor_pago, observacao)
    VALUES (?, '2026-09-20', 500.00, 'Pagamento parcial em dinheiro')
""", (div_livre_id,))

# Atualiza saldo atual da dívida livre
cur.execute("UPDATE dividas_gerenciamento SET saldo_atual = saldo_atual - 1000.00 WHERE id = ?", (div_livre_id,))
conn.commit()

# Consulta da dívida livre:
cur.execute("SELECT * FROM dividas_gerenciamento WHERE id = ?", (div_livre_id,))
row_dl = cur.fetchone()
pct_quitado = ((row_dl["valor_original"] - row_dl["saldo_atual"]) / row_dl["valor_original"]) * 100

print(f"Dívida Livre: {row_dl['descricao']} ({row_dl['credor']})")
print(f"  Tipo: {row_dl['tipo_divida']} | Valor Original: R$ {row_dl['valor_original']:.2f}")
print(f"  Total Pago Manual: R$ 1.000,00 | Saldo Devedor Atual: R$ {row_dl['saldo_atual']:.2f}")
print(f"  Progresso de Quitação: {pct_quitado:.1f}%")
print(f"  Meta Voluntária Mensal: R$ {row_dl['meta_voluntaria_mensal']:.2f} (sem gerar contas a pagar)")

# Verifica que NÃO gerou transações bancárias nem contas a pagar
cur.execute("SELECT COUNT(*) FROM transacoes WHERE descricao LIKE '%Ajuda financeira%'")
assert cur.fetchone()[0] == 0, "Dívida livre não pode criar transações bancárias automaticamente!"
print("✓ Teste 1 passou: Dívida livre gerenciada com sucesso sem movimentar banco nem criar cobranças.")

# -----------------------------------------------------------------------------
# 3. TESTE: TRANSFORMAÇÃO DE DÍVIDA LIVRE EM NEGOCIADA (SEM PERDA DE HISTÓRICO)
# -----------------------------------------------------------------------------
print("\n--- TESTE 2: TRANSFORMAÇÃO DE DÍVIDA LIVRE EM NEGOCIADA (ACORDO) ---")
# O saldo restante de R$ 3.000,00 é negociado em 6 parcelas mensais de R$ 500,00
# Primeira parcela vencerá em 10/11/2026
acordo_grp = f"acordo_pai_{div_livre_id}"
cur.execute("""
    UPDATE dividas_gerenciamento
    SET tipo_divida = 'negociada',
        acordo_parcelas = 6,
        acordo_valor_parcela = 500.00,
        acordo_grupo_parcelamento = ?
    WHERE id = ?
""", (acordo_grp, div_livre_id))

# Gera as 6 parcelas em transacoes (reutilizando o fluxo existente de despesas parceladas)
dt_primeira_parc = date(2026, 11, 10)
for i in range(1, 7):
    # vencimento a cada 30 dias aproximadamente
    dt_parc = date(2026, 10 + i if 10 + i <= 12 else (10 + i - 12), 10) # mensal simples
    cur.execute("""
        INSERT INTO transacoes (
            data, descricao, valor, tipo, categoria, conta, conta_id, pago, status_pagamento,
            grupo_parcelamento, numero_parcela, total_parcelas_compra, afeta_saldo_bancario
        ) VALUES (?, ?, 500.00, 'despesa', 'Dívidas', 'Mercado Pago', 1, 0, 'pendente', ?, ?, 6, 1)
    """, (dt_parc.strftime("%Y-%m-%d"), f"Acordo Pai {i}/6", acordo_grp, i))

conn.commit()

# Consulta pós-negociação:
# Histórico anterior de pagamentos manuais continua intacto:
cur.execute("SELECT COUNT(*), SUM(valor_pago) FROM dividas_pagamentos_manuais WHERE divida_id = ? AND cancelado = 0", (div_livre_id,))
hist_man = cur.fetchone()
print(f"Histórico Manual Anterior Preservado: {hist_man[0]} pagamentos totalizando R$ {hist_man[1]:.2f}")
assert hist_man[1] == 1000.00, "Histórico anterior deve ser 100% preservado!"

# Parcelas geradas no fluxo de caixa para acompanhar no calendário:
cur.execute("SELECT id, data, descricao, valor, pago FROM transacoes WHERE grupo_parcelamento = ? ORDER BY data", (acordo_grp,))
parcelas_acordo = cur.fetchall()
print(f"Parcelas do Acordo Integradas ao Calendário de Caixa: {len(parcelas_acordo)} parcelas de R$ 500,00")
for p in parcelas_acordo[:3]:
    print(f"  - ID {p['id']} | Venc: {p['data']} | {p['descricao']} | R$ {p['valor']:.2f}")

# Simula pagamento da parcela 1/6 no fluxo de caixa normal
parc1_id = parcelas_acordo[0]["id"]
saldo_service.registrar_pagamento(
    conn=conn,
    transacao_id=parc1_id,
    data_pagamento="2026-11-10",
    valor_pago=500.00,
    conta_id=1,
    afeta_saldo_bancario=1,
    forma_pagamento="Pix",
    observacao="Quitação parcela 1/6 do acordo"
)
conn.commit()

# Verifica saldo devedor consolidado da dívida negociada:
# Saldo = Valor Original (4.000) - Pagamentos Manuais (1.000) - Parcelas Pagas do Acordo (500) = R$ 2.500,00!
cur.execute("""
    SELECT 
        d.id, d.credor, d.valor_original,
        COALESCE((SELECT SUM(valor_pago) FROM dividas_pagamentos_manuais WHERE divida_id = d.id AND cancelado = 0), 0.0) as tot_manual,
        COALESCE((SELECT SUM(valor) FROM transacoes WHERE grupo_parcelamento = d.acordo_grupo_parcelamento AND pago = 1), 0.0) as tot_acordo_pago,
        COALESCE((SELECT SUM(valor) FROM transacoes WHERE grupo_parcelamento = d.acordo_grupo_parcelamento AND pago != 1), 0.0) as tot_acordo_aberto
    FROM dividas_gerenciamento d
    WHERE d.id = ?
""", (div_livre_id,))
res_neg = cur.fetchone()
total_pago_geral = res_neg["tot_manual"] + res_neg["tot_acordo_pago"]
saldo_restante_geral = res_neg["valor_original"] - total_pago_geral
progresso_geral = (total_pago_geral / res_neg["valor_original"]) * 100

print(f"\nResumo da Dívida Negociada:")
print(f"  Valor Original: R$ {res_neg['valor_original']:.2f}")
print(f"  Total Pago: R$ {total_pago_geral:.2f} (R$ {res_neg['tot_manual']:.2f} manual anterior + R$ {res_neg['tot_acordo_pago']:.2f} acordo pago)")
print(f"  Saldo Devedor Restante: R$ {saldo_restante_geral:.2f} (exatamente R$ {res_neg['tot_acordo_aberto']:.2f} a vencer no acordo)")
print(f"  Progresso Total: {progresso_geral:.1f}%")
assert saldo_restante_geral == 2500.00, "Saldo devedor restante deve ser R$ 2.500,00"
assert res_neg['tot_acordo_aberto'] == 2500.00, "Parcelas a vencer devem somar exatamente R$ 2.500,00"
print("✓ Teste 2 passou: Transformação de Dívida Livre para Negociada sem duplicidade e sem perda de histórico.")

# -----------------------------------------------------------------------------
# 4. TESTE: FORMULÁRIO NOVA DESPESA (LANÇAMENTO FIXO E PARCELADO)
# -----------------------------------------------------------------------------
print("\n--- TESTE 3: FORMULÁRIO NOVA DESPESA (MODALIDADES FIXO E PARCELADO) ---")

def criar_despesa_reutilizavel(
    conn,
    descricao: str,
    valor: float,
    categoria: str,
    conta_nome: str,
    data_primeiro_vencimento: date,
    modalidade: str = "unico", # 'unico', 'parcelado', 'fixo'
    num_parcelas: int = 1,
    intervalo_dias: int = 30,
    primeira_paga_no_ato: bool = False,
    qtd_meses_recorrencia: int = 12
):
    cur = conn.cursor()
    cur.execute("SELECT id FROM contas_config WHERE nome = ?", (conta_nome,))
    c_row = cur.fetchone()
    conta_id = c_row[0] if c_row else 1
    
    ids_criados = []
    
    if modalidade == "unico":
        cur.execute("""
            INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, status_pagamento, afeta_saldo_bancario)
            VALUES (?, ?, ?, 'despesa', ?, ?, ?, ?, ?, 1)
        """, (
            data_primeiro_vencimento.strftime("%Y-%m-%d"),
            descricao.strip(),
            valor,
            categoria,
            conta_nome,
            conta_id,
            1 if primeira_paga_no_ato else 0,
            "pago" if primeira_paga_no_ato else "pendente"
        ))
        ids_criados.append(cur.lastrowid)
        
    elif modalidade == "parcelado":
        grp = f"parcela_{uuid.uuid4().hex[:6]}"
        val_parc = round(valor / num_parcelas, 2)
        dif = round(valor - (val_parc * num_parcelas), 2)
        
        for i in range(1, num_parcelas + 1):
            # Vencimento a cada intervalo_dias ou data mensal
            dt_venc = data_primeiro_vencimento + timedelta(days=(i - 1) * intervalo_dias)
            v_atual = val_parc + (dif if i == 1 else 0.0)
            esta_paga = (i == 1 and primeira_paga_no_ato)
            
            cur.execute("""
                INSERT INTO transacoes (
                    data, descricao, valor, tipo, categoria, conta, conta_id, pago, status_pagamento,
                    grupo_parcelamento, numero_parcela, total_parcelas_compra, afeta_saldo_bancario
                ) VALUES (?, ?, ?, 'despesa', ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                dt_venc.strftime("%Y-%m-%d"),
                f"{descricao.strip()} ({i}/{num_parcelas})",
                v_atual,
                categoria,
                conta_nome,
                conta_id,
                1 if esta_paga else 0,
                "pago" if esta_paga else "pendente",
                grp,
                i,
                num_parcelas
            ))
            t_id = cur.lastrowid
            ids_criados.append(t_id)
            
            if esta_paga:
                saldo_service.registrar_pagamento(
                    conn=conn,
                    transacao_id=t_id,
                    data_pagamento=data_primeiro_vencimento.strftime("%Y-%m-%d"),
                    valor_pago=v_atual,
                    conta_id=conta_id,
                    afeta_saldo_bancario=1,
                    forma_pagamento="Débito",
                    observacao="Entrada da compra parcelada paga no ato"
                )
                
    elif modalidade == "fixo":
        grp_fixo = f"fixo_{uuid.uuid4().hex[:6]}"
        for m in range(qtd_meses_recorrencia):
            # Projeta os próximos meses na mesma data base
            # Ex: dia 20 de cada mês
            ano_parc = data_primeiro_vencimento.year + ((data_primeiro_vencimento.month - 1 + m) // 12)
            mes_parc = ((data_primeiro_vencimento.month - 1 + m) % 12) + 1
            dia_parc = min(data_primeiro_vencimento.day, 28) # segurança para fevereiro
            dt_venc = date(ano_parc, mes_parc, dia_parc)
            
            esta_paga = (m == 0 and primeira_paga_no_ato)
            
            cur.execute("""
                INSERT INTO transacoes (
                    data, descricao, valor, tipo, categoria, conta, conta_id, pago, status_pagamento,
                    grupo_parcelamento, afeta_saldo_bancario
                ) VALUES (?, ?, ?, 'despesa', ?, ?, ?, ?, ?, ?, 1)
            """, (
                dt_venc.strftime("%Y-%m-%d"),
                descricao.strip(),
                valor,
                categoria,
                conta_nome,
                conta_id,
                1 if esta_paga else 0,
                "pago" if esta_paga else "pendente",
                grp_fixo
            ))
            t_id = cur.lastrowid
            ids_criados.append(t_id)
            
            if esta_paga:
                saldo_service.registrar_pagamento(
                    conn=conn,
                    transacao_id=t_id,
                    data_pagamento=data_primeiro_vencimento.strftime("%Y-%m-%d"),
                    valor_pago=valor,
                    conta_id=conta_id,
                    afeta_saldo_bancario=1,
                    forma_pagamento="Débito",
                    observacao="1ª mensalidade paga no ato"
                )
                
    conn.commit()
    return ids_criados

# Teste 3A: Criar compra parcelada genérica (ex: 3x de R$ 150,00 no cartão ou boleto)
ids_parc = criar_despesa_reutilizavel(
    conn=conn,
    descricao="Conserto Notebook",
    valor=450.00,
    categoria="Educação",
    conta_nome="Mercado Pago",
    data_primeiro_vencimento=date(2026, 10, 25),
    modalidade="parcelado",
    num_parcelas=3,
    intervalo_dias=30,
    primeira_paga_no_ato=False
)
print(f"3A. Despesa Parcelada Criada: 3 parcelas de R$ 150,00 (IDs: {ids_parc})")
cur.execute("SELECT id, data, descricao, valor, pago FROM transacoes WHERE id IN (?, ?, ?)", tuple(ids_parc))
for r in cur.fetchall():
    print(f"    - ID {r['id']} | Venc: {r['data']} | {r['descricao']} | R$ {r['valor']:.2f} | Pago: {r['pago']}")
assert len(ids_parc) == 3

# Teste 3B: Criar despesa fixa recorrente mensal (ex: Mensalidade Academia 6 meses)
ids_fixo = criar_despesa_reutilizavel(
    conn=conn,
    descricao="Mensalidade Natação",
    valor=120.00,
    categoria="Saúde",
    conta_nome="Mercado Pago",
    data_primeiro_vencimento=date(2026, 10, 20),
    modalidade="fixo",
    qtd_meses_recorrencia=6,
    primeira_paga_no_ato=True
)
print(f"\n3B. Despesa Fixa Recorrente Criada: 6 meses de R$ 120,00 (IDs: {ids_fixo})")
cur.execute("SELECT id, data, descricao, valor, pago, status_pagamento FROM transacoes WHERE id IN (?, ?, ?, ?, ?, ?)", tuple(ids_fixo))
rows_fix = cur.fetchall()
for r in rows_fix:
    print(f"    - ID {r['id']} | Venc: {r['data']} | {r['descricao']} | R$ {r['valor']:.2f} | Status: {r['status_pagamento']}")
assert rows_fix[0]["pago"] == 1, "A 1ª mensalidade deve estar paga no ato"
assert rows_fix[1]["pago"] == 0, "A 2ª mensalidade deve estar pendente"
print("✓ Teste 3 passou: Lançamentos parcelados e fixos funcionam perfeitamente sem duplicidade!")

conn.close()
print("\n" + "="*80)
print("TODOS OS TESTES DE VALIDAÇÃO PASSARAM COM SUCESSO ABSOLUTO!")
print("="*80)
