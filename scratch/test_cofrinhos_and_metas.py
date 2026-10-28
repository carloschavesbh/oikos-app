import sqlite3
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Conectar ao banco de teste primeiro para verificar as alterações
test_db = 'scratch/financas_casa_teste_migracao.db'
conn = sqlite3.connect(test_db)
cur = conn.cursor()

# 1. Verificar colunas de planejamento_metas
cur.execute("PRAGMA table_info(planejamento_metas)")
cols_metas = [c[1] for c in cur.fetchall()]
print("Colunas em planejamento_metas:", cols_metas)

if 'status' not in cols_metas:
    cur.execute("ALTER TABLE planejamento_metas ADD COLUMN status TEXT DEFAULT 'ativa'")
    print("Coluna 'status' adicionada a planejamento_metas.")

if 'prioridade' not in cols_metas:
    cur.execute("ALTER TABLE planejamento_metas ADD COLUMN prioridade TEXT DEFAULT 'alta'")
    print("Coluna 'prioridade' adicionada a planejamento_metas.")

# 2. Criar tabela de cofrinhos reais
cur.execute("""
CREATE TABLE IF NOT EXISTS cofrinhos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conta_pai_id INTEGER DEFAULT 1 REFERENCES contas_config(id),
    nome TEXT NOT NULL UNIQUE,
    saldo_confirmado REAL DEFAULT 0.0,
    meta_valor REAL DEFAULT 0.0,
    objetivo TEXT,
    data_atualizacao DATE,
    observacoes TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")
print("Tabela 'cofrinhos' verificada/criada.")

# Inserir os cofrinhos reais conhecidos se não existirem
cofrinhos_iniciais = [
    ("Cofrinho IPVA", "Reserva para IPVA 2025/2026", 431.11),
    ("Cofrinho Acordo BV", "Reserva para Acordo BV", 1428.82),
    ("Cofrinho Rubens", "Reserva Rubens", 0.0),
    ("Cofrinho Contas de Casa", "Reserva para contas essenciais da casa", 0.0),
    ("Cofrinho Mercado", "Alimentação e supermercado", 0.0),
    ("Cofrinho Reserva de Segurança", "Fundo de emergência familiar", 0.0)
]

for nome, obj, meta in cofrinhos_iniciais:
    cur.execute("""
        INSERT OR IGNORE INTO cofrinhos (conta_pai_id, nome, saldo_confirmado, meta_valor, objetivo, data_atualizacao)
        VALUES (1, ?, 0.0, ?, ?, date('now'))
    """, (nome, meta, obj))

conn.commit()

df_cof = pd.read_sql_query("SELECT * FROM cofrinhos", conn)
print("\n--- COFRINHOS CADASTRADOS ---")
print(df_cof[['id', 'nome', 'saldo_confirmado', 'meta_valor', 'objetivo']])

conn.close()
