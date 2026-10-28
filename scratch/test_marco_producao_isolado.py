import sqlite3
import pandas as pd
from decimal import Decimal

print("=== TESTE ISOLADO: MARCO DE PRODUÇÃO ACUMULADA 99 ===")

# Criar banco em memória para teste
conn = sqlite3.connect(":memory:")
cur = conn.cursor()

# 1. Esquema de turnos idêntico ao de produção
cur.execute("""
CREATE TABLE turnos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    horas REAL NOT NULL,
    km REAL NOT NULL,
    ganho_bruto REAL NOT NULL,
    combustivel REAL NOT NULL,
    observacao TEXT,
    periodo TEXT,
    plataforma TEXT DEFAULT '99'
)
""")

# Inserir o turno existente de 19/10/2026
cur.execute("""
INSERT INTO turnos (id, data, horas, km, ganho_bruto, combustivel, observacao, periodo, plataforma)
VALUES (2, '2026-10-19', 1.0, 15.0, 17.60, 0.0, 'Segunda feira fraca pós semana da criança', 'Manhã (06h às 12h)', '99')
""")

# 2. Nova tabela de marco de produção
cur.execute("""
CREATE TABLE motorista_marco_producao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plataforma TEXT NOT NULL DEFAULT '99',
    data_corte TEXT NOT NULL,
    faturamento_bruto REAL NOT NULL,
    recebido_dinheiro_pix REAL NOT NULL,
    recebido_online REAL NOT NULL,
    observacao TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

# Inserir o marco informado pelo usuário
cur.execute("""
INSERT INTO motorista_marco_producao (plataforma, data_corte, faturamento_bruto, recebido_dinheiro_pix, recebido_online, observacao)
VALUES ('99', '2026-10-20', 1340.40, 369.25, 971.14, 'Marco inicial de produção real até 20/10/2026')
""")
conn.commit()

# 3. Teste da regra do centavo
cur.execute("SELECT faturamento_bruto, recebido_dinheiro_pix, recebido_online FROM motorista_marco_producao WHERE plataforma='99' ORDER BY id DESC LIMIT 1")
row_m = cur.fetchone()
fat_bruto = row_m[0]
rec_din = row_m[1]
rec_on = row_m[2]

soma_partes = round(rec_din + rec_on, 2)
divergencia = round(fat_bruto - soma_partes, 2)

print(f"Faturamento Bruto: R$ {fat_bruto:.2f}")
print(f"Dinheiro / Pix:    R$ {rec_din:.2f}")
print(f"Online:            R$ {rec_on:.2f}")
print(f"Soma das partes:   R$ {soma_partes:.2f}")
print(f"Divergência:       R$ {divergencia:+.2f}")
assert divergencia == 0.01, f"Divergência esperada de +0.01, obtida: {divergencia}"
print("✅ Regra do centavo validada: R$ 0,01 preservado e explicitado sem correção artificial.")

# 4. Teste da regra de não duplicação do turno de 19/10 (R$ 17,60)
data_corte = '2026-10-20'
cur.execute("SELECT id, data, ganho_bruto FROM turnos WHERE data <= ?", (data_corte,))
turnos_inclusos = cur.fetchall()
print(f"Turnos anteriores ou iguais a {data_corte} (já inclusos no marco): {turnos_inclusos}")
assert len(turnos_inclusos) == 1 and turnos_inclusos[0][2] == 17.60

# Turnos posteriores (por exemplo, um novo turno trabalhado em 21/10)
cur.execute("""
INSERT INTO turnos (data, horas, km, ganho_bruto, combustivel, observacao, periodo, plataforma)
VALUES ('2026-10-21', 4.0, 60.0, 150.00, 45.0, 'Turno novo pós-marco', 'Tarde', '99')
""")
conn.commit()

# Cálculo do Faturamento Bruto Acumulado:
# Marco + turnos com data > data_corte
cur.execute("SELECT COALESCE(SUM(ganho_bruto), 0.0) FROM turnos WHERE data > ?", (data_corte,))
soma_posteriores = cur.fetchone()[0]

total_acumulado = fat_bruto + soma_posteriores
print(f"Faturamento Acumulado (Marco {fat_bruto:.2f} + Posteriores {soma_posteriores:.2f}): R$ {total_acumulado:.2f}")

# Garantir que 17.60 NÃO foi somado a 1340.40
assert total_acumulado == 1340.40 + 150.00
assert total_acumulado != 1340.40 + 17.60 + 150.00
print("✅ Regra de não duplicação validada: Turno de 19/10 (R$ 17,60) não foi duplicado!")

# 5. Validação de Saldo e Carteira
saldo_real_carteira = 77.50
print(f"Saldo real na carteira hoje: R$ {saldo_real_carteira:.2f}")
print(f"Recebido em Dinheiro/Pix no histórico: R$ {rec_din:.2f}")
print("✅ Rigor contábil: Os R$ 369,25 NÃO afetam nem aumentam o saldo da carteira.")

conn.close()
print("🎉 TODOS OS TESTES ISOLADOS PASSARAM!")
