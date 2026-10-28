import sys
import os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3
import json
from decimal import Decimal

def aplicar_migracao(db_path: str):
    print(f"\n--- APLICANDO MIGRAÇÃO NO BANCO: {db_path} ---")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Tabelas de Grupos e Subcategorias
    cur.execute("""
    CREATE TABLE IF NOT EXISTS grupos_categoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        icone TEXT DEFAULT '📁',
        tipo TEXT NOT NULL DEFAULT 'despesa',
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
        natureza_padrao TEXT DEFAULT 'variavel',
        finalidade TEXT DEFAULT 'familiar',
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
        tipo_orcamento TEXT DEFAULT 'manual',
        valor_orcado REAL NOT NULL DEFAULT 0.0,
        observacoes TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(mes_ano, subcategoria_id)
    );
    """)

    # 2. Tabelas de Dívidas (Desacopladas)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dividas_gerenciamento (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        credor TEXT NOT NULL,
        descricao TEXT NOT NULL,
        tipo_divida TEXT NOT NULL DEFAULT 'livre', -- 'livre', 'negociada'
        valor_original REAL NOT NULL,
        saldo_atual REAL NOT NULL,
        meta_voluntaria_mensal REAL DEFAULT 0.0,
        meta_voluntaria_semanal REAL DEFAULT 0.0,
        acordo_parcelas INTEGER,
        acordo_valor_parcela REAL,
        acordo_grupo_parcelamento TEXT,
        data_inicio DATE,
        status TEXT DEFAULT 'ativa',
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

    # 3. Tabelas de Paga Leve (Independentes)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS pagaleve_contas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titular TEXT NOT NULL UNIQUE,
        tipo_limite TEXT NOT NULL,
        limite_total REAL,
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
        titular TEXT DEFAULT 'A Confirmar',
        categoria_id INTEGER REFERENCES subcategorias(id),
        valor_original REAL NOT NULL,
        total_parcelas INTEGER DEFAULT 4,
        valor_parcela REAL NOT NULL,
        juros REAL DEFAULT 0.0,
        iof REAL DEFAULT 0.0,
        valor_financiado_total REAL NOT NULL,
        data_compra DATE,
        status TEXT DEFAULT 'ativa',
        observacoes TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Adicionar colunas em transações preservando integridade
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

    # 5. Carga de Grupos
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

    # 6. Carga de Subcategorias
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

    # Mapa de subcategorias (grupo_nome, subcat_nome) -> (subcat_id, natureza)
    cur.execute("""
        SELECT s.id, g.nome as grupo_nome, s.nome as subcat_nome, s.natureza_padrao
        FROM subcategorias s
        JOIN grupos_categoria g ON g.id = s.grupo_id
    """)
    mapa_subcats = {(r["grupo_nome"], r["subcat_nome"]): (r["id"], r["natureza_padrao"]) for r in cur.fetchall()}

    # 7. Contas Paga Leve de Carlos e Fernanda
    cur.execute("""
    INSERT OR IGNORE INTO pagaleve_contas (titular, tipo_limite, limite_total, observacoes)
    VALUES 
        ('Carlos', 'fixo', 1200.0, 'Conta Carlos com limite pré-estabelecido'),
        ('Fernanda', 'sob_demanda', 0.0, 'Conta Fernanda com disponibilidade aprovada por compra')
    """)

    # 8. Compras Legadas Paga Leve com titular 'A Confirmar'
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

    # 9. Mapeamento Seguro de Lançamentos Inequívocos em transacoes
    # Preservando ambiguidades como 'pendente_confirmacao'
    MAPEAMENTOS_SEGUROS = [
        (2, "Habitação", "Água (Copasa)"),
        (15, "Habitação", "Energia (CEMIG + CEMIG SIM)"),
        (32, "Habitação", "Energia (CEMIG + CEMIG SIM)"),
        (16, "Habitação", "Telefone (Fernanda)"),
        (14, "Lazer", "Streaming / Entretenimento"),
        (26, "Educação", "Livros / Assinaturas"),
        (17, "Educação", "Pós-Graduação Fernanda"),
        (9, "Saúde", "Plano de Saúde"),
        (10, "Saúde", "Plano Odonto"),
        (20, "Saúde", "Coparticipação Unimed"),
        (21, "Saúde", "Academia / Wellhub"),
        (24, "Saúde", "Academia / Wellhub"),
        (5, "Saúde", "Medicamentos"),
        (8, "Saúde", "Medicamentos"),
        (6, "Transporte Pessoal", "Seguro Veículo (HB20 AGV)"),
        (33, "Transporte Pessoal", "Documentação (IPVA, Multas)"),
        (19, "Lazer", "Restaurante / Lanche fora"),
        (31, "Lazer", "Restaurante / Lanche fora"),
        (37, "Alimentação", "Supermercado / Feira"),
        (38, "Alimentação", "Supermercado / Feira"),
        (27, "Dívidas", "Acordo BV"),
        (11, "Dívidas", "Crediserv - Empréstimo"),
        (12, "Investimentos", "Conta Capital Sicoob"),
        (28, "Pessoal — Carlos", "Barbearia"),
        (7, "Receitas Fixas", "Salário Fernanda"),
    ]

    for t_id, g_nome, s_nome in MAPEAMENTOS_SEGUROS:
        g_id = mapa_grupos[g_nome]
        s_id, nat = mapa_subcats[(g_nome, s_nome)]
        cur.execute("""
            UPDATE transacoes
            SET grupo_id = ?, subcategoria_id = ?, natureza_gasto = ?
            WHERE id = ?
        """, (g_id, s_id, nat, t_id))

    # Sinaliza lançamentos ambíguos explicitamente sem rateios fictícios:
    cur.execute("UPDATE transacoes SET status_rateio = 'pendente_confirmacao' WHERE id = 29") # Internet Banda Larga
    cur.execute("UPDATE transacoes SET status_rateio = 'pendente_rateio' WHERE id IN (3, 23)") # Raia Fraldas/Venvanse
    cur.execute("UPDATE transacoes SET status_rateio = 'pendente_confirmacao' WHERE id IN (18, 30)") # Whey
    cur.execute("UPDATE transacoes SET status_rateio = 'liquidacao_cartao' WHERE id = 13") # Pagamento fatura
    cur.execute("UPDATE transacoes SET status_rateio = 'abertura_saldo' WHERE id = 1") # Saldo inicial

    # Atualiza o config_dashboard para incluir 'paga_leve' nas visíveis se ainda não estiver
    cur.execute("SELECT valor FROM config_dashboard WHERE chave = 'visiveis'")
    vis_row = cur.fetchone()
    if vis_row:
        vis_dict = json.loads(vis_row[0])
        if "paga_leve" not in vis_dict:
            vis_dict["paga_leve"] = True
            cur.execute("UPDATE config_dashboard SET valor = ? WHERE chave = 'visiveis'", (json.dumps(vis_dict),))

    conn.commit()
    conn.close()
    print("✓ Migração concluída com sucesso absoluto!")

if __name__ == "__main__":
    # Testar na cópia primeiro
    db_teste_clone = "scratch/financas_casa_teste_preflight.db"
    import shutil
    shutil.copy2("financas_casa.db", db_teste_clone)
    aplicar_migracao(db_teste_clone)
    print("✓ Pré-teste em clone finalizado com sucesso.")
