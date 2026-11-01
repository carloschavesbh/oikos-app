"""
=============================================================================
PLANEJAMENTO DE RENDA VARIÁVEL, CENÁRIOS E DESPESAS ANUAIS / EVENTUAIS
Módulo do Oikos Pessoal para análise de renda familiar estável vs. variável,
cenários de sensibilidade (conservador/habitual/favorável), natureza das
despesas, calendário de despesas eventuais/anuais e alocação de cofrinhos.
=============================================================================
"""

import sqlite3
import datetime
import calendar
from typing import Dict, List, Optional, Tuple, Any

# Naturezas Orçamentárias Permitidas
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
        "descricao": "Amortização acelerada de dívidas, formação de reservas e metas patrimoniais."
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

    # 3. Calendário anual e despesas sazonais/eventuais
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
        frequencia_contribuicao TEXT DEFAULT 'mensal',
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
    # Complementa com mapeamento padrão se alguma categoria nova não estiver no banco
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
# 2. ANÁLISE DE HISTÓRICO DE RENDA & DETECÇÃO DE LACUNAS
# =============================================================================

def analisar_historico_renda(conn: sqlite3.Connection, meses_analise: int = 12, ano_ref: Optional[int] = None, mes_ref: Optional[int] = None) -> Dict[str, Any]:
    """
    Analisa o histórico mensal de receitas até meses_analise meses atrás.
    Distingue:
      - Renda estável: Salário Fernanda
      - Renda variável: 99 / Chaves (Carlos) e Receitas Extras
      - Entradas não-operacionais: Aportes/Empréstimos (não contam como renda de trabalho)
      - Transferências: desconsideradas (não são receitas)
    Detecta meses incompletos e lacunas de informação sem tratar ausência de dados como zero.
    """
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()

    hoje = datetime.date.today()
    if ano_ref is None or mes_ref is None:
        ano_ref = hoje.year
        mes_ref = hoje.month

    # Monta lista dos últimos N meses em ordem decrescente
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
            SUM(valor) as total
        FROM transacoes
        WHERE tipo = 'receita'
          AND strftime('%Y-%m', data) IN ({placeholders})
        GROUP BY mes, categoria
        ORDER BY mes ASC
    """
    cur.execute(query, meses_alvo)
    linhas = cur.fetchall()

    # Dicionário por mês: {mes: {'estavel': X, 'variavel': X, 'outros': X, 'detalhes': []}}
    dados_por_mes: Dict[str, Dict[str, Any]] = {}
    for m in meses_alvo:
        dados_por_mes[m] = {
            "mes": m,
            "estavel": 0.0,
            "variavel": 0.0,
            "aportes_emprestimos": 0.0,
            "rendimentos": 0.0,
            "qtd_lancamentos": 0,
            "incompleto": False,
            "motivo_incompleto": None,
            "tem_dados": False
        }

    for mes_str, categoria, qtd, total in linhas:
        if mes_str not in dados_por_mes:
            continue
        val = float(total or 0.0)
        dados_por_mes[mes_str]["qtd_lancamentos"] += qtd
        dados_por_mes[mes_str]["tem_dados"] = True

        cat_norm = (categoria or "").strip()
        if cat_norm in ("Salário Fernanda", "Salário", "Salários"):
            dados_por_mes[mes_str]["estavel"] += val
        elif cat_norm in ("99 / Chaves (Carlos)", "Receitas Extras", "Ganhos Drive", "Freelas"):
            dados_por_mes[mes_str]["variavel"] += val
        elif cat_norm in ("Empréstimo / Aporte", "Empréstimos"):
            dados_por_mes[mes_str]["aportes_emprestimos"] += val
        elif cat_norm in ("Rendimentos", "Rendimento"):
            dados_por_mes[mes_str]["rendimentos"] += val
        else:
            # Qualquer outra receita entra em variável por segurança analítica
            dados_por_mes[mes_str]["variavel"] += val

    # Identificar meses incompletos / lacunas
    historico_ordenado = []
    valores_estaveis_validos = []
    valores_variaveis_validos = []

    for m in sorted(meses_alvo):
        info = dados_por_mes[m]
        # Regra de mês incompleto:
        # Se for o mês corrente e estiver antes do dia 28
        eh_mes_corrente = (m == f"{hoje.year:04d}-{hoje.month:02d}")
        if eh_mes_corrente:
            info["incompleto"] = True
            info["motivo_incompleto"] = f"Mês em andamento (dia {hoje.day})"
        elif not info["tem_dados"]:
            info["incompleto"] = True
            info["motivo_incompleto"] = "Sem registros cadastrados (lacuna histórica)"
        elif info["qtd_lancamentos"] < 2 and (info["estavel"] + info["variavel"]) < 500:
            info["incompleto"] = True
            info["motivo_incompleto"] = "Registros parciais no mês"

        # Apenas meses com dados participam da amostra estatística
        # (Não trata ausência de dados como zero!)
        if info["tem_dados"] and not eh_mes_corrente:
            if info["estavel"] > 0:
                valores_estaveis_validos.append(info["estavel"])
            if info["variavel"] > 0:
                valores_variaveis_validos.append(info["variavel"])

        historico_ordenado.append(info)

    # Estatísticas da Renda Variável (Drive + Extras)
    qtd_meses_variavel = len(valores_variaveis_validos)
    if qtd_meses_variavel > 0:
        min_var = min(valores_variaveis_validos)
        max_var = max(valores_variaveis_validos)
        media_var = sum(valores_variaveis_validos) / qtd_meses_variavel
    else:
        # Se não há meses anteriores fechados, usa o mês atual se tiver dados ou 0.0
        val_curr = dados_por_mes.get(f"{ano_ref:04d}-{mes_ref:02d}", {}).get("variavel", 0.0)
        min_var = val_curr
        max_var = val_curr
        media_var = val_curr

    # Estatísticas da Renda Estável (Salário)
    qtd_meses_estavel = len(valores_estaveis_validos)
    if qtd_meses_estavel > 0:
        media_estavel = sum(valores_estaveis_validos) / qtd_meses_estavel
    else:
        media_estavel = dados_por_mes.get(f"{ano_ref:04d}-{mes_ref:02d}", {}).get("estavel", 3500.0)

    # Geração dos Cenários Sugeridos
    # Conservador: mínimo observado (ou percentil 25 aproximado)
    cenario_conservador_sugerido = round(min_var, 2)
    # Habitual: média histórica observada
    cenario_habitual_sugerido = round(media_var, 2)
    # Favorável: máximo observado (ou média + margem)
    cenario_favoravel_sugerido = round(max_var, 2)

    # Verificar se existem ajustes manuais gravados para este mês
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
            "qtd_meses_validos": qtd_meses_variavel,
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
                "descricao": "Mínimo observado no histórico recente (dias de chuva, feriados fracos ou menor disponibilidade)"
            },
            "habitual": {
                "base": cenario_habitual_sugerido,
                "manual": hab_manual,
                "valor_final": hab_final,
                "is_manual": hab_manual is not None,
                "descricao": "Média de corridas e ganhos em meses normais de operação"
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
        "aviso_metodologico": "O mínimo histórico não é uma renda garantida. Em atividades de aplicativo, a renda depende de horas rodadas, demanda, condições do trânsito e do veículo."
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

    # Obtém as bases históricas
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
# 3. INTEGRAÇÃO COM O DRIVE & MARGEM LÍQUIDA OPERACIONAL
# =============================================================================

def obter_margem_operacional_drive(conn: sqlite3.Connection, ano: int, mes: int) -> Dict[str, Any]:
    """
    Retorna métricas do Drive para o mês:
    - Faturamento bruto registrado
    - Custos registrados (combustível e manutenção)
    - Resultado líquido estimado disponível para a família
    - Custos ainda não registrados/disponíveis
    - Alerta transparente anti-duplicidade
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
    qtd_receitas_99 = row_rx[1] or 0

    # 3. Custos operacionais reais registrados no mês
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0)
        FROM transacoes
        WHERE tipo = 'despesa'
          AND categoria IN ('Combustível', 'Combustível (Trabalho)', 'Manutenção Veículo')
          AND data BETWEEN ? AND ?
    """, (inicio_mes, fim_mes))
    custos_veiculo_reais = float(cur.fetchone()[0] or 0.0)

    # Resultado líquido estimado da atividade
    # Usa o maior entre ganho de turnos e receita financeira lançada
    faturamento_bruto = max(ganho_bruto_turnos, receita_financeira_99)
    # Custos diretos registrados
    custos_registrados = max(custos_veiculo_reais, combustivel_estimado_turnos)
    resultado_liquido_disponivel = round(faturamento_bruto - custos_registrados, 2)

    # R$ 35/h como referência
    referencia_ganho_hora = 35.0
    faturamento_esperado_horas = round(horas_totais * referencia_ganho_hora, 2)
    ganho_hora_real = round(faturamento_bruto / horas_totais, 2) if horas_totais > 0 else 0.0

    return {
        "qtd_turnos": qtd_turnos,
        "horas_totais": round(horas_totais, 1),
        "km_totais": round(km_totais, 1),
        "referencia_hora": referencia_ganho_hora,
        "faturamento_bruto": round(faturamento_bruto, 2),
        "faturamento_esperado_horas": faturamento_esperado_horas,
        "ganho_hora_real": ganho_hora_real,
        "custos_registrados": round(custos_registrados, 2),
        "detalhe_custos": {
            "combustivel_registrado": round(custos_veiculo_reais, 2),
            "combustivel_turnos_estimado": round(combustivel_estimado_turnos, 2)
        },
        "resultado_liquido_disponivel": resultado_liquido_disponivel,
        "custos_nao_disponiveis": [
            "Provisão de desgaste de pneus (~R$ 0,08/km rodado)",
            "Manutenção preventiva periódica futura (óleo, suspensão, freios)",
            "Depreciação real do veículo HB20"
        ],
        "aviso_anti_duplicidade": "Os ganhos dos turnos já são creditados como lançamentos de receita ('Ganho Online 99Pay' e 'Ganho Dinheiro/Pix 99'). Transferências entre contas (99Pay -> Mercado Pago) não representam novas receitas e são desconsideradas da renda."
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
    """
    Compara os cenários (conservador, habitual, favorável) com as despesas
    projetadas do mês, agrupadas por natureza orçamentária.
    """
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()

    inicio_mes = f"{ano:04d}-{mes:02d}-01"
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    fim_mes = f"{ano:04d}-{mes:02d}-{ultimo_dia:02d}"

    # 1. Classificação das categorias
    classificacao = obter_classificacao_natureza(conn)

    # 2. Despesas do mês por categoria
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

    # 3. Analisa os 3 cenários
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
# 5. CALENDÁRIO ANUAL & DESPESAS EVENTUAIS (12 MESES) COM COFRINHOS
# =============================================================================

def obter_calendario_anual(conn: sqlite3.Connection, ano_inicio: Optional[int] = None, mes_inicio: Optional[int] = None) -> Dict[str, Any]:
    """
    Gera a visão dos próximos 12 meses com despesas anuais, sazonais e eventuais,
    integradas com os cofrinhos e com distribuição anti-duplicidade de saldo.
    """
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()

    hoje = datetime.date.today()
    if ano_inicio is None or mes_inicio is None:
        ano_inicio = hoje.year
        mes_inicio = hoje.month

    # Monta os 12 meses a partir do mês inicial
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
    cur.execute("SELECT id, nome, saldo_confirmado, meta_valor, objetivo FROM cofrinhos")
    rows_cof = cur.fetchall()
    cofrinhos_dict = {
        r[0]: {
            "id": r[0],
            "nome": r[1],
            "saldo_confirmado": float(r[2] or 0.0),
            "meta_valor": float(r[3] or 0.0),
            "objetivo": r[4],
            "despesas_vinculadas": []
        }
        for r in rows_cof
    }

    # Carrega despesas cadastradas
    cur.execute("""
        SELECT 
            id, nome, categoria, responsavel, data_prevista, mes_previsto,
            valor_estimado, valor_confirmado, recorrencia, status,
            transacao_id, cofrinho_id, frequencia_contribuicao, observacoes
        FROM planejamento_despesas_eventuais
        WHERE status != 'cancelada'
        ORDER BY data_prevista ASC
    """)
    despesas_raw = cur.fetchall()

    # Mapeia despesas para cofrinhos para distribuir o saldo sem duplicar
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
        freq = r[12] or "mensal"
        obs = r[13]

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
            "frequencia_contribuicao": freq,
            "observacoes": obs,
            "saldo_reservado_alocado": 0.0,
            "falta_reservar": valor_alvo,
            "sugestao_mensal": 0.0,
            "sugestao_semanal": 0.0,
            "meses_ate_data": 1,
            "obrigacao_constituida": tx_id is not None
        }

        if cof_id and cof_id in cofrinhos_dict:
            if cof_id not in cofrinho_para_despesas:
                cofrinho_para_despesas[cof_id] = []
            cofrinho_para_despesas[cof_id].append(item)

        lista_despesas.append(item)

    # Distribuição anti-duplicidade de saldos dos cofrinhos
    # Se um cofrinho estiver vinculado a mais de 1 compromisso, o saldo é rateado
    # proporcionalmente ao valor_alvo de cada compromisso, garantindo que o mesmo real
    # não cubra 2 despesas simultâneas.
    for cof_id, itens_vinculados in cofrinho_para_despesas.items():
        saldo_total_cof = cofrinhos_dict[cof_id]["saldo_confirmado"]
        soma_alvos = sum(it["valor_alvo"] for it in itens_vinculados)

        if soma_alvos > 0:
            for it in itens_vinculados:
                proporcao = it["valor_alvo"] / soma_alvos
                # Saldo alocado não pode exceder o valor alvo do item
                saldo_alocado = min(it["valor_alvo"], round(saldo_total_cof * proporcao, 2))
                it["saldo_reservado_alocado"] = saldo_alocado
                it["falta_reservar"] = max(0.0, round(it["valor_alvo"] - saldo_alocado, 2))
        else:
            for it in itens_vinculados:
                it["saldo_reservado_alocado"] = 0.0
                it["falta_reservar"] = it["valor_alvo"]

    # Cálculo do prazo e das sugestões de contribuição para cada compromisso
    hoje_iso = hoje.strftime("%Y-%m-%d")
    for it in lista_despesas:
        # Calcula diferença em meses entre hoje e data_prevista
        try:
            dt_p = datetime.datetime.strptime(it["data_prevista"], "%Y-%m-%d").date()
            meses_diff = (dt_p.year - hoje.year) * 12 + (dt_p.month - hoje.month)
            meses_ate = max(1, meses_diff)
        except Exception:
            meses_ate = 1

        it["meses_ate_data"] = meses_ate
        sug_mes = round(it["falta_reservar"] / meses_ate, 2) if it["falta_reservar"] > 0 else 0.0
        sug_sem = round(sug_mes / 4.33, 2)
        it["sugestao_mensal"] = sug_mes
        it["sugestao_semanal"] = sug_sem

        # Adiciona na linha do tempo se cair nos próximos 12 meses
        if it["mes_previsto"] in mapa_meses:
            mapa_meses[it["mes_previsto"]]["despesas"].append(it)
            mapa_meses[it["mes_previsto"]]["total_previsto"] = round(
                mapa_meses[it["mes_previsto"]]["total_previsto"] + it["valor_alvo"], 2
            )
            mapa_meses[it["mes_previsto"]]["total_reservado"] = round(
                mapa_meses[it["mes_previsto"]]["total_reservado"] + it["saldo_reservado_alocado"], 2
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
    """Cadastra uma nova despesa anual/eventual."""
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

    freq = dados.get("frequencia_contribuicao") or "mensal"
    obs = dados.get("observacoes") or ""
    tx_id = dados.get("transacao_id")
    if tx_id in ("", None, "null"):
        tx_id = None
    else:
        tx_id = int(tx_id)

    cur.execute("""
        INSERT INTO planejamento_despesas_eventuais (
            nome, categoria, responsavel, data_prevista, mes_previsto,
            valor_estimado, valor_confirmado, recorrencia, status,
            transacao_id, cofrinho_id, frequencia_contribuicao, observacoes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'planejada', ?, ?, ?, ?)
    """, (
        nome, cat, resp, dt_prev, mes_prev,
        val_est, val_conf, recorr,
        tx_id, cof_id, freq, obs
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

    freq = dados.get("frequencia_contribuicao") or "mensal"
    obs = dados.get("observacoes") or ""
    status = dados.get("status") or "planejada"

    cur.execute("""
        UPDATE planejamento_despesas_eventuais
        SET nome = ?, categoria = ?, responsavel = ?, data_prevista = ?, mes_previsto = ?,
            valor_estimado = ?, valor_confirmado = ?, recorrencia = ?, status = ?,
            cofrinho_id = ?, frequencia_contribuicao = ?, observacoes = ?
        WHERE id = ?
    """, (
        nome, cat, resp, dt_prev, mes_prev,
        val_est, val_conf, recorr, status,
        cof_id, freq, obs, despesa_id
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
    """
    Registra a liquidação de um compromisso anual/eventual.
    Se baixar_reserva_cofrinho for True e houver cofrinho vinculado, reduz o saldo
    do cofrinho utilizado sem duplicar o lançamento de despesa financeira.
    """
    inicializar_tabelas_renda_e_anual(conn)
    cur = conn.cursor()

    cur.execute("SELECT id, cofrinho_id, valor_estimado, valor_confirmado FROM planejamento_despesas_eventuais WHERE id = ?", (despesa_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError("Despesa eventual não encontrada.")

    cof_id = row[1]

    # Atualiza status da despesa eventual
    cur.execute("""
        UPDATE planejamento_despesas_eventuais
        SET status = 'paga', valor_confirmado = ?
        WHERE id = ?
    """, (valor_pago, despesa_id))

    # Baixa no cofrinho se solicitado
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
