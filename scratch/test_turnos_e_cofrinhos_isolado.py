import sys, os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
import shutil
from datetime import date, datetime
from decimal import Decimal

# Copia financas_casa.db para banco de teste isolado
TEST_DB = "scratch/financas_teste_isolado.db"
shutil.copyfile("financas_casa.db", TEST_DB)

conn = sqlite3.connect(TEST_DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== 1. VERIFICANDO / APLICANDO MIGRAÇÕES NO BANCO ISOLADO ===")

# 1.1 Migração turnos
cur.execute("PRAGMA table_info(turnos)")
turnos_cols = {r["name"] for r in cur.fetchall()}

novas_cols_turnos = [
    ("km_inicial", "REAL"),
    ("km_final", "REAL"),
    ("ganho_dinheiro_pix", "REAL DEFAULT 0.0"),
    ("ganho_online", "REAL DEFAULT 0.0"),
    ("status_turno", "TEXT DEFAULT 'encerrado'"),
    ("combustivel_consumido_estimado", "REAL DEFAULT 0.0"),
    ("created_at", "TEXT")
]
for col, col_def in novas_cols_turnos:
    if col not in turnos_cols:
        cur.execute(f"ALTER TABLE turnos ADD COLUMN {col} {col_def}")
        print(f"+ Coluna adicionada em turnos: {col}")

# 1.2 Migração contas_config e cofrinhos
cur.execute("PRAGMA table_info(contas_config)")
contas_cols = {r["name"] for r in cur.fetchall()}
if "conta_pai_id" not in contas_cols:
    cur.execute("ALTER TABLE contas_config ADD COLUMN conta_pai_id INTEGER REFERENCES contas_config(id)")
    print("+ Coluna adicionada em contas_config: conta_pai_id")
if "incluir_saldo_consolidado" not in contas_cols:
    cur.execute("ALTER TABLE contas_config ADD COLUMN incluir_saldo_consolidado INTEGER DEFAULT 1")
    print("+ Coluna adicionada em contas_config: incluir_saldo_consolidado")

cur.execute("PRAGMA table_info(cofrinhos)")
cof_cols = {r["name"] for r in cur.fetchall()}
if "conta_config_id" not in cof_cols:
    cur.execute("ALTER TABLE cofrinhos ADD COLUMN conta_config_id INTEGER REFERENCES contas_config(id)")
    print("+ Coluna adicionada em cofrinhos: conta_config_id")
if "incluir_saldo_consolidado" not in cof_cols:
    cur.execute("ALTER TABLE cofrinhos ADD COLUMN incluir_saldo_consolidado INTEGER DEFAULT 0")
    print("+ Coluna adicionada em cofrinhos: incluir_saldo_consolidado")

# Sincronização dos 6 cofrinhos com contas_config
cur.execute("SELECT id, nome, saldo_confirmado FROM cofrinhos")
cofrinhos_atuais = cur.fetchall()
for cof in cofrinhos_atuais:
    c_id = cof["id"]
    c_nome = cof["nome"]
    # Verifica se já existe em contas_config
    cur.execute("SELECT id FROM contas_config WHERE nome = ?", (c_nome,))
    row_cc = cur.fetchone()
    if row_cc:
        cc_id = row_cc["id"]
        cur.execute("UPDATE contas_config SET tipo = 'cofrinho', conta_pai_id = 1 WHERE id = ?", (cc_id,))
    else:
        cur.execute("""
            INSERT INTO contas_config (nome, tipo, cor, conta_pai_id, incluir_saldo_consolidado)
            VALUES (?, 'cofrinho', '#f59e0b', 1, 0)
        """, (c_nome,))
        cc_id = cur.lastrowid
        print(f"+ Cofrinho sincronizado em contas_config: {c_nome} (id={cc_id})")
    cur.execute("UPDATE cofrinhos SET conta_config_id = ? WHERE id = ?", (cc_id, c_id))

conn.commit()

print("\n=== 2. TESTANDO FLUXO DE TURNOS (ABERTURA, ENCERRAMENTO, PERSISTÊNCIA) ===")

def obter_turno_aberto(db_conn):
    c = db_conn.cursor()
    c.execute("SELECT * FROM turnos WHERE status_turno = 'aberto' ORDER BY id DESC LIMIT 1")
    r = c.fetchone()
    return dict(r) if r else None

def iniciar_turno(db_conn, data_str, hora_ini, km_ini, plataforma="99", periodo="Manhã", obs=""):
    c = db_conn.cursor()
    c.execute("""
        INSERT INTO turnos (data, hora_inicio, km_inicial, ganho_bruto, horas, km, 
                           plataforma, periodo, observacao, status_turno, combustivel)
        VALUES (?, ?, ?, 0.0, 0.0, 0.0, ?, ?, ?, 'aberto', 0.0)
    """, (data_str, hora_ini, km_ini, plataforma, periodo, obs))
    db_conn.commit()
    return c.lastrowid

def encerrar_turno(db_conn, turno_id, hora_fim, km_final, ganho_dinheiro_pix, ganho_online, comb_estimado=0.0, obs=None):
    c = db_conn.cursor()
    c.execute("SELECT * FROM turnos WHERE id = ?", (turno_id,))
    row = c.fetchone()
    if not row:
        return False, "Turno não encontrado."
    
    t_dict = dict(row)
    km_ini = float(t_dict.get("km_inicial") or 0.0)
    if km_final < km_ini:
        return False, f"KM final ({km_final}) não pode ser menor que o KM inicial ({km_ini})."
    
    km_rodado = round(km_final - km_ini, 1)
    
    # Cálculo duração
    hora_ini = t_dict.get("hora_inicio") or "00:00"
    try:
        t_ini = datetime.strptime(hora_ini, "%H:%M")
        t_fim = datetime.strptime(hora_fim, "%H:%M")
        if t_fim >= t_ini:
            duracao_segundos = (t_fim - t_ini).total_seconds()
        else: # passou da meia-noite
            duracao_segundos = (t_fim - t_ini).total_seconds() + 86400
        duracao_horas = round(duracao_segundos / 3600.0, 2)
    except Exception:
        duracao_horas = 0.0

    ganho_bruto_total = round(ganho_dinheiro_pix + ganho_online, 2)
    obs_final = obs if obs is not None else t_dict.get("observacao")

    c.execute("""
        UPDATE turnos
        SET status_turno = 'encerrado',
            hora_fim = ?,
            km_final = ?,
            km = ?,
            horas = ?,
            ganho_dinheiro_pix = ?,
            ganho_online = ?,
            ganho_bruto = ?,
            dinheiro_fisico_recebido = ?,
            combustivel = ?,
            combustivel_consumido_estimado = ?,
            observacao = ?
        WHERE id = ?
    """, (hora_fim, km_final, km_rodado, duracao_horas, 
          ganho_dinheiro_pix, ganho_online, ganho_bruto_total,
          ganho_dinheiro_pix, comb_estimado, comb_estimado, obs_final, turno_id))
    db_conn.commit()
    return True, "Turno encerrado com sucesso."

# Teste: Não deve haver turno aberto inicialmente
assert obter_turno_aberto(conn) is None, "Erro: Não deveria haver turno aberto"

# Teste: Inicia turno da manhã em 2026-10-21
id_t1 = iniciar_turno(conn, "2026-10-21", "07:00", 85000.0, "99", "Manhã", "Turno matutino")
print(f"Turno 1 iniciado: ID={id_t1}")

# Persistência: novo cursor/conexão deve enxergar o turno aberto
t_aberto = obter_turno_aberto(conn)
assert t_aberto is not None and t_aberto["id"] == id_t1 and t_aberto["status_turno"] == "aberto"
print(f"Turno aberto persistido verificado: {t_aberto['hora_inicio']} - {t_aberto['km_inicial']} km")

# Encerra turno da manhã
ok, msg = encerrar_turno(conn, id_t1, "11:30", 85080.0, ganho_dinheiro_pix=50.0, ganho_online=110.0, comb_estimado=25.0)
assert ok, f"Falha ao encerrar turno: {msg}"
print("Turno 1 encerrado com sucesso!")

cur.execute("SELECT * FROM turnos WHERE id = ?", (id_t1,))
t1_fechado = dict(cur.fetchone())
assert t1_fechado["status_turno"] == "encerrado"
assert t1_fechado["km"] == 80.0
assert t1_fechado["horas"] == 4.5
assert t1_fechado["ganho_bruto"] == 160.0
assert t1_fechado["ganho_dinheiro_pix"] == 50.0
assert t1_fechado["ganho_online"] == 110.0
print(f"Turno 1 métricas calculadas: {t1_fechado['horas']}h, {t1_fechado['km']}km, Bruto: R$ {t1_fechado['ganho_bruto']}")

# Teste: Múltiplos turnos no mesmo dia (Turno da Tarde)
id_t2 = iniciar_turno(conn, "2026-10-21", "14:00", 85080.0, "99", "Tarde", "Turno vespertino")
ok2, msg2 = encerrar_turno(conn, id_t2, "18:00", 85150.0, ganho_dinheiro_pix=30.0, ganho_online=90.0, comb_estimado=20.0)
assert ok2
cur.execute("SELECT * FROM turnos WHERE id = ?", (id_t2,))
t2_fechado = dict(cur.fetchone())
assert t2_fechado["km"] == 70.0
assert t2_fechado["horas"] == 4.0
assert t2_fechado["ganho_bruto"] == 120.0
print(f"Turno 2 métricas calculadas: {t2_fechado['horas']}h, {t2_fechado['km']}km, Bruto: R$ {t2_fechado['ganho_bruto']}")

# Total do dia: 2 turnos, 150 km, 8.5h, R$ 280,00 bruto
cur.execute("SELECT COUNT(*), SUM(km), SUM(horas), SUM(ganho_bruto) FROM turnos WHERE data = '2026-10-21'")
r_tot = cur.fetchone()
assert r_tot[0] == 2
assert r_tot[1] == 150.0
assert r_tot[2] == 8.5
assert r_tot[3] == 280.0
print(f"Total do dia 2026-10-21: {r_tot[0]} turnos, {r_tot[1]} km, {r_tot[2]}h, R$ {r_tot[3]:.2f}")

# NENHUMA receita bancária foi criada automaticamente!
cur.execute("SELECT COUNT(*) FROM transacoes WHERE data = '2026-10-21'")
assert cur.fetchone()[0] == 0, "Erro: Não deveria haver transações financeiras geradas automaticamente"
print("Garantia cumprida: Nenhuma receita bancária foi criada automaticamente ao encerrar turnos.")

print("\n=== 3. TESTANDO COFRINHOS COMO CONTAS REAIS E TRANSFERÊNCIAS INTERNAS ===")
import saldo_service
import planejamento_service

# Verifica saldo inicial do Mercado Pago (conta_id=1)
res_mp_ini = saldo_service.calcular_saldo_conta(conn, 1)
saldo_mp_ini = res_mp_ini["saldo_atual"]
print(f"Saldo inicial Mercado Pago (livre): R$ {saldo_mp_ini}")

# Localiza Cofrinho IPVA em contas_config
cur.execute("SELECT id FROM contas_config WHERE nome = 'Cofrinho IPVA'")
id_conta_cof_ipva = cur.fetchone()[0]

res_cof_ini = saldo_service.calcular_saldo_conta(conn, id_conta_cof_ipva)
assert res_cof_ini["saldo_atual"] == Decimal("0.00")
print(f"Saldo inicial Cofrinho IPVA: R$ {res_cof_ini['saldo_atual']}")

# Realiza transferência interna: Mercado Pago -> Cofrinho IPVA (Aporte de R$ 2,00)
# (Dentro do saldo disponível do MP que é R$ 3,83)
valor_transf = 2.00
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, conta_destino_id, pago, afeta_saldo_bancario)
    VALUES ('2026-10-21', 'Aporte Cofrinho IPVA', ?, 'transferencia', 'Transferência Interna', 'Mercado Pago', 1, ?, 1, 1)
""", (valor_transf, id_conta_cof_ipva))
conn.commit()
id_tx_transf = cur.lastrowid
print(f"Transferência registrada: ID={id_tx_transf}, Valor=R$ {valor_transf}")

# Recalcula saldos
res_mp_pos = saldo_service.calcular_saldo_conta(conn, 1)
res_cof_pos = saldo_service.calcular_saldo_conta(conn, id_conta_cof_ipva)

assert res_mp_pos["saldo_atual"] == saldo_mp_ini - Decimal("2.00")
assert res_cof_pos["saldo_atual"] == Decimal("2.00")
print(f"Saldo Mercado Pago após aporte: R$ {res_mp_pos['saldo_atual']} (reduziu exatamente R$ 2,00)")
print(f"Saldo Cofrinho IPVA após aporte: R$ {res_cof_pos['saldo_atual']} (aumentou exatamente R$ 2,00)")

# Verifica que NÃO criou receita nem despesa
cur.execute("SELECT COUNT(*) FROM transacoes WHERE tipo IN ('receita', 'despesa') AND id = ?", (id_tx_transf,))
assert cur.fetchone()[0] == 0
print("Garantia cumprida: Transferência interna não gerou receita nem despesa.")

# Atualiza / sincroniza saldo_confirmado em cofrinhos
cur.execute("UPDATE cofrinhos SET saldo_confirmado = ? WHERE conta_config_id = ?", (float(res_cof_pos["saldo_atual"]), id_conta_cof_ipva))
conn.commit()

# Retirada de Cofrinho IPVA -> Mercado Pago (R$ 0,50)
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, conta_destino_id, pago, afeta_saldo_bancario)
    VALUES ('2026-10-21', 'Resgate Cofrinho IPVA', 0.50, 'transferencia', 'Transferência Interna', 'Cofrinho IPVA', ?, 1, 1, 1)
""", (id_conta_cof_ipva,))
conn.commit()
id_tx_resgate = cur.lastrowid

res_mp_resgate = saldo_service.calcular_saldo_conta(conn, 1)
res_cof_resgate = saldo_service.calcular_saldo_conta(conn, id_conta_cof_ipva)
assert res_mp_resgate["saldo_atual"] == saldo_mp_ini - Decimal("1.50")
assert res_cof_resgate["saldo_atual"] == Decimal("1.50")
print(f"Saldo Mercado Pago após resgate: R$ {res_mp_resgate['saldo_atual']} (aumentou R$ 0,50)")
print(f"Saldo Cofrinho IPVA após resgate: R$ {res_cof_resgate['saldo_atual']} (reduziu R$ 0,50)")

# Teste de Estorno (exclusão da retirada)
cur.execute("DELETE FROM transacoes WHERE id = ?", (id_tx_resgate,))
conn.commit()
res_mp_pos_estorno = saldo_service.calcular_saldo_conta(conn, 1)
res_cof_pos_estorno = saldo_service.calcular_saldo_conta(conn, id_conta_cof_ipva)
assert res_mp_pos_estorno["saldo_atual"] == res_mp_pos["saldo_atual"]
assert res_cof_pos_estorno["saldo_atual"] == res_cof_pos["saldo_atual"]
print("Estorno testado com sucesso: Saldos retornaram perfeitamente ao estado anterior!")

conn.close()
os.remove(TEST_DB)
print("\n=== TODOS OS TESTES ISOLADOS PASSARAM COM 100% DE SUCESSO! ===")
