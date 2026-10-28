import sys
import os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
from decimal import Decimal
from datetime import date, timedelta
import saldo_service
import planejamento_service

sys.stdout.reconfigure(encoding='utf-8')

DB_TESTE = 'scratch/financas_casa_teste_paga_leve.db'
conn = sqlite3.connect(DB_TESTE)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("="*80)
print(f"TESTE INTEGRADO: DUAS CONTAS PAGA LEVE, OPERAÇÃO DE DÍVIDA E SPLIT DE CATEGORIA")
print(f"Banco: {DB_TESTE}")
print("="*80)

# 1. TABELA DE CONTAS PAGA LEVE (CARLOS E FERNANDA)
cur.execute("""
CREATE TABLE IF NOT EXISTS pagaleve_contas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titular TEXT NOT NULL UNIQUE, -- 'Carlos', 'Fernanda'
    tipo_limite TEXT NOT NULL, -- 'fixo', 'sob_demanda'
    limite_total REAL, -- Limite cadastrado (ex: Carlos) ou NULL/0 para sob demanda
    ativo INTEGER DEFAULT 1,
    observacoes TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

cur.execute("""
INSERT OR IGNORE INTO pagaleve_contas (titular, tipo_limite, limite_total, observacoes)
VALUES 
    ('Carlos', 'fixo', 1200.0, 'Conta Carlos com limite pré-aprovado'),
    ('Fernanda', 'sob_demanda', 0.0, 'Conta Fernanda com aprovação sob demanda por compra')
""")
conn.commit()
print("✓ Tabela pagaleve_contas criada com Carlos e Fernanda.")

# 2. TABELA DE COMPRAS PAGA LEVE
cur.execute("""
CREATE TABLE IF NOT EXISTS pagaleve_compras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grupo_parcelamento TEXT NOT NULL UNIQUE,
    descricao TEXT NOT NULL,
    titular TEXT DEFAULT 'A Confirmar', -- 'Carlos', 'Fernanda', 'A Confirmar'
    categoria_id INTEGER REFERENCES subcategorias(id),
    valor_original REAL NOT NULL, -- Valor real original da compra
    total_parcelas INTEGER DEFAULT 4,
    valor_parcela REAL NOT NULL,
    tipo_operacao TEXT DEFAULT 'consumo', -- 'consumo', 'pagamento_divida'
    divida_vinculada_id INTEGER REFERENCES transacoes(id),
    valor_enviado_credor REAL DEFAULT 0.0,
    custo_encargos REAL DEFAULT 0.0,
    valor_financiado_total REAL NOT NULL,
    data_primeira_parcela DATE,
    status TEXT DEFAULT 'ativa', -- 'ativa', 'quitada'
    observacoes TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# 3. COLUNAS EM TRANSACOES PARA TITULAR, PARCELAMENTO E SPLIT
cur.execute("PRAGMA table_info(transacoes)")
cols_t = [c[1] for c in cur.fetchall()]

if "titular" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN titular TEXT DEFAULT 'A Confirmar'")
if "numero_parcela" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN numero_parcela INTEGER")
if "total_parcelas_compra" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN total_parcelas_compra INTEGER DEFAULT 4")
if "pagaleve_compra_id" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN pagaleve_compra_id INTEGER REFERENCES pagaleve_compras(id)")
if "subcategoria_split_id" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN subcategoria_split_id INTEGER REFERENCES subcategorias(id)")
if "valor_split_principal" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN valor_split_principal REAL")
if "valor_split_secundario" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN valor_split_secundario REAL")

conn.commit()
print("✓ Colunas de titular, parcelamento e split adicionadas em transacoes.")

# 4. REGISTRO DAS COMPRAS LEGADAS EM PAGALEVE_COMPRAS COM VALOR ORIGINAL HISTÓRICO CORRETO
# Sem inventar titular: todos os legados entram como 'A Confirmar'!
compras_legadas = [
    # (grupo_parcelamento, descricao, valor_original, total_parcelas, valor_parc)
    ("pagaleve_99food", "Almoço Domingo 99 Food - Júnior", 71.24, 4, 17.81),
    ("pagaleve_agv", "Seguro HB20 AGV", 157.56, 3, 52.52),
    ("pagaleve_ozivy", "Ozivy", 278.88, 4, 69.72),
    ("pagaleve_psyllium", "Psyllium", 30.12, 4, 7.53),
    ("pagaleve_raia", "Raia Fraldas- Venvanse", 294.52, 4, 73.63),
    ("pagaleve_whey", "Raia whey", 161.40, 4, 40.35)
]

for grp, desc, v_orig, tot_p, v_parc in compras_legadas:
    cur.execute("""
        INSERT OR IGNORE INTO pagaleve_compras 
        (grupo_parcelamento, descricao, titular, valor_original, total_parcelas, valor_parcela, valor_financiado_total)
        VALUES (?, ?, 'A Confirmar', ?, ?, ?, ?)
    """, (grp, desc, v_orig, tot_p, v_parc, v_orig))

conn.commit()
print("✓ 6 compras legadas cadastradas com titular 'A Confirmar' e valor histórico original.")

# 5. TESTE DA OPERAÇÃO ESPECIAL: PAGAMENTO DE DÍVIDA VIA PAGA LEVE (R$ 100 enviado + R$ 18 custo = 4x R$ 29,50)
print("\n--- TESTANDO OPERAÇÃO: PAGAMENTO DE DÍVIDA VIA PAGA LEVE ---")
# Vamos localizar uma dívida familiar para testar (ex: ID 11 Crediserv ou uma dívida teste)
# Vamos criar uma obrigação de dívida familiar no teste para demonstrar
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, pago, status_pagamento)
    VALUES ('2026-10-15', 'Empréstimo Familiar (Credor Teste)', 500.00, 'despesa', 'Dívidas', 'Mercado Pago', 0, 'pendente')
""")
divida_id = cur.lastrowid
print(f"Dívida original criada para teste: ID {divida_id} | Valor R$ 500.00")

# Agora executamos a operação Paga Leve:
# 1) Cadastra a compra Paga Leve do tipo 'pagamento_divida'
grp_div = "pagaleve_divida_credor_500"
cur.execute("""
    INSERT INTO pagaleve_compras (
        grupo_parcelamento, descricao, titular, valor_original, total_parcelas, valor_parcela,
        tipo_operacao, divida_vinculada_id, valor_enviado_credor, custo_encargos, valor_financiado_total
    ) VALUES (?, ?, 'Carlos', 100.0, 4, 29.50, 'pagamento_divida', ?, 100.0, 18.0, 118.0)
""", (grp_div, "Envio Credor Familiar via Paga Leve", divida_id))
pl_compra_id = cur.lastrowid

# 2) Abate R$ 100 da dívida original via pagamentos_despesas COM afeta_saldo_bancario = 0
# (pois o dinheiro não saiu da conta bancária para o credor, foi adiantado pelo Paga Leve!)
cur.execute("""
    INSERT INTO pagamentos_despesas (
        transacao_id, data_pagamento, valor_pago, valor_pago_centavos, conta_id,
        afeta_saldo_bancario, forma_pagamento, observacao
    ) VALUES (?, '2026-10-20', 100.00, 10000, 1, 0, 'Paga Leve', 'Amortização financiada via Paga Leve')
""", (divida_id,))
conn.commit()

# Verifica saldo devedor restante da dívida original:
res_div = saldo_service.obter_resumo_obrigacao(conn, divida_id)
print(f"Saldo devedor restante da dívida original após envio: R$ {res_div['saldo_devedor']} (era R$ 500.00, abateu R$ 100.00!)")
assert res_div["saldo_devedor"] == Decimal("400.00"), "O saldo da dívida original deve ser exatamente R$ 400.00!"

# 3) Cria as 4 parcelas do Paga Leve em transacoes (1 paga e 3 pendentes)
dt_base = date(2026, 10, 20)
# Parcela 1/4 paga no ato (saída de caixa real de R$ 29.50 da conta bancária)
cur.execute("""
    INSERT INTO transacoes (
        data, descricao, valor, tipo, categoria, conta, conta_id, pago, status_pagamento,
        grupo_parcelamento, titular, numero_parcela, total_parcelas_compra, pagaleve_compra_id, afeta_saldo_bancario
    ) VALUES (?, 'Envio Credor Familiar - Paga Leve 1/4', 29.50, 'despesa', 'Dívidas', 'Mercado Pago', 1, 1, 'pago', ?, 'Carlos', 1, 4, ?, 1)
""", (dt_base.strftime("%Y-%m-%d"), grp_div, pl_compra_id))
p1_id = cur.lastrowid

cur.execute("""
    INSERT INTO pagamentos_despesas (
        transacao_id, data_pagamento, valor_pago, valor_pago_centavos, conta_id,
        afeta_saldo_bancario, forma_pagamento, observacao
    ) VALUES (?, ?, 29.50, 2950, 1, 1, 'Pix', 'Entrada Paga Leve 1/4 debitada em conta')
""", (p1_id, dt_base.strftime("%Y-%m-%d")))

# Parcelas 2, 3 e 4 pendentes
for i in [2, 3, 4]:
    dt_venc = dt_base + timedelta(days=14 * (i - 1))
    cur.execute("""
        INSERT INTO transacoes (
            data, descricao, valor, tipo, categoria, conta, conta_id, pago, status_pagamento,
            grupo_parcelamento, titular, numero_parcela, total_parcelas_compra, pagaleve_compra_id, afeta_saldo_bancario
        ) VALUES (?, ?, 29.50, 'despesa', 'Dívidas', 'Mercado Pago', 1, 0, 'pendente', ?, 'Carlos', ?, 4, ?, 1)
    """, (dt_venc.strftime("%Y-%m-%d"), f"Envio Credor Familiar - Paga Leve {i}/4", grp_div, i, pl_compra_id))

conn.commit()
print("✓ Operação de dívida no Paga Leve criada com sucesso:")
print(f"  - Credor recebeu: R$ 100.00")
print(f"  - Custo de encargos da estratégia: R$ 18.00 (custo financeiro)")
print(f"  - Total financiado: R$ 118.00 (4 parcelas de R$ 29.50)")
print(f"  - Parcela 1/4: PAGA (debitou R$ 29.50 do banco)")
print(f"  - Parcelas 2/4 a 4/4: PENDENTES (R$ 88.50 em aberto no fluxo de caixa)")

# 6. TESTE DE CONSULTA PARA O CARD DA VISÃO GERAL (CONSOLIDADO E POR TITULAR)
print("\n--- TESTE DE CONSULTA PARA O NOVO CARD PAGA LEVE NO DASHBOARD ---")
def obter_dados_card_paga_leve(conn, titular_filtro=None):
    cur = conn.cursor()
    filtro_sql = ""
    params = []
    if titular_filtro and titular_filtro != "Todos":
        filtro_sql = "AND t.titular = ?"
        params.append(titular_filtro)
        
    cur.execute(f"""
        SELECT 
            COUNT(t.id) as total_parcelas_abertas,
            COALESCE(SUM(t.valor), 0.0) as valor_total_aberto,
            MIN(t.data) as proximo_vencimento
        FROM transacoes t
        WHERE (t.grupo_parcelamento LIKE 'pagaleve%' OR t.descricao LIKE '%Paga Leve%')
          AND (t.pago IS NULL OR t.pago != 1)
          {filtro_sql}
    """, params)
    row_geral = cur.fetchone()
    
    # Próximas parcelas
    cur.execute(f"""
        SELECT t.id, t.data, t.descricao, t.valor, COALESCE(t.titular, 'A Confirmar') as tit
        FROM transacoes t
        WHERE (t.grupo_parcelamento LIKE 'pagaleve%' OR t.descricao LIKE '%Paga Leve%')
          AND (t.pago IS NULL OR t.pago != 1)
          {filtro_sql}
        ORDER BY t.data ASC
        LIMIT 3
    """, params)
    proximos = cur.fetchall()
    
    # Atrasadas
    hoje_str = date.today().strftime("%Y-%m-%d")
    cur.execute(f"""
        SELECT COUNT(t.id), COALESCE(SUM(t.valor), 0.0)
        FROM transacoes t
        WHERE (t.grupo_parcelamento LIKE 'pagaleve%' OR t.descricao LIKE '%Paga Leve%')
          AND (t.pago IS NULL OR t.pago != 1)
          AND t.data < ?
          {filtro_sql}
    """, [hoje_str] + params)
    row_atraso = cur.fetchone()
    
    return {
        "titular_filtro": titular_filtro or "Consolidado Família",
        "total_parcelas_abertas": row_geral[0],
        "valor_total_aberto": Decimal(str(row_geral[1])),
        "proximo_vencimento": row_geral[2],
        "proximas_parcelas": [dict(r) for r in proximos],
        "qtd_atrasadas": row_atraso[0],
        "valor_atrasadas": Decimal(str(row_atraso[1]))
    }

card_fam = obter_dados_card_paga_leve(conn, "Todos")
print("Card Consolidado da Família:")
print(f"  Parcelas em aberto: {card_fam['total_parcelas_abertas']} | Valor total: R$ {card_fam['valor_total_aberto']:.2f}")
print(f"  Atrasadas: {card_fam['qtd_atrasadas']} (R$ {card_fam['valor_atrasadas']:.2f})")
print(f"  Próximos vencimentos:")
for p in card_fam['proximas_parcelas']:
    print(f"    - {p['data']} | R$ {p['valor']:.2f} | {p['descricao']} [Titular: {p['tit']}]")

card_carlos = obter_dados_card_paga_leve(conn, "Carlos")
print(f"\nCard Filtrado por Titular: Carlos:")
print(f"  Parcelas em aberto: {card_carlos['total_parcelas_abertas']} | Valor: R$ {card_carlos['valor_total_aberto']:.2f}")

# 7. TESTE DO SPLIT DE SUBCATEGORIA (RAIA FRALDAS + VENVANSE)
print("\n--- TESTANDO SPLIT DE CATEGORIA (FRALDAS + VENVANSE) ---")
# ID 23: Raia Fraldas- Venvanse (R$ 73.63)
# Dividir em:
# 1) Venvanse: R$ 45.00 -> Saúde -> Medicamentos (subcat_id)
# 2) Fraldas: R$ 28.63 -> Pedro -> Higiene / Fraldas (subcategoria_split_id)
cur.execute("SELECT id FROM subcategorias WHERE nome LIKE '%Medicamentos%' LIMIT 1")
sub_med_id = cur.fetchone()[0]
cur.execute("SELECT id FROM subcategorias WHERE nome LIKE '%Fraldas%' LIMIT 1")
sub_fraldas_id = cur.fetchone()[0]

cur.execute("""
    UPDATE transacoes
    SET subcategoria_id = ?, 
        valor_split_principal = 45.00,
        subcategoria_split_id = ?,
        valor_split_secundario = 28.63
    WHERE id = 23
""", (sub_med_id, sub_fraldas_id))
conn.commit()

# Verificação contábil do split:
cur.execute("""
    SELECT t.id, t.descricao, t.valor, 
           s1.nome as sub_principal, t.valor_split_principal,
           s2.nome as sub_secundaria, t.valor_split_secundario
    FROM transacoes t
    JOIN subcategorias s1 ON s1.id = t.subcategoria_id
    JOIN subcategorias s2 ON s2.id = t.subcategoria_split_id
    WHERE t.id = 23
""")
row_split = cur.fetchone()
print(f"Lançamento com Split ID {row_split['id']} ({row_split['descricao']}):")
print(f"  Valor Total: R$ {row_split['valor']:.2f}")
print(f"  Parte 1: R$ {row_split['valor_split_principal']:.2f} -> {row_split['sub_principal']}")
print(f"  Parte 2: R$ {row_split['valor_split_secundario']:.2f} -> {row_split['sub_secundaria']}")
assert Decimal(str(row_split['valor_split_principal'])) + Decimal(str(row_split['valor_split_secundario'])) == Decimal(str(row_split['valor'])), "A soma do split deve bater exatamente com o valor total!"
print("✓ Teste de split passou com integridade centavo a centavo.")

conn.close()
print("\n=== TODOS OS TESTES EM BANCO ISOLADO FORAM CONCLUÍDOS COM SUCESSO! ===")
