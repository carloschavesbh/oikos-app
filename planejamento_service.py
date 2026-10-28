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

    # 6. Adiciona status e prioridade em planejamento_metas para missões flexíveis
    cur.execute("PRAGMA table_info(planejamento_metas)")
    cols_metas = [c[1] for c in cur.fetchall()]
    if 'status' not in cols_metas:
        try:
            cur.execute("ALTER TABLE planejamento_metas ADD COLUMN status TEXT DEFAULT 'ativa'")
        except Exception:
            pass
    if 'prioridade' not in cols_metas:
        try:
            cur.execute("ALTER TABLE planejamento_metas ADD COLUMN prioridade TEXT DEFAULT 'alta'")
        except Exception:
            pass
    if 'ativa_na_semana' not in cols_metas:
        try:
            cur.execute("ALTER TABLE planejamento_metas ADD COLUMN ativa_na_semana INTEGER DEFAULT 1")
        except Exception:
            pass

    # 7. Tabela de Cofrinhos Reais (Mercado Pago / Envelopes)
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

    # Sementes dos cofrinhos reais conhecidos pelo usuário (iniciados com saldo R$ 0,00 sem presumir positivo)
    cofrinhos_iniciais = [
        ("Cofrinho IPVA", "Reserva para IPVA 2025/2026", 431.11),
        ("Cofrinho Acordo BV", "Reserva para Acordo BV", 1428.82),
        ("Cofrinho Rubens", "Reserva Rubens", 0.0),
        ("Cofrinho Contas de Casa", "Reserva para contas essenciais da casa", 0.0),
        ("Cofrinho Mercado", "Alimentação e supermercado", 0.0),
        ("Cofrinho Reserva de Segurança", "Fundo de emergência familiar", 0.0)
    ]
    for nome_c, obj_c, meta_c in cofrinhos_iniciais:
        cur.execute("""
            INSERT OR IGNORE INTO cofrinhos (conta_pai_id, nome, saldo_confirmado, meta_valor, objetivo, data_atualizacao)
            VALUES (1, ?, 0.0, ?, ?, date('now'))
        """, (nome_c, meta_c, obj_c))

    # Garante colunas de conta vinculada e inclusão no consolidado em cofrinhos
    cur.execute("PRAGMA table_info(cofrinhos)")
    cols_cof = [r[1] for r in cur.fetchall()]
    if "conta_config_id" not in cols_cof:
        try:
            cur.execute("ALTER TABLE cofrinhos ADD COLUMN conta_config_id INTEGER REFERENCES contas_config(id)")
        except Exception:
            pass
    if "incluir_saldo_consolidado" not in cols_cof:
        try:
            cur.execute("ALTER TABLE cofrinhos ADD COLUMN incluir_saldo_consolidado INTEGER DEFAULT 0")
        except Exception:
            pass

    conn.commit()



# =============================================================================
# 1. CÁLCULO DA NECESSIDADE DE CAIXA DOS PRÓXIMOS 7 DIAS
# =============================================================================
def calcular_necessidade_caixa_7dias(
    conn: sqlite3.Connection,
    data_referencia: Optional[date] = None,
    semana_ref: Optional[str] = None,
    incluir_bv_semana: bool = False,
    missao_transacao_id: Optional[int] = None,
    incluir_variaveis: bool = False
) -> Dict[str, Any]:
    """
    Calcula a necessidade de caixa dos próximos 7 dias diferenciando:
    - Obrigações regulares confirmadas da semana corrente (sem forçar BV nem todas atrasadas).
    - Obrigações vencidas selecionadas voluntariamente como prioritárias ou como missão.
    - Acordo BV incluído estritamente se incluir_bv_semana=True.
    - Missão ativa da semana (adiciona de forma limpa e transparente o valor restante).
    - Saldo livre e entradas confirmadas.
    """
    if data_referencia is None:
        data_referencia = date.today()
    if semana_ref is None:
        semana_ref = data_referencia.strftime("%Y-W%W")

    data_limite_7d = data_referencia + timedelta(days=6)
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

        # Caso A: Fatura ou acordo com parcelamento pesado/longo prazo (ex: Acordo BV)
        if t_st_fatura == "pendente_confirmacao" or "Acordo BV" in t_desc or "BV" in t_desc:
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

    # 4. Gastos Variáveis Essenciais Esperados na Semana (opcional)
    gastos_variaveis_semana = Decimal("0.00")
    if incluir_variaveis:
        cur.execute("""
            SELECT COALESCE(SUM(essencial_semanal), 0.0)
            FROM planejamento_previsao_variaveis
            WHERE mes_ano = ?
        """, (mes_ano_ref,))
        row_var = cur.fetchone()
        gastos_variaveis_semana = to_decimal(row_var[0] if row_var else Decimal("150.00"))

    # 5. Missão Ativa da Semana (Adiciona o valor restante de forma limpa)
    valor_missao_semana = Decimal("0.00")
    missao_info: Optional[Dict[str, Any]] = None
    if missao_transacao_id is not None:
        if missao_transacao_id > 0:
            res_m = saldo_service.obter_resumo_obrigacao(conn, missao_transacao_id)
            if res_m:
                cur.execute("SELECT COALESCE(valor_reservado, 0.0), titulo FROM planejamento_metas WHERE transacao_alvo_id = ? AND mes_ano = ?", (missao_transacao_id, mes_ano_ref))
                row_m = cur.fetchone()
                res_m_val = to_decimal(row_m[0] if row_m else 0.0)
                tit_m = row_m[1] if row_m else res_m["descricao"]
                sal_m = max(Decimal("0.00"), res_m["saldo_devedor"] - res_m_val)
                missao_info = {
                    "transacao_id": missao_transacao_id,
                    "titulo": tit_m,
                    "saldo_devedor_restante": sal_m
                }
                ja_incluso = any(x["id"] == missao_transacao_id for x in obrigacoes_confirmadas_7d) or any(x["id"] == missao_transacao_id for x in obrigacoes_vencidas_prioritarias)
                if not ja_incluso:
                    valor_missao_semana = sal_m
    else:
        missao_info = obter_missao_ativa_semana(conn, mes_ano_ref, data_referencia)
        if missao_info and missao_info.get("tem_missao") and missao_info.get("is_ativa"):
            t_m_id = missao_info.get("transacao_id")
            sal_m = to_decimal(missao_info.get("saldo_devedor_restante", 0.0))
            ja_incluso = any(x["id"] == t_m_id for x in obrigacoes_confirmadas_7d) or any(x["id"] == t_m_id for x in obrigacoes_vencidas_prioritarias)
            if not ja_incluso:
                valor_missao_semana = sal_m

    # 6. Acordo BV: apenas se o usuário ativar explicitamente a opção
    valor_bv_semana = total_pendente_confirmacao if incluir_bv_semana else Decimal("0.00")

    # 7. Entradas Futuras Confirmadas nos Próximos 7 Dias (receitas pendentes confirmadas)
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0.0)
        FROM transacoes
        WHERE tipo = 'receita' AND pago = 0 AND data >= ? AND data <= ?
    """, (dt_ref_str, dt_limite_str))
    row_rec = cur.fetchone()
    entradas_futuras_confirmadas = to_decimal(row_rec[0] if row_rec else 0.0)

    # 8. Cálculo dos Totais e da Necessidade Adicional de Caixa
    compromissos_minimos_semana = (
        total_confirmadas_7d +
        total_vencidas_prioritarias +
        valor_missao_semana +
        valor_bv_semana +
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
        "valor_bv_semana": valor_bv_semana,
        "incluir_bv_semana": incluir_bv_semana,
        "valor_missao_semana": valor_missao_semana,
        "missao_info": missao_info,
        "gastos_variaveis_semana": gastos_variaveis_semana,
        "entradas_futuras_confirmadas": entradas_futuras_confirmadas,
        "compromissos_minimos_semana": compromissos_minimos_semana,
        "necessidade_adicional_caixa": necessidade_adicional_caixa,
        "status_bv_pendente": len(valores_pendentes_confirmacao) > 0,
        "aviso_bv": (
            f"O Acordo BV (R$ {total_pendente_confirmacao:,.2f}) está mantido na Meta Mensal para preservar o ritmo de trabalho saudável."
            if not incluir_bv_semana and total_pendente_confirmacao > 0 else
            (f"Acordo BV (R$ {total_pendente_confirmacao:,.2f}) incluído na meta desta semana por escolha do usuário." if incluir_bv_semana else "")
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

    # Categorias de dívidas/parcelas e despesas contratuais fixas a ignorar estritamente
    # para evitar duplicidade com as obrigações confirmadas de contas a pagar
    CATEGORIAS_IGNORAR = {
        "Acordo BV", "Outras Dívidas", "Pagamento de fatura", "Impostos Veículo",
        "Saldo Inicial", "Salário Fernanda", "Renda Corridas (99/Uber)",
        "Habitação", "Água (Copasa)", "Energia (CEMIG + CEMIG SIM)", "Internet Residencial",
        "Telefone (Fernanda)", "Streaming", "Streaming / Entretenimento", "Plano de Saúde",
        "Plano Odonto", "Pós-Graduação Fernanda", "Seguro Veículo (HB20 AGV)",
        "Documentação (IPVA, Multas)", "Conta Capital Sicoob", "Crediserv - Empréstimo",
        "Dízimo (Igreja)", "Reserva de Emergência"
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
        elif any(k in cat.lower() for k in ["supermercado", "alimenta", "refei", "padaria", "farm", "medic", "combust", "restaurante", "lazer", "eventual"]):
            val_previsto = teto * Decimal("0.5")  # fallback conservador para variáveis autênticas
            val_essencial_sem = val_previsto * Decimal("0.25")
            tipo_prev = "mensal"
        else:
            val_previsto = Decimal("0.00")
            val_essencial_sem = Decimal("0.00")
            tipo_prev = "ignorado_fixo"

        # Gasto já realizado DEPOIS da data de referência (apenas despesas avulsas pagas, sem parcelas futuras)
        cur.execute("""
            SELECT COALESCE(SUM(valor), 0.0)
            FROM transacoes
            WHERE (categoria = ? OR subcategoria_id IN (SELECT id FROM subcategorias WHERE nome = ?))
              AND tipo = 'despesa'
              AND pago = 1
              AND (grupo_parcelamento IS NULL OR grupo_parcelamento = '')
              AND data > ? AND data LIKE ?
        """, (cat, cat, dt_ref_str, f"{mes_ano}%"))
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
    dt_venc_padrao = datetime.strptime(t_data, "%Y-%m-%d").date() if isinstance(t_data, str) else t_data
    valor_nominal_padrao = to_decimal(t_valor)

    # 2. Resumo de pagamentos reais já efetuados no banco
    resumo_obrig = saldo_service.obter_resumo_obrigacao(conn, t_id)
    valor_ja_pago = resumo_obrig["total_pago"]

    # 3. Busca meta e reserva virtual cadastrada em planejamento_metas
    cur.execute("""
        SELECT id, valor_reservado, turnos_planejados, horas_por_turno,
               ganho_bruto_hora_estimado, combustivel_hora_estimado,
               status, prioridade, valor_alvo, data_limite, titulo
        FROM planejamento_metas
        WHERE transacao_alvo_id = ? AND mes_ano = ?
    """, (t_id, mes_ano))
    row_meta = cur.fetchone()

    if row_meta:
        meta_id = row_meta[0]
        valor_reservado = to_decimal(row_meta[1])
        turnos_planejados = int(row_meta[2] or 5)
        horas_turno = float(row_meta[3] or 4.0)
        ganho_hora = float(row_meta[4] or 35.0)
        comb_hora = float(row_meta[5] or 10.0)
        status = str(row_meta[6] or 'ativa')
        prioridade = str(row_meta[7] or 'alta')
        valor_alvo = to_decimal(row_meta[8]) if row_meta[8] else valor_nominal_padrao
        data_limite_str = str(row_meta[9]) if row_meta[9] else str(t_data)
        titulo = str(row_meta[10]) if row_meta[10] else str(t_desc)
    else:
        meta_id = None
        valor_reservado = Decimal("0.00")
        turnos_planejados = 5
        horas_turno = 4.0
        ganho_hora = 35.0
        comb_hora = 10.0
        status = 'ativa'
        prioridade = 'alta'
        valor_alvo = valor_nominal_padrao
        data_limite_str = str(t_data)
        titulo = str(t_desc)

    dt_venc = datetime.strptime(data_limite_str, "%Y-%m-%d").date() if isinstance(data_limite_str, str) else data_limite_str

    # 3.1 Cofrinho IPVA (Fundo IPVA) - alimenta automaticamente a reserva sem lançar duas vezes
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cofrinhos'")
    if cur.fetchone() is not None:
        cur.execute("""
            SELECT id, saldo_confirmado, conta_config_id 
            FROM cofrinhos 
            WHERE nome LIKE '%IPVA%' 
            ORDER BY id ASC LIMIT 1
        """)
        row_cof_ipva = cur.fetchone()
        saldo_cof_ipva = Decimal("0.00")
        if row_cof_ipva:
            if row_cof_ipva[2]:
                try:
                    res_sc = saldo_service.calcular_saldo_conta(conn, row_cof_ipva[2])
                    saldo_cof_ipva = res_sc["saldo_atual"]
                except Exception:
                    saldo_cof_ipva = to_decimal(row_cof_ipva[1])
            else:
                saldo_cof_ipva = to_decimal(row_cof_ipva[1])
        valor_reservado = max(valor_reservado, saldo_cof_ipva)

    # 4. Cálculos de Saldo e Prazo
    # O que falta cobrir: valor alvo menos o que já foi pago e menos o que já está reservado
    saldo_devedor_restante = max(Decimal("0.00"), valor_alvo - valor_ja_pago - valor_reservado)
    dias_restantes = max(0, (dt_venc - data_referencia).days)

    meta_por_turno = (
        saldo_devedor_restante / Decimal(str(max(1, turnos_planejados)))
    ).quantize(CENTAVOS, rounding=ROUND_HALF_EVEN)

    percentual_coberto = (
        ((valor_ja_pago + valor_reservado) / valor_alvo * 100)
        if valor_alvo > 0 else Decimal("100.00")
    )

    return {
        "tem_missao": True,
        "meta_id": meta_id,
        "transacao_id": t_id,
        "titulo": titulo,
        "data_vencimento": data_limite_str,
        "dias_restantes": dias_restantes,
        "valor_nominal": valor_alvo,
        "valor_ja_pago": valor_ja_pago,
        "valor_reservado": valor_reservado,
        "saldo_devedor_restante": saldo_devedor_restante,
        "percentual_coberto": float(percentual_coberto),
        "turnos_planejados": turnos_planejados,
        "horas_por_turno": horas_turno,
        "meta_por_turno": meta_por_turno,
        "ganho_hora_estimado": ganho_hora,
        "comb_hora_estimado": comb_hora,
        "status": status,
        "prioridade": prioridade,
        "is_ativa": status == "ativa",
        "is_concluida": status == "concluida"
    }


def atualizar_missao_parametros(
    conn: sqlite3.Connection,
    transacao_id: int,
    valor_alvo: Decimal,
    data_limite: str,
    prioridade: str = "alta",
    valor_reserva: Decimal = Decimal("0.00"),
    turnos_planejados: int = 5,
    horas_por_turno: float = 4.0,
    status: str = "ativa",
    titulo: Optional[str] = None,
    mes_ano: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Edita os parâmetros da missão: valor, vencimento, prioridade, reserva virtual, turnos e status.
    Garante consistência: não cria pagamentos fictícios e valida se a reserva virtual não ultrapassa o saldo disponível.
    """
    if mes_ano is None:
        mes_ano = date.today().strftime("%Y-%m")

    saldo_info = saldo_service.calcular_saldo_consolidado(conn)
    saldo_disp = saldo_info["saldo_consolidado"]

    if valor_reserva < Decimal("0.00"):
        return False, "O valor da reserva não pode ser negativo."

    if valor_reserva > saldo_disp:
        return False, f"Reserva (R$ {valor_reserva:.2f}) excede o saldo disponível total em caixa (R$ {saldo_disp:.2f})."

    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM planejamento_metas
        WHERE transacao_alvo_id = ? AND mes_ano = ?
    """, (transacao_id, mes_ano))
    row = cur.fetchone()

    val_alvo_flt = float(valor_alvo)
    val_res_flt = float(valor_reserva)

    if row:
        meta_id = row[0]
        cur.execute("""
            UPDATE planejamento_metas
            SET valor_alvo = ?,
                data_limite = ?,
                prioridade = ?,
                valor_reservado = ?,
                turnos_planejados = ?,
                horas_por_turno = ?,
                status = ?,
                titulo = COALESCE(?, titulo)
            WHERE id = ?
        """, (val_alvo_flt, str(data_limite), prioridade, val_res_flt, turnos_planejados, horas_por_turno, status, titulo, meta_id))
    else:
        if not titulo:
            cur.execute("SELECT descricao FROM transacoes WHERE id = ?", (transacao_id,))
            t_row = cur.fetchone()
            titulo = t_row[0] if t_row else "Missão IPVA"

        cur.execute("""
            INSERT INTO planejamento_metas (
                mes_ano, titulo, transacao_alvo_id, valor_alvo, valor_reservado,
                data_limite, turnos_planejados, horas_por_turno, status, prioridade
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (mes_ano, titulo, transacao_id, val_alvo_flt, val_res_flt, str(data_limite), turnos_planejados, horas_por_turno, status, prioridade))

    conn.commit()
    return True, f"Missão '{titulo}' atualizada com sucesso!"


def atualizar_status_missao(
    conn: sqlite3.Connection,
    transacao_id: int,
    novo_status: str,
    mes_ano: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Atualiza o estado de uma missão ('ativa', 'pausada', 'concluida', 'arquivada').
    Quando concluída (quitada), a missão deixa de aparecer como pendência ativa, permanecendo no histórico.
    Não cria pagamentos fictícios nem altera a transação bancária original.
    """
    if novo_status not in ('ativa', 'pausada', 'concluida', 'arquivada'):
        return False, f"Status inválido: '{novo_status}'."

    if mes_ano is None:
        mes_ano = date.today().strftime("%Y-%m")

    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM planejamento_metas
        WHERE transacao_alvo_id = ? AND mes_ano = ?
    """, (transacao_id, mes_ano))
    row = cur.fetchone()

    if row:
        cur.execute("UPDATE planejamento_metas SET status = ? WHERE id = ?", (novo_status, row[0]))
    else:
        cur.execute("SELECT data, descricao, valor FROM transacoes WHERE id = ?", (transacao_id,))
        t_row = cur.fetchone()
        dt_venc = t_row[0] if t_row else "2026-10-29"
        tit = t_row[1] if t_row else "Missão IPVA"
        val_nom = float(t_row[2]) if t_row else 431.11

        cur.execute("""
            INSERT INTO planejamento_metas (mes_ano, titulo, transacao_alvo_id, valor_alvo, valor_reservado, data_limite, status)
            VALUES (?, ?, ?, ?, 0.0, ?, ?)
        """, (mes_ano, tit, transacao_id, val_nom, dt_venc, novo_status))

    conn.commit()
    return True, f"Status da missão alterado para '{novo_status}' com sucesso!"


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


def obter_missao_ativa_semana(
    conn: sqlite3.Connection,
    mes_ano: Optional[str] = None,
    data_referencia: Optional[date] = None,
    mes_str: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Retorna a missão ativa vinculada à meta da semana corrente.
    Prioriza o registro em planejamento_metas com ativa_na_semana = 1 e status = 'ativa'.
    Se nenhuma for marcada explicitamente, assume por padrão o IPVA (se houver obrigação ativa).
    Suporta de forma transparente mes_ano ou mes_str para compatibilidade total com o dashboard.
    """
    if mes_ano is None and mes_str is not None:
        mes_ano = mes_str
    if data_referencia is None:
        data_referencia = date.today()
    if mes_ano is None:
        mes_ano = data_referencia.strftime("%Y-%m")

    cur = conn.cursor()
    inicializar_esquema_planejamento(conn)

    cur.execute("""
        SELECT id, transacao_alvo_id, titulo, valor_alvo, valor_reservado,
               data_limite, turnos_planejados, horas_por_turno, status, prioridade
        FROM planejamento_metas
        WHERE mes_ano = ? AND status = 'ativa' AND COALESCE(ativa_na_semana, 1) = 1
        ORDER BY id DESC LIMIT 1
    """, (mes_ano,))
    row = cur.fetchone()

    if not row:
        return obter_status_missao_ipva(conn, mes_ano, data_referencia)

    meta_id, t_id, titulo, val_alvo, val_res, dt_limite, turnos, horas_t, status, prio = row
    val_alvo_dec = to_decimal(val_alvo)
    val_res_dec = to_decimal(val_res)

    if t_id:
        resumo_obrig = saldo_service.obter_resumo_obrigacao(conn, t_id)
        val_ja_pago = resumo_obrig["total_pago"] if resumo_obrig else Decimal("0.00")
        dt_venc_str = str(dt_limite) if dt_limite else (resumo_obrig["data_vencimento"] if resumo_obrig else str(data_referencia))
    else:
        val_ja_pago = Decimal("0.00")
        dt_venc_str = str(dt_limite) if dt_limite else str(data_referencia)

    if "ipva" in str(titulo).lower():
        cur.execute("SELECT id, saldo_confirmado FROM cofrinhos WHERE nome LIKE '%IPVA%' LIMIT 1")
        row_cof = cur.fetchone()
        if row_cof:
            val_res_dec = max(val_res_dec, to_decimal(row_cof[1]))

    saldo_restante = max(Decimal("0.00"), val_alvo_dec - val_ja_pago - val_res_dec)
    try:
        dt_venc_obj = datetime.strptime(dt_venc_str, "%Y-%m-%d").date()
        dias_rest = max(0, (dt_venc_obj - data_referencia).days)
    except Exception:
        dias_rest = 0

    pct = float(((val_ja_pago + val_res_dec) / val_alvo_dec * 100)) if val_alvo_dec > 0 else 100.0
    meta_turno = (saldo_restante / Decimal(str(max(1, turnos or 5)))).quantize(CENTAVOS, rounding=ROUND_HALF_EVEN)

    return {
        "tem_missao": True,
        "meta_id": meta_id,
        "transacao_id": t_id,
        "titulo": titulo,
        "data_vencimento": dt_venc_str,
        "dias_restantes": dias_rest,
        "valor_nominal": val_alvo_dec,
        "valor_ja_pago": val_ja_pago,
        "valor_reservado": val_res_dec,
        "saldo_devedor_restante": saldo_restante,
        "percentual_coberto": pct,
        "turnos_planejados": turnos or 5,
        "horas_por_turno": horas_t or 4.0,
        "meta_por_turno": meta_turno,
        "status": status,
        "prioridade": prio,
        "is_ativa": status == "ativa",
        "is_concluida": status == "concluida"
    }


def obter_opcoes_missoes_semana(conn: sqlite3.Connection, mes_ano: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retorna todas as opções disponíveis para serem selecionadas como Missão da Semana:
    - Missões já cadastradas (IPVA, etc.)
    - Contas vencidas / atrasadas de outubro
    - Contas futuras da casa
    """
    if mes_ano is None:
        mes_ano = date.today().strftime("%Y-%m")
    cur = conn.cursor()
    inicializar_esquema_planejamento(conn)

    cur.execute("""
        SELECT t.id, t.data, t.descricao, t.valor, t.categoria, t.conta
        FROM transacoes t
        WHERE t.tipo = 'despesa' AND (t.pago IS NULL OR t.pago != 1)
        ORDER BY t.data ASC, t.id ASC
    """)
    rows = cur.fetchall()

    hoje = date.today()
    dt_hoje_str = hoje.strftime("%Y-%m-%d")

    cur.execute("SELECT transacao_alvo_id, ativa_na_semana FROM planejamento_metas WHERE mes_ano = ?", (mes_ano,))
    metas_map = {r[0]: r[1] for r in cur.fetchall()}

    opcoes = []
    for r in rows:
        t_id, t_data, t_desc, t_val, t_cat, t_conta = r
        resumo = saldo_service.obter_resumo_obrigacao(conn, t_id)
        saldo_dev = resumo["saldo_devedor"]
        if saldo_dev <= Decimal("0.00"):
            continue

        is_vencida = str(t_data) < dt_hoje_str
        is_ipva = "ipva" in t_desc.lower()
        is_bv = "bv" in t_desc.lower()
        is_ativa = bool(metas_map.get(t_id, 0) == 1)

        if is_ipva:
            rotulo = f"🎯 [Missão IPVA] {t_desc} • Restante: R$ {saldo_dev:,.2f}"
            tipo = "missao_ipva"
        elif is_vencida:
            rotulo = f"🚨 [Atrasada {t_data[-2:]}/{t_data[5:7]}] {t_desc} • R$ {saldo_dev:,.2f}"
            tipo = "atrasada"
        elif is_bv:
            rotulo = f"🏦 [Acordo BV] {t_desc} • R$ {saldo_dev:,.2f}"
            tipo = "acordo"
        else:
            rotulo = f"📅 [Venc {t_data[-2:]}/{t_data[5:7]}] {t_desc} • R$ {saldo_dev:,.2f}"
            tipo = "regular"

        opcoes.append({
            "transacao_id": t_id,
            "titulo": t_desc,
            "data_vencimento": str(t_data),
            "valor_nominal": to_decimal(t_val),
            "saldo_devedor": saldo_dev,
            "tipo": tipo,
            "rotulo": rotulo,
            "is_vencida": is_vencida,
            "is_ativa_semana": is_ativa
        })

    return opcoes


def definir_missao_ativa_semana(
    conn: sqlite3.Connection,
    transacao_id: Optional[int],
    mes_ano: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Define qual obrigação é a Missão Ativa da Semana.
    Desativa outras missões semanais para manter foco em um desafio limpo por vez.
    Se transacao_id for None ou 0, desativa todas as missões da semana.
    """
    if mes_ano is None:
        mes_ano = date.today().strftime("%Y-%m")
    cur = conn.cursor()
    inicializar_esquema_planejamento(conn)

    cur.execute("UPDATE planejamento_metas SET ativa_na_semana = 0 WHERE mes_ano = ?", (mes_ano,))

    if not transacao_id or transacao_id == 0:
        conn.commit()
        return True, "Nenhuma missão extra ativa na semana. Meta focada apenas nas obrigações regulares."

    cur.execute("SELECT id FROM planejamento_metas WHERE transacao_alvo_id = ? AND mes_ano = ?", (transacao_id, mes_ano))
    row = cur.fetchone()

    if row:
        cur.execute("UPDATE planejamento_metas SET ativa_na_semana = 1, status = 'ativa' WHERE id = ?", (row[0],))
        conn.commit()
        return True, f"Missão #{transacao_id} ativada para a meta desta semana!"
    else:
        cur.execute("SELECT data, descricao, valor FROM transacoes WHERE id = ?", (transacao_id,))
        t = cur.fetchone()
        if not t:
            conn.commit()
            return False, f"Transação #{transacao_id} não encontrada."

        dt_venc, desc, val = t
        cur.execute("""
            INSERT INTO planejamento_metas (
                mes_ano, titulo, transacao_alvo_id, valor_alvo, valor_reservado,
                data_limite, turnos_planejados, horas_por_turno, status, prioridade, ativa_na_semana
            ) VALUES (?, ?, ?, ?, 0.0, ?, 5, 4.0, 'ativa', 'alta', 1)
        """, (mes_ano, desc, transacao_id, float(val), str(dt_venc)))
        conn.commit()
        return True, f"Obrigação '{desc}' vinculada com sucesso como Missão Ativa da Semana!"


# =============================================================================
# COFRINHOS REAIS (MERCADO PAGO / ENVELOPES)
# =============================================================================
def obter_cofrinhos(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Retorna a lista de cofrinhos reais cadastrados no Mercado Pago.
    Calcula dinamicamente o saldo com base nas transferências internas para a subconta vinculada.
    """
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(cofrinhos)")
    cols = [r[1] for r in cur.fetchall()]
    tem_cc = "conta_config_id" in cols
    tem_inc = "incluir_saldo_consolidado" in cols

    query = "SELECT id, conta_pai_id, nome, saldo_confirmado, meta_valor, objetivo, data_atualizacao, observacoes"
    if tem_cc:
        query += ", conta_config_id"
    else:
        query += ", NULL as conta_config_id"
    if tem_inc:
        query += ", incluir_saldo_consolidado"
    else:
        query += ", 0 as incluir_saldo_consolidado"
    query += " FROM cofrinhos ORDER BY id ASC"

    cur.execute(query)
    rows = cur.fetchall()
    res = []
    for r in rows:
        cof_id = r[0]
        c_pai_id = r[1]
        c_nome = r[2]
        s_conf = to_decimal(r[3])
        m_val = to_decimal(r[4])
        obj = r[5] or ""
        dt_at = r[6] or ""
        obs = r[7] or ""
        cc_id = r[8]
        inc_cons = r[9] if len(r) > 9 and r[9] is not None else 0

        # Se houver conta_config vinculada, calcula saldo contábil exato
        saldo_real = s_conf
        if cc_id:
            try:
                calc = saldo_service.calcular_saldo_conta(conn, cc_id)
                saldo_real = calc["saldo_atual"]
            except Exception:
                saldo_real = s_conf

        res.append({
            "id": cof_id,
            "conta_pai_id": c_pai_id,
            "nome": c_nome,
            "saldo_confirmado": saldo_real,
            "meta_valor": m_val,
            "objetivo": obj,
            "data_atualizacao": dt_at,
            "observacoes": obs,
            "conta_config_id": cc_id,
            "incluir_saldo_consolidado": inc_cons
        })
    return res



def atualizar_saldo_cofrinho(
    conn: sqlite3.Connection,
    cofrinho_id: int,
    novo_saldo: Decimal,
    observacoes: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Atualiza o saldo confirmado de um cofrinho real do Mercado Pago informado manualmente pelo usuário.
    Não duplica com o saldo geral da conta Mercado Pago.
    """
    if novo_saldo < Decimal("0.00"):
        return False, "O saldo do cofrinho não pode ser negativo."

    cur = conn.cursor()
    dt_hoje = date.today().strftime("%Y-%m-%d")
    val_flt = float(novo_saldo)
    cur.execute("""
        UPDATE cofrinhos
        SET saldo_confirmado = ?,
            data_atualizacao = ?,
            observacoes = COALESCE(?, observacoes)
        WHERE id = ?
    """, (val_flt, dt_hoje, observacoes, cofrinho_id))
    conn.commit()
    return True, f"Saldo do cofrinho atualizado para R$ {novo_saldo:.2f} com sucesso!"


def criar_ou_editar_cofrinho(
    conn: sqlite3.Connection,
    nome: str,
    meta_valor: Decimal,
    objetivo: str,
    cofrinho_id: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Permite cadastrar ou editar cofrinhos reais manualmente.
    """
    nome_limpo = nome.strip()
    if not nome_limpo:
        return False, "O nome do cofrinho não pode ser vazio."

    cur = conn.cursor()
    meta_flt = float(meta_valor)
    dt_hoje = date.today().strftime("%Y-%m-%d")

    if cofrinho_id:
        cur.execute("""
            UPDATE cofrinhos
            SET nome = ?, meta_valor = ?, objetivo = ?
            WHERE id = ?
        """, (nome_limpo, meta_flt, objetivo.strip(), cofrinho_id))
        conn.commit()
        return True, f"Cofrinho '{nome_limpo}' atualizado com sucesso!"
    else:
        try:
            cur.execute("""
                INSERT INTO cofrinhos (conta_pai_id, nome, saldo_confirmado, meta_valor, objetivo, data_atualizacao)
                VALUES (1, ?, 0.0, ?, ?, ?)
            """, (nome_limpo, meta_flt, objetivo.strip(), dt_hoje))
            conn.commit()
            return True, f"Cofrinho '{nome_limpo}' cadastrado com sucesso!"
        except sqlite3.IntegrityError:
            return False, f"Já existe um cofrinho com o nome '{nome_limpo}'."


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

    # Classificação rigorosa de viabilidade com linguagem prudente e estimativa
    if horas_necessarias <= 0:
        status_viabilidade = "coberta_folga"
        rotulo_viabilidade = "Estimativa: Sem necessidade adicional de caixa para compromissos mínimos confirmados"
        cor_badge = "green"
    elif horas_necessarias <= horas_disponiveis_total:
        folga = diferenca_horas
        status_viabilidade = "coberta"
        rotulo_viabilidade = f"Estimativa Preliminar: Meta coberta com margem estimada de {folga:.1f}h"
        cor_badge = "green"
    else:
        deficit = abs(diferenca_horas)
        status_viabilidade = "deficit"
        rotulo_viabilidade = f"Estimativa Preliminar: Projeção de déficit estimado de {deficit:.1f}h de volante"
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
        "modo_estimativa": True,
        "aviso_metodologico": "Projeção preliminar baseada em estimativas operacionais. Condições reais de trânsito e demanda podem variar."
    }
