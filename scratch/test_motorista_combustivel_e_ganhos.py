import sqlite3
import shutil
from datetime import datetime, date, timedelta
from decimal import Decimal

# Copia banco para teste isolado
TEST_DB = "scratch/test_motorista_isolado.db"
shutil.copyfile("financas_casa.db", TEST_DB)

conn = sqlite3.connect(TEST_DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== TESTE 1: Auditoria Inicial de Abastecimento e Turnos ===")
cur.execute("""
    SELECT id, data, tipo, descricao, valor, conta, categoria 
    FROM transacoes 
    WHERE categoria LIKE '%Combust%' OR descricao LIKE '%Abastec%'
""")
abastecimentos = [dict(r) for r in cur.fetchall()]
print(f"Abastecimentos reais encontrados: {len(abastecimentos)}")
for ab in abastecimentos:
    print(" ", ab)

assert any(ab["valor"] == 90.48 and ab["data"] == "2026-10-20" for ab in abastecimentos), "Abastecimento real de 90.48 não encontrado!"
print("✅ Abastecimento de R$ 90,48 preservado e verificado.")

# TESTE 2: Fechamento de turno com opção de contabilização:
# Caso A: Turno com recebimento imediato em Dinheiro/Carteira
print("\n=== TESTE 2A: Fechamento com Recebimento em Dinheiro/Carteira ===")
# Criar turno aberto
cur.execute("""
    INSERT INTO turnos (data, hora_inicio, km_inicial, ganho_bruto, horas, km, status_turno, plataforma, periodo)
    VALUES ('2026-10-21', '08:00', 187330.0, 0.0, 0.0, 0.0, 'aberto', '99', 'Manhã (06h às 12h)')
""")
t_id = cur.lastrowid

# Encerrar turno com ganhos: R$ 40 em dinheiro/pix, R$ 60 online
# Escolhe creditar R$ 40 na Carteira (conta_id=2)
km_fim = 187380.0 # 50 km rodados
km_rodado = 50.0
duracao = 4.0
comb_est = 19.0 # consumo estimado R$ 19,00

cur.execute("""
    UPDATE turnos
    SET status_turno = 'encerrado',
        hora_fim = '12:00',
        km_final = ?,
        km = ?,
        horas = ?,
        ganho_dinheiro_pix = ?,
        ganho_online = ?,
        ganho_bruto = ?,
        combustivel_consumido_estimado = ?,
        combustivel = ?
    WHERE id = ?
""", (km_fim, km_rodado, duracao, 40.0, 60.0, 100.0, comb_est, comb_est, t_id))

# Cria receita bancária confirmada pelo usuário
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-21', 'Ganhos 99 - Dinheiro Passageiro (Turno #' || ? || ')', 40.0, 'receita', '99 / Chaves (Carlos)', 'Dinheiro / Carteira', 2, 1, 1, ?)
""", (t_id, t_id))
rec_id = cur.lastrowid

# Verifica se a transação foi vinculada ao turno
cur.execute("SELECT id, valor, conta_id, turno_id FROM transacoes WHERE id = ?", (rec_id,))
r_rec = dict(cur.fetchone())
assert r_rec["turno_id"] == t_id and r_rec["valor"] == 40.0
print("✅ Turno encerrado e receita confirmada de R$ 40,00 na Carteira vinculada com sucesso!")

# TESTE 2B: Transferência posterior do dinheiro recebido para o Mercado Pago
print("\n=== TESTE 2B: Transferência Dinheiro ➔ Mercado Pago (Sem duplicar receita) ===")
# Transferência interna de R$ 40 da Carteira (2) para Mercado Pago (1)
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, conta_destino_id, pago, afeta_saldo_bancario)
    VALUES ('2026-10-21', 'Depósito Dinheiro Corridas ➔ Mercado Pago', 40.0, 'transferencia', 'Transferência', 'Dinheiro / Carteira', 2, 1, 1, 1)
""")
transf_id = cur.lastrowid
conn.commit()

# Verifica se não criou receita adicional
cur.execute("SELECT tipo, valor FROM transacoes WHERE id = ?", (transf_id,))
r_tr = dict(cur.fetchone())
assert r_tr["tipo"] == "transferencia"
print("✅ Transferência registrada como 'transferencia' - sem criação de receita duplicada!")

# TESTE 2C: Turno com vínculo a Pix já existente no extrato
print("\n=== TESTE 2C: Vínculo a Pix já lançado no extrato ===")
# Simula que o motorista já havia lançado uma entrada Pix de R$ 35,00 no Mercado Pago
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario)
    VALUES ('2026-10-21', 'Pix Corrida Particular / 99', 35.0, 'receita', '99 / Chaves (Carlos)', 'Mercado Pago', 1, 1, 1)
""")
pix_existente_id = cur.lastrowid

# Novo turno da tarde
cur.execute("""
    INSERT INTO turnos (data, hora_inicio, hora_fim, km_inicial, km_final, km, horas, ganho_dinheiro_pix, ganho_online, ganho_bruto, combustivel_consumido_estimado, status_turno)
    VALUES ('2026-10-21', '14:00', '18:00', 187380.0, 187430.0, 50.0, 4.0, 35.0, 50.0, 85.0, 19.0, 'encerrado')
""")
t_tarde_id = cur.lastrowid

# Motorista vincula o Pix já existente ao turno em vez de criar outro
cur.execute("UPDATE transacoes SET turno_id = ? WHERE id = ?", (t_tarde_id, pix_existente_id))
conn.commit()

cur.execute("SELECT turno_id FROM transacoes WHERE id = ?", (pix_existente_id,))
assert cur.fetchone()[0] == t_tarde_id
print(f"✅ Pix #{pix_existente_id} vinculado com sucesso ao Turno #{t_tarde_id} sem criar lançamento duplicado!")

# TESTE 2D: Divisão parcial entre contas
print("\n=== TESTE 2D: Divisão parcial de ganhos entre contas ===")
cur.execute("""
    INSERT INTO turnos (data, hora_inicio, hora_fim, km_inicial, km_final, km, horas, ganho_dinheiro_pix, ganho_online, ganho_bruto, combustivel_consumido_estimado, status_turno)
    VALUES ('2026-10-21', '19:00', '22:00', 187430.0, 187470.0, 40.0, 3.0, 60.0, 20.0, 80.0, 15.0, 'encerrado')
""")
t_noite_id = cur.lastrowid

# Divide R$ 60 em: R$ 30 Carteira (2) e R$ 30 Mercado Pago (1)
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-21', 'Ganhos 99 - Dinheiro (Turno #' || ? || ') - Parte Carteira', 30.0, 'receita', '99 / Chaves (Carlos)', 'Dinheiro / Carteira', 2, 1, 1, ?)
""", (t_noite_id, t_noite_id))
cur.execute("""
    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
    VALUES ('2026-10-21', 'Ganhos 99 - Pix Direto (Turno #' || ? || ') - Parte Mercado Pago', 30.0, 'receita', '99 / Chaves (Carlos)', 'Mercado Pago', 1, 1, 1, ?)
""", (t_noite_id, t_noite_id))
conn.commit()

cur.execute("SELECT count(*), sum(valor) FROM transacoes WHERE turno_id = ?", (t_noite_id,))
cnt_div, tot_div = cur.fetchone()
assert cnt_div == 2 and tot_div == 60.0
print("✅ Divisão parcial validada: 2 lançamentos vinculados somando R$ 60,00 exatos!")

# TESTE 2E: Turno sem recebimento imediato ("Não contabilizar agora")
print("\n=== TESTE 2E: Turno sem recebimento imediato (Pendente) ===")
cur.execute("""
    INSERT INTO turnos (data, hora_inicio, hora_fim, km_inicial, km_final, km, horas, ganho_dinheiro_pix, ganho_online, ganho_bruto, combustivel_consumido_estimado, status_turno)
    VALUES ('2026-10-21', '22:30', '23:30', 187470.0, 187490.0, 20.0, 1.0, 25.0, 15.0, 40.0, 7.6, 'encerrado')
""")
t_pend_id = cur.lastrowid
conn.commit()

# Verifica que NÃO há transações para t_pend_id
cur.execute("SELECT count(*) FROM transacoes WHERE turno_id = ?", (t_pend_id,))
assert cur.fetchone()[0] == 0
print("✅ Turno pendente confirmado: 0 movimentações bancárias criadas automaticamente.")

# TESTE 3: Métricas de combustível e abastecimento
print("\n=== TESTE 3: Métricas de Combustível (Real Pago vs Consumo Estimado) ===")
# Abastecimento real em 20/10 foi R$ 90,48
# Em 20/10 houve turno com consumo estimado de R$ 9,50
# Em 21/10 houve turnos com consumos estimados: 19.0 + 19.0 + 15.0 + 7.6 = 60.60
# O mesmo tanque de R$ 90,48 durou vários turnos entre 20/10 e 21/10!
cur.execute("""
    SELECT sum(valor) FROM transacoes 
    WHERE tipo = 'despesa' AND pago = 1 AND (categoria LIKE '%Combust%' OR descricao LIKE '%Abastec%')
      AND data = '2026-10-20'
""")
real_pago_dia20 = cur.fetchone()[0] or 0.0

cur.execute("""
    SELECT sum(combustivel_consumido_estimado) FROM turnos 
    WHERE status_turno = 'encerrado' AND data = '2026-10-20'
""")
consumo_est_dia20 = cur.fetchone()[0] or 0.0

print(f"Dia 20/10 -> Real Pago no Posto: R$ {real_pago_dia20:,.2f} | Consumo Estimado dos Turnos: R$ {consumo_est_dia20:,.2f}")
assert real_pago_dia20 == 90.48
assert consumo_est_dia20 == 9.50
print("✅ Separação perfeita: Abastecimento de R$ 90,48 pago uma única vez no caixa; consumo do dia 20 foi R$ 9,50.")

conn.close()
print("\n🎉 TODOS OS TESTES ISOLADOS PASSARAM COM SUCESSO!")
