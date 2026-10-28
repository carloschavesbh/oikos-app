import sqlite3
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal
import sys
sys.path.append('.')
import saldo_service
import planejamento_service

conn = sqlite3.connect('financas_casa.db')
conn.row_factory = sqlite3.Row

# Initialize schemas
planejamento_service.inicializar_esquema_planejamento(conn)

# Test mission query
missao = planejamento_service.obter_status_missao_ipva(conn)
print("Missao IPVA:", missao)

# Test cofrinhos query
cofrinhos = planejamento_service.obter_cofrinhos(conn)
print(f"Total Cofrinhos: {len(cofrinhos)}")
for c in cofrinhos:
    print(c)

# Test update cofrinho
sucesso, msg = planejamento_service.atualizar_saldo_cofrinho(conn, 1, Decimal("0.00"), "Teste")
print("Update cofrinho:", sucesso, msg)

# Test mission update
sucesso_m, msg_m = planejamento_service.atualizar_missao_parametros(
    conn,
    transacao_id=missao['transacao_id'],
    valor_alvo=Decimal("431.11"),
    data_limite="2026-10-29",
    prioridade="critica",
    valor_reserva=Decimal("0.00"),
    turnos_planejados=5,
    horas_por_turno=4.0,
    status="ativa"
)
print("Update missao:", sucesso_m, msg_m)

conn.close()
print("All DB operations succeeded!")
