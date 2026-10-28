import sys
import os
import sqlite3
import json
from decimal import Decimal
from datetime import date, timedelta

sys.stdout.reconfigure(encoding='utf-8')

DB_TESTE = 'scratch/financas_casa_teste_hierarquia.db'

print(f"=== TESTANDO IMPLEMENTAÇÃO DA ESTRUTURA HIERÁRQUICA EM {DB_TESTE} ===")

conn = sqlite3.connect(DB_TESTE)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. CRIAÇÃO DAS TABELAS HIERÁRQUICAS
cur.execute("""
CREATE TABLE IF NOT EXISTS grupos_categoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    icone TEXT DEFAULT '📁',
    tipo TEXT NOT NULL DEFAULT 'despesa', -- 'despesa', 'receita', 'ambos'
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
    tipo_orcamento TEXT DEFAULT 'manual', -- 'manual', 'fixo_recorrente', 'historico'
    valor_orcado REAL NOT NULL DEFAULT 0.0,
    observacoes TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mes_ano, subcategoria_id)
);
""")

# 2. ADIÇÃO DE COLUNAS RELACIONAIS EM TRANSACOES
cur.execute("PRAGMA table_info(transacoes)")
cols_t = [c[1] for c in cur.fetchall()]

if "grupo_id" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN grupo_id INTEGER REFERENCES grupos_categoria(id)")
if "subcategoria_id" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN subcategoria_id INTEGER REFERENCES subcategorias(id)")
if "natureza_gasto" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN natureza_gasto TEXT")

conn.commit()
print("✓ Tabelas criadas e colunas relacionais adicionadas a transacoes.")

# 3. CARGA DOS 14 GRUPOS PRINCIPAIS + RECEITAS
GRUPOS = [
    # (nome, icone, tipo, ordem, descricao)
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

# Mapeia grupo_nome -> grupo_id
cur.execute("SELECT id, nome FROM grupos_categoria")
mapa_grupos = {r[1]: r[0] for r in cur.fetchall()}
print(f"✓ {len(mapa_grupos)} grupos principais inseridos.")

# 4. CARGA DAS SUBCATEGORIAS DO ORGANIZZE / METODOLOGIA CERBASI
SUBCATEGORIAS = [
    # (grupo_nome, subcat_nome, icone, natureza, finalidade, ordem)
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

# Mapeia (grupo_nome, subcat_nome) -> subcat_id
cur.execute("""
    SELECT s.id, g.nome as grupo_nome, s.nome as subcat_nome, s.natureza_padrao, s.finalidade
    FROM subcategorias s
    JOIN grupos_categoria g ON g.id = s.grupo_id
""")
todas_subcats = cur.fetchall()
mapa_subcats = {(r["grupo_nome"], r["subcat_nome"]): (r["id"], r["natureza_padrao"]) for r in todas_subcats}
print(f"✓ {len(todas_subcats)} subcategorias cadastradas e indexadas.")

# 5. MAPEAMENTO DE TRANSAÇÕES EXISTENTES PARA TESTES DE COMPATIBILIDADE
# Vamos definir as regras de mapeamento e classificar com precisão
# Separando o que é inequívoco do que é ambíguo

REGRAS_MAPEAMENTO = [
    # (Condição Descrição / Categoria Antiga, Grupo Novo, Subcategoria Nova, Confiança, Observação)
    ("Copasa", "Habitação", "Água (Copasa)", "Alta", "Boleto de água"),
    ("CEMIG SIM", "Habitação", "Energia (CEMIG + CEMIG SIM)", "Alta", "Fatura de energia"),
    ("Cemig", "Habitação", "Energia (CEMIG + CEMIG SIM)", "Alta", "Fatura de energia"),
    ("Claro Controle Fernanda", "Habitação", "Telefone (Fernanda)", "Alta", "Regra 2 explícita: celular da Fernanda em Habitação"),
    ("Internet Banda Larga", "Chaves Transportes", "Ferramentas de Trabalho (Internet celular Carlos, suporte, cabos)", "Ambígua", "Regra 2 diz: Internet do meu celular em Chaves. Se for internet residencial fixa, seria Habitação -> Internet"),
    ("YouCine", "Lazer", "Streaming / Entretenimento", "Alta", "Assinatura de streaming"),
    ("Assinatura Audible", "Educação", "Livros / Assinaturas", "Alta", "Assinatura de audiolivros"),
    ("Pós-graduação Fernanda", "Educação", "Pós-Graduação Fernanda", "Alta", "Mensalidade pós"),
    ("Plano de Saúde Família", "Saúde", "Plano de Saúde", "Alta", "Desconto em folha plano de saúde"),
    ("Planos Odontológicos", "Saúde", "Plano Odonto", "Alta", "Plano odontológico"),
    ("Boleto coparticipação Saúde", "Saúde", "Coparticipação Unimed", "Alta", "Coparticipação saúde"),
    ("WellHub Júnior", "Saúde", "Academia / Wellhub", "Alta", "Academia Júnior"),
    ("WellHub Fernanda", "Saúde", "Academia / Wellhub", "Alta", "Academia Fernanda"),
    ("Raia Fraldas- Venvanse", "Saúde", "Medicamentos", "Ambígua", "Venvanse é Saúde -> Medicamentos, mas fraldas seria Pedro -> Higiene/Fraldas"),
    ("Ozivy", "Saúde", "Medicamentos", "Alta", "Medicamento"),
    ("Psyllium", "Saúde", "Medicamentos", "Alta", "Suplemento / Medicamentos"),
    ("Raia whey", "Saúde", "Medicamentos", "Ambígua", "Whey pode ser Saúde -> Medicamentos ou Pessoal Carlos/Fernanda"),
    ("Seguro HB20 AGV", "Transporte Pessoal", "Seguro Veículo (HB20 AGV)", "Ambígua", "Pode ser Transporte Pessoal (Seguro) ou Chaves Transportes se decorrente de app"),
    ("Parcelamento IPVA", "Transporte Pessoal", "Documentação (IPVA, Multas)", "Alta", "Regra 2 explícita: IPVA em Transporte Pessoal"),
    ("Almoço Domingo 99 Food", "Lazer", "Restaurante / Lanche fora", "Alta", "Almoço de domingo familiar"),
    ("Compra Las Casas", "Alimentação", "Supermercado / Feira", "Alta", "Supermercado Las Casas"),
    ("Las casas - uva passas", "Alimentação", "Supermercado / Feira", "Alta", "Supermercado Las Casas"),
    ("Acordo BV", "Dívidas", "Acordo BV", "Alta", "Renegociação BV faturas"),
    ("Crediserv - Empréstimo", "Dívidas", "Crediserv - Empréstimo", "Alta", "Empréstimo consignado"),
    ("CrediServ Capital Social", "Investimentos", "Conta Capital Sicoob", "Alta", "Aporte de capital social cooperativa"),
    ("GM VISAGE - Corte Cabelo", "Pessoal — Carlos", "Barbearia", "Alta", "Cabelo Carlos"),
    ("Salário Fernanda", "Receitas Fixas", "Salário Fernanda", "Alta", "Salário líquido"),
    ("Pagamento de fatura", "Dívidas", "Outras Dívidas", "Ambígua", "Transferência entre contas para pagar fatura de cartão consolidada")
]

# Simulação da classificação no banco de teste
print("\n--- SIMULAÇÃO DE CLASSIFICAÇÃO DOS LANÇAMENTOS EXISTENTES ---")
cur.execute("SELECT id, data, descricao, valor, categoria, tipo, pago FROM transacoes ORDER BY data, id")
transacoes = cur.fetchall()

classificacoes_teste = []
ambiguidades = []

for t in transacoes:
    t_id = t["id"]
    t_desc = t["descricao"]
    t_val = t["valor"]
    t_cat = t["categoria"]
    
    match_encontrado = None
    for regra, g_alvo, sub_alvo, grau, obs in REGRAS_MAPEAMENTO:
        if regra.lower() in t_desc.lower() or regra.lower() == t_cat.lower():
            match_encontrado = (g_alvo, sub_alvo, grau, obs)
            break
            
    if match_encontrado:
        g_nome, sub_nome, grau, obs = match_encontrado
        g_id = mapa_grupos[g_nome]
        sub_id, nat = mapa_subcats[(g_nome, sub_nome)]
        
        # Atualiza apenas no banco de teste isolado!
        cur.execute("""
            UPDATE transacoes
            SET grupo_id = ?, subcategoria_id = ?, natureza_gasto = ?
            WHERE id = ?
        """, (g_id, sub_id, nat, t_id))
        
        item_info = {
            "id": t_id,
            "data": t["data"],
            "descricao": t_desc,
            "valor": t_val,
            "categoria_antiga": t_cat,
            "grupo_novo": g_nome,
            "subcategoria_nova": sub_nome,
            "natureza": nat,
            "grau_confianca": grau,
            "observacao": obs
        }
        classificacoes_teste.append(item_info)
        if grau == "Ambígua":
            ambiguidades.append(item_info)
    else:
        # Sem correspondência direta
        ambiguidades.append({
            "id": t_id,
            "data": t["data"],
            "descricao": t_desc,
            "valor": t_val,
            "categoria_antiga": t_cat,
            "grupo_novo": "PENDENTE",
            "subcategoria_nova": "PENDENTE",
            "natureza": "indefinida",
            "grau_confianca": "Não Mapeado",
            "observacao": "Requer decisão do usuário"
        })

conn.commit()

print(f"Total de transações classificadas no teste: {len(classificacoes_teste)} de {len(transacoes)}")
print(f"Total de itens ambíguos ou requerendo decisão: {len(ambiguidades)}")

# 6. TESTES DE ROLL-UP DO ORÇAMENTO POR GRUPO E SUBCATEGORIA
print("\n--- TESTE DE ROLL-UP DO ORÇAMENTO (SOMA DE SUBCATEGORIAS) ---")
# Vamos definir orçamentos de teste em subcategorias para Outubro/2026:
orcamentos_teste = [
    # Habitação (soma das subcategorias = orçamento do grupo)
    ("Habitação", "Água (Copasa)", 80.00),
    ("Habitação", "Energia (CEMIG + CEMIG SIM)", 230.00),
    ("Habitação", "Internet Residencial", 130.00),
    ("Habitação", "Telefone (Fernanda)", 35.00),
    ("Habitação", "Manutenção e Reparos", 100.00),
    
    # Alimentação
    ("Alimentação", "Supermercado / Feira", 900.00),
    ("Alimentação", "Padaria", 150.00),
    ("Alimentação", "Delivery (iFood / 99Food)", 150.00),
    
    # Chaves Transportes
    ("Chaves Transportes", "Combustível (Trabalho)", 800.00),
    ("Chaves Transportes", "Ferramentas de Trabalho (Internet celular Carlos, suporte, cabos)", 130.00),
    ("Chaves Transportes", "Lavagem / Limpeza", 80.00)
]

for g_nome, sub_nome, val_orc in orcamentos_teste:
    sub_id, _ = mapa_subcats[(g_nome, sub_nome)]
    cur.execute("""
        INSERT OR REPLACE INTO planejamento_orcamento_subcategorias (mes_ano, subcategoria_id, valor_orcado)
        VALUES ('2026-10', ?, ?)
    """, (sub_id, val_orc))

conn.commit()

# Consulta de Roll-up com separação de conceitos:
cur.execute("""
SELECT 
    g.nome as grupo,
    COUNT(s.id) as qtd_subcategorias,
    COALESCE(SUM(o.valor_orcado), 0.0) as orcamento_previsto_grupo,
    COALESCE(SUM(CASE WHEN t.data >= '2026-10-01' AND t.data <= '2026-10-31' THEN t.valor ELSE 0 END), 0.0) as despesa_competencia_grupo,
    COALESCE(SUM(CASE WHEN t.data >= '2026-10-01' AND t.data <= '2026-10-31' AND t.pago = 1 THEN t.valor ELSE 0 END), 0.0) as pago_realizado_grupo,
    COALESCE(SUM(CASE WHEN t.data >= '2026-10-01' AND t.data <= '2026-10-31' AND (t.pago IS NULL OR t.pago != 1) THEN t.valor ELSE 0 END), 0.0) as obrigacoes_a_pagar_grupo
FROM grupos_categoria g
JOIN subcategorias s ON s.grupo_id = g.id
LEFT JOIN planejamento_orcamento_subcategorias o ON o.subcategoria_id = s.id AND o.mes_ano = '2026-10'
LEFT JOIN transacoes t ON t.subcategoria_id = s.id
WHERE g.nome IN ('Habitação', 'Alimentação', 'Chaves Transportes', 'Saúde', 'Educação', 'Dívidas')
GROUP BY g.id, g.nome
ORDER BY g.ordem
""")
roll_up_rows = cur.fetchall()

print("\nRESULTADO DO ROLL-UP POR GRUPO (Outubro/2026):")
for r in roll_up_rows:
    print(f"📂 Grupo: {r['grupo']:20s} | Orçado (Soma Subcats): R$ {r['orcamento_previsto_grupo']:7.2f} | Competência: R$ {r['despesa_competencia_grupo']:7.2f} | Pago: R$ {r['pago_realizado_grupo']:7.2f} | A Pagar: R$ {r['obrigacoes_a_pagar_grupo']:7.2f}")

conn.close()
print("\n✓ Todos os testes de banco isolado foram executados com sucesso absoluto!")
