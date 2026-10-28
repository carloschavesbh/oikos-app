"""
=============================================================================
PLANEJAMENTO FINANCEIRO INTELIGENTE & METAS DE TRABALHO
Serviço independente para projeções de caixa, planejamento semanal/mensal,
controle de reservas financeiras e viabilidade operacional do motorista.
=============================================================================
"""

import sqlite3
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Dict, List, Optional, Tuple, Any
import saldo_service

CENTAVOS = Decimal("0.01")


def to_decimal(val: Any) -> Decimal:
    """Converte valor para Decimal de 2 casas decimais de forma segura."""
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val.quantize(CENTAVOS, rounding=ROUND_HALF_EVEN)
    try:
        return Decimal(str(val)).quantize(CENTAVOS, rounding=ROUND_HALF_EVEN)
    except Exception:
        return Decimal("0.00")


def inicializar_esquema_planejamento(conn: sqlite3.Connection) -> None:
    """
    Cria as tabelas necessárias para o módulo de planejamento financeiro inteligente
    sem modificar nem afetar as tabelas pré-existentes.
    """
    cur = conn.cursor()

    # 1. Metas específicas e Missão Prioritária (ex: IPVA)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS planejamento_metas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mes_ano TEXT NOT NULL,
        titulo TEXT NOT NULL,
        transacao_alvo_id INTEGER REFERENCES transacoes(id),
        valor_alvo REAL NOT NULL,
        valor_reservado REAL DEFAULT 0.0,
        data_limite DATE NOT NULL,
        turnos_planejados INTEGER DEFAULT 5,
        horas_por_turno REAL DEFAULT 4.0,
        ganho_bruto_hora_estimado REAL DEFAULT 35.0,
        combustivel_hora_estimado REAL DEFAULT 10.0,
        observacoes TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Previsão de despesas variáveis realistas (a partir de hoje para outubro, mensal para seguintes)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS planejamento_previsao_variaveis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mes_ano TEXT NOT NULL,
        categoria TEXT NOT NULL,
        tipo_previsao TEXT DEFAULT 'mensal',
        data_inicio DATE,
        valor_previsto REAL NOT NULL,
        essencial_semanal REAL DEFAULT 0.0,
        observacoes TEXT,
        UNIQUE(mes_ano, categoria)
    );
    """)

    # 3. Priorização de contas atrasadas por semana de referência
    cur.execute("""
    CREATE TABLE IF NOT EXISTS planejamento_prioridades_atrasados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        semana_ref TEXT NOT NULL,
        transacao_id INTEGER NOT NULL REFERENCES transacoes(id),
        prioritaria INTEGER DEFAULT 1,
        valor_alocado REAL DEFAULT 0.0,
        UNIQUE(semana_ref, transacao_id)
    );
    """)

    # 4. Parâmetros de simulação de capacidade de trabalho do motorista
    cur.execute("""
    CREATE TABLE IF NOT EXISTS planejamento_simulacao_trabalho (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        semana_ref TEXT NOT NULL UNIQUE,
        dias_disponiveis INTEGER DEFAULT 5,
        horas_disponiveis_dia REAL DEFAULT 4.0,
        ganho_bruto_hora_estimado REAL DEFAULT 35.0,
        combustivel_hora_estimado REAL DEFAULT 10.0,
        observacoes TEXT
    );
    """)

    # 5. Adiciona coluna auxiliar em transacoes se não existir para sinalizar faturas sob conciliação
    try:
        cur.execute("ALTER TABLE transacoes ADD COLUMN status_conciliacao_fatura TEXT DEFAULT 'normal'")
    except Exception:
        pass

    conn.commit()


# =============================================================================
# 1. CÁLCULO DA NECESSIDADE DE CAIXA DOS PRÓXIMOS 7 DIAS
# =============================================================================
def calcular_necessidade_caixa_7dias(
    conn: sqlite3.Connection,
    data_referencia: Optional[date] = None,
    semana_ref: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calcula a necessidade de caixa dos próximos 7 dias diferenciando:
    - Obrigações confirmadas da semana.
    - Obrigações vencidas selecionadas como prioritárias para esta semana.
    - Obrigações vencidas reprogramadas (não somadas na meta imediata).
    - Valores pendentes de confirmação (ex: Acordo BV de R$ 1.428,82).
    - Gastos variáveis essenciais esperados.
    - Saldo bancário total, reservas virtuais e saldo livre.
    - Entradas confirmadas e rendas estimadas.
    """
    if data_referencia is None:
        data_referencia = date.today()
    if semana_ref is None:
        semana_ref = data_referencia.strftime("%Y-W%W")

    data_limite_7d = data_referencia + timedelta(days=7)
    dt_ref_str = data_referencia.strftime("%Y-%m-%d")
    dt_limite_str = data_limite_7d.strftime("%Y-%m-%d")
    mes_ano_ref = data_referencia.strftime("%Y-%m")

    cur = conn.cursor()

    # 1. Saldo Bancário Consolidado e Reservas Virtuais
    saldo_info = saldo_service.calcular_saldo_consolidado(conn, data_referencia)
    saldo_total_disponivel = saldo_info["saldo_consolidado"]

    # Busca total de reservas virtuais alocadas em planejamento_metas
    cur.execute("""
        SELECT COALESCE(SUM(valor_reservado), 0.0)
        FROM planejamento_metas
        WHERE mes_ano = ?
    """, (mes_ano_ref,))
    res_row = cur.fetchone()
    total_reservas_virtuais = to_decimal(res_row[0] if res_row else 0.0)

    # Saldo livre para outros compromissos (nunca negativo para fins de cálculo de caixa)
    saldo_livre = max(Decimal("0.00"), saldo_total_disponivel - total_reservas_virtuais)

    # 2. Busca lista de transações priorizadas para esta semana
    cur.execute("""
        SELECT transacao_id, prioritaria, valor_alocado
        FROM planejamento_prioridades_atrasados
        WHERE semana_ref = ?
    """, (semana_ref,))
    mapa_prioridades = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

    # 3. Mapeamento de todas as obrigações pendentes (tipo='despesa', pago != 1)
    cur.execute("""
        SELECT t.id, t.data, t.descricao, t.valor, t.categoria, t.conta, t.pago,
               COALESCE(t.status_conciliacao_fatura, 'normal') as status_fatura
        FROM transacoes t
        WHERE t.tipo = 'despesa' AND (t.pago IS NULL OR t.pago != 1)
        ORDER BY t.data ASC, t.id ASC
    """)
    linhas_despesas = cur.fetchall()

    obrigacoes_confirmadas_7d = []
    obrigacoes_vencidas_prioritarias = []
    obrigacoes_vencidas_reprogramadas = []
    valores_pendentes_confirmacao = []

    total_confirmadas_7d = Decimal("0.00")
    total_vencidas_prioritarias = Decimal("0.00")
    total_vencidas_reprogramadas = Decimal("0.00")
    total_pendente_confirmacao = Decimal("0.00")

    for r in linhas_despesas:
        t_id, t_data, t_desc, t_valor_nom, t_cat, t_conta, t_pago, t_st_fatura = r
        dt_venc = datetime.strptime(t_data, "%Y-%m-%d").date() if isinstance(t_data, str) else t_data

        # Obtém saldo devedor real descontando pagamentos parciais já feitos
        resumo_obrig = saldo_service.obter_resumo_obrigacao(conn, t_id)
        saldo_devedor = resumo_obrig["saldo_devedor"]

        if saldo_devedor <= Decimal("0.00"):
            continue

        item_dict = {
            "id": t_id,
            "data": t_data,
            "descricao": t_desc,
            "valor_nominal": to_decimal(t_valor_nom),
            "saldo_devedor": saldo_devedor,
            "categoria": t_cat,
            "conta": t_conta,
            "status_fatura": t_st_fatura
        }

        # Caso A: Fatura ou acordo com parcelamento pendente de confirmação (ex: BV)
        if t_st_fatura == "pendente_confirmacao" or "Acordo BV" in t_desc:
            valores_pendentes_confirmacao.append(item_dict)
            total_pendente_confirmacao += saldo_devedor
            continue

        # Caso B: Conta Vencida antes da data de referência
        if dt_venc < data_referencia:
            is_prioritaria = mapa_prioridades.get(t_id, (0, 0.0))[0] == 1
            if is_prioritaria:
                val_alocado = to_decimal(mapa_prioridades[t_id][1])
                val_efetivo = val_alocado if val_alocado > 0 else saldo_devedor
                item_dict["valor_priorizado"] = val_efetivo
                obrigacoes_vencidas_prioritarias.append(item_dict)
                total_vencidas_prioritarias += val_efetivo
            else:
                obrigacoes_vencidas_reprogramadas.append(item_dict)
                total_vencidas_reprogramadas += saldo_devedor

        # Caso C: Conta Vincenda nos próximos 7 dias (data_ref <= venc <= data_limite_7d)
        elif data_referencia <= dt_venc <= data_limite_7d:
            obrigacoes_confirmadas_7d.append(item_dict)
            total_confirmadas_7d += saldo_devedor

    # 4. Gastos Variáveis Essenciais Esperados na Semana
    cur.execute("""
        SELECT COALESCE(SUM(essencial_semanal), 0.0)
        FROM planejamento_previsao_variaveis
        WHERE mes_ano = ?
    """, (mes_ano_ref,))
    row_var = cur.fetchone()
    gastos_variaveis_semana = to_decimal(row_var[0] if row_var else Decimal("150.00"))
    if gastos_variaveis_semana == Decimal("0.00"):
        # Referência padrão conservadora para despesas essenciais básicas (Supermercado + Farmácia)
        gastos_variaveis_semana = Decimal("150.00")

    # 5. Entradas Futuras Confirmadas nos Próximos 7 Dias (receitas pendentes confirmadas)
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0.0)
        FROM transacoes
        WHERE tipo = 'receita' AND pago = 0 AND data >= ? AND data <= ?
    """, (dt_ref_str, dt_limite_str))
    row_rec = cur.fetchone()
    entradas_futuras_confirmadas = to_decimal(row_rec[0] if row_rec else 0.0)

    # 6. Cálculo dos Totais e da Necessidade Adicional de Caixa
    compromissos_minimos_semana = (
        total_confirmadas_7d +
        total_vencidas_prioritarias +
        gastos_variaveis_semana
    )

    # A necessidade adicional é o que precisa entrar de dinheiro novo
    necessidade_adicional_caixa = max(
        Decimal("0.00"),
        compromissos_minimos_semana - saldo_livre - entradas_futuras_confirmadas
    )

    return {
        "data_referencia": dt_ref_str,
        "data_limite_7d": dt_limite_str,
        "saldo_total_disponivel": saldo_total_disponivel,
        "total_reservas_virtuais": total_reservas_virtuais,
        "saldo_livre": saldo_livre,
        "obrigacoes_confirmadas_7d": obrigacoes_confirmadas_7d,
        "total_confirmadas_7d": total_confirmadas_7d,
        "obrigacoes_vencidas_prioritarias": obrigacoes_vencidas_prioritarias,
        "total_vencidas_prioritarias": total_vencidas_prioritarias,
        "obrigacoes_vencidas_reprogramadas": obrigacoes_vencidas_reprogramadas,
        "total_vencidas_reprogramadas": total_vencidas_reprogramadas,
        "valores_pendentes_confirmacao": valores_pendentes_confirmacao,
        "total_pendente_confirmacao": total_pendente_confirmacao,
        "gastos_variaveis_semana": gastos_variaveis_semana,
        "entradas_futuras_confirmadas": entradas_futuras_confirmadas,
        "compromissos_minimos_semana": compromissos_minimos_semana,
        "necessidade_adicional_caixa": necessidade_adicional_caixa,
        "status_bv_pendente": len(valores_pendentes_confirmacao) > 0,
        "aviso_bv": (
            f"Existe R$ {total_pendente_confirmacao:,.2f} em parcelamento de fatura pendente de conciliação (BV). "
            f"A necessidade calculada de R$ {necessidade_adicional_caixa:,.2f} representa apenas o mínimo confirmado."
            if total_pendente_confirmacao > 0 else ""
        )
    }


# =============================================================================
# 2. CÁLCULO DA PROJEÇÃO MENSAL (FECHAMENTO ATÉ O FIM DO MÊS)
# =============================================================================
def calcular_projecao_mensal(
    conn: sqlite3.Connection,
    data_referencia: Optional[date] = None
) -> Dict[str, Any]:
    """
    Projeta o fechamento do mês (ex: 31/10/2026) considerando:
    - Todas as obrigações pendentes até o final do mês.
    - Previsão de despesas variáveis manuais a partir da data atual (para outubro).
    - Desconto de valores reservados virtualmente para missões (IPVA).
    - Saldo final projetado e déficit/superávit.
    """
    if data_referencia is None:
        data_referencia = date.today()

    dt_ref_str = data_referencia.strftime("%Y-%m-%d")
    mes_ano_ref = data_referencia.strftime("%Y-%m")
    ano = data_referencia.year
    mes = data_referencia.month
    
    # Último dia do mês
    if mes == 12:
        ultimo_dia = date(ano, 12, 31)
    else:
        ultimo_dia = date(ano, mes + 1, 1) - timedelta(days=1)
    ultimo_dia_str = ultimo_dia.strftime("%Y-%m-%d")

    cur = conn.cursor()

    # 1. Saldo inicial disponível
    saldo_info = saldo_service.calcular_saldo_consolidado(conn, data_referencia)
    saldo_total_disponivel = saldo_info["saldo_consolidado"]

    # 2. Despesas fixas/obrigações pendentes no mês
    cur.execute("""
        SELECT t.id, t.valor, COALESCE(t.status_conciliacao_fatura, 'normal')
        FROM transacoes t
        WHERE t.tipo = 'despesa' AND (t.pago IS NULL OR t.pago != 1)
          AND t.data <= ?
    """, (ultimo_dia_str,))
    rows_obrig = cur.fetchall()

    total_obrigacoes_confirmadas = Decimal("0.00")
    total_bv_pendente = Decimal("0.00")

    for r in rows_obrig:
        t_id, t_val, t_st = r
        resumo = saldo_service.obter_resumo_obrigacao(conn, t_id)
        saldo_dev = resumo["saldo_devedor"]
        if saldo_dev <= Decimal("0.00"):
            continue
        if t_st == "pendente_confirmacao":
            total_bv_pendente += saldo_dev
        else:
            total_obrigacoes_confirmadas += saldo_dev

    # 3. Despesas Variáveis Restantes (modelo manual a partir de hoje para outubro)
    resumo_variaveis = calcular_despesas_variaveis_restantes(conn, mes_ano_ref, data_referencia)
    total_variaveis_restantes = resumo_variaveis["total_consumo_esperado_restante"]

    # 4. Total de reservas alocadas para missões
    cur.execute("""
        SELECT COALESCE(SUM(valor_reservado), 0.0)
        FROM planejamento_metas
        WHERE mes_ano = ?
    """, (mes_ano_ref,))
    row_res = cur.fetchone()
    total_reservas = to_decimal(row_res[0] if row_res else 0.0)

    # 5. Receitas confirmadas previstas até o fim do mês
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0.0)
        FROM transacoes
        WHERE tipo = 'receita' AND pago = 0 AND data >= ? AND data <= ?
    """, (dt_ref_str, ultimo_dia_str))
    row_rec = cur.fetchone()
    receitas_confirmadas_previstas = to_decimal(row_rec[0] if row_rec else 0.0)

    # Total de saídas mínimas confirmadas
    total_saidas_projetadas = total_obrigacoes_confirmadas + total_variaveis_restantes

    # Saldo final projetado (sem contar rendas futuras ainda não trabalhadas)
    saldo_final_projetado_sem_renda_app = (
        saldo_total_disponivel +
        receitas_confirmadas_previstas -
        total_saidas_projetadas
    )

    necessidade_geral_fim_mes = max(Decimal("0.00"), -saldo_final_projetado_sem_renda_app)

    return {
        "mes_ano": mes_ano_ref,
        "ultimo_dia_mes": ultimo_dia_str,
        "saldo_atual": saldo_total_disponivel,
        "total_reservas_virtuais": total_reservas,
        "total_obrigacoes_confirmadas": total_obrigacoes_confirmadas,
        "total_bv_pendente": total_bv_pendente,
        "total_variaveis_restantes": total_variaveis_restantes,
        "receitas_confirmadas_previstas": receitas_confirmadas_previstas,
        "total_saidas_projetadas": total_saidas_projetadas,
        "saldo_final_projetado_sem_renda_app": saldo_final_projetado_sem_renda_app,
        "necessidade_geral_fim_mes": necessidade_geral_fim_mes,
        "resumo_variaveis": resumo_variaveis
    }


# =============================================================================
# 3. GESTÃO DE DESPESAS VARIÁVEIS (PREVISÃO A PARTIR DE HOJE EM OUTUBRO)
# =============================================================================
def calcular_despesas_variaveis_restantes(
    conn: sqlite3.Connection,
    mes_ano: Optional[str] = None,
    data_referencia: Optional[date] = None
) -> Dict[str, Any]:
    """
    Calcula as despesas variáveis esperadas.
    Para outubro/2026:
    Utiliza previsão manual de gastos futuros a partir da data atual (19/10 a 31/10).
    Lançamentos reais POSTERIORES à data de referência consomem e abatem a previsão,
    sem duplicação de valores.
    Exclui rigorosamente dívidas, acordos, cartões e parcelas.
    """
    if data_referencia is None:
        data_referencia = date.today()
    if mes_ano is None:
        mes_ano = data_referencia.strftime("%Y-%m")

    cur = conn.cursor()
    dt_ref_str = data_referencia.strftime("%Y-%m-%d")

    # Categorias de dívidas/parcelas a ignorar estritamente
    CATEGORIAS_IGNORAR = {
        "Acordo BV", "Outras Dívidas", "Pagamento de fatura", "Impostos Veículo",
        "Saldo Inicial", "Salário Fernanda", "Renda Corridas (99/Uber)"
    }

    # Busca limites de gastos cadastrados (tetos de segurança)
    cur.execute("SELECT categoria, limite FROM limites_categoria")
    tetos_categoria = {r[0]: to_decimal(r[1]) for r in cur.fetchall()}

    # Busca previsões manuais cadastradas para o mês
    cur.execute("""
        SELECT categoria, valor_previsto, essencial_semanal, tipo_previsao
        FROM planejamento_previsao_variaveis
        WHERE mes_ano = ?
    """, (mes_ano,))
    previsoes_db = {r[0]: (to_decimal(r[1]), to_decimal(r[2]), r[3]) for r in cur.fetchall()}

    # Valores padrão iniciais de previsão manual a partir de 19/10 (para quando não houver registro manual)
    PREVISOES_PADRAO_OUTUBRO = {
        "Supermercado": (Decimal("350.00"), Decimal("120.00")),
        "Medicamentos": (Decimal("80.00"), Decimal("30.00")),
        "Combustível": (Decimal("200.00"), Decimal("70.00")),
        "Restaurante": (Decimal("100.00"), Decimal("0.00")),
        "Outros": (Decimal("60.00"), Decimal("0.00"))
    }

    detalhe_categorias = []
    total_consumo_esperado_restante = Decimal("0.00")
    total_essencial_semana = Decimal("0.00")

    todas_categorias = set(tetos_categoria.keys()) | set(previsoes_db.keys()) | set(PREVISOES_PADRAO_OUTUBRO.keys())
    todas_categorias = {c for c in todas_categorias if c not in CATEGORIAS_IGNORAR}

    for cat in sorted(todas_categorias):
        teto = tetos_categoria.get(cat, Decimal("0.00"))

        if cat in previsoes_db:
            val_previsto, val_essencial_sem, tipo_prev = previsoes_db[cat]
        elif mes_ano == "2026-10" and cat in PREVISOES_PADRAO_OUTUBRO:
            val_previsto, val_essencial_sem = PREVISOES_PADRAO_OUTUBRO[cat]
            tipo_prev = "a_partir_de_hoje"
        else:
            val_previsto = teto * Decimal("0.5")  # fallback conservador
            val_essencial_sem = val_previsto * Decimal("0.25")
            tipo_prev = "mensal"

        # Gasto já realizado DEPOIS da data de referência (que consome a previsão futura)
        cur.execute("""
            SELECT COALESCE(SUM(valor), 0.0)
            FROM transacoes
            WHERE categoria = ? AND tipo = 'despesa' AND data > ? AND data LIKE ?
        """, (cat, dt_ref_str, f"{mes_ano}%"))
        gasto_posterior = to_decimal(cur.fetchone()[0])

        # Consumo restante esperado: a despesa real posterior substitui a previsão
        consumo_restante = max(Decimal("0.00"), val_previsto - gasto_posterior)
        total_consumo_esperado_restante += consumo_restante
        total_essencial_semana += val_essencial_sem

        detalhe_categorias.append({
            "categoria": cat,
            "teto_limite": teto,
            "previsao_futura": val_previsto,
            "gasto_posterior_realizado": gasto_posterior,
            "consumo_restante": consumo_restante,
            "essencial_semanal": val_essencial_sem,
            "tipo_previsao": tipo_prev
        })

    return {
        "mes_ano": mes_ano,
        "detalhe_categorias": detalhe_categorias,
        "total_consumo_esperado_restante": total_consumo_esperado_restante,
        "total_essencial_semana": total_essencial_semana
    }


# =============================================================================
# 4. MISSÃO PRIORITÁRIA (IPVA) E GESTÃO DE RESERVAS VIRTUAIS
# =============================================================================
def obter_status_missao_ipva(
    conn: sqlite3.Connection,
    mes_ano: Optional[str] = None,
    data_referencia: Optional[date] = None
) -> Dict[str, Any]:
    """
    Recupera a Missão Prioritária vinculada à obrigação existente do IPVA (id=33),
    sem criar duplicidade de passivo nem gerar movimentações bancárias automáticas.
    """
    if data_referencia is None:
        data_referencia = date.today()
    if mes_ano is None:
        mes_ano = data_referencia.strftime("%Y-%m")

    cur = conn.cursor()

    # 1. Localiza a obrigação real do IPVA
    cur.execute("""
        SELECT id, data, descricao, valor, pago
        FROM transacoes
        WHERE (descricao LIKE '%IPVA%' OR categoria LIKE '%IPVA%')
          AND tipo = 'despesa'
        ORDER BY id DESC LIMIT 1
    """)
    row_ipva = cur.fetchone()

    if not row_ipva:
        return {"tem_missao": False, "mensagem": "Nenhuma obrigação de IPVA encontrada no banco."}

    t_id, t_data, t_desc, t_valor, t_pago = row_ipva
    dt_venc = datetime.strptime(t_data, "%Y-%m-%d").date() if isinstance(t_data, str) else t_data
    valor_nominal = to_decimal(t_valor)

    # 2. Resumo de pagamentos reais já efetuados
    resumo_obrig = saldo_service.obter_resumo_obrigacao(conn, t_id)
    valor_ja_pago = resumo_obrig["total_pago"]

    # 3. Busca meta e reserva virtual cadastrada em planejamento_metas
    cur.execute("""
        SELECT id, valor_reservado, turnos_planejados, horas_por_turno,
               ganho_bruto_hora_estimado, combustivel_hora_estimado
        FROM planejamento_metas
        WHERE transacao_alvo_id = ? AND mes_ano = ?
    """, (t_id, mes_ano))
    row_meta = cur.fetchone()

    if row_meta:
        meta_id, val_res, t_plan, h_turno, g_h, c_h = row_meta
        valor_reservado = to_decimal(val_res)
        turnos_planejados = int(t_plan or 5)
        horas_turno = float(h_turno or 4.0)
        ganho_hora = float(g_h or 35.0)
        comb_hora = float(c_h or 10.0)
    else:
        meta_id = None
        valor_reservado = Decimal("0.00")
        turnos_planejados = 5
        horas_turno = 4.0
        ganho_hora = 35.0
        comb_hora = 10.0

    # 4. Cálculos de Saldo e Prazo
    # O que falta cobrir: valor nominal menos o que já foi pago e menos o que já está reservado
    saldo_devedor_restante = max(Decimal("0.00"), valor_nominal - valor_ja_pago - valor_reservado)
    dias_restantes = max(0, (dt_venc - data_referencia).days)

    meta_por_turno = (
        saldo_devedor_restante / Decimal(str(max(1, turnos_planejados)))
    ).quantize(CENTAVOS, rounding=ROUND_HALF_EVEN)

    percentual_coberto = (
        ((valor_ja_pago + valor_reservado) / valor_nominal * 100)
        if valor_nominal > 0 else Decimal("100.00")
    )

    return {
        "tem_missao": True,
        "meta_id": meta_id,
        "transacao_id": t_id,
        "titulo": t_desc,
        "data_vencimento": t_data,
        "dias_restantes": dias_restantes,
        "valor_nominal": valor_nominal,
        "valor_ja_pago": valor_ja_pago,
        "valor_reservado": valor_reservado,
        "saldo_devedor_restante": saldo_devedor_restante,
        "percentual_coberto": float(percentual_coberto),
        "turnos_planejados": turnos_planejados,
        "horas_por_turno": horas_turno,
        "meta_por_turno": meta_por_turno,
        "ganho_hora_estimado": ganho_hora,
        "comb_hora_estimado": comb_hora
    }


def atualizar_reserva_missao(
    conn: sqlite3.Connection,
    transacao_id: int,
    valor_reserva: Decimal,
    mes_ano: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Atualiza a reserva virtual vinculada a uma missão.
    Não permite reservar mais do que o saldo total disponível no banco,
    garantindo consistência contábil sem criar movimentação financeira.
    """
    if mes_ano is None:
        mes_ano = date.today().strftime("%Y-%m")
    saldo_info = saldo_service.calcular_saldo_consolidado(conn)
    saldo_disp = saldo_info["saldo_consolidado"]

    if valor_reserva < Decimal("0.00"):
        return False, "O valor da reserva não pode ser negativo."

    if valor_reserva > saldo_disp:
        return False, f"Reserva (R$ {valor_reserva:.2f}) excede o saldo disponível total (R$ {saldo_disp:.2f})."

    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM planejamento_metas
        WHERE transacao_alvo_id = ? AND mes_ano = ?
    """, (transacao_id, mes_ano))
    row = cur.fetchone()

    val_flt = float(valor_reserva)
    if row:
        cur.execute("""
            UPDATE planejamento_metas
            SET valor_reservado = ?
            WHERE id = ?
        """, (val_flt, row[0]))
    else:
        cur.execute("""
            SELECT data, descricao, valor FROM transacoes WHERE id = ?
        """, (transacao_id,))
        t_row = cur.fetchone()
        dt_venc = t_row[0] if t_row else "2026-10-29"
        tit = t_row[1] if t_row else "Missão IPVA"
        val_nom = float(t_row[2]) if t_row else 431.11

        cur.execute("""
            INSERT INTO planejamento_metas (mes_ano, titulo, transacao_alvo_id, valor_alvo, valor_reservado, data_limite)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (mes_ano, tit, transacao_id, val_nom, val_flt, dt_venc))

    conn.commit()
    return True, f"Reserva de R$ {valor_reserva:.2f} atualizada com sucesso!"


# =============================================================================
# 5. SIMULAÇÃO DE METAS DE TRABALHO DO MOTORISTA & VIABILIDADE RIGOROSA
# =============================================================================
def calcular_viabilidade_metas_trabalho(
    necessidade_financeira: Decimal,
    dias_disponiveis: int = 5,
    horas_disponiveis_dia: float = 4.0,
    ganho_bruto_hora: float = 35.0,
    combustivel_hora: float = 10.0
) -> Dict[str, Any]:
    """
    Calcula a viabilidade operacional do motorista para cobrir a necessidade financeira.
    Regra de rigor exigida pelo usuário:
    Se preciso de 21 horas, mas tenho apenas 20 disponíveis, a meta NÃO está coberta (déficit de 1 hora).
    """
    ganho_liq_hora = max(1.0, ganho_bruto_hora - combustivel_hora)
    liq_decimal = to_decimal(ganho_liq_hora)

    horas_disponiveis_total = float(dias_disponiveis * horas_disponiveis_dia)
    
    # Horas necessárias para cobrir o valor em dinheiro
    if necessidade_financeira <= Decimal("0.00"):
        horas_necessarias = 0.0
    else:
        horas_necessarias = float(necessidade_financeira / liq_decimal)

    diferenca_horas = horas_disponiveis_total - horas_necessarias

    # Classificação rigorosa de viabilidade
    if horas_necessarias <= 0:
        status_viabilidade = "coberta_folga"
        rotulo_viabilidade = "Meta 100% Coberta (Sem necessidade de caixa adicional)"
        cor_badge = "green"
    elif horas_necessarias <= horas_disponiveis_total:
        folga = diferenca_horas
        status_viabilidade = "coberta"
        rotulo_viabilidade = f"Meta Coberta com Sucesso (Folga de {folga:.1f}h)"
        cor_badge = "green"
    else:
        deficit = abs(diferenca_horas)
        status_viabilidade = "deficit"
        rotulo_viabilidade = f"Meta NÃO Coberta (Faltam {deficit:.1f} horas de volante)"
        cor_badge = "red"

    return {
        "necessidade_financeira": necessidade_financeira,
        "ganho_bruto_hora": ganho_bruto_hora,
        "combustivel_hora": combustivel_hora,
        "ganho_liquido_hora": ganho_liq_hora,
        "dias_disponiveis": dias_disponiveis,
        "horas_disponiveis_dia": horas_disponiveis_dia,
        "horas_disponiveis_total": horas_disponiveis_total,
        "horas_necessarias": round(horas_necessarias, 1),
        "diferenca_horas": round(diferenca_horas, 1),
        "status_viabilidade": status_viabilidade,
        "rotulo_viabilidade": rotulo_viabilidade,
        "cor_badge": cor_badge,
        "modo_estimativa": True
    }
