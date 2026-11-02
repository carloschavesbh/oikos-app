"""
=============================================================================
PLANEJAMENTO DE RENDA FAMILIAR, CENÁRIOS E CALENDÁRIO ANUAL (12 MESES)
Módulo do Oikos Pessoal para análise da renda familiar (estável vs variável),
cenários de sensibilidade com controle de meses da amostra pelo usuário,
margem operacional do Drive (resultado após custos registrados), natureza das
despesas e calendário anual com cálculo real de contribuições e cofrinhos.
=============================================================================
"""

import sqlite3
import datetime
import calendar
from typing import Dict, List, Optional, Tuple, Any

# Naturezas Orçamentárias Permitidas (Classificação por atributo separado)
NATUREZAS_ORCAMENTARIAS = [
    {
        "id": "estrutura_familiar",
        "nome": "Estrutura da Família",
        "icone": "🏠",
        "descricao": "Despesas essenciais para manutenção do lar, alimentação, saúde, educação e trabalho."
    },
    {
        "id": "qualidade_vida",
        "nome": "Qualidade de Vida",
        "icone": "🌱",
        "descricao": "Bem-estar, lazer, cuidados pessoais, saídas e conforto familiar."
    },
    {
        "id": "objetivos_investimentos",
        "nome": "Objetivos & Investimentos",
        "icone": "🎯",
        "descricao": "Amortização de dívidas, formação de reservas e metas patrimoniais."
    }
]

MAPEAMENTO_PADRAO_NATUREZA = {
    # Estrutura da Família
    "Habitação": "estrutura_familiar",
    "HABITAÇÃO": "estrutura_familiar",
    "Moradia/Contas": "estrutura_familiar",
    "Energia": "estrutura_familiar",
    "Alimentação": "estrutura_familiar",
    "Supermercado": "estrutura_familiar",
    "Supermercado / Feira": "estrutura_familiar",
    "Padaria": "estrutura_familiar",
    "SAÚDE": "estrutura_familiar",
    "Saúde": "estrutura_familiar",
    "Medicamentos": "estrutura_familiar",
    "Educação": "estrutura_familiar",
    "Transporte": "estrutura_familiar",
    "Combustível": "estrutura_familiar",
    "Combustível (Trabalho)": "estrutura_familiar",
    "Manutenção Veículo": "estrutura_familiar",
    "Impostos Veículo": "estrutura_familiar",
    "Pagamento de fatura": "estrutura_familiar",

    # Qualidade de Vida
    "Pessoal": "qualidade_vida",
    "PESSOAL - Carlos": "qualidade_vida",
    "Barbearia": "qualidade_vida",
    "Academia / Wellhub": "qualidade_vida",
    "Streaming": "qualidade_vida",
    "Lazer": "qualidade_vida",
    "Restaurante": "qualidade_vida",
    "Eletrodomésticos": "qualidade_vida",
    "Táxi / Uber": "qualidade_vida",

    # Objetivos & Investimentos / Dívidas
    "Acordo BV": "objetivos_investimentos",
    "Outras Dívidas": "objetivos_investimentos",
    "Empréstimos": "objetivos_investimentos",
    "Dívidas": "objetivos_investimentos",
    "Investimentos": "objetivos_investimentos",
    "Outros": "qualidade_vida"
}


def inicializar_tabelas_renda_e_anual(conn: sqlite3.Connection) -> None:
    """Cria as tabelas necessárias de renda variável, cenários e despesas eventuais."""
    cur = conn.cursor()

    # 1. Classificação de natureza das despesas (atributo separado)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS planejamento_natureza_despesas (
        categoria TEXT PRIMARY KEY,
        natureza TEXT NOT NULL,
        origem TEXT DEFAULT 'padrao',
        atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Cenários de renda por período (com valores base do histórico e ajustes manuais)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS planejamento_cenarios_renda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ano INTEGER NOT NULL,
        mes INTEGER NOT NULL,
        renda_estavel_base REAL DEFAULT 0.0,
        renda_estavel_manual REAL,
        cenario_conservador_base REAL DEFAULT 0.0,
        cenario_conservador_manual REAL,
        cenario_habitual_base REAL DEFAULT 0.0,
        cenario_habitual_manual REAL,
        cenario_favoravel_base REAL DEFAULT 0.0,
        cenario_favoravel_manual REAL,
        meses_analise INTEGER DEFAULT 12,
        observacoes TEXT,
        atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ano, mes)
    );
    """)

    # 3. Meses selecionados pelo usuário para compor a amostra dos cenários
    cur.execute("""
    CREATE TABLE IF NOT EXISTS planejamento_meses_amostra (
        mes_key TEXT PRIMARY KEY,
        incluir INTEGER DEFAULT 1,
        confirmado_usuario INTEGER DEFAULT 0,
        qualidade_usuario TEXT,
        notas TEXT,
        atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Calendário anual e despesas sazonais/eventuais
    cur.execute("""
    CREATE TABLE IF NOT EXISTS planejamento_despesas_eventuais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        categoria TEXT NOT NULL,
        responsavel TEXT DEFAULT 'Família',
        data_prevista DATE NOT NULL,
        mes_previsto TEXT NOT NULL,
        valor_estimado REAL NOT NULL,
        valor_confirmado REAL,
        recorrencia TEXT DEFAULT 'anual',
        status TEXT DEFAULT 'planejada',
        transacao_id INTEGER REFERENCES transacoes(id),
        cofrinho_id INTEGER REFERENCES cofrinhos(id),
        valor_reservado_manual REAL DEFAULT 0.0,
        frequencia_contribuicao TEXT DEFAULT 'mensal',
        primeira_contribuicao DATE,
        observacoes TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Popula categorias padrão na tabela de natureza se estiver vazia
    for cat, nat in MAPEAMENTO_PADRAO_NATUREZA.items():
        cur.execute("""
            INSERT OR IGNORE INTO planejamento_natureza_despesas (categoria, natureza, origem)
            VALUES (?, ?, 'padrao')
        """, (cat, nat))

    # Migração idempotente de colunas novas em planejamento_meses_amostra
    cur.execute("PRAGMA table_info(planejamento_meses_amostra)")
    colunas_pma = [c[1] for c in cur.fetchall()]
    if "confirmado_usuario" not in colunas_pma:
        cur.execute("ALTER TABLE planejamento_meses_amostra ADD COLUMN confirmado_usuario INTEGER DEFAULT 0")
    if "qualidade_usuario" not in colunas_pma:
        cur.execute("ALTER TABLE planejamento_meses_amostra ADD COLUMN qualidade_usuario TEXT")
    if "notas" not in colunas_pma:
        cur.execute("ALTER TABLE planejamento_meses_amostra ADD COLUMN notas TEXT")

    # Migração idempotente de colunas novas em planejamento_despesas_eventuais
    cur.execute("PRAGMA table_info(planejamento_despesas_eventuais)")
    colunas_dev = [c[1] for c in cur.fetchall()]
    if "valor_reservado_manual" not in colunas_dev:
        cur.execute("ALTER TABLE planejamento_despesas_eventuais ADD COLUMN valor_reservado_manual REAL DEFAULT 0.0")
    if "primeira_contribuicao" not in colunas_dev:
        cur.execute("ALTER TABLE planejamento_despesas_eventuais ADD COLUMN primeira_contribuicao DATE")

    conn.commit()


# =============================================================================
# 1. CLASSIFICAÇÃO DE DESPESAS (NATUREZA ORÇAMENTÁRIA)
# =============================================================================

def obter_classificacao_natureza(conn: sqlite3.Connection) -> Dict[str, str]:
    """Retorna dicionário {categoria: natureza}."""
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()
    cur.execute("SELECT categoria, natureza FROM planejamento_natureza_despesas")
    resultado = {r[0]: r[1] for r in cur.fetchall()}
    for cat, nat in MAPEAMENTO_PADRAO_NATUREZA.items():
        if cat not in resultado:
            resultado[cat] = nat
    return resultado


def salvar_classificacao_natureza(conn: sqlite3.Connection, categoria: str, natureza: str) -> bool:
    """Atualiza a classificação de uma categoria por atributo separado."""
    inicializar_tabelas_renda_e_anual(conn)
    if natureza not in ("estrutura_familiar", "qualidade_vida", "objetivos_investimentos"):
        raise ValueError("Natureza orçamentária inválida.")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO planejamento_natureza_despesas (categoria, natureza, origem, atualizado_em)
        VALUES (?, ?, 'usuario', CURRENT_TIMESTAMP)
        ON CONFLICT(categoria) DO UPDATE SET 
            natureza = excluded.natureza,
            origem = 'usuario',
            atualizado_em = CURRENT_TIMESTAMP
    """, (categoria.strip(), natureza))
    conn.commit()
    return True


# =============================================================================
# 2. ANÁLISE DE HISTÓRICO DE RENDA & CONTROLE DE MESES PELO USUÁRIO
# =============================================================================

def salvar_selecao_meses_amostra(
    conn: sqlite3.Connection,
    meses_ativos: List[str],
    meses_confirmados: Optional[List[str]] = None,
    qualidade_map: Optional[Dict[str, str]] = None
) -> bool:
    """
    Salva a seleção do usuário para a amostra dos cenários e sua confirmação explícita de cobertura.
    """
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()
    # Preserva metadados anteriores ou atualiza
    meses_conf_set = set(meses_confirmados or [])
    qual_map = qualidade_map or {}

    cur.execute("DELETE FROM planejamento_meses_amostra")
    for m in meses_ativos:
        m_key = m.strip()
        conf = 1 if m_key in meses_conf_set else 0
        q_user = qual_map.get(m_key)
        cur.execute("""
            INSERT INTO planejamento_meses_amostra (mes_key, incluir, confirmado_usuario, qualidade_usuario)
            VALUES (?, 1, ?, ?)
        """, (m_key, conf, q_user))
    conn.commit()
    return True


def obter_configuracoes_meses_amostra(conn: sqlite3.Connection) -> Optional[Dict[str, Dict[str, Any]]]:
    """Retorna dicionário {mes_key: {'incluir': bool, 'confirmado_usuario': bool, 'qualidade_usuario': str}}."""
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()
    cur.execute("SELECT mes_key, incluir, confirmado_usuario, qualidade_usuario FROM planejamento_meses_amostra")
    rows = cur.fetchall()
    if not rows:
        return None
    return {
        r[0]: {
            "incluir": bool(r[1]),
            "confirmado_usuario": bool(r[2]),
            "qualidade_usuario": r[3]
        }
        for r in rows
    }


def obter_meses_amostra_salvos(conn: sqlite3.Connection) -> Optional[set]:
    """Retorna o conjunto de meses que o usuário marcou para incluir, ou None se nunca configurado."""
    config = obter_configuracoes_meses_amostra(conn)
    if config is None:
        return None
    return {m for m, dados in config.items() if dados["incluir"]}


def analisar_historico_renda(
    conn: sqlite3.Connection,
    meses_analise: int = 12,
    ano_ref: Optional[int] = None,
    mes_ref: Optional[int] = None
) -> Dict[str, Any]:
    """
    Analisa o histórico de receitas mês a mês com decomposição transparente:
      - Renda estável: Salário Fernanda
      - Renda variável: 99 / Chaves (Carlos) e Receitas Extras
      - Entradas não-operacionais: Aportes/Empréstimos de terceiros
      - Rendimentos bancários
    Diferencia com rigor:
      - 'completo_confirmado': fluxo regular contínuo de trabalho
      - 'parcial': poucos lançamentos (ex: repasse isolado, mês em andamento ou atípico)
      - 'sem_dados': sem registros de receitas da atividade
    Permite ao usuário incluir/excluir meses da amostra estatística.
    """
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()

    hoje = datetime.date.today()
    if ano_ref is None or mes_ref is None:
        ano_ref = hoje.year
        mes_ref = hoje.month

    # Monta lista dos últimos N meses
    meses_alvo = []
    curr_y, curr_m = ano_ref, mes_ref
    for _ in range(meses_analise):
        meses_alvo.append(f"{curr_y:04d}-{curr_m:02d}")
        curr_m -= 1
        if curr_m < 1:
            curr_m = 12
            curr_y -= 1

    placeholders = ",".join("?" for _ in meses_alvo)
    query = f"""
        SELECT 
            strftime('%Y-%m', data) as mes,
            categoria,
            COUNT(*) as qtd,
            SUM(valor) as total,
            MIN(data) as d_min,
            MAX(data) as d_max
        FROM transacoes
        WHERE tipo = 'receita'
          AND strftime('%Y-%m', data) IN ({placeholders})
        GROUP BY mes, categoria
        ORDER BY mes ASC
    """
    cur.execute(query, meses_alvo)
    linhas = cur.fetchall()

    dados_por_mes: Dict[str, Dict[str, Any]] = {}
    for m in meses_alvo:
        dados_por_mes[m] = {
            "mes": m,
            "estavel": 0.0,
            "variavel": 0.0,
            "aportes_externos": 0.0,
            "rendimentos": 0.0,
            "qtd_tx_variavel": 0,
            "qtd_tx_total": 0,
            "primeira_data": None,
            "ultima_data": None,
            "qualidade": "sem_dados",
            "qualidade_label": "Sem Dados / Lacuna",
            "motivo_qualidade": "Nenhuma receita operacional registrada.",
            "incluir_na_amostra": False,
            "tem_dados": False
        }

    for mes_str, categoria, qtd, total, d_min, d_max in linhas:
        if mes_str not in dados_por_mes:
            continue
        info = dados_por_mes[mes_str]
        val = float(total or 0.0)
        info["qtd_tx_total"] += qtd
        info["tem_dados"] = True

        cat_norm = (categoria or "").strip()
        if cat_norm in ("Salário Fernanda", "Salário", "Salários"):
            info["estavel"] += val
        elif cat_norm in ("99 / Chaves (Carlos)", "Receitas Extras", "Ganhos Drive", "Freelas"):
            info["variavel"] += val
            info["qtd_tx_variavel"] += qtd
        elif cat_norm in ("Empréstimo / Aporte", "Empréstimos"):
            info["aportes_externos"] += val
        elif cat_norm in ("Rendimentos", "Rendimento"):
            info["rendimentos"] += val
        else:
            info["variavel"] += val
            info["qtd_tx_variavel"] += qtd

        if info["primeira_data"] is None or d_min < info["primeira_data"]:
            info["primeira_data"] = d_min
        if info["ultima_data"] is None or d_max > info["ultima_data"]:
            info["ultima_data"] = d_max

    # Carrega meses e configurações salvas pelo usuário
    config_usuario = obter_configuracoes_meses_amostra(conn)

    historico_ordenado = []
    for m in sorted(meses_alvo):
        info = dados_por_mes[m]
        eh_mes_corrente = (m == f"{hoje.year:04d}-{hoje.month:02d}")

        # 1. Sugestão automática do sistema baseada em evidências
        if not info["tem_dados"] or (info["estavel"] == 0 and info["variavel"] == 0):
            qualidade_sugerida = "sem_dados"
            label_sugerido = "Sem Dados / Lacuna"
            motivo_sugerido = "Nenhuma receita operacional registrada no período."
            default_incluir = False
        elif eh_mes_corrente:
            qualidade_sugerida = "em_andamento"
            label_sugerido = "Mês em Andamento"
            motivo_sugerido = f"Mês atual em curso (dia {hoje.day})."
            default_incluir = True
        elif info["qtd_tx_variavel"] >= 10:
            # Sugestão de provável mês completo pela frequência de turnos
            qualidade_sugerida = "provavel_completo"
            label_sugerido = "Sugestão: Provável Completo"
            motivo_sugerido = f"Frequência observada de {info['qtd_tx_variavel']} lançamentos de corridas/turnos ao longo do mês."
            default_incluir = True
        elif info["qtd_tx_variavel"] > 0:
            # Poucos lançamentos de aplicativo: pode ser mês incompleto ou mês com baixa renda/pouca escala
            qualidade_sugerida = "poucos_registros"
            label_sugerido = "Sugestão: Poucos Registros / Renda Baixa"
            motivo_sugerido = (
                f"{info['qtd_tx_variavel']} lançamento(s) da 99 no mês (R$ {info['variavel']:,.2f}). "
                "Pode indicar mês incompleto ou mês trabalhado com faturamento reduzido."
            )
            default_incluir = True
        else:
            qualidade_sugerida = "apenas_fixa"
            label_sugerido = "Sugestão: Apenas Renda Fixa"
            motivo_sugerido = "Sem registros de corridas da 99 no mês."
            default_incluir = False

        # 2. Status de Confirmação pelo Usuário
        cfg_m = config_usuario.get(m) if config_usuario else None
        if cfg_m:
            info["incluir_na_amostra"] = cfg_m["incluir"]
            info["confirmado_usuario"] = cfg_m["confirmado_usuario"]
            info["qualidade_usuario"] = cfg_m["qualidade_usuario"]
        else:
            info["incluir_na_amostra"] = default_incluir
            info["confirmado_usuario"] = False
            info["qualidade_usuario"] = None

        # Exibição: se confirmado pelo usuário, exibe confirmação explícita
        if info["confirmado_usuario"]:
            info["qualidade"] = info["qualidade_usuario"] or qualidade_sugerida
            info["qualidade_label"] = "✓ Confirmado pelo Usuário"
            info["motivo_qualidade"] = f"Cobertura do período confirmada pelo usuário ({motivo_sugerido})."
            info["eh_sugestao"] = False
        else:
            info["qualidade"] = qualidade_sugerida
            info["qualidade_label"] = label_sugerido
            info["motivo_qualidade"] = motivo_sugerido
            info["eh_sugestao"] = True

        historico_ordenado.append(info)

    # Coleta valores dos meses efetivamente incluídos na amostra estatística
    valores_estaveis_amostra = []
    valores_variaveis_amostra = []

    for h in historico_ordenado:
        if h["incluir_na_amostra"]:
            if h["estavel"] > 0:
                valores_estaveis_amostra.append(h["estavel"])
            if h["variavel"] > 0:
                valores_variaveis_amostra.append(h["variavel"])

    # Estatísticas da Renda Variável com base na amostra selecionada
    qtd_meses_amostra = len(valores_variaveis_amostra)
    if qtd_meses_amostra > 0:
        min_var = min(valores_variaveis_amostra)
        max_var = max(valores_variaveis_amostra)
        media_var = sum(valores_variaveis_amostra) / qtd_meses_amostra
    else:
        # Fallback seguro
        val_curr = dados_por_mes.get(f"{ano_ref:04d}-{mes_ref:02d}", {}).get("variavel", 0.0)
        min_var = val_curr
        max_var = val_curr
        media_var = val_curr

    # Estatísticas da Renda Estável (Salário)
    qtd_meses_estavel = len(valores_estaveis_amostra)
    if qtd_meses_estavel > 0:
        media_estavel = sum(valores_estaveis_amostra) / qtd_meses_estavel
    else:
        media_estavel = dados_por_mes.get(f"{ano_ref:04d}-{mes_ref:02d}", {}).get("estavel", 3500.0)

    # Cenários sugeridos
    cenario_conservador_sugerido = round(min_var, 2)
    cenario_habitual_sugerido = round(media_var, 2)
    cenario_favoravel_sugerido = round(max_var, 2)

    # Consulta se há ajustes manuais gravados pelo usuário para este mês
    cur.execute("""
        SELECT 
            renda_estavel_base, renda_estavel_manual,
            cenario_conservador_base, cenario_conservador_manual,
            cenario_habitual_base, cenario_habitual_manual,
            cenario_favoravel_base, cenario_favoravel_manual,
            observacoes
        FROM planejamento_cenarios_renda
        WHERE ano = ? AND mes = ?
    """, (ano_ref, mes_ref))
    row_cenario = cur.fetchone()

    if row_cenario:
        estavel_manual = row_cenario[1]
        cons_manual = row_cenario[3]
        hab_manual = row_cenario[5]
        fav_manual = row_cenario[7]
        obs = row_cenario[8]
    else:
        estavel_manual = None
        cons_manual = None
        hab_manual = None
        fav_manual = None
        obs = None

    estavel_final = float(estavel_manual) if estavel_manual is not None else round(media_estavel, 2)
    cons_final = float(cons_manual) if cons_manual is not None else cenario_conservador_sugerido
    hab_final = float(hab_manual) if hab_manual is not None else cenario_habitual_sugerido
    fav_final = float(fav_manual) if fav_manual is not None else cenario_favoravel_sugerido

    return {
        "mes_referencia": f"{ano_ref:04d}-{mes_ref:02d}",
        "meses_analise": meses_analise,
        "historico": historico_ordenado,
        "estatisticas_variavel": {
            "qtd_meses_validos": qtd_meses_amostra,
            "minimo_observado": round(min_var, 2),
            "media_observada": round(media_var, 2),
            "maximo_observado": round(max_var, 2)
        },
        "estatisticas_estavel": {
            "qtd_meses_validos": qtd_meses_estavel,
            "media_observada": round(media_estavel, 2)
        },
        "cenarios": {
            "estavel": {
                "base": round(media_estavel, 2),
                "manual": estavel_manual,
                "valor_final": estavel_final,
                "is_manual": estavel_manual is not None,
                "descricao": "Renda fixa contratual familiar (salário líquido comprovado)"
            },
            "conservador": {
                "base": cenario_conservador_sugerido,
                "manual": cons_manual,
                "valor_final": cons_final,
                "is_manual": cons_manual is not None,
                "descricao": "Mínimo observado na amostra de meses selecionada (dias com menor demanda ou menor disponibilidade)"
            },
            "habitual": {
                "base": cenario_habitual_sugerido,
                "manual": hab_manual,
                "valor_final": hab_final,
                "is_manual": hab_manual is not None,
                "descricao": "Média de corridas e faturamento nos meses normais de operação"
            },
            "favorável": {
                "base": cenario_favoravel_sugerido,
                "manual": fav_manual,
                "valor_final": fav_final,
                "is_manual": fav_manual is not None,
                "descricao": "Pico observado em meses de alta demanda e maior escala de trabalho"
            }
        },
        "observacoes": obs,
        "aviso_metodologico": "O mínimo histórico não é uma renda garantida. Em atividades de aplicativo, a renda depende de horas trabalhadas, demanda de passageiros e disponibilidade operacional."
    }


def salvar_cenarios_renda(
    conn: sqlite3.Connection,
    ano: int,
    mes: int,
    estavel_manual: Optional[float],
    conservador_manual: Optional[float],
    habitual_manual: Optional[float],
    favoravel_manual: Optional[float],
    observacoes: Optional[str] = None
) -> bool:
    """Grava os ajustes manuais dos cenários de renda do usuário para o mês."""
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()

    info_hist = analisar_historico_renda(conn, 12, ano, mes)
    base_estavel = info_hist["estatisticas_estavel"]["media_observada"]
    base_cons = info_hist["estatisticas_variavel"]["minimo_observado"]
    base_hab = info_hist["estatisticas_variavel"]["media_observada"]
    base_fav = info_hist["estatisticas_variavel"]["maximo_observado"]

    cur.execute("""
        INSERT INTO planejamento_cenarios_renda (
            ano, mes,
            renda_estavel_base, renda_estavel_manual,
            cenario_conservador_base, cenario_conservador_manual,
            cenario_habitual_base, cenario_habitual_manual,
            cenario_favoravel_base, cenario_favoravel_manual,
            observacoes, atualizado_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(ano, mes) DO UPDATE SET
            renda_estavel_manual = excluded.renda_estavel_manual,
            cenario_conservador_manual = excluded.cenario_conservador_manual,
            cenario_habitual_manual = excluded.cenario_habitual_manual,
            cenario_favoravel_manual = excluded.cenario_favoravel_manual,
            observacoes = excluded.observacoes,
            atualizado_em = CURRENT_TIMESTAMP
    """, (
        ano, mes,
        base_estavel, estavel_manual,
        base_cons, conservador_manual,
        base_hab, habitual_manual,
        base_fav, favoravel_manual,
        observacoes
    ))
    conn.commit()
    return True


# =============================================================================
# 3. RESULTADO DO DRIVE & DECOMPOSIÇÃO DE CUSTOS DE COMBUSTÍVEL
# =============================================================================

def obter_margem_operacional_drive(conn: sqlite3.Connection, ano: int, mes: int) -> Dict[str, Any]:
    """
    Retorna a análise operacional do Drive para o mês:
    - Faturamento bruto registrado
    - Custos de combustível pagos no posto (saída de caixa real)
    - Consumo de combustível estimado nos turnos (referência teórica por km)
    - Resultado após os custos registrados (descrição precisa, sem dedução dupla)
    - Custos ainda não registrados/disponíveis (pneus, manutenção futura, depreciação)
    """
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()

    inicio_mes = f"{ano:04d}-{mes:02d}-01"
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    fim_mes = f"{ano:04d}-{mes:02d}-{ultimo_dia:02d}"

    # 1. Turnos registrados no mês
    cur.execute("""
        SELECT 
            COUNT(*),
            COALESCE(SUM(horas), 0),
            COALESCE(SUM(km), 0),
            COALESCE(SUM(ganho_bruto), 0),
            COALESCE(SUM(combustivel), 0)
        FROM turnos
        WHERE data BETWEEN ? AND ?
    """, (inicio_mes, fim_mes))
    row_t = cur.fetchone()
    qtd_turnos = row_t[0] or 0
    horas_totais = float(row_t[1] or 0.0)
    km_totais = float(row_t[2] or 0.0)
    ganho_bruto_turnos = float(row_t[3] or 0.0)
    combustivel_estimado_turnos = float(row_t[4] or 0.0)

    # 2. Transações financeiras de receitas da 99 no mês
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0), COUNT(*)
        FROM transacoes
        WHERE tipo = 'receita'
          AND categoria = '99 / Chaves (Carlos)'
          AND data BETWEEN ? AND ?
    """, (inicio_mes, fim_mes))
    row_rx = cur.fetchone()
    receita_financeira_99 = float(row_rx[0] or 0.0)

    # Faturamento bruto operacional (usa o ganho dos turnos se houver, ou a receita das transações)
    faturamento_bruto = max(ganho_bruto_turnos, receita_financeira_99)

    # 3. Combustível pago no posto (saída de caixa real)
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0), COUNT(*)
        FROM transacoes
        WHERE tipo = 'despesa'
          AND categoria IN ('Combustível', 'Combustível (Trabalho)')
          AND data BETWEEN ? AND ?
    """, (inicio_mes, fim_mes))
    row_comb = cur.fetchone()
    combustivel_pago_posto = float(row_comb[0] or 0.0)
    qtd_abastecimentos_posto = row_comb[1] or 0

    # 4. Outros custos diretos registrados (ex: seguro ou manutenção lançada)
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0)
        FROM transacoes
        WHERE tipo = 'despesa'
          AND categoria = 'Manutenção Veículo'
          AND data BETWEEN ? AND ?
    """, (inicio_mes, fim_mes))
    manutencao_registrada = float(cur.fetchone()[0] or 0.0)

    # Custo de combustível utilizado no resultado financeiro:
    # Usa os abastecimentos reais pagos no posto (saída de caixa comprovada).
    # Se não houver abastecimentos pagos registrados no mês, utiliza o consumo estimado dos turnos como fallback.
    # NUNCA desconta ambos simultaneamente!
    if combustivel_pago_posto > 0:
        custo_combustivel_efetivo = combustivel_pago_posto
        origem_combustivel = "abastecimentos_pagos"
    else:
        custo_combustivel_efetivo = combustivel_estimado_turnos
        origem_combustivel = "estimado_turnos"

    custos_registrados_total = round(custo_combustivel_efetivo + manutencao_registrada, 2)
    # Resultado após os custos registrados (terminologia precisa conforme orientação do usuário)
    resultado_apos_custos_registrados = round(faturamento_bruto - custos_registrados_total, 2)

    # Referência média pessoal informada pelo motorista (R$ 35,00/h - não é tarifa oficial da plataforma)
    referencia_ganho_hora = 35.0
    faturamento_esperado_horas = round(horas_totais * referencia_ganho_hora, 2)
    ganho_hora_real = round(faturamento_bruto / horas_totais, 2) if horas_totais > 0 else 0.0

    return {
        "qtd_turnos": qtd_turnos,
        "horas_totais": round(horas_totais, 1),
        "km_totais": round(km_totais, 1),
        "referencia_hora": referencia_ganho_hora,
        "referencia_hora_rotulo": "Referência média pessoal informada pelo motorista (R$ 35,00/h)",
        "faturamento_bruto": round(faturamento_bruto, 2),
        "faturamento_esperado_horas": faturamento_esperado_horas,
        "ganho_hora_real": ganho_hora_real,
        "custos_registrados_total": custos_registrados_total,
        "resultado_apos_custos_registrados": resultado_apos_custos_registrados,
        "detalhe_combustivel": {
            "pago_posto": round(combustivel_pago_posto, 2),
            "qtd_abastecimentos": qtd_abastecimentos_posto,
            "estimado_turnos": round(combustivel_estimado_turnos, 2),
            "origem_utilizada": origem_combustivel,
            "diferenca_combustivel": round(combustivel_pago_posto - combustivel_estimado_turnos, 2),
            "explicacao": (
                "O valor descontado no resultado corresponde aos abastecimentos efetivamente pagos no posto "
                f"(R$ {combustivel_pago_posto:,.2f}). O consumo estimado nos turnos (R$ {combustivel_estimado_turnos:,.2f}) "
                "é uma referência teórica baseada nos km rodados e não é descontado novamente, evitando dupla dedução."
            )
        },
        "manutencao_registrada": round(manutencao_registrada, 2),
        "custos_nao_disponiveis": [
            "Provisão de desgaste de pneus (~R$ 0,08/km)",
            "Manutenção preventiva periódica futura (óleo, suspensão, freios)",
            "Depreciação real do veículo HB20"
        ],
        "aviso_anti_duplicidade": "Os ganhos dos turnos já são lançados como receitas em contas ('99Pay' e 'Dinheiro/Carteira'). Transferências entre contas (99Pay -> Mercado Pago) não representam novas receitas e são desconsideradas."
    }


# =============================================================================
# 4. COMPARATIVO DE CENÁRIOS VS DESPESAS POR NATUREZA
# =============================================================================

def comparar_cenarios_com_despesas(
    conn: sqlite3.Connection,
    ano: int,
    mes: int,
    cenarios: Dict[str, Any]
) -> Dict[str, Any]:
    """Compara os cenários (conservador, habitual, favorável) com as despesas por natureza."""
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()

    inicio_mes = f"{ano:04d}-{mes:02d}-01"
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    fim_mes = f"{ano:04d}-{mes:02d}-{ultimo_dia:02d}"

    classificacao = obter_classificacao_natureza(conn)

    cur.execute("""
        SELECT categoria, COALESCE(SUM(valor), 0)
        FROM transacoes
        WHERE tipo = 'despesa'
          AND data BETWEEN ? AND ?
        GROUP BY categoria
    """, (inicio_mes, fim_mes))
    linhas_desp = cur.fetchall()

    tot_estrutura = 0.0
    tot_qualidade = 0.0
    tot_objetivos = 0.0
    detalhes_natureza = {
        "estrutura_familiar": [],
        "qualidade_vida": [],
        "objetivos_investimentos": []
    }

    for cat, val in linhas_desp:
        v = float(val or 0.0)
        nat = classificacao.get(cat, "estrutura_familiar")
        if nat == "estrutura_familiar":
            tot_estrutura += v
        elif nat == "qualidade_vida":
            tot_qualidade += v
        elif nat == "objetivos_investimentos":
            tot_objetivos += v
        else:
            tot_estrutura += v
            nat = "estrutura_familiar"

        detalhes_natureza[nat].append({"categoria": cat, "valor": round(v, 2)})

    despesas_totais = round(tot_estrutura + tot_qualidade + tot_objetivos, 2)

    renda_estavel = cenarios["estavel"]["valor_final"]
    resultados_cenarios = {}

    for nome_cen in ("conservador", "habitual", "favorável"):
        renda_var = cenarios[nome_cen]["valor_final"]
        renda_total = round(renda_estavel + renda_var, 2)
        sobra_ou_falta = round(renda_total - despesas_totais, 2)
        cobertura_estrutura = round((renda_total / tot_estrutura * 100), 1) if tot_estrutura > 0 else 100.0

        resultados_cenarios[nome_cen] = {
            "renda_estavel": renda_estavel,
            "renda_variavel": renda_var,
            "renda_total": renda_total,
            "despesas_totais": despesas_totais,
            "sobra_ou_falta": sobra_ou_falta,
            "status": "superavit" if sobra_ou_falta >= 0 else "deficit",
            "cobertura_estrutura_pct": cobertura_estrutura,
            "cobre_estrutura": renda_total >= tot_estrutura,
            "cobre_tudo": sobra_ou_falta >= 0
        }

    return {
        "despesas_totais": despesas_totais,
        "por_natureza": {
            "estrutura_familiar": {
                "nome": "Estrutura da Família",
                "icone": "🏠",
                "total": round(tot_estrutura, 2),
                "pct_total": round((tot_estrutura / despesas_totais * 100), 1) if despesas_totais > 0 else 0,
                "itens": sorted(detalhes_natureza["estrutura_familiar"], key=lambda x: x["valor"], reverse=True)
            },
            "qualidade_vida": {
                "nome": "Qualidade de Vida",
                "icone": "🌱",
                "total": round(tot_qualidade, 2),
                "pct_total": round((tot_qualidade / despesas_totais * 100), 1) if despesas_totais > 0 else 0,
                "itens": sorted(detalhes_natureza["qualidade_vida"], key=lambda x: x["valor"], reverse=True)
            },
            "objetivos_investimentos": {
                "nome": "Objetivos & Investimentos",
                "icone": "🎯",
                "total": round(tot_objetivos, 2),
                "pct_total": round((tot_objetivos / despesas_totais * 100), 1) if despesas_totais > 0 else 0,
                "itens": sorted(detalhes_natureza["objetivos_investimentos"], key=lambda x: x["valor"], reverse=True)
            }
        },
        "cenarios": resultados_cenarios
    }


# =============================================================================
# 5. CALENDÁRIO ANUAL & CÁLCULO REAL DE CONTRIBUIÇÕES E COFRINHOS
# =============================================================================

def calcular_datas_contribuicao_efetivas(
    data_inicio: datetime.date,
    data_vencimento: datetime.date,
    frequencia: str = "mensal"
) -> List[datetime.date]:
    """
    Gera as datas efetivas de contribuição entre data_inicio e data_vencimento (inclusive).
    Regras estritas:
    - Se data_vencimento < data_inicio: 0 oportunidades (vencido/sem datas futuras).
    - Se data_vencimento == data_inicio: exatamente 1 oportunidade (hoje / aporte imediato).
    - Para 'mensal': respeita os meses do calendário e ajusta dias inexistentes (ex: dia 31 vira 28/29 em fev, 30 em abr).
    - Para 'semanal': incrementos exatos de 7 dias a partir de data_inicio.
    - Para 'quinzenal': incrementos exatos de 14 dias a partir de data_inicio.
    - Para 'unica' ou 'pontual': 1 oportunidade em data_inicio.
    """
    if data_vencimento < data_inicio:
        return []

    datas: List[datetime.date] = []
    freq = (frequencia or "mensal").lower().strip()

    if freq == "semanal":
        curr = data_inicio
        while curr <= data_vencimento:
            datas.append(curr)
            curr += datetime.timedelta(days=7)

    elif freq == "quinzenal":
        curr = data_inicio
        while curr <= data_vencimento:
            datas.append(curr)
            curr += datetime.timedelta(days=14)

    elif freq in ("unica", "pontual"):
        datas.append(data_inicio)

    else:
        # Frequência mensal (padrão): avança pelos meses do calendário respeitando dia alvo
        dia_alvo = data_inicio.day
        ano = data_inicio.year
        mes = data_inicio.month
        while True:
            max_dias = calendar.monthrange(ano, mes)[1]
            dia_efetivo = min(dia_alvo, max_dias)
            dt = datetime.date(ano, mes, dia_efetivo)
            if dt > data_vencimento:
                break
            if dt >= data_inicio:
                datas.append(dt)
            # Avança para o mês seguinte
            mes += 1
            if mes > 12:
                mes = 1
                ano += 1

    return datas


def obter_saldo_disponivel_cofrinho(conn: sqlite3.Connection, cofrinho_id: int) -> float:
    """
    Retorna o saldo real do cofrinho (via saldo_service ou saldo_confirmado da tabela).
    """
    cur = conn.cursor()
    cur.execute("SELECT conta_config_id, saldo_confirmado FROM cofrinhos WHERE id = ?", (cofrinho_id,))
    row = cur.fetchone()
    if not row:
        return 0.0

    conta_id, s_conf = row
    if conta_id:
        try:
            import saldo_service
            res_s = saldo_service.calcular_saldo_conta(conn, conta_id)
            return float(res_s["saldo_atual"])
        except Exception:
            pass
    return float(s_conf or 0.0)


def obter_calendario_anual(conn: sqlite3.Connection, ano_inicio: Optional[int] = None, mes_inicio: Optional[int] = None) -> Dict[str, Any]:
    """
    Gera a visão dos próximos 12 meses com cálculo real de contribuições e
    diferenciação explícita entre saldo do cofrinho, distribuição teórica e valor efetivamente destinado.
    """
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()

    hoje = datetime.date.today()
    if ano_inicio is None or mes_inicio is None:
        ano_inicio = hoje.year
        mes_inicio = hoje.month

    meses_12 = []
    y, m = ano_inicio, mes_inicio
    for _ in range(12):
        mes_key = f"{y:04d}-{m:02d}"
        MESES_PT = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        meses_12.append({
            "mes_key": mes_key,
            "ano": y,
            "mes": m,
            "label": f"{MESES_PT[m]} {y}",
            "total_previsto": 0.0,
            "total_reservado": 0.0,
            "despesas": []
        })
        m += 1
        if m > 12:
            m = 1
            y += 1

    mapa_meses = {item["mes_key"]: item for item in meses_12}

    # Carrega cofrinhos disponíveis
    cur.execute("SELECT id, nome, saldo_confirmado, meta_valor, objetivo, conta_config_id FROM cofrinhos")
    rows_cof = cur.fetchall()
    cofrinhos_dict = {}
    for r in rows_cof:
        cof_id_val = r[0]
        s_disp = obter_saldo_disponivel_cofrinho(conn, cof_id_val)
        cofrinhos_dict[cof_id_val] = {
            "id": cof_id_val,
            "nome": r[1],
            "saldo_confirmado": s_disp,
            "meta_valor": float(r[3] or 0.0),
            "objetivo": r[4],
            "conta_config_id": r[5],
            "compromissos_vinculados": []
        }

    # Carrega despesas cadastradas
    cur.execute("""
        SELECT 
            id, nome, categoria, responsavel, data_prevista, mes_previsto,
            valor_estimado, valor_confirmado, recorrencia, status,
            transacao_id, cofrinho_id, valor_reservado_manual, frequencia_contribuicao,
            primeira_contribuicao, observacoes
        FROM planejamento_despesas_eventuais
        WHERE status != 'cancelada'
        ORDER BY data_prevista ASC
    """)
    despesas_raw = cur.fetchall()

    cofrinho_para_despesas: Dict[int, List[Dict[str, Any]]] = {}
    lista_despesas = []

    for r in despesas_raw:
        d_id = r[0]
        nome = r[1]
        cat = r[2]
        resp = r[3]
        dt_prev = r[4]
        mes_prev = r[5]
        v_est = float(r[6] or 0.0)
        v_conf = float(r[7]) if r[7] is not None else None
        recorr = r[8]
        status = r[9]
        tx_id = r[10]
        cof_id = r[11]
        v_res_manual = float(r[12] or 0.0)
        freq = r[13] or "mensal"
        dt_prim_contrib = r[14]
        obs = r[15]

        valor_alvo = v_conf if v_conf is not None else v_est

        item = {
            "id": d_id,
            "nome": nome,
            "categoria": cat,
            "responsavel": resp,
            "data_prevista": dt_prev,
            "mes_previsto": mes_prev,
            "valor_estimado": v_est,
            "valor_confirmado": v_conf,
            "valor_alvo": valor_alvo,
            "recorrencia": recorr,
            "status": status,
            "transacao_id": tx_id,
            "cofrinho_id": cof_id,
            "cofrinho_nome": cofrinhos_dict.get(cof_id, {}).get("nome") if cof_id else None,
            "saldo_total_cofrinho": cofrinhos_dict.get(cof_id, {}).get("saldo_confirmado", 0.0) if cof_id else 0.0,
            "valor_reservado_manual": v_res_manual,
            "distribuicao_sugerida_teorica": 0.0,
            "valor_efetivamente_reservado": 0.0,
            "falta_reservar": valor_alvo,
            "primeira_contribuicao": dt_prim_contrib,
            "proxima_contribuicao": None,
            "qtd_oportunidades": 0,
            "valor_por_contribuicao": 0.0,
            "datas_contribuicao": [],
            "sugestao_mensal": 0.0,
            "sugestao_semanal": 0.0,
            "dias_restantes": 0,
            "semanas_reais": 0,
            "meses_reais": 0,
            "status_prazo": "no_prazo",
            "status_prazo_label": "No Prazo",
            "frequencia_contribuicao": freq,
            "observacoes": obs,
            "obrigacao_constituida": tx_id is not None
        }

        if cof_id and cof_id in cofrinhos_dict:
            if cof_id not in cofrinho_para_despesas:
                cofrinho_para_despesas[cof_id] = []
            cofrinho_para_despesas[cof_id].append(item)

        lista_despesas.append(item)

    # 1. Distribuição teórica vs Alocação manual de Cofrinhos
    # Garante estritamente que a soma atribuída nunca ultrapasse o saldo real disponível do cofrinho
    for cof_id, itens_vinculados in cofrinho_para_despesas.items():
        saldo_cof = cofrinhos_dict[cof_id]["saldo_confirmado"]
        soma_alvos = sum(it["valor_alvo"] for it in itens_vinculados)

        # Rateio teórico proporcional (meramente informativo)
        for it in itens_vinculados:
            if soma_alvos > 0:
                prop = it["valor_alvo"] / soma_alvos
                it["distribuicao_sugerida_teorica"] = min(it["valor_alvo"], round(saldo_cof * prop, 2))
            else:
                it["distribuicao_sugerida_teorica"] = 0.0

        # Alocação efetiva:
        # Se os itens possuem reservas manuais, aloca respeitando a soma limitada ao saldo do cofrinho
        saldo_remanescente_cof = saldo_cof
        itens_com_manual = [it for it in itens_vinculados if it["valor_reservado_manual"] > 0]

        if itens_com_manual:
            for it in itens_com_manual:
                aloc_pretendida = min(it["valor_alvo"], it["valor_reservado_manual"])
                aloc_real = min(saldo_remanescente_cof, aloc_pretendida)
                it["valor_efetivamente_reservado"] = round(aloc_real, 2)
                saldo_remanescente_cof = max(0.0, round(saldo_remanescente_cof - aloc_real, 2))
            # Itens sem alocação manual dividem o saldo remanescente pela distribuição proporcional
            itens_sem_manual = [it for it in itens_vinculados if it["valor_reservado_manual"] <= 0]
            soma_alvos_sem = sum(it["valor_alvo"] for it in itens_sem_manual)
            for it in itens_sem_manual:
                if soma_alvos_sem > 0 and saldo_remanescente_cof > 0:
                    prop = it["valor_alvo"] / soma_alvos_sem
                    aloc = min(it["valor_alvo"], round(saldo_remanescente_cof * prop, 2))
                    it["valor_efetivamente_reservado"] = aloc
                else:
                    it["valor_efetivamente_reservado"] = 0.0
        else:
            # Sem alocação manual: todos usam a distribuição teórica sugerida
            for it in itens_vinculados:
                it["valor_efetivamente_reservado"] = it["distribuicao_sugerida_teorica"]

        for it in itens_vinculados:
            it["falta_reservar"] = max(0.0, round(it["valor_alvo"] - it["valor_efetivamente_reservado"], 2))

    # 2. Cálculo Real de Prazos, Datas Efetivas e Oportunidades de Contribuição
    for it in lista_despesas:
        if not it["cofrinho_id"]:
            # Sem cofrinho: reserva manual fica limitada ao valor alvo
            it["valor_efetivamente_reservado"] = min(it["valor_alvo"], it["valor_reservado_manual"])
            it["falta_reservar"] = max(0.0, round(it["valor_alvo"] - it["valor_efetivamente_reservado"], 2))

        try:
            dt_p = datetime.datetime.strptime(it["data_prevista"], "%Y-%m-%d").date()
            dias_rest = (dt_p - hoje).days
        except Exception:
            dt_p = hoje
            dias_rest = 0

        it["dias_restantes"] = dias_rest

        # Determina a data da primeira contribuição (se informada, usa; senão inicia hoje)
        if it.get("primeira_contribuicao"):
            try:
                dt_inicio_contrib = datetime.datetime.strptime(it["primeira_contribuicao"], "%Y-%m-%d").date()
            except Exception:
                dt_inicio_contrib = hoje
        else:
            dt_inicio_contrib = hoje

        # Gera as datas efetivas reais de contribuição
        datas_efetivas = calcular_datas_contribuicao_efetivas(dt_inicio_contrib, dt_p, it["frequencia_contribuicao"])
        it["datas_contribuicao"] = [d.strftime("%Y-%m-%d") for d in datas_efetivas]
        qtd_op = len(datas_efetivas)
        it["qtd_oportunidades"] = qtd_op

        # Identifica a próxima contribuição
        proximas = [d for d in datas_efetivas if d >= hoje]
        it["proxima_contribuicao"] = proximas[0].strftime("%Y-%m-%d") if proximas else (dt_p.strftime("%Y-%m-%d") if dt_p >= hoje else None)

        # Valor exato por contribuição
        if it["falta_reservar"] > 0 and qtd_op > 0:
            it["valor_por_contribuicao"] = round(it["falta_reservar"] / qtd_op, 2)
        elif it["falta_reservar"] > 0 and qtd_op == 0:
            it["valor_por_contribuicao"] = it["falta_reservar"]
        else:
            it["valor_por_contribuicao"] = 0.0

        # Tratamento de status de prazo
        if dias_rest < 0:
            it["status_prazo"] = "vencido"
            it["status_prazo_label"] = f"Vencido há {abs(dias_rest)} dia(s)"
            it["sugestao_mensal"] = it["falta_reservar"]
            it["sugestao_semanal"] = it["falta_reservar"]
        elif dias_rest == 0:
            it["status_prazo"] = "hoje"
            it["status_prazo_label"] = "Vence Hoje"
            it["sugestao_mensal"] = it["falta_reservar"]
            it["sugestao_semanal"] = it["falta_reservar"]
        elif dt_p < dt_inicio_contrib:
            it["status_prazo"] = "antes_primeira_contribuicao"
            it["status_prazo_label"] = "Vencimento anterior à 1ª contribuição"
            it["sugestao_mensal"] = it["falta_reservar"]
            it["sugestao_semanal"] = it["falta_reservar"]
        elif dias_rest <= 7:
            it["status_prazo"] = "imediato"
            it["status_prazo_label"] = f"Vencimento Imediato ({dias_rest} dias)"
            it["sugestao_mensal"] = it["falta_reservar"]
            it["sugestao_semanal"] = it["falta_reservar"]
        else:
            it["status_prazo"] = "no_prazo"
            freq_label = "contribuição" if it["frequencia_contribuicao"] == "mensal" else it["frequencia_contribuicao"]
            it["status_prazo_label"] = f"Em {dias_rest} dias ({qtd_op} {freq_label}(ões))"
            it["sugestao_mensal"] = it["valor_por_contribuicao"] if it["frequencia_contribuicao"] == "mensal" else round(it["falta_reservar"] / max(1, qtd_op), 2)
            it["sugestao_semanal"] = it["valor_por_contribuicao"] if it["frequencia_contribuicao"] == "semanal" else round(it["falta_reservar"] / max(1, dias_rest // 7), 2)

        # Adiciona na linha do tempo mensal
        if it["mes_previsto"] in mapa_meses:
            mapa_meses[it["mes_previsto"]]["despesas"].append(it)
            mapa_meses[it["mes_previsto"]]["total_previsto"] = round(
                mapa_meses[it["mes_previsto"]]["total_previsto"] + it["valor_alvo"], 2
            )
            mapa_meses[it["mes_previsto"]]["total_reservado"] = round(
                mapa_meses[it["mes_previsto"]]["total_reservado"] + it["valor_efetivamente_reservado"], 2
            )

    total_geral_previsto = sum(m["total_previsto"] for m in meses_12)
    total_geral_reservado = sum(m["total_reservado"] for m in meses_12)
    total_geral_falta = max(0.0, round(total_geral_previsto - total_geral_reservado, 2))

    return {
        "meses": meses_12,
        "todas_despesas": lista_despesas,
        "cofrinhos_disponiveis": list(cofrinhos_dict.values()),
        "total_geral_previsto": total_geral_previsto,
        "total_geral_reservado": total_geral_reservado,
        "total_geral_falta": total_geral_falta,
        "taxa_cobertura_global": round((total_geral_reservado / total_geral_previsto * 100), 1) if total_geral_previsto > 0 else 0.0
    }


def criar_despesa_eventual(conn: sqlite3.Connection, dados: Dict[str, Any]) -> int:
    """Cadastra um novo compromisso anual/eventual legítimo."""
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()

    nome = (dados.get("nome") or "").strip()
    if not nome:
        raise ValueError("O nome do compromisso é obrigatório.")

    cat = dados.get("categoria") or "Impostos Veículo"
    resp = dados.get("responsavel") or "Família"
    dt_prev = dados.get("data_prevista") or datetime.date.today().strftime("%Y-%m-%d")
    mes_prev = dt_prev[:7]

    val_est = float(dados.get("valor_estimado") or 0.0)
    if val_est <= 0:
        raise ValueError("O valor estimado deve ser positivo.")

    val_conf_raw = dados.get("valor_confirmado")
    val_conf = float(val_conf_raw) if (val_conf_raw is not None and str(val_conf_raw).strip() != "") else None

    recorr = dados.get("recorrencia") or "anual"
    cof_id = dados.get("cofrinho_id")
    if cof_id in ("", None, "null"):
        cof_id = None
    else:
        cof_id = int(cof_id)

    val_res_manual = float(dados.get("valor_reservado_manual") or 0.0)
    freq = dados.get("frequencia_contribuicao") or "mensal"
    dt_prim_contrib = dados.get("primeira_contribuicao") or None
    obs = dados.get("observacoes") or ""
    tx_id = dados.get("transacao_id")
    if tx_id in ("", None, "null"):
        tx_id = None
    else:
        tx_id = int(tx_id)

    # Validação rigorosa de teto: a soma das reservas manuais não pode ultrapassar o saldo do cofrinho
    if cof_id and val_res_manual > 0:
        saldo_cof_disp = obter_saldo_disponivel_cofrinho(conn, cof_id)
        cur.execute("""
            SELECT COALESCE(SUM(valor_reservado_manual), 0)
            FROM planejamento_despesas_eventuais
            WHERE cofrinho_id = ? AND status != 'cancelada'
        """, (cof_id,))
        soma_atual = float(cur.fetchone()[0] or 0.0)
        if round(soma_atual + val_res_manual, 2) > round(saldo_cof_disp, 2):
            disponivel_livre = max(0.0, round(saldo_cof_disp - soma_atual, 2))
            raise ValueError(
                f"A soma das reservas manuais ultrapassa o saldo disponível do cofrinho "
                f"(Saldo cofrinho: R$ {saldo_cof_disp:,.2f}, já atribuído: R$ {soma_atual:,.2f}, livre: R$ {disponivel_livre:,.2f})."
            )

    cur.execute("""
        INSERT INTO planejamento_despesas_eventuais (
            nome, categoria, responsavel, data_prevista, mes_previsto,
            valor_estimado, valor_confirmado, recorrencia, status,
            transacao_id, cofrinho_id, valor_reservado_manual, frequencia_contribuicao,
            primeira_contribuicao, observacoes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'planejada', ?, ?, ?, ?, ?, ?)
    """, (
        nome, cat, resp, dt_prev, mes_prev,
        val_est, val_conf, recorr,
        tx_id, cof_id, val_res_manual, freq,
        dt_prim_contrib, obs
    ))
    conn.commit()
    return cur.lastrowid


def atualizar_despesa_eventual(conn: sqlite3.Connection, despesa_id: int, dados: Dict[str, Any]) -> bool:
    """Atualiza dados de uma despesa eventual."""
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()

    nome = (dados.get("nome") or "").strip()
    if not nome:
        raise ValueError("O nome do compromisso é obrigatório.")

    cat = dados.get("categoria") or "Impostos Veículo"
    resp = dados.get("responsavel") or "Família"
    dt_prev = dados.get("data_prevista")
    mes_prev = dt_prev[:7] if dt_prev else None

    val_est = float(dados.get("valor_estimado") or 0.0)
    val_conf_raw = dados.get("valor_confirmado")
    val_conf = float(val_conf_raw) if (val_conf_raw is not None and str(val_conf_raw).strip() != "") else None

    recorr = dados.get("recorrencia") or "anual"
    cof_id = dados.get("cofrinho_id")
    if cof_id in ("", None, "null"):
        cof_id = None
    else:
        cof_id = int(cof_id)

    val_res_manual = float(dados.get("valor_reservado_manual") or 0.0)
    freq = dados.get("frequencia_contribuicao") or "mensal"
    dt_prim_contrib = dados.get("primeira_contribuicao") or None
    obs = dados.get("observacoes") or ""
    status = dados.get("status") or "planejada"

    # Validação rigorosa de teto na edição: a soma de outros itens + este não pode exceder o saldo do cofrinho
    if cof_id and val_res_manual > 0:
        saldo_cof_disp = obter_saldo_disponivel_cofrinho(conn, cof_id)
        cur.execute("""
            SELECT COALESCE(SUM(valor_reservado_manual), 0)
            FROM planejamento_despesas_eventuais
            WHERE cofrinho_id = ? AND id != ? AND status != 'cancelada'
        """, (cof_id, despesa_id))
        soma_outros = float(cur.fetchone()[0] or 0.0)
        if round(soma_outros + val_res_manual, 2) > round(saldo_cof_disp, 2):
            disponivel_livre = max(0.0, round(saldo_cof_disp - soma_outros, 2))
            raise ValueError(
                f"A soma das reservas manuais ultrapassa o saldo disponível do cofrinho "
                f"(Saldo cofrinho: R$ {saldo_cof_disp:,.2f}, outros compromissos: R$ {soma_outros:,.2f}, livre: R$ {disponivel_livre:,.2f})."
            )

    cur.execute("""
        UPDATE planejamento_despesas_eventuais
        SET nome = ?, categoria = ?, responsavel = ?, data_prevista = ?, mes_previsto = ?,
            valor_estimado = ?, valor_confirmado = ?, recorrencia = ?, status = ?,
            cofrinho_id = ?, valor_reservado_manual = ?, frequencia_contribuicao = ?,
            primeira_contribuicao = ?, observacoes = ?
        WHERE id = ?
    """, (
        nome, cat, resp, dt_prev, mes_prev,
        val_est, val_conf, recorr, status,
        cof_id, val_res_manual, freq,
        dt_prim_contrib, obs, despesa_id
    ))
    conn.commit()
    return cur.rowcount > 0


def conciliar_pagamento_despesa_eventual(
    conn: sqlite3.Connection,
    despesa_id: int,
    valor_pago: float,
    data_pagamento: str,
    baixar_reserva_cofrinho: bool = True
) -> bool:
    """Registra a liquidação de um compromisso e opcionalmente abate a reserva utilizada."""
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()

    cur.execute("SELECT id, cofrinho_id, valor_estimado, valor_confirmado FROM planejamento_despesas_eventuais WHERE id = ?", (despesa_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError("Despesa eventual não encontrada.")

    cof_id = row[1]

    cur.execute("""
        UPDATE planejamento_despesas_eventuais
        SET status = 'paga', valor_confirmado = ?
        WHERE id = ?
    """, (valor_pago, despesa_id))

    if baixar_reserva_cofrinho and cof_id:
        cur.execute("SELECT saldo_confirmado FROM cofrinhos WHERE id = ?", (cof_id,))
        cof_row = cur.fetchone()
        if cof_row:
            saldo_atual = float(cof_row[0] or 0.0)
            novo_saldo = max(0.0, round(saldo_atual - valor_pago, 2))
            cur.execute("""
                UPDATE cofrinhos
                SET saldo_confirmado = ?, data_atualizacao = ?
                WHERE id = ?
            """, (novo_saldo, data_pagamento, cof_id))

    conn.commit()
    return True
