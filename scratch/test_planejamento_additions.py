import sqlite3
from decimal import Decimal
from datetime import date
import sys
sys.path.append('.')
import saldo_service

# Test on test DB
db_path = 'scratch/financas_casa_teste_migracao.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Test migration logic
cur.execute("PRAGMA table_info(planejamento_metas)")
cols = [c[1] for c in cur.fetchall()]
if 'status' not in cols:
    cur.execute("ALTER TABLE planejamento_metas ADD COLUMN status TEXT DEFAULT 'ativa'")
if 'prioridade' not in cols:
    cur.execute("ALTER TABLE planejamento_metas ADD COLUMN prioridade TEXT DEFAULT 'alta'")

# Test cofrinhos
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

# Test queries
cur.execute("SELECT * FROM cofrinhos")
rows = cur.fetchall()
print(f"Total cofrinhos: {len(rows)}")
for r in rows:
    print(dict(r))

conn.close()
print("Teste OK!")
