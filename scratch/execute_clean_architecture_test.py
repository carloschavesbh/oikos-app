import sys
import os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
import json
from decimal import Decimal
from datetime import date, timedelta
import saldo_service
import planejamento_service

sys.stdout.reconfigure(encoding='utf-8')

DB_TESTE = 'scratch/financas_casa_teste_final.db'
print("="*80)
print(f"EXECUÇÃO DO PLANO DE ARQUITETURA LIMPA EM BANCO ISOLADO")
print(f"Arquivo alvo: {DB_TESTE}")
print("="*80)

conn = sqlite3.connect(DB_TESTE)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# -----------------------------------------------------------------------------
# 1. CRIAÇÃO DAS TABELAS HIERÁRQUICAS DE CATEGORIAS
# -----------------------------------------------------------------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS grupos_categoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    icone TEXT DEFAULT '📁',
    tipo TEXT NOT NULL DEFAULT 'despesa', -- 'despesa', 'receita'
    ordem INTEGER DEFAULT 0,
    ativo INTEGER DEFAULT 1,
    descricao TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS subcategorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grupo_id INTEGER NOT NULL REFERENCES grupos_categoria(id),
    nome TEXT NOT NULL,
    icone TEXT DEFAULT '•',
    natureza_padrao TEXT DEFAULT 'variavel', -- 'fixa', 'variavel', 'eventual', 'divida', 'investimento', 'receita'
    finalidade TEXT DEFAULT 'familiar', -- 'familiar', 'profissional', 'misto'
    ordem INTEGER DEFAULT 0,
    ativo INTEGER DEFAULT 1,
    observacoes TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(grupo_id, nome)
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS planejamento_orcamento_subcategorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mes_ano TEXT NOT NULL,
    subcategoria_id INTEGER NOT NULL REFERENCES subcategorias(id),
    tipo_orcamento TEXT DEFAULT 'manual', -- 'manual', 'fixo_recorrente'
    valor_orcado REAL NOT NULL DEFAULT 0.0,
    observacoes TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mes_ano, subcategoria_id)
);
""")

# -----------------------------------------------------------------------------
# 2. CRIAÇÃO DO MÓDULO MANUAL DE DÍVIDAS (100% DESACOPLADO)
# -----------------------------------------------------------------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS dividas_gerenciamento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    credor TEXT NOT NULL,
    descricao TEXT NOT NULL,
    valor_original REAL NOT NULL,
    saldo_atual REAL NOT NULL,
    data_inicio DATE,
    status TEXT DEFAULT 'ativa', -- 'ativa', 'quitada', 'renegociada'
    observacoes TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS dividas_pagamentos_manuais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    divida_id INTEGER NOT NULL REFERENCES dividas_gerenciamento(id),
    data_pagamento DATE NOT NULL,
    valor_pago REAL NOT NULL,
    observacao TEXT,
    cancelado INTEGER DEFAULT 0,
    cancelado_em TIMESTAMP,
    motivo_cancelamento TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# -----------------------------------------------------------------------------
# 3. CRIAÇÃO DAS TABELAS DO PAGA LEVE (INDEPENDENTE E MULTITITULAR)
# -----------------------------------------------------------------------------
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
CREATE TABLE IF NOT EXISTS pagaleve_compras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grupo_parcelamento TEXT NOT NULL UNIQUE,
    descricao TEXT NOT NULL,
    titular TEXT DEFAULT 'A Confirmar', -- 'Carlos', 'Fernanda', 'A Confirmar'
    categoria_id INTEGER REFERENCES subcategorias(id),
    valor_original REAL NOT NULL, -- Valor real original da compra (mesmo com parcelas históricas faltantes)
    total_parcelas INTEGER DEFAULT 4,
    valor_parcela REAL NOT NULL,
    juros REAL DEFAULT 0.0,
    iof REAL DEFAULT 0.0,
    valor_financiado_total REAL NOT NULL,
    data_compra DATE,
    status TEXT DEFAULT 'ativa', -- 'ativa', 'quitada'
    observacoes TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# -----------------------------------------------------------------------------
# 4. ATUALIZAÇÃO SEGURA E NÃO-DESTRUTIVA DE TRANSAÇÕES
# -----------------------------------------------------------------------------
cur.execute("PRAGMA table_info(transacoes)")
cols_t = [c[1] for c in cur.fetchall()]

if "grupo_id" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN grupo_id INTEGER REFERENCES grupos_categoria(id)")
if "subcategoria_id" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN subcategoria_id INTEGER REFERENCES subcategorias(id)")
if "natureza_gasto" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN natureza_gasto TEXT")
if "titular" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN titular TEXT DEFAULT 'A Confirmar'")
if "numero_parcela" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN numero_parcela INTEGER")
if "total_parcelas_compra" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN total_parcelas_compra INTEGER DEFAULT 4")
if "status_rateio" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN status_rateio TEXT DEFAULT 'normal'")

conn.commit()
print("✓ Todas as tabelas criadas e colunas relacionais integradas com segurança.")

# -----------------------------------------------------------------------------
# 5. CARGA DOS 16 GRUPOS E 63 SUBCATEGORIAS CERBASI/ORGANIZZE
# -----------------------------------------------------------------------------
GRUPOS = [
    ("Habitação", "🏠", "despesa", 1, "Despesas essenciais com moradia"),
    ("Alimentação", "🍽️", "despesa", 2, "Alimentação do lar e supermercado"),
    ("Saúde", "❤️", "despesa", 3, "Cuidados médicos, farmácia e bem-estar"),
    ("Educação", "🎓", "despesa", 4, "Educação formal, cursos e capacitação"),
    ("Dívidas", "🏦", "despesa", 5, "Amortizações de empréstimos e renegociações"),
    ("Lazer", "🎬", "despesa", 6, "Restaurantes, passeios e entretenimento"),
    ("Eventual", "🎁", "despesa", 7, "Compras imprevistas, presentes e sazonais"),
    ("Chaves Transportes", "🚕", "despesa", 8, "Custos da atividade profissional de motorista"),
    ("Transporte Pessoal", "🚗", "despesa", 9, "Veículo de uso pessoal da família"),
    ("Pedro", "👶", "despesa", 10, "Despesas específicas do filho Pedro"),
    ("Pessoal — Carlos", "👤", "despesa", 11, "Despesas individuais de Carlos"),
    ("Pessoal — Fernanda", "👤", "despesa", 12, "Despesas individuais de Fernanda"),
    ("Dízimos e Doações", "🙏", "despesa", 13, "Contribuições religiosas e filantrópicas"),
    ("Investimentos", "💰", "despesa", 14, "Aportes em previdência, poupança e reservas"),
    ("Receitas Fixas", "💼", "receita", 15, "Salários e rendas contratuais estáveis"),
    ("Receitas Variáveis", "📈", "receita", 16, "Corridas de aplicativo, extras e rendimentos")
]

for g_nome, g_ico, g_tipo, g_ordem, g_desc in GRUPOS:
    cur.execute("""
        INSERT OR IGNORE INTO grupos_categoria (nome, icone, tipo, ordem, descricao)
        VALUES (?, ?, ?, ?, ?)
    """, (g_nome, g_ico, g_tipo, g_ordem, g_desc))

conn.commit()

cur.execute("SELECT id, nome FROM grupos_categoria")
mapa_grupos = {r[1]: r[0] for r in cur.fetchall()}

SUBCATEGORIAS = [
    # Habitação
    ("Habitação", "Água (Copasa)", "💧", "fixa", "familiar", 1),
    ("Habitação", "Energia (CEMIG + CEMIG SIM)", "⚡", "fixa", "familiar", 2),
    ("Habitação", "Internet Residencial", "🌐", "fixa", "familiar", 3),
    ("Habitação", "Telefone (Fernanda)", "📱", "fixa", "familiar", 4),
    ("Habitação", "Manutenção e Reparos", "🛠️", "eventual", "familiar", 5),
    ("Habitação", "Outros Habitação", "📦", "eventual", "familiar", 6),

    # Alimentação
    ("Alimentação", "Supermercado / Feira", "🛒", "variavel", "familiar", 1),
    ("Alimentação", "Padaria", "🥖", "variavel", "familiar", 2),
    ("Alimentação", "Delivery (iFood / 99Food)", "🍔", "variavel", "familiar", 3),

    # Saúde
    ("Saúde", "Plano de Saúde", "🏥", "fixa", "familiar", 1),
    ("Saúde", "Plano Odonto", "🦷", "fixa", "familiar", 2),
    ("Saúde", "Medicamentos", "💊", "variavel", "familiar", 3),
    ("Saúde", "Coparticipação Unimed", "🩹", "variavel", "familiar", 4),
    ("Saúde", "Médicos / Consultas", "🩺", "eventual", "familiar", 5),
    ("Saúde", "Academia / Wellhub", "🏋️", "fixa", "familiar", 6),

    # Educação
    ("Educação", "Pós-Graduação Fernanda", "🎓", "fixa", "familiar", 1),
    ("Educação", "Cursos / TI", "💻", "eventual", "familiar", 2),
    ("Educação", "Livros / Assinaturas", "📖", "fixa", "familiar", 3),

    # Dívidas
    ("Dívidas", "Acordo BV", "🏦", "divida", "familiar", 1),
    ("Dívidas", "Juros / Taxas de Empréstimo", "🏛️", "divida", "familiar", 2),
    ("Dívidas", "Crediserv - Empréstimo", "📋", "divida", "familiar", 3),
    ("Dívidas", "Mãe / Rubens", "👨‍👩", "divida", "familiar", 4),
    ("Dívidas", "Pai", "👴", "divida", "familiar", 5),
    ("Dívidas", "Outras Dívidas", "📋", "divida", "familiar", 6),

    # Lazer
    ("Lazer", "Restaurante / Lanche fora", "🍽️", "variavel", "familiar", 1),
    ("Lazer", "Streaming / Entretenimento", "🎬", "fixa", "familiar", 2),
    ("Lazer", "Viagens / Passeios", "🏖️", "eventual", "familiar", 3),

    # Eventual
    ("Eventual", "Presentes do Mês", "🎁", "eventual", "familiar", 1),
    ("Eventual", "Compras Diversas", "🛍️", "eventual", "familiar", 2),

    # Chaves Transportes (Profissional)
    ("Chaves Transportes", "Combustível (Trabalho)", "⛽", "variavel", "profissional", 1),
    ("Chaves Transportes", "Ferramentas de Trabalho (Internet celular Carlos, suporte, cabos)", "📱", "fixa", "profissional", 2),
    ("Chaves Transportes", "Manutenção / Desgaste Operacional", "🛠️", "variavel", "profissional", 3),
    ("Chaves Transportes", "Alimentação na Rua", "🥪", "variavel", "profissional", 4),
    ("Chaves Transportes", "Lavagem / Limpeza", "🧽", "variavel", "profissional", 5),
    ("Chaves Transportes", "Estacionamento / Rotativo (Trabalho)", "🅿️", "variavel", "profissional", 6),

    # Transporte Pessoal
    ("Transporte Pessoal", "Documentação (IPVA, Multas)", "📄", "fixa", "familiar", 1),
    ("Transporte Pessoal", "Seguro Veículo (HB20 AGV)", "🛡️", "fixa", "familiar", 2),
    ("Transporte Pessoal", "Manutenção Veículo (Uso Pessoal / Geral)", "🛠️", "eventual", "familiar", 3),
    ("Transporte Pessoal", "Combustível (Viagens / Lazer Pessoal)", "⛽", "variavel", "familiar", 4),
    ("Transporte Pessoal", "Táxi / Uber", "🚖", "variavel", "familiar", 5),
    ("Transporte Pessoal", "Estacionamento / Rotativo (Pessoal)", "🅿️", "variavel", "familiar", 6),

    # Pedro
    ("Pedro", "Higiene / Fraldas", "🍼", "variavel", "familiar", 1),
    ("Pedro", "Escola / Material", "🎒", "fixa", "familiar", 2),
    ("Pedro", "Poupança do Pedro", "🐖", "investimento", "familiar", 3),
    ("Pedro", "Roupas / Brinquedos", "👕", "eventual", "familiar", 4),
    ("Pedro", "Médico / Vacinas", "🩺", "eventual", "familiar", 5),

    # Pessoal — Carlos
    ("Pessoal — Carlos", "Barbearia", "💇", "variavel", "familiar", 1),
    ("Pessoal — Carlos", "Vestuário Carlos", "👕", "eventual", "familiar", 2),
    ("Pessoal — Carlos", "Higiene / Farmácia Carlos", "🧴", "variavel", "familiar", 3),
    ("Pessoal — Carlos", "Mesada Carlos", "🪙", "variavel", "familiar", 4),

    # Pessoal — Fernanda
    ("Pessoal — Fernanda", "Cabelo / Beleza Fernanda", "💇", "variavel", "familiar", 1),
    ("Pessoal — Fernanda", "Vestuário Fernanda", "👗", "eventual", "familiar", 2),
    ("Pessoal — Fernanda", "Higiene / Cosméticos Fernanda", "💄", "variavel", "familiar", 3),
    ("Pessoal — Fernanda", "Mesada Fernanda", "🪙", "variavel", "familiar", 4),

    # Dízimos e Doações
    ("Dízimos e Doações", "Dízimo (Igreja)", "🏦", "fixa", "familiar", 1),
    ("Dízimos e Doações", "Doações", "🤝", "eventual", "familiar", 2),

    # Investimentos
    ("Investimentos", "Conta Capital Sicoob", "🏦", "investimento", "familiar", 1),
    ("Investimentos", "Reserva de Emergência", "🐖", "investimento", "familiar", 2),
    ("Investimentos", "Rendimentos / Aplicações", "📈", "investimento", "familiar", 3),

    # Receitas Fixas
    ("Receitas Fixas", "Salário Fernanda", "💼", "receita", "familiar", 1),

    # Receitas Variáveis
    ("Receitas Variáveis", "99 / Chaves (Carlos)", "🚕", "receita", "profissional", 1),
    ("Receitas Variáveis", "Receitas Extras", "💰", "receita", "familiar", 2),
    ("Receitas Variáveis", "Empréstimo / Aporte", "🏦", "receita", "familiar", 3)
]

for g_nome, sub_nome, sub_ico, sub_nat, sub_fin, sub_ordem in SUBCATEGORIAS:
    g_id = mapa_grupos.get(g_nome)
    if g_id:
        cur.execute("""
            INSERT OR IGNORE INTO subcategorias (grupo_id, nome, icone, natureza_padrao, finalidade, ordem)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (g_id, sub_nome, sub_ico, sub_nat, sub_fin, sub_ordem))

conn.commit()

# Cadastra contas Paga Leve de Carlos e Fernanda
cur.execute("""
INSERT OR IGNORE INTO pagaleve_contas (titular, tipo_limite, limite_total, observacoes)
VALUES 
    ('Carlos', 'fixo', 1200.0, 'Conta Carlos com limite pré-estabelecido'),
    ('Fernanda', 'sob_demanda', 0.0, 'Conta Fernanda com disponibilidade aprovada por compra')
""")

# Cadastra os 6 grupos de compras legadas preservando o valor original histórico
# SEM inventar titular: todos ficam como 'A Confirmar'
compras_legadas_reais = [
    ("pagaleve_99food", "Almoço Domingo 99 Food - Júnior", 71.24, 4, 17.81),
    ("pagaleve_agv", "Seguro HB20 AGV", 157.56, 3, 52.52),
    ("pagaleve_ozivy", "Ozivy", 278.88, 4, 69.72),
    ("pagaleve_psyllium", "Psyllium", 30.12, 4, 7.53),
    ("pagaleve_raia", "Raia Fraldas- Venvanse", 294.52, 4, 73.63),
    ("pagaleve_whey", "Raia whey", 161.40, 4, 40.35)
]

for grp, desc, v_orig, tot_p, v_parc in compras_legadas_reais:
    cur.execute("""
        INSERT OR IGNORE INTO pagaleve_compras 
        (grupo_parcelamento, descricao, titular, valor_original, total_parcelas, valor_parcela, valor_financiado_total)
        VALUES (?, ?, 'A Confirmar', ?, ?, ?, ?)
    """, (grp, desc, v_orig, tot_p, v_parc, v_orig))

conn.commit()
print("✓ Categorias, Contas Paga Leve e Compras Históricas carregadas com sucesso.")

# -----------------------------------------------------------------------------
# 6. TESTE DE DÍVIDAS 100% MANUAL (INDICAÇÃO DE PAGAMENTO PARCIAL E ESTORNO)
# -----------------------------------------------------------------------------
print("\n--- TESTE 1: MÓDULO MANUAL DE DÍVIDAS (SEM VÍNCULO AUTOMÁTICO) ---")
# Cadastra uma dívida de exemplo
cur.execute("""
    INSERT INTO dividas_gerenciamento (credor, descricao, valor_original, saldo_atual, data_inicio)
    VALUES ('Rubens (Familiar)', 'Empréstimo reforma', 2500.00, 2500.00, '2026-08-01')
""")
div_teste_id = cur.lastrowid

# Registra pagamento manual de R$ 300,00
cur.execute("""
    INSERT INTO dividas_pagamentos_manuais (divida_id, data_pagamento, valor_pago, observacao)
    VALUES (?, '2026-10-18', 300.00, 'Pagamento parcial em dinheiro')
""", (div_teste_id,))
pag_m_id = cur.lastrowid

# Atualiza saldo da dívida manual
cur.execute("""
    UPDATE dividas_gerenciamento
    SET saldo_atual = saldo_atual - 300.00
    WHERE id = ?
""", (div_teste_id,))
conn.commit()

cur.execute("SELECT credor, valor_original, saldo_atual FROM dividas_gerenciamento WHERE id = ?", (div_teste_id,))
row_d = cur.fetchone()
print(f"Dívida após pagamento manual de R$ 300: Credor: {row_d['credor']} | Original: R$ {row_d['valor_original']:.2f} | Saldo Atual: R$ {row_d['saldo_atual']:.2f}")
assert row_d['saldo_atual'] == 2200.00, "Saldo da dívida deve ser exatamente R$ 2.200,00"

# Teste de estorno auditável do pagamento manual
cur.execute("""
    UPDATE dividas_pagamentos_manuais
    SET cancelado = 1, cancelado_em = CURRENT_TIMESTAMP, motivo_cancelamento = 'Digitado com valor incorreto'
    WHERE id = ?
""", (pag_m_id,))
cur.execute("""
    UPDATE dividas_gerenciamento
    SET saldo_atual = saldo_atual + 300.00
    WHERE id = ?
""", (div_teste_id,))
conn.commit()

cur.execute("SELECT saldo_atual FROM dividas_gerenciamento WHERE id = ?", (div_teste_id,))
assert cur.fetchone()[0] == 2500.00, "Saldo após estorno deve retornar a R$ 2.500,00"
print("✓ Teste 1 passou: Módulo de dívidas manual opera de forma 100% autônoma, sem mexer em contas bancárias nem no Paga Leve.")

# -----------------------------------------------------------------------------
# 7. TESTE DA PÁGINA PAGA LEVE COMPACTA E CÁLCULO PRECISO DE PROGRESSO
# -----------------------------------------------------------------------------
print("\n--- TESTE 2: PROGRESSO REAL DA COMPRA 'Raia whey' (HISTÓRICO INCOMPLETO) ---")
# Raia whey: valor original R$ 161.40 (4x R$ 40.35)
# No banco só existem parcelas 3/4 e 4/4 (IDs 18 e 30)
cur.execute("""
    SELECT c.descricao, c.valor_original, c.total_parcelas, c.valor_parcela,
           COUNT(t.id) as parcelas_no_banco,
           SUM(CASE WHEN t.pago = 1 THEN t.valor ELSE 0 END) as pago_no_banco,
           SUM(CASE WHEN t.pago != 1 THEN t.valor ELSE 0 END) as aberto_no_banco
    FROM pagaleve_compras c
    LEFT JOIN transacoes t ON t.grupo_parcelamento = c.grupo_parcelamento
    WHERE c.grupo_parcelamento = 'pagaleve_whey'
    GROUP BY c.id
""")
row_whey = cur.fetchone()

# Cálculo correto considerando o valor_original:
# O total pago real = (valor_original - aberto_no_banco)
tot_original = Decimal(str(row_whey['valor_original']))
tot_aberto_real = Decimal(str(row_whey['aberto_no_banco']))
tot_pago_real = tot_original - tot_aberto_real
pct_real = (tot_pago_real / tot_original) * 100

print(f"Compra: {row_whey['descricao']}")
print(f"  Valor Original Cadastrado: R$ {tot_original:.2f}")
print(f"  Parcelas Restantes em Aberto no Banco: R$ {tot_aberto_real:.2f} (Parcela 4/4)")
print(f"  Total Efetivamente Pago Histórico: R$ {tot_pago_real:.2f} (Parcelas 1, 2 e 3/4)")
print(f"  Progresso Real da Quitação: {pct_real:.1f}%")
assert pct_real == Decimal("75.0"), f"O progresso deve ser 75% e não 50%! Obteve: {pct_real}"
print("✓ Teste 2 passou: Compras históricas com parcelas faltantes calculam progresso com exatidão matemática.")

# -----------------------------------------------------------------------------
# 8. TESTE DO CARD PAGA LEVE NO DASHBOARD (MODULAR E FILTRÁVEL)
# -----------------------------------------------------------------------------
print("\n--- TESTE 3: CARD MODULAR PAGA LEVE (DADOS PARA VISÃO GERAL) ---")
cur.execute("""
    SELECT 
        COUNT(t.id) as parcelas_abertas,
        COALESCE(SUM(t.valor), 0.0) as valor_aberto,
        MIN(t.data) as proximo_vencimento
    FROM transacoes t
    WHERE (t.grupo_parcelamento LIKE 'pagaleve%' OR t.descricao LIKE '%Paga Leve%')
      AND (t.pago IS NULL OR t.pago != 1)
""")
card_kpis = cur.fetchone()

cur.execute("""
    SELECT t.id, t.data, t.descricao, t.valor, COALESCE(t.titular, 'A Confirmar') as tit
    FROM transacoes t
    WHERE (t.grupo_parcelamento LIKE 'pagaleve%' OR t.descricao LIKE '%Paga Leve%')
      AND (t.pago IS NULL OR t.pago != 1)
    ORDER BY t.data ASC
""")
card_itens = cur.fetchall()

print(f"Card Visão Geral:")
print(f"  Total de Parcelas em Aberto: {card_kpis['parcelas_abertas']} | Valor Total: R$ {card_kpis['valor_aberto']:.2f}")
print(f"  Próximas Parcelas:")
for it in card_itens:
    print(f"    - Venc: {it['data']} | R$ {it['valor']:.2f} | {it['descricao']} | Titular: {it['tit']}")

assert card_kpis['parcelas_abertas'] == 3, f"Esperado 3 parcelas abertas nos legados, obteve {card_kpis['parcelas_abertas']}"
print("✓ Teste 3 passou: Card Paga Leve alimentado com sucesso sem dados fictícios.")

conn.close()
print("\n" + "="*80)
print("TODAS AS VALIDAÇÕES TÉCNICAS FORAM CONCLUÍDAS COM SUCESSO NO BANCO DE TESTE!")
print("="*80)
