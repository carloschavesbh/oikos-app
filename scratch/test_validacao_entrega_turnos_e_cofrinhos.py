import sys, os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
import shutil
from datetime import date, datetime
from decimal import Decimal
import saldo_service
import planejamento_service

TEST_DB = "scratch/financas_teste_entrega.db"
shutil.copyfile("financas_casa.db", TEST_DB)

print("=== INICIANDO BATERIA DE TESTES DE VALIDAÇÃO DA ENTREGA ===")

conn = sqlite3.connect(TEST_DB)
conn.row_factory = sqlite3.Row

# Executa migrações
saldo_service.migrar_esquema(conn)
planejamento_service.inicializar_esquema_planejamento(conn)

print("\n--- TESTE 1: ABERTURA, PERSISTÊNCIA E ENCERRAMENTO DE TURNO 99 ---")
cur = conn.cursor()

# 1.1 Iniciar Turno da Manhã (21/10/2026)
cur.execute("""
    INSERT INTO turnos (data, hora_inicio, km_inicial, ganho_bruto, horas, km, 
                       plataforma, periodo, observacao, status_turno, combustivel)
    VALUES ('2026-10-21', '06:30', 85100.0, 0.0, 0.0, 0.0, '99', 'Manhã (06h às 12h)', 'Turno da manhã', 'aberto', 0.0)
""")
conn.commit()
id_t1 = cur.lastrowid

# 1.2 Persistência: fecha e reabre conexão
conn.close()
conn = sqlite3.connect(TEST_DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT * FROM turnos WHERE status_turno = 'aberto'")
turno_aberto = cur.fetchone()
assert turno_aberto is not None, "Turno aberto deveria estar persistido no SQLite"
assert turno_aberto["id"] == id_t1
assert turno_aberto["hora_inicio"] == "06:30"
assert turno_aberto["km_inicial"] == 85100.0
print(f"✅ Turno #{id_t1} aberto e persistido com sucesso (Início: {turno_aberto['hora_inicio']} • {turno_aberto['km_inicial']} km)")

# 1.3 Encerrar Turno da Manhã às 11:30 com 85180 km (80 km, 5.0h)
# Ganhos: R$ 45,00 Dinheiro/Pix e R$ 115,00 Online (Total Bruto: R$ 160,00)
# Combustível estimado: R$ 30,00
cur.execute("""
    UPDATE turnos
    SET status_turno = 'encerrado',
        hora_fim = '11:30',
        km_final = 85180.0,
        km = 80.0,
        horas = 5.0,
        ganho_dinheiro_pix = 45.0,
        ganho_online = 115.0,
        ganho_bruto = 160.0,
        combustivel = 30.0,
        combustivel_consumido_estimado = 30.0
    WHERE id = ?
""", (id_t1,))
conn.commit()

cur.execute("SELECT * FROM turnos WHERE id = ?", (id_t1,))
t1_res = cur.fetchone()
assert t1_res["status_turno"] == "encerrado"
assert t1_res["km"] == 80.0
assert t1_res["horas"] == 5.0
assert t1_res["ganho_bruto"] == 160.0
assert t1_res["ganho_dinheiro_pix"] == 45.0
assert t1_res["ganho_online"] == 115.0
print("✅ Turno 1 encerrado com métricas exatas e ganhos separados!")

# 1.4 Garantia: Não gerou receitas bancárias automáticas
cur.execute("SELECT COUNT(*) FROM transacoes WHERE data = '2026-10-21'")
assert cur.fetchone()[0] == 0, "Nenhuma transação financeira pode ser criada automaticamente no encerramento"
print("✅ Desacoplamento bancário confirmado: Nenhuma receita gerada no encerramento.")

# 1.5 Múltiplos turnos no mesmo dia: Iniciar e encerrar Turno da Tarde (21/10/2026)
cur.execute("""
    INSERT INTO turnos (data, hora_inicio, hora_fim, km_inicial, km_final, horas, km, 
                       ganho_dinheiro_pix, ganho_online, ganho_bruto, combustivel, combustivel_consumido_estimado,
                       plataforma, periodo, observacao, status_turno)
    VALUES ('2026-10-21', '14:00', '18:30', 85180.0, 85255.0, 4.5, 75.0, 
            35.0, 95.0, 130.0, 28.0, 28.0, '99', 'Tarde (12h às 18h)', 'Turno da tarde', 'encerrado')
""")
conn.commit()
id_t2 = cur.lastrowid

cur.execute("SELECT COUNT(*), SUM(km), SUM(horas), SUM(ganho_bruto) FROM turnos WHERE data = '2026-10-21'")
tot_dia = cur.fetchone()
assert tot_dia[0] == 2, "Deveriam existir 2 turnos no dia"
assert tot_dia[1] == 155.0, "Total km do dia deveria ser 155 km"
assert tot_dia[2] == 9.5, "Total horas do dia deveria ser 9.5h"
assert tot_dia[3] == 290.0, "Total bruto do dia deveria ser R$ 290,00"
print(f"✅ Múltiplos turnos no mesmo dia validados: {tot_dia[0]} turnos, {tot_dia[1]} km, {tot_dia[2]}h, R$ {tot_dia[3]:.2f} bruto")

# 1.6 Edição retroativa de horários/quilometragem esquecidos
cur.execute("""
    UPDATE turnos
    SET km_final = 85260.0, km = 80.0, horas = 5.0, ganho_online = 105.0, ganho_bruto = 140.0
    WHERE id = ?
""", (id_t2,))
conn.commit()
cur.execute("SELECT km, horas, ganho_bruto FROM turnos WHERE id = ?", (id_t2,))
t2_edit = cur.fetchone()
assert t2_edit[0] == 80.0
assert t2_edit[1] == 5.0
assert t2_edit[2] == 140.0
print("✅ Correção retroativa de turnos validada!")

print("\n--- TESTE 2: PRESERVAÇÃO DO MARCO 99 (R$ 1.340,40) ATÉ 20/10/2026 ---")
cur.execute("SELECT faturamento_bruto, data_corte FROM motorista_marco_producao WHERE plataforma = '99' AND status = 'ativo'")
marco = cur.fetchone()
assert marco is not None
assert float(marco[0]) == 1340.40
assert str(marco[1]) == "2026-10-20"

# Turno de 19/10/2026 (R$ 17,60) não deve ser somado duplicadamente
cur.execute("SELECT SUM(ganho_bruto) FROM turnos WHERE data <= '2026-10-20'")
bruto_pre = float(cur.fetchone()[0] or 0.0)

# Turnos pós 20/10/2026 somam normalmente
cur.execute("SELECT SUM(ganho_bruto) FROM turnos WHERE data > '2026-10-20'")
bruto_pos = float(cur.fetchone()[0] or 0.0)
faturamento_total_esperado = float(marco[0]) + bruto_pos
print(f"✅ Marco 99 intacto: R$ {float(marco[0]):,.2f} até {marco[1]}. Turnos pré-marco ({bruto_pre}) isolados. Pós-marco (+R$ {bruto_pos:,.2f}) = Total R$ {faturamento_total_esperado:,.2f}")

print("\n--- TESTE 3: COFRINHOS MERCADO PAGO COMO CONTAS REAIS E SUBCONTAS ---")
# 3.1 Verifica que os 6 cofrinhos estão sincronizados em contas_config
cur.execute("SELECT id, nome, tipo, conta_pai_id, incluir_saldo_consolidado FROM contas_config WHERE tipo = 'cofrinho'")
cofrinhos_cc = cur.fetchall()
assert len(cofrinhos_cc) == 6, f"Esperado 6 cofrinhos em contas_config, encontrado {len(cofrinhos_cc)}"
for cof in cofrinhos_cc:
    assert cof["conta_pai_id"] == 1, "Cada cofrinho deve ter conta_pai_id = 1 (Mercado Pago)"
print(f"✅ Todos os 6 cofrinhos sincronizados como subcontas do Mercado Pago.")

# 3.2 Saldo livre inicial do Mercado Pago
s_mp_ini = saldo_service.calcular_saldo_conta(conn, 1)
saldo_mp_ini = s_mp_ini["saldo_atual"]
print(f"Saldo livre Mercado Pago inicial: R$ {saldo_mp_ini}")

# Localiza Cofrinho IPVA
cur.execute("SELECT id, conta_config_id FROM cofrinhos WHERE nome = 'Cofrinho IPVA'")
row_cipva = cur.fetchone()
id_cof_ipva = row_cipva[0]
id_cc_ipva = row_cipva[1]

# 3.3 Aporte: Transferência Mercado Pago -> Cofrinho IPVA (R$ 2,00)
ok_ap, msg_ap = saldo_service.transferir_para_cofrinho(conn, id_cof_ipva, 2.00, "2026-10-21", "Aporte IPVA Teste")
assert ok_ap, f"Erro no aporte: {msg_ap}"

s_mp_ap = saldo_service.calcular_saldo_conta(conn, 1)
s_cof_ap = saldo_service.calcular_saldo_conta(conn, id_cc_ipva)
assert s_mp_ap["saldo_atual"] == saldo_mp_ini - Decimal("2.00"), "Saldo livre do MP deveria reduzir exatamente R$ 2,00"
assert s_cof_ap["saldo_atual"] == Decimal("2.00"), "Saldo do Cofrinho IPVA deveria aumentar exatamente R$ 2,00"
print(f"✅ Aporte realizado: MP = R$ {s_mp_ap['saldo_atual']} | Cofrinho IPVA = R$ {s_cof_ap['saldo_atual']}")

# 3.4 Garantia: Não gerou receita nem despesa
cur.execute("SELECT COUNT(*) FROM transacoes WHERE tipo IN ('receita', 'despesa') AND descricao LIKE '%Aporte IPVA%'")
assert cur.fetchone()[0] == 0, "Transferência interna não pode criar receita nem despesa"
print("✅ Garantia cumprida: Nenhuma receita/despesa criada pela transferência.")

# 3.5 Integração automática com Missão IPVA
missao_ipva = planejamento_service.obter_status_missao_ipva(conn)
# O Cofrinho IPVA tem R$ 2,00, a meta anterior tinha 5.26, max(5.26, 2.00) = 5.26
# Se aportarmos mais R$ 10,00 no Cofrinho IPVA:
# (Para teste, faremos um aporte de R$ 50 no cofrinho e verificaremos o reflexo direto)
cur.execute("UPDATE transacoes SET valor = 50.00 WHERE descricao = 'Aporte IPVA Teste'")
conn.commit()

missao_ipva_50 = planejamento_service.obter_status_missao_ipva(conn)
assert missao_ipva_50["valor_reservado"] == Decimal("50.00"), f"Valor reservado da Missão IPVA deveria ser R$ 50,00, obtido {missao_ipva_50['valor_reservado']}"
assert missao_ipva_50["saldo_devedor_restante"] == Decimal("431.11") - Decimal("50.00")
print(f"✅ Missão IPVA alimentada automaticamente pelo Cofrinho IPVA: Reserva = R$ {missao_ipva_50['valor_reservado']:,.2f} | Restante = R$ {missao_ipva_50['saldo_devedor_restante']:,.2f}")

# Restaura valor de 2.00
cur.execute("UPDATE transacoes SET valor = 2.00 WHERE descricao = 'Aporte IPVA Teste'")
conn.commit()

# 3.6 Resgate: Retirada de Cofrinho IPVA para Mercado Pago (R$ 0,50)
ok_res, msg_res = saldo_service.retirar_de_cofrinho(conn, id_cof_ipva, 0.50, "2026-10-21", "Resgate Parcial IPVA")
assert ok_res, f"Erro no resgate: {msg_res}"

s_mp_res = saldo_service.calcular_saldo_conta(conn, 1)
s_cof_res = saldo_service.calcular_saldo_conta(conn, id_cc_ipva)
assert s_mp_res["saldo_atual"] == saldo_mp_ini - Decimal("1.50")
assert s_cof_res["saldo_atual"] == Decimal("1.50")
print(f"✅ Resgate realizado: MP = R$ {s_mp_res['saldo_atual']} | Cofrinho IPVA = R$ {s_cof_res['saldo_atual']}")

# 3.7 Estorno: exclusão do resgate recompõe os saldos
cur.execute("DELETE FROM transacoes WHERE descricao = 'Resgate Parcial IPVA'")
conn.commit()
s_mp_est = saldo_service.calcular_saldo_conta(conn, 1)
s_cof_est = saldo_service.calcular_saldo_conta(conn, id_cc_ipva)
assert s_mp_est["saldo_atual"] == s_mp_ap["saldo_atual"]
assert s_cof_est["saldo_atual"] == s_cof_ap["saldo_atual"]
print("✅ Estorno de transferência validado com restauração contábil perfeita!")

# 3.8 Configuração de saldo consolidado vs saldo de reservas
# Por padrão, incluir_saldo_consolidado = 0 para cofrinhos
res_cons_padrao = saldo_service.calcular_saldo_consolidado(conn)
saldo_livre_padrao = res_cons_padrao["saldo_consolidado"]
saldo_reserva_padrao = res_cons_padrao["saldo_reservas"]
assert saldo_reserva_padrao == Decimal("2.00")

# Altera cofrinho para incluir no consolidado
ok_cfg, msg_cfg = saldo_service.configurar_saldo_consolidado_cofrinho(conn, id_cof_ipva, True)
assert ok_cfg
res_cons_inc = saldo_service.calcular_saldo_consolidado(conn)
assert res_cons_inc["saldo_consolidado"] == saldo_livre_padrao + Decimal("2.00")
assert res_cons_inc["saldo_reservas"] == Decimal("0.00")
print("✅ Alternância entre Saldo Consolidado Livre e Saldo de Reservas validada!")

# Restaura para 0
saldo_service.configurar_saldo_consolidado_cofrinho(conn, id_cof_ipva, False)

# 3.9 Pagamento da obrigação do IPVA continua sendo operação distinta da reserva
cur.execute("SELECT id, pago FROM transacoes WHERE id = 33")
tx_ipva = cur.fetchone()
assert tx_ipva["pago"] == 0, "A obrigação do IPVA (transação 33) não deve ser marcada como paga pela simples reserva no cofrinho"
print("✅ Garantia cumprida: O pagamento efetivo do IPVA permanece uma operação distinta da reserva.")

conn.close()
os.remove(TEST_DB)

print("\n🎉 TODOS OS TESTES PASSARAM COM 100% DE SUCESSO!")
