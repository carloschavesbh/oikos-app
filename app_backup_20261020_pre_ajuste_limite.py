"""
=============================================================================
SISTEMA DE GESTÃO FINANCEIRA PESSOAL & CENTRAL DO MOTORISTA (99 / UBER)
Estrutura modular, limpa e responsiva baseada na metodologia Organizze.
Página dedicada para gestão operacional e financeira do trabalho como motorista.
=============================================================================
"""

import os
import re
import sqlite3
import uuid
import calendar
from datetime import datetime, timedelta, date
from typing import List, Dict, Tuple, Optional, Any
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import json
from decimal import Decimal
import saldo_service
import planejamento_service


# =============================================================================
# 1. CONFIGURAÇÕES GERAIS E PALETA DE CORES
# =============================================================================
DB_NAME = "financas_casa.db"
APP_TITLE = "Central Financeira"
APP_SUBTITLE = "Gestão Pessoal & Motorista"

# Mapeamento de Ícones por Categoria
ICONES_CATEGORIA = {
    "Habitação": "🏠",
    "HABITAÇÃO": "🏠",
    "Medicamentos": "💊",
    "Saúde": "❤️",
    "SAÚDE": "❤️",
    "Educação": "🎓",
    "EDUCAÇÃO": "🎓",
    "Manutenção Veículo": "🚗",
    "Impostos Veículo": "🚘",
    "Combustível": "⛽",
    "Salário Fernanda": "💰",
    "Renda Corridas (99/Uber)": "🚕",
    "Saldo Inicial": "🏦",
    "Outras Dívidas": "💸",
    "Acordo BV": "📄",
    "Pagamento de fatura": "💳",
    "Streaming": "📺",
    "Energia": "⚡",
    "Restaurante": "🍔",
    "Academia / Wellhub": "🏋️",
    "Barbearia": "💈",
    "PESSOAL - Carlos": "👤",
    "Supermercado": "🛒",
    "Lazer": "🎉",
    "Outros": "📌"
}

def obter_icone_categoria(cat: str) -> str:
    """Retorna o ícone representativo da categoria com suporte a fallback inteligente."""
    if not cat:
        return "📌"
    if cat in ICONES_CATEGORIA:
        return ICONES_CATEGORIA[cat]
    
    cat_upper = cat.upper()
    for chave, icone in ICONES_CATEGORIA.items():
        if chave.upper() in cat_upper or cat_upper in chave.upper():
            return icone
            
    if "HABIT" in cat_upper or "CASA" in cat_upper:
        return "🏠"
    if "MEDIC" in cat_upper or "FARM" in cat_upper:
        return "💊"
    if "SAUD" in cat_upper or "SAÚ" in cat_upper:
        return "❤️"
    if "EDUC" in cat_upper:
        return "🎓"
    if "VEIC" in cat_upper or "VEÍC" in cat_upper or "CARRO" in cat_upper or "PNEU" in cat_upper or "ÓLEO" in cat_upper:
        return "🚗"
    if "COMBUST" in cat_upper or "GASOL" in cat_upper or "ETANOL" in cat_upper:
        return "⛽"
    if "SALAR" in cat_upper or "SALÁR" in cat_upper:
        return "💰"
    if "CORRIDA" in cat_upper or "UBER" in cat_upper or "99" in cat_upper:
        return "🚕"
    if "DIVID" in cat_upper or "DÍVID" in cat_upper or "ACORDO" in cat_upper:
        return "📄"
    if "FATURA" in cat_upper or "CART" in cat_upper:
        return "💳"
    if "ENERG" in cat_upper or "LUZ" in cat_upper or "CEMIG" in cat_upper:
        return "⚡"
    if "REST" in cat_upper or "ALIM" in cat_upper or "LANCH" in cat_upper:
        return "🍔"
    if "ACAD" in cat_upper:
        return "🏋️"
    return "📌"

def formatar_moeda_br(val) -> str:
    """Formata valor float/Decimal no padrão monetário brasileiro: R$ 131,79 ou R$ 1.234,56."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "R$ 0,00"
    try:
        val_flt = float(val)
        negativo = val_flt < 0
        val_abs = abs(val_flt)
        fmt = f"{val_abs:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"- R$ {fmt}" if negativo else f"R$ {fmt}"
    except Exception:
        return f"R$ {val}"


# =============================================================================
# 2. ESTILOS CSS E GERENCIADOR DE TEMAS (CLARO & NOTURNO SUAVE)
# =============================================================================
def aplicar_estilos_tema(tema: str):
    """
    Injeta o CSS dinâmico eliminando o preto chapado ('pretão') e corrigindo cortes visuais.
    Garante alta legibilidade no menu e botões tanto no modo claro quanto no escuro.
    """
    if tema == "Claro":
        css_vars = """
            --bg-app: #f8fafc;
            --bg-card: #ffffff;
            --bg-subcard: #f1f5f9;
            --border-color: #e2e8f0;
            --text-primary: #0f172a;
            --text-muted: #64748b;
            --text-nav-inactive: #334155;
            --card-shadow: 0 1px 4px 0 rgba(0, 0, 0, 0.06);
            --dia-bg: #e2e8f0;
            --dia-text: #1e293b;
            --card-grad: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            --btn-action-bg: #ffffff;
            --btn-action-border: #cbd5e1;
            --drop-indicator: #2563eb;
        """
    else:
        # Modo Noturno Suave (Charcoal / Slate - ZERO 'pretão')
        css_vars = """
            --bg-app: #181b22;
            --bg-card: #212631;
            --bg-subcard: #2b3242;
            --border-color: #384255;
            --text-primary: #f8fafc;
            --text-muted: #94a3b8;
            --text-nav-inactive: #e2e8f0;
            --card-shadow: 0 4px 10px 0 rgba(0, 0, 0, 0.3);
            --dia-bg: #2b3242;
            --dia-text: #f1f5f9;
            --card-grad: linear-gradient(135deg, #242c3d 0%, #1a202c 100%);
            --btn-action-bg: #283040;
            --btn-action-border: #3d475c;
            --drop-indicator: #38bdf8;
        """

    st.markdown(f"""
    <style>
        :root {{
            {css_vars}
        }}

        /* Remove o header fantasma do Streamlit para evitar que corte o topo da página */
        header[data-testid="stHeader"] {{
            display: none !important;
        }}

        /* Fundo geral da aplicação e espaçamento superior seguro */
        .stApp {{
            background-color: var(--bg-app) !important;
            color: var(--text-primary) !important;
        }}

        .block-container {{
            padding-top: 1.5rem !important;
            padding-bottom: 3rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            max-width: 1440px !important;
            overflow: visible !important;
        }}

        @media (max-width: 768px) {{
            .block-container {{
                padding-top: 1rem !important;
                padding-bottom: 2rem !important;
                padding-left: 0.9rem !important;
                padding-right: 0.9rem !important;
            }}
        }}

        /* Títulos sem corte vertical */
        h1, h2, h3, h4, h5, h6 {{
            color: var(--text-primary) !important;
            line-height: 1.35 !important;
            overflow: visible !important;
        }}

        p, label, .stMarkdown {{
            color: var(--text-primary);
        }}

        /* MENU DE NAVEGAÇÃO SUPERIOR & SEGMENTED CONTROLS - CORREÇÃO DE COR E RESPONSIVIDADE */
        div[data-baseweb="segmented-control"] {{
            background-color: var(--bg-subcard) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 12px !important;
            padding: 3px !important;
            box-shadow: var(--card-shadow) !important;
            display: inline-flex !important;
            max-width: 100% !important;
            overflow-x: auto !important;
            scrollbar-width: none !important;
            -ms-overflow-style: none !important;
        }}

        div[data-baseweb="segmented-control"]::-webkit-scrollbar {{
            display: none !important;
        }}

        div[data-baseweb="segmented-control"] button {{
            font-weight: 600 !important;
            font-size: 0.84rem !important;
            border-radius: 8px !important;
            padding: 6px 11px !important;
            white-space: nowrap !important;
            flex-shrink: 0 !important;
            transition: all 0.2s ease !important;
        }}

        @media (max-width: 900px) {{
            div[data-baseweb="segmented-control"] button {{
                font-size: 0.78rem !important;
                padding: 5px 8px !important;
            }}
        }}

        /* Alinhamento refinado do seletor de tema e submenu em telas menores */
        .header-theme-wrapper {{
            display: flex;
            justify-content: flex-end;
            align-items: center;
            width: 100%;
        }}

        @media (max-width: 768px) {{
            .header-theme-wrapper {{
                justify-content: flex-start;
                margin-top: 6px;
            }}
            .sub-menu-indicator {{
                display: none !important;
            }}
        }}

        /* Aba Ativa: Destaque azul elegante com texto branco */
        div[data-baseweb="segmented-control"] button[aria-checked="true"] {{
            background-color: #2563eb !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            box-shadow: 0 2px 8px rgba(37, 99, 235, 0.45) !important;
        }}

        /* Abas Inativas: VISÍVEIS E NÍTIDAS (sem ficar apagado!) */
        div[data-baseweb="segmented-control"] button[aria-checked="false"] {{
            color: var(--text-nav-inactive) !important;
            background-color: transparent !important;
            opacity: 1 !important;
        }}

        div[data-baseweb="segmented-control"] button[aria-checked="false"]:hover {{
            color: var(--text-primary) !important;
            background-color: var(--bg-card) !important;
        }}

        /* Containers com borda (Cards do Streamlit) */
        div[data-testid="stVerticalBlockBorderWrapper"] > div {{
            background-color: var(--bg-card) !important;
            border-color: var(--border-color) !important;
            box-shadow: var(--card-shadow) !important;
            border-radius: 14px !important;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }}

        /* ESTILO DOS BOTÕES EM AMBOS OS TEMAS (SEM RETÂNGULO BRANCO NO ESCURO) */
        div[data-testid="stVerticalBlockBorderWrapper"] button,
        div[data-testid="stHorizontalBlock"] button {{
            background-color: var(--btn-action-bg) !important;
            color: var(--text-primary) !important;
            border: 1px solid var(--btn-action-border) !important;
            border-radius: 9px !important;
            font-weight: 600 !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
            transition: all 0.2s ease !important;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] button:hover,
        div[data-testid="stHorizontalBlock"] button:hover {{
            background-color: var(--bg-subcard) !important;
            border-color: #3b82f6 !important;
            transform: translateY(-1px);
        }}

        /* Cards de Métricas (KPIs) */
        div[data-testid="stMetric"] {{
            background-color: var(--bg-card) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 14px !important;
            padding: 16px 20px !important;
            box-shadow: var(--card-shadow) !important;
        }}
        div[data-testid="stMetric"] label {{
            color: var(--text-muted) !important;
            font-size: 0.85rem !important;
            font-weight: 600 !important;
        }}
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
            color: var(--text-primary) !important;
            font-weight: 800 !important;
        }}

        /* Modais Pop-up (st.dialog) */
        div[data-testid="stDialog"] div[role="dialog"] {{
            background-color: var(--bg-card) !important;
            color: var(--text-primary) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 16px !important;
            box-shadow: 0 10px 25px rgba(0,0,0,0.4) !important;
        }}

        /* Subcards e linhas de extrato personalizadas */
        .subcard-item {{
            background-color: var(--bg-subcard);
            padding: 12px 14px;
            border-radius: 10px;
            margin-bottom: 8px;
            border: 1px solid var(--border-color);
        }}
        .row-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid var(--border-color);
        }}

        /* Cabeçalho de data no extrato */
        .dia-header {{
            font-size: 0.88rem;
            color: var(--dia-text);
            font-weight: 700;
            margin-top: 18px;
            margin-bottom: 8px;
            padding: 7px 12px;
            background-color: var(--dia-bg);
            border-radius: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        /* Saldo ao final do dia */
        .saldo-dia {{
            text-align: right;
            font-size: 0.85rem;
            color: var(--text-muted);
            padding: 6px 12px 14px 0;
        }}
        .saldo-dia span {{
            color: #10b981;
            font-weight: 700;
            margin-left: 8px;
        }}

        /* Mockup de Cartão de Crédito */
        .cartao-credito-mockup {{
            background: var(--card-grad);
            border: 1px solid #3b82f6;
            border-radius: 14px;
            padding: 20px;
            color: #ffffff;
            box-shadow: 0 4px 12px -2px rgba(0,0,0,0.3);
            margin-bottom: 10px;
        }}

        /* Efeito de Cursor Arrastável (Drag & Drop) e Controles de Reordenação */
        .bloco-dashboard {{
            cursor: grab;
        }}
        .bloco-dashboard:active {{
            cursor: grabbing;
        }}
        .drag-handle {{
            color: var(--text-muted);
            cursor: grab;
            margin-right: 6px;
            font-size: 1.1rem;
            user-select: none;
        }}
        .drag-handle:hover {{
            color: #3b82f6;
        }}

        /* Controles de movimentação e reordenação nos cartões */
        div[class*="st-key-btn_up_"] button,
        div[class*="st-key-btn_down_"] button,
        div[class*="st-key-btn_swap_"] button {{
            padding: 2px 4px !important;
            min-height: 28px !important;
            height: 28px !important;
            font-size: 0.8rem !important;
            line-height: 1 !important;
            border-radius: 6px !important;
        }}
        div[class*="st-key-card_"] {{
            transition: box-shadow 0.2s ease, border-color 0.2s ease;
        }}
        div[class*="st-key-card_"]:hover {{
            border-color: rgba(59, 130, 246, 0.45) !important;
        }}
    </style>
    """, unsafe_allow_html=True)


def injetar_script_cards_arrastaveis():
    """
    Injeta o motor JavaScript de Drag & Drop (arrastar e soltar) nativo.
    Permite reordenar os blocos do dashboard interativamente pelo usuário.
    """
    components.html("""
    <script>
    function inicializarDragAndDrop() {
        try {
            const pDoc = window.parent.document;
            const anchors = pDoc.querySelectorAll('.bloco-card-anchor');
            if (!anchors || anchors.length === 0) return;

            let arrastado = null;

            anchors.forEach(anc => {
                const card = anc.closest('[class*="st-key-card_"]') || anc.closest('[data-testid="stVerticalBlock"]') || anc.parentElement;
                if (!card) return;

                card.setAttribute('draggable', 'true');
                card.style.cursor = 'grab';

                card.ondragstart = function(e) {
                    if (e.target.tagName === 'BUTTON' || e.target.closest('button') || e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') {
                        e.preventDefault();
                        return;
                    }
                    arrastado = card;
                    card.style.opacity = '0.45';
                    card.style.transform = 'scale(0.98)';
                    e.dataTransfer.effectAllowed = 'move';
                };

                card.ondragend = function() {
                    card.style.opacity = '1';
                    card.style.cursor = 'grab';
                    card.style.transform = 'none';
                    pDoc.querySelectorAll('[class*="st-key-card_"]').forEach(c => {
                        c.style.borderTop = '';
                        c.style.borderBottom = '';
                    });
                };

                card.ondragover = function(e) {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = 'move';
                    if (arrastado && this !== arrastado) {
                        const rect = this.getBoundingClientRect();
                        const meio = (e.clientY - rect.top) / (rect.bottom - rect.top) > 0.5;
                        if (meio) {
                            this.style.borderBottom = '3px solid #3b82f6';
                            this.style.borderTop = '';
                        } else {
                            this.style.borderTop = '3px solid #3b82f6';
                            this.style.borderBottom = '';
                        }
                    }
                };

                card.ondragleave = function() {
                    this.style.borderTop = '';
                    this.style.borderBottom = '';
                };

                card.ondrop = function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    this.style.borderTop = '';
                    this.style.borderBottom = '';
                    if (arrastado && this !== arrastado) {
                        const rect = this.getBoundingClientRect();
                        const meio = (e.clientY - rect.top) / (rect.bottom - rect.top) > 0.5;
                        this.parentNode.insertBefore(arrastado, meio ? this.nextSibling : this);
                    }
                };
            });
        } catch (err) {
            // Silencioso em caso de restrição de iframe
        }
    }

    setTimeout(inicializarDragAndDrop, 350);
    setTimeout(inicializarDragAndDrop, 1000);
    setTimeout(inicializarDragAndDrop, 2000);
    </script>
    """, height=0, width=0)


# =============================================================================
# 3. CAMADA DE BANCO DE DADOS (SQLite)
# =============================================================================
def conectar() -> sqlite3.Connection:
    """Abre conexão com o banco de dados principal."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_banco() -> None:
    """Garante a integridade das tabelas existentes e inicializa tabelas complementares."""
    conn = conectar()
    cur = conn.cursor()
    
    # 1. Transações principais
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data DATE NOT NULL,
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        tipo TEXT NOT NULL,
        categoria TEXT NOT NULL,
        conta TEXT NOT NULL,
        pago INTEGER DEFAULT 0,
        grupo_parcelamento TEXT
    );
    """)
    
    # 2. Turnos de Trabalho (para motoristas e autônomos)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS turnos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data DATE NOT NULL,
        horas REAL NOT NULL,
        km REAL DEFAULT 0,
        ganho_bruto REAL NOT NULL,
        combustivel REAL DEFAULT 0,
        observacao TEXT
    );
    """)

    # Colunas adicionais em turnos para inteligência operacional e conciliação
    for col, col_def in [
        ('periodo', "TEXT DEFAULT 'Noite'"),
        ('hora_inicio', "TEXT"),
        ('hora_fim', "TEXT"),
        ('alimentacao', "REAL DEFAULT 0"),
        ('plataforma', "TEXT DEFAULT '99'"),
        ('valor_transferido_banco', "REAL DEFAULT 0"),
        ('dinheiro_fisico_recebido', "REAL DEFAULT 0"),
        ('despesas_diretas_app', "REAL DEFAULT 0"),
        ('combustivel_consumido', "REAL DEFAULT 0"),
        ('status_conciliacao', "TEXT DEFAULT 'conciliado'")
    ]:
        try:
            cur.execute(f"ALTER TABLE turnos ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    # Garante coluna turno_id em transacoes para rastreamento não destrutivo
    try:
        cur.execute("ALTER TABLE transacoes ADD COLUMN turno_id INTEGER REFERENCES turnos(id)")
    except Exception:
        pass
    
    # 3. Despesas específicas do veículo / trabalho (Manutenções, seguro, etc.)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS despesas_veiculo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data DATE NOT NULL,
        tipo TEXT NOT NULL,
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        km_atual REAL,
        proxima_troca_km REAL,
        conta TEXT DEFAULT 'Mercado Pago',
        observacao TEXT
    );
    """)

    # 4. Limites de Gastos (Orçamentos por categoria)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS limites_categoria (
        categoria TEXT PRIMARY KEY,
        limite REAL NOT NULL
    );
    """)

    # 5. Cartões de Crédito
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cartoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        bandeira TEXT DEFAULT 'Mastercard',
        limite_total REAL NOT NULL,
        dia_fechamento INTEGER DEFAULT 5,
        dia_vencimento INTEGER DEFAULT 12,
        cor TEXT DEFAULT '#1e293b'
    );
    """)

    # 6. Configuração de Contas bancárias / carteiras
    cur.execute("""
    CREATE TABLE IF NOT EXISTS contas_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        tipo TEXT DEFAULT 'corrente',
        cor TEXT DEFAULT '#0284c7'
    );
    """)

    # Migração segura e centralizada de esquemas (ajustes_saldo, conta_id, afeta_saldo_bancario)
    saldo_service.migrar_esquema(conn)
    
    # Normalização de nomes de categorias com acentuação
    correcoes = {
        'HABITAO': 'Habitação',
        'Manuteno Veculo': 'Manutenção Veículo',
        'Salrio Fernanda': 'Salário Fernanda',
        'SADE': 'Saúde',
        'Outras Dvidas': 'Outras Dívidas',
        'Educao': 'Educação',
        'EDUCAO': 'Educação',
        'Impostos Veculo': 'Impostos Veículo'
    }
    for err, fix in correcoes.items():
        cur.execute("UPDATE transacoes SET categoria = ? WHERE categoria = ?", (fix, err))

    # Inserção de contas padrão caso as tabelas estejam vazias
    cur.execute("INSERT OR IGNORE INTO contas_config (nome, tipo, cor) VALUES ('Mercado Pago', 'digital', '#0284c7')")
    cur.execute("INSERT OR IGNORE INTO contas_config (nome, tipo, cor) VALUES ('Dinheiro / Carteira', 'dinheiro', '#10b981')")
    
    # Remove qualquer duplicidade existente na tabela de cartões
    cur.execute("DELETE FROM cartoes WHERE id NOT IN (SELECT MIN(id) FROM cartoes GROUP BY nome)")

    # Insere apenas 1 cartão de exemplo caso não exista nenhum cadastrado
    cur.execute("SELECT count(*) FROM cartoes")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO cartoes (nome, bandeira, limite_total, dia_fechamento, dia_vencimento, cor) VALUES ('Mercado Pago Card', 'Visa', 2500.0, 5, 12, '#2563eb')")

    # Limites de gastos iniciais padrão se ainda não cadastrados
    cur.execute("SELECT count(*) FROM limites_categoria")
    if cur.fetchone()[0] == 0:
        limites_iniciais = [
            ("Combustível", 800.0),
            ("Habitação", 1200.0),
            ("Medicamentos", 350.0),
            ("Supermercado", 900.0),
            ("Restaurante", 300.0),
            ("Streaming", 120.0),
        ]
        cur.executemany("INSERT OR IGNORE INTO limites_categoria (categoria, limite) VALUES (?, ?)", limites_iniciais)

    # 7. Configurações de layout do dashboard
    cur.execute("""
    CREATE TABLE IF NOT EXISTS config_dashboard (
        chave TEXT PRIMARY KEY,
        valor TEXT
    );
    """)

    # 8. Módulo de Planejamento Financeiro Inteligente
    planejamento_service.inicializar_esquema_planejamento(conn)
    cur.execute("UPDATE transacoes SET status_conciliacao_fatura = 'pendente_confirmacao' WHERE (descricao LIKE '%Acordo BV%' OR categoria LIKE '%Acordo BV%') AND (status_conciliacao_fatura IS NULL OR status_conciliacao_fatura = 'normal')")

    conn.commit()
    conn.close()

def carregar_layout_dashboard() -> Tuple[List[str], List[str], Dict[str, bool]]:
    """Carrega as posições salvas dos blocos do banco de dados SQLite ou retorna o padrão."""
    padrao_esq = ["contas", "cartoes", "paga_leve", "limites", "missao_ipva", "capacidade_trabalho"]
    padrao_dir = ["contas_pagar", "caixa_7dias", "projecao_mes", "maiores_gastos", "turnos"]
    padrao_visiveis = {
        "contas": True,
        "cartoes": True,
        "paga_leve": True,
        "limites": True,
        "contas_pagar": True,
        "maiores_gastos": True,
        "turnos": True,
        "missao_ipva": True,
        "caixa_7dias": True,
        "projecao_mes": True,
        "capacidade_trabalho": True
    }
    
    conn = conectar()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS config_dashboard (chave TEXT PRIMARY KEY, valor TEXT)")
    cur.execute("SELECT chave, valor FROM config_dashboard")
    configs = dict(cur.fetchall())
    conn.close()
    
    col_esq = [b.strip() for b in configs.get("col_esq", "").split(",") if b.strip()] if configs.get("col_esq") else padrao_esq
    col_dir = [b.strip() for b in configs.get("col_dir", "").split(",") if b.strip()] if configs.get("col_dir") else padrao_dir
    
    todos_blocos = [
        "contas", "cartoes", "paga_leve", "limites", "contas_pagar", "maiores_gastos", "turnos",
        "missao_ipva", "caixa_7dias", "projecao_mes", "capacidade_trabalho"
    ]
    col_esq = [b for b in col_esq if b in todos_blocos]
    col_dir = [b for b in col_dir if b in todos_blocos]
    
    presentes = set(col_esq + col_dir)
    novos_dir = {"caixa_7dias", "projecao_mes"}
    for b in todos_blocos:
        if b not in presentes:
            if b in novos_dir:
                col_dir.append(b)
            else:
                col_esq.append(b)
            
    visiveis = padrao_visiveis.copy()
    if "visiveis" in configs and configs["visiveis"]:
        import json
        try:
            visiveis.update(json.loads(configs["visiveis"]))
        except Exception:
            pass
            
    return col_esq, col_dir, visiveis

def salvar_layout_dashboard(col_esq: List[str], col_dir: List[str], visiveis: Dict[str, bool]):
    """Salva permanentemente o layout do dashboard no banco SQLite."""
    import json
    conn = conectar()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO config_dashboard (chave, valor) VALUES (?, ?)", ("col_esq", ",".join(col_esq)))
    cur.execute("INSERT OR REPLACE INTO config_dashboard (chave, valor) VALUES (?, ?)", ("col_dir", ",".join(col_dir)))
    cur.execute("INSERT OR REPLACE INTO config_dashboard (chave, valor) VALUES (?, ?)", ("visiveis", json.dumps(visiveis)))
    conn.commit()
    conn.close()

def mover_bloco(bloco_id: str, direcao: str):
    """Move um bloco de posição (subir, descer ou trocar coluna) e persiste imediatamente."""
    col_esq = list(st.session_state.get("blocos_col_esq", ["contas", "cartoes", "limites", "missao_ipva", "capacidade_trabalho"]))
    col_dir = list(st.session_state.get("blocos_col_dir", ["contas_pagar", "caixa_7dias", "projecao_mes", "maiores_gastos", "turnos"]))
    
    if bloco_id in col_esq:
        origem = col_esq
        destino = col_dir
    elif bloco_id in col_dir:
        origem = col_dir
        destino = col_esq
    else:
        return
        
    idx = origem.index(bloco_id)
    if direcao == "subir" and idx > 0:
        origem[idx], origem[idx - 1] = origem[idx - 1], origem[idx]
    elif direcao == "descer" and idx < len(origem) - 1:
        origem[idx], origem[idx + 1] = origem[idx + 1], origem[idx]
    elif direcao == "trocar_coluna":
        origem.remove(bloco_id)
        destino.append(bloco_id)
        
    st.session_state["blocos_col_esq"] = col_esq
    st.session_state["blocos_col_dir"] = col_dir
    salvar_layout_dashboard(col_esq, col_dir, st.session_state.get("blocos_visiveis", {}))
    st.rerun()

def restaurar_layout_padrao():
    """Restaura a distribuição padrão dos blocos."""
    padrao_esq = ["contas", "cartoes", "paga_leve", "limites", "missao_ipva", "capacidade_trabalho"]
    padrao_dir = ["contas_pagar", "caixa_7dias", "projecao_mes", "maiores_gastos", "turnos"]
    padrao_vis = {b: True for b in padrao_esq + padrao_dir}
    st.session_state["blocos_col_esq"] = padrao_esq
    st.session_state["blocos_col_dir"] = padrao_dir
    st.session_state["blocos_visiveis"] = padrao_vis
    salvar_layout_dashboard(padrao_esq, padrao_dir, padrao_vis)
    st.rerun()

def carregar_dividas_antigas_selecionadas() -> set:
    """Carrega os IDs de pendências antigas que o usuário selecionou para incluir na meta."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS config_dashboard (chave TEXT PRIMARY KEY, valor TEXT)")
    cur.execute("SELECT valor FROM config_dashboard WHERE chave = 'dividas_antigas_selecionadas'")
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        return set()
    try:
        return set(int(x.strip()) for x in row[0].split(",") if x.strip())
    except Exception:
        return set()

def salvar_dividas_antigas_selecionadas(ids_set: set) -> None:
    """Salva os IDs das pendências antigas selecionadas no SQLite sem alterar a tabela de transações."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS config_dashboard (chave TEXT PRIMARY KEY, valor TEXT)")
    val_str = ",".join(str(i) for i in sorted(list(ids_set)))
    cur.execute("INSERT OR REPLACE INTO config_dashboard (chave, valor) VALUES ('dividas_antigas_selecionadas', ?)", (val_str,))
    conn.commit()
    conn.close()

def carregar_dias_trabalho_planejados(padrao: int) -> int:
    """Carrega a quantidade de dias que o usuário planeja trabalhar no restante do mês."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS config_dashboard (chave TEXT PRIMARY KEY, valor TEXT)")
    cur.execute("SELECT valor FROM config_dashboard WHERE chave = 'dias_trabalho_planejados'")
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        return padrao
    try:
        return max(1, int(row[0]))
    except Exception:
        return padrao

def salvar_dias_trabalho_planejados(dias: int) -> None:
    """Salva a quantidade de dias de trabalho planejados no SQLite."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS config_dashboard (chave TEXT PRIMARY KEY, valor TEXT)")
    cur.execute("INSERT OR REPLACE INTO config_dashboard (chave, valor) VALUES ('dias_trabalho_planejados', ?)", (str(dias),))
    conn.commit()
    conn.close()

def alternar_status_pago(id_transacao: int, status_atual: int) -> None:
    """Alterna o status entre Pago (1) e Pendente (0)."""
    conn = conectar()
    novo_status = 0 if status_atual == 1 else 1
    conn.execute("UPDATE transacoes SET pago = ? WHERE id = ?", (novo_status, id_transacao))
    conn.commit()
    conn.close()

def excluir_transacao(id_transacao: int) -> None:
    """Remove uma transação pelo ID."""
    conn = conectar()
    conn.execute("DELETE FROM transacoes WHERE id = ?", (id_transacao,))
    conn.commit()
    conn.close()

def excluir_cartao(id_cartao: int) -> None:
    """Remove um cartão pelo ID."""
    conn = conectar()
    conn.execute("DELETE FROM cartoes WHERE id = ?", (id_cartao,))
    conn.commit()
    conn.close()

def excluir_turno(id_turno: int) -> None:
    """Remove um turno registrado pelo ID sem excluir movimentações bancárias legítimas."""
    conn = conectar()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE transacoes SET turno_id = NULL WHERE turno_id = ?", (id_turno,))
    except Exception:
        pass
    cur.execute("DELETE FROM turnos WHERE id = ?", (id_turno,))
    conn.commit()
    conn.close()

def excluir_despesa_veiculo(id_despesa: int) -> None:
    """Remove uma despesa de veículo pelo ID."""
    conn = conectar()
    conn.execute("DELETE FROM despesas_veiculo WHERE id = ?", (id_despesa,))
    conn.commit()
    conn.close()

def obter_contas_disponiveis() -> List[str]:
    """Retorna lista única de contas registradas."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT conta FROM transacoes WHERE conta IS NOT NULL AND conta != ''")
    contas_db = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT nome FROM contas_config")
    contas_cfg = [r[0] for r in cur.fetchall()]
    conn.close()
    contas_unificadas = list(dict.fromkeys(contas_cfg + contas_db))
    return contas_unificadas if contas_unificadas else ["Mercado Pago", "Dinheiro"]

def calcular_datas_recorrentes(data_base: date, periodicidade: str, qtd: int) -> List[date]:
    """
    Calcula datas de vencimento respeitando rigorosamente o calendário gregoriano:
    - 'Mensal': preserva o dia base do mês (ex: dia 31 vira 28/29 em Fev, 30 em Abr/Jun/Set/Nov).
    - 'Quinzenal': soma 14 dias a cada ciclo.
    - 'Semanal': soma 7 dias a cada ciclo.
    - 'Anual': soma 1 ano ajustando para ano bissexto se 29/02.
    """
    datas = []
    dia_base = data_base.day
    ano_base = data_base.year
    mes_base = data_base.month
    p_lower = str(periodicidade).strip().lower()

    for i in range(qtd):
        if p_lower in ("mensal", "mês", "mes"):
            novo_ano = ano_base + ((mes_base - 1 + i) // 12)
            novo_mes = ((mes_base - 1 + i) % 12) + 1
            max_dia = calendar.monthrange(novo_ano, novo_mes)[1]
            dia_efetivo = min(dia_base, max_dia)
            datas.append(date(novo_ano, novo_mes, dia_efetivo))
        elif p_lower in ("quinzenal", "quinzena"):
            datas.append(data_base + timedelta(days=14 * i))
        elif p_lower in ("semanal", "semana"):
            datas.append(data_base + timedelta(days=7 * i))
        elif p_lower in ("anual", "ano"):
            novo_ano = ano_base + i
            max_dia = calendar.monthrange(novo_ano, mes_base)[1]
            dia_efetivo = min(dia_base, max_dia)
            datas.append(date(novo_ano, mes_base, dia_efetivo))
        else:
            datas.append(data_base + timedelta(days=30 * i))
    return datas

def obter_estrutura_categorias() -> Dict[int, Dict[str, Any]]:
    """Carrega grupos e subcategorias ativos organizados na metodologia Cerbasi/Organizze."""
    conn = conectar()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT g.id as grupo_id, g.nome as grupo_nome, g.icone as grupo_icone, g.tipo as grupo_tipo,
                   s.id as sub_id, s.nome as sub_nome, s.icone as sub_icone, s.natureza_padrao, s.finalidade
            FROM grupos_categoria g
            LEFT JOIN subcategorias s ON s.grupo_id = g.id AND s.ativo = 1
            WHERE g.ativo = 1
            ORDER BY g.ordem ASC, s.ordem ASC
        """)
        rows = cur.fetchall()
    except Exception:
        rows = []
    conn.close()

    grupos = {}
    for r in rows:
        g_id, g_nome, g_ico, g_tipo, s_id, s_nome, s_ico, s_nat, s_fin = r
        if g_id not in grupos:
            grupos[g_id] = {
                "id": g_id,
                "nome": g_nome,
                "icone": g_ico or "📁",
                "tipo": g_tipo or "despesa",
                "subcategorias": []
            }
        if s_id:
            grupos[g_id]["subcategorias"].append({
                "id": s_id,
                "nome": s_nome,
                "icone": s_ico or "•",
                "natureza": s_nat or "variavel",
                "finalidade": s_fin or "familiar"
            })
    return grupos

def obter_categorias_disponiveis() -> List[str]:
    """Retorna lista de categorias para seleção nos formulários."""
    conn = conectar()
    cur = conn.cursor()
    try:
        cur.execute("SELECT nome FROM subcategorias WHERE ativo = 1 ORDER BY nome ASC")
        subs = [r[0] for r in cur.fetchall()]
    except Exception:
        subs = []
    conn.close()
    if subs:
        return subs
    cats = list(ICONES_CATEGORIA.keys())
    return sorted(list(set(cats)))


# =============================================================================
# 4. JANELAS POP-UP (st.dialog) - AÇÕES RÁPIDAS
# =============================================================================

@st.dialog("💳 Confirmar Pagamento", width="large")
def modal_registrar_pagamento(id_transacao: int):
    """Pop-up para registrar pagamento efetivo (integral ou parcial) com vínculo e controle de conciliação."""
    conn = conectar()
    resumo = saldo_service.obter_resumo_obrigacao(conn, id_transacao)
    contas_raw = saldo_service.obter_contas(conn)
    saldos_contas = {c["id"]: saldo_service.calcular_saldo_conta(conn, c["id"])["saldo_atual"] for c in contas_raw}
    conn.close()

    if not resumo:
        st.error("Obrigação não encontrada.")
        return

    st.markdown(f"### 📋 {resumo['descricao']}")
    col_inf1, col_inf2, col_inf3 = st.columns(3)
    col_inf1.metric("Valor Nominal", f"R$ {resumo['valor_original']:,.2f}")
    col_inf2.metric("Já Pago", f"R$ {resumo['total_pago']:,.2f}")
    col_inf3.metric("Saldo Devedor", f"R$ {resumo['saldo_devedor']:,.2f}")

    data_venc_br = datetime.strptime(resumo['data_vencimento'], "%Y-%m-%d").strftime("%d/%m/%Y")
    st.caption(f"🗓️ Vencimento Original: **{data_venc_br}** (será preservado)")

    # Monta opções de contas com visualização de saldo disponível
    mapa_contas = {}
    lista_nomes_contas = []
    idx_padrao = 0
    for i, c in enumerate(contas_raw):
        s_val = saldos_contas.get(c["id"], Decimal("0.00"))
        rotulo = f"{c['nome']} (Saldo disp: R$ {s_val:,.2f})"
        mapa_contas[rotulo] = c
        lista_nomes_contas.append(rotulo)
        if c["id"] == resumo.get("conta_id"):
            idx_padrao = i

    with st.form(f"form_pagar_{id_transacao}"):
        st.markdown("##### 💵 Detalhes do Pagamento")
        c1, c2 = st.columns(2)
        tipo_quitar = c1.radio(
            "Tipo de Pagamento",
            ["Quitar Valor Restante", "Pagamento Parcial", "Outro Valor"],
            index=0,
            horizontal=True
        )
        
        valor_restante_flt = float(resumo["saldo_devedor"])
        if tipo_quitar == "Quitar Valor Restante":
            val_pago = c2.number_input("Valor a Pagar (R$)", value=valor_restante_flt, disabled=True)
            val_pago_real = valor_restante_flt
        elif tipo_quitar == "Pagamento Parcial":
            val_pago_real = c2.number_input("Valor a Pagar (R$)", min_value=0.01, max_value=max(0.01, valor_restante_flt), value=min(50.0, max(0.01, valor_restante_flt)), step=5.0)
        else:
            val_pago_real = c2.number_input("Valor a Pagar (R$)", min_value=0.01, value=valor_restante_flt, step=5.0)

        # Condição 13: Regime de ajuste para evitar pagamentos que ultrapassem o saldo devedor sem registro explícito
        tipo_regime = st.selectbox(
            "Regime de Ajuste do Valor (Condição 13)",
            [
                "Normal (sem juros nem abatimento)",
                "Com Juros / Encargos de atraso (valor pago maior que o nominal)",
                "Com Desconto / Abatimento concedido",
                "Renegociação / Acordo de quitação"
            ]
        )

        c3, c4 = st.columns(2)
        data_pag = c3.date_input("Data Efetiva do Pagamento", date.today())
        conta_sel_rotulo = c4.selectbox("Conta Realmente Utilizada (Condição 10)", lista_nomes_contas, index=idx_padrao)
        conta_obj = mapa_contas[conta_sel_rotulo]
        saldo_conta_sel = saldos_contas.get(conta_obj["id"], Decimal("0.00"))

        data_pag_str = data_pag.strftime("%Y-%m-%d")
        marco_data = "2026-10-19"
        
        considerado_no_marco = 0
        if data_pag_str == marco_data:
            st.info("⚠️ **Pagamento na Data do Marco Inicial (19/10/2026):**")
            momento_sel = st.radio(
                "Em que momento este pagamento ocorreu?",
                [
                    "Depois das 17h03 (debitar do saldo atual)",
                    "Antes das 17h03 (já estava embutido no saldo inicial reconciliado)"
                ],
                index=0
            )
            if "Antes" in momento_sel:
                considerado_no_marco = 1
        elif data_pag_str < marco_data:
            st.info("💡 **Pagamento Retroativo:** Como este pagamento ocorreu antes do marco de 19/10, a obrigação será quitada, mas o saldo atual não será debitado novamente pois já integrava o saldo inicial reconciliado.")
            considerado_no_marco = 1
        else:
            st.caption("ℹ️ Este pagamento debita a conta selecionada na data informada.")

        # Condição 11: Avisar se o pagamento for maior que o saldo disponível sem alterar a conta
        if val_pago_real > float(saldo_conta_sel) and considerado_no_marco == 0:
            st.warning(
                f"⚠️ **Atenção (Saldo Insuficiente):** O valor a pagar (R$ {val_pago_real:,.2f}) é maior que o saldo disponível na conta **{conta_obj['nome']}** (R$ {saldo_conta_sel:,.2f}). "
                f"A conta permanecerá selecionada conforme sua instrução, mas o saldo bancário ficará negativo em R$ {float(saldo_conta_sel) - val_pago_real:,.2f}."
            )

        c5, c6 = st.columns(2)
        forma_pag = c5.selectbox("Forma de Pagamento", ["Pix", "Débito em Conta", "Dinheiro Físico", "Boleto", "Outro"])
        obs_pag = c6.text_input("Observação / Comprovante", placeholder="Ex: Pago via app no almoço")

        st.divider()
        if st.form_submit_button("✅ Confirmar Pagamento", use_container_width=True, type="primary"):
            if val_pago_real <= 0:
                st.error("O valor pago deve ser maior que zero.")
                return

            # Validação Condição 13: evitar ultrapassar o saldo devedor sem declaração explícita
            valor_encargos = 0.0
            valor_desconto = 0.0
            tipo_ajuste_db = "normal"

            if "Normal" in tipo_regime:
                if val_pago_real > valor_restante_flt + 0.001:
                    st.error(
                        f"❌ O valor informado (R$ {val_pago_real:,.2f}) ultrapassa o saldo devedor restante (R$ {valor_restante_flt:,.2f}). "
                        f"Para registrar valor excedente, selecione 'Com Juros / Encargos' ou 'Renegociação / Acordo'."
                    )
                    return
            elif "Juros" in tipo_regime:
                tipo_ajuste_db = "com_juros"
                valor_encargos = max(0.0, val_pago_real - valor_restante_flt)
            elif "Desconto" in tipo_regime:
                tipo_ajuste_db = "com_desconto"
                valor_desconto = max(0.0, valor_restante_flt - val_pago_real)
            elif "Acordo" in tipo_regime:
                tipo_ajuste_db = "acordo"

            conn = conectar()
            try:
                saldo_service.registrar_pagamento(
                    conn=conn,
                    transacao_id=id_transacao,
                    data_pagamento=data_pag_str,
                    valor_pago=val_pago_real,
                    conta_id=conta_obj["id"],
                    afeta_saldo_bancario=1,
                    considerado_no_marco=considerado_no_marco,
                    forma_pagamento=forma_pag,
                    observacao=obs_pag,
                    tipo_ajuste_valor=tipo_ajuste_db,
                    valor_encargos=valor_encargos,
                    valor_desconto=valor_desconto
                )
                conn.close()
                st.success("Pagamento registrado com sucesso!")
                st.rerun()
            except Exception as e:
                conn.close()
                st.error(f"Erro ao registrar pagamento: {e}")


@st.dialog("🔄 Histórico & Estorno de Pagamentos", width="large")
def modal_historico_pagamento(id_transacao: int):
    """Pop-up para visualização dos pagamentos realizados e estorno seguro com rastreabilidade."""
    conn = conectar()
    resumo = saldo_service.obter_resumo_obrigacao(conn, id_transacao)
    pags = resumo.get("pagamentos", [])
    conn.close()

    st.markdown(f"### 📋 {resumo['descricao']}")
    st.caption(f"Valor Original: **R$ {resumo['valor_original']:,.2f}** | Total Pago: **R$ {resumo['total_pago']:,.2f}** | Saldo Restante: **R$ {resumo['saldo_devedor']:,.2f}**")

    if not pags:
        st.info("Esta conta possui status marcado como pago legado (sem pagamentos detalhados registrados).")
        if st.button("🔄 Desfazer Quitação e Retornar para Pendente", type="secondary", use_container_width=True):
            conn = conectar()
            conn.execute("UPDATE transacoes SET pago = 0, status_pagamento = 'pendente' WHERE id = ?", (id_transacao,))
            conn.commit()
            conn.close()
            st.success("Obrigação retornada para pendente.")
            st.rerun()
        return

    st.markdown("##### Histórico de Pagamentos:")
    for p in pags:
        p_id = p["id"]
        # Condição 5: Tratamento seguro de pagamentos com data desconhecida pré-marco
        if p["data_pagamento"]:
            try:
                dt_p_br = datetime.strptime(p["data_pagamento"], "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                dt_p_br = str(p["data_pagamento"])
        else:
            dt_p_br = "Histórico pré-marco"
        
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2.5, 1.8, 1.8, 1.5], vertical_alignment="center")
            with c1:
                st.markdown(f"🗓️ **{dt_p_br}** • 🏦 {p['conta_nome']}")
                if p.get("data_real_desconhecida"):
                    st.caption("*(Pagamento histórico já contemplado no saldo conciliado em 19/10/2026)*")
                elif p["observacao"]:
                    st.caption(f"📝 {p['observacao']}")
                else:
                    st.caption(f"Forma: {p['forma_pagamento']}")
                
                if p.get("tipo_ajuste_valor") and p["tipo_ajuste_valor"] != "normal":
                    st.caption(f"⚖️ Ajuste: {p['tipo_ajuste_valor']} (Encargos: R$ {p.get('valor_encargos', 0):,.2f})")
            with c2:
                st.markdown(f"**R$ {p['valor_pago']:,.2f}**")
                if p["considerado_no_marco"]:
                    st.caption("*(Refletido no marco)*")
            with c3:
                if p["cancelado"]:
                    st.markdown(":red[**CANCELADO / ESTORNADO**]")
                    st.caption(f"Motivo: {p['motivo_cancelamento'] or 'Sem motivo'}")
                else:
                    st.markdown(":green[**Ativo / Efetivado**]")
            with c4:
                if not p["cancelado"]:
                    if st.button("↩️ Estornar", key=f"btn_estornar_{p_id}", help="Estornar este pagamento com rastreabilidade"):
                        st.session_state[f"confirm_estorno_{p_id}"] = True

            if st.session_state.get(f"confirm_estorno_{p_id}"):
                with st.form(f"form_estornar_{p_id}"):
                    motivo_est = st.text_input("Motivo do estorno", placeholder="Ex: Pagamento duplicado, erro no valor...")
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.form_submit_button("Confirmar Estorno", type="primary"):
                        conn = conectar()
                        saldo_service.estornar_pagamento(conn, p_id, motivo=motivo_est or "Estorno pelo usuário")
                        conn.close()
                        st.session_state[f"confirm_estorno_{p_id}"] = False
                        st.success("Pagamento estornado com sucesso!")
                        st.rerun()
                    if c_btn2.form_submit_button("Cancelar"):
                        st.session_state[f"confirm_estorno_{p_id}"] = False
                        st.rerun()

    if resumo["saldo_devedor"] > 0:
        st.divider()
        if st.button("➕ Registrar Pagamento Complementar", use_container_width=True, type="primary"):
            modal_registrar_pagamento(id_transacao)

@st.dialog("➕ Nova Despesa", width="large")
def modal_nova_despesa():
    """Janela pop-up para cadastrar despesas nas modalidades Única, Parcelada ou Fixa/Recorrente."""
    st.caption("Cadastre despesas avulsas, parcelamentos com prévia ou despesas fixas recorrentes com calendário mensal exato.")

    modalidade = st.segmented_control(
        "Modalidade da Despesa",
        options=["🏷️ Única", "💳 Parcelada", "🔄 Fixa / Recorrente"],
        default="🏷️ Única",
        label_visibility="collapsed"
    )

    contas = obter_contas_disponiveis()
    estrutura_cats = obter_estrutura_categorias()
    
    # Monta opções de grupos
    nomes_grupos = [f"{g['icone']} {g['nome']}" for g in estrutura_cats.values() if g['tipo'] == 'despesa']
    if not nomes_grupos:
        nomes_grupos = ["🏠 Habitação", "🍽️ Alimentação", "❤️ Saúde", "🚕 Chaves Transportes", "Outros"]

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        grupo_escolhido_rotulo = st.selectbox("Grupo Principal (Cerbasi)", nomes_grupos, index=0)
    
    # Identifica o grupo selecionado
    g_obj = None
    for g in estrutura_cats.values():
        if f"{g['icone']} {g['nome']}" == grupo_escolhido_rotulo:
            g_obj = g
            break
            
    # Subcategorias do grupo
    subs_do_grupo = g_obj["subcategorias"] if g_obj and g_obj["subcategorias"] else []
    nomes_subs = [f"{s['icone']} {s['nome']}" for s in subs_do_grupo] if subs_do_grupo else ["Geral"]

    with col_g2:
        sub_escolhida_rotulo = st.selectbox("Subcategoria", nomes_subs, index=0)
        
    sub_obj = None
    if subs_do_grupo:
        for s in subs_do_grupo:
            if f"{s['icone']} {s['nome']}" == sub_escolhida_rotulo:
                sub_obj = s
                break
                
    cat_texto_final = sub_obj["nome"] if sub_obj else (g_obj["nome"] if g_obj else "Outros")
    grupo_id_final = g_obj["id"] if g_obj else None
    subcat_id_final = sub_obj["id"] if sub_obj else None
    natureza_final = sub_obj["natureza"] if sub_obj else "variavel"

    st.write("")

    if modalidade == "🏷️ Única":
        with st.form("form_despesa_unica"):
            c1, c2 = st.columns([2, 1])
            desc = c1.text_input("Descrição", placeholder="Ex: Farmácia Raia, Conta de Luz...")
            valor = c2.number_input("Valor (R$)", min_value=0.01, value=50.0, step=5.0)

            c3, c4 = st.columns(2)
            conta = c3.selectbox("Conta / Cartão de Origem", contas, index=0)
            data_venc = c4.date_input("Data de Vencimento", date.today())

            c5, c6 = st.columns(2)
            esta_pago = c5.checkbox("Já está pago? (Confirmar débito imediato)", value=False)
            forma_pag = c6.selectbox("Forma de Pagamento", ["Pix", "Débito em Conta", "Dinheiro", "Boleto", "Outro"], disabled=not esta_pago)

            afeta_saldo = st.checkbox("Debitar do saldo bancário?", value=True, help="Desmarque para despesas descontadas em folha ou sem impacto em contas")

            st.divider()
            if st.form_submit_button("💾 Salvar Despesa Única", use_container_width=True, type="primary"):
                if not desc.strip():
                    st.error("Por favor, informe a descrição da despesa.")
                    return
                conn = conectar()
                cur = conn.cursor()
                cur.execute("SELECT id FROM contas_config WHERE nome = ?", (conta,))
                c_row = cur.fetchone()
                c_id = c_row[0] if c_row else 1

                data_str = data_venc.strftime("%Y-%m-%d")
                cur.execute("""
                    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, grupo_id, subcategoria_id, natureza_gasto)
                    VALUES (?, ?, ?, 'despesa', ?, ?, ?, ?, ?, ?, ?, ?)
                """, (data_str, desc.strip(), valor, cat_texto_final, conta, c_id, 1 if esta_pago else 0, 1 if afeta_saldo else 0, grupo_id_final, subcat_id_final, natureza_final))
                novo_id = cur.lastrowid

                if esta_pago and afeta_saldo:
                    saldo_service.registrar_pagamento(
                        conn=conn,
                        transacao_id=novo_id,
                        data_pagamento=data_str,
                        valor_pago=valor,
                        conta_id=c_id,
                        afeta_saldo_bancario=1,
                        forma_pagamento=forma_pag,
                        observacao="Pago no ato do cadastro"
                    )

                conn.commit()
                conn.close()
                st.success("Despesa adicionada com sucesso!")
                st.rerun()

    elif modalidade == "💳 Parcelada":
        c1, c2 = st.columns([2, 1])
        desc = c1.text_input("Descrição da Compra Parcelada", placeholder="Ex: Manutenção Veículo Oficina, Eletrodoméstico...", key="parc_desc")
        valor_total = c2.number_input("Valor Total da Compra (R$)", min_value=0.01, value=300.0, step=20.0, key="parc_val_tot")

        c3, c4, c5 = st.columns([1, 1, 1.2])
        num_parcelas = c3.number_input("Nº de Parcelas", min_value=2, max_value=48, value=3, step=1, key="parc_num")
        periodicidade = c4.selectbox("Periodicidade", ["Mensal", "Quinzenal", "Semanal"], index=0, key="parc_period")
        conta = c5.selectbox("Conta / Cartão de Origem", contas, index=0, key="parc_conta")

        c6, c7 = st.columns(2)
        data_pri = c6.date_input("Data da 1ª Parcela", date.today(), key="parc_dt_pri")
        primeira_paga = c7.checkbox("⚠️ Marcar 1ª parcela como já paga agora?", value=False, key="parc_pri_paga", help="Exige confirmação explícita. Marque apenas se a entrada ou 1ª parcela já foi quitada hoje.")

        # Prévia das parcelas
        datas_previa = calcular_datas_recorrentes(data_pri, periodicidade, int(num_parcelas))
        val_parc_base = round(valor_total / num_parcelas, 2)
        dif_centavos = round(valor_total - (val_parc_base * num_parcelas), 2)

        st.markdown("##### 🔍 Prévia das Parcelas Calculadas:")
        dados_previa = []
        for i, dt in enumerate(datas_previa):
            v_efetivo = val_parc_base + (dif_centavos if i == 0 else 0.0)
            st_parc = "✅ Paga no ato" if (i == 0 and primeira_paga) else "⏳ Pendente"
            dados_previa.append({
                "Parcela": f"{i+1}/{num_parcelas}",
                "Vencimento": dt.strftime("%d/%m/%Y"),
                "Valor": formatar_moeda_br(v_efetivo),
                "Status": st_parc
            })
        st.dataframe(pd.DataFrame(dados_previa), use_container_width=True, hide_index=True)

        if st.button("💾 Salvar Compra Parcelada", use_container_width=True, type="primary", key="btn_salvar_parc"):
            if not desc.strip():
                st.error("Por favor, informe a descrição da compra parcelada.")
            else:
                conn = conectar()
                cur = conn.cursor()
                cur.execute("SELECT id FROM contas_config WHERE nome = ?", (conta,))
                c_row = cur.fetchone()
                c_id = c_row[0] if c_row else 1

                grp_id = f"parc_{uuid.uuid4().hex[:8]}"

                for i, dt in enumerate(datas_previa):
                    v_efetivo = val_parc_base + (dif_centavos if i == 0 else 0.0)
                    esta_p = (i == 0 and primeira_paga)
                    dt_str = dt.strftime("%Y-%m-%d")

                    cur.execute("""
                        INSERT INTO transacoes (
                            data, descricao, valor, tipo, categoria, conta, conta_id, pago,
                            status_pagamento, afeta_saldo_bancario, grupo_parcelamento,
                            numero_parcela, total_parcelas_compra, grupo_id, subcategoria_id, natureza_gasto
                        ) VALUES (?, ?, ?, 'despesa', ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                    """, (
                        dt_str,
                        f"{desc.strip()} ({i+1}/{num_parcelas})",
                        v_efetivo,
                        cat_texto_final,
                        conta,
                        c_id,
                        1 if esta_p else 0,
                        "pago" if esta_p else "pendente",
                        grp_id,
                        i + 1,
                        int(num_parcelas),
                        grupo_id_final,
                        subcat_id_final,
                        natureza_final
                    ))
                    t_id_novo = cur.lastrowid

                    if esta_p:
                        saldo_service.registrar_pagamento(
                            conn=conn,
                            transacao_id=t_id_novo,
                            data_pagamento=dt_str,
                            valor_pago=v_efetivo,
                            conta_id=c_id,
                            afeta_saldo_bancario=1,
                            forma_pagamento="Débito",
                            observacao="1ª parcela paga no ato do cadastro"
                        )

                conn.commit()
                conn.close()
                st.success(f"Compra parcelada em {num_parcelas}x cadastrada com sucesso!")
                st.rerun()

    elif modalidade == "🔄 Fixa / Recorrente":
        c1, c2 = st.columns([2, 1])
        desc = c1.text_input("Descrição do Gasto Fixo", placeholder="Ex: Internet Residencial, Seguro Auto, Mensalidade...", key="fixa_desc")
        valor_rec = c2.number_input("Valor por Ciclo (R$)", min_value=0.01, value=120.0, step=10.0, key="fixa_val")

        c3, c4, c5 = st.columns([1.2, 1.2, 1])
        periodicidade = c3.selectbox("Periodicidade", ["Mensal", "Semanal", "Anual"], index=0, key="fixa_period")
        conta = c4.selectbox("Conta de Débito", contas, index=0, key="fixa_conta")
        qtd_meses = c5.number_input("Projetar Ocorrências", min_value=1, max_value=24, value=12, step=1, key="fixa_qtd", help="Evita criar infinitas transações no banco. Padrão: 12 meses.")

        c6, c7 = st.columns(2)
        proximo_venc = c6.date_input("Próximo Vencimento", date.today(), key="fixa_dt_prox")
        pri_paga = c7.checkbox("Marcar próximo vencimento como já pago hoje?", value=False, key="fixa_pri_paga")

        # Prévia das datas respeitando o dia base e dias de meses mais curtos
        datas_fixa = calcular_datas_recorrentes(proximo_venc, periodicidade, int(qtd_meses))

        st.markdown(f"##### 🔍 Prévia das {qtd_meses} Ocorrências Projetadas (Dia {proximo_venc.day} fixado):")
        dados_fixa_previa = []
        for i, dt in enumerate(datas_fixa):
            st_f = "✅ Paga hoje" if (i == 0 and pri_paga) else "⏳ Agendada"
            dados_fixa_previa.append({
                "Nº": f"{i+1}/{qtd_meses}",
                "Vencimento": dt.strftime("%d/%m/%Y"),
                "Valor": formatar_moeda_br(valor_rec),
                "Status": st_f
            })
        st.dataframe(pd.DataFrame(dados_fixa_previa), use_container_width=True, hide_index=True)

        if st.button("💾 Salvar Despesa Fixa / Recorrente", use_container_width=True, type="primary", key="btn_salvar_fixa"):
            if not desc.strip():
                st.error("Por favor, informe a descrição da despesa fixa.")
            else:
                conn = conectar()
                cur = conn.cursor()
                cur.execute("SELECT id FROM contas_config WHERE nome = ?", (conta,))
                c_row = cur.fetchone()
                c_id = c_row[0] if c_row else 1

                grp_fixa = f"fixa_{uuid.uuid4().hex[:8]}"

                for i, dt in enumerate(datas_fixa):
                    esta_p = (i == 0 and pri_paga)
                    dt_str = dt.strftime("%Y-%m-%d")

                    cur.execute("""
                        INSERT INTO transacoes (
                            data, descricao, valor, tipo, categoria, conta, conta_id, pago,
                            status_pagamento, afeta_saldo_bancario, grupo_parcelamento,
                            numero_parcela, total_parcelas_compra, status_rateio,
                            grupo_id, subcategoria_id, natureza_gasto
                        ) VALUES (?, ?, ?, 'despesa', ?, ?, ?, ?, ?, 1, ?, ?, ?, 'fixa_recorrente', ?, ?, ?)
                    """, (
                        dt_str,
                        desc.strip(),
                        valor_rec,
                        cat_texto_final,
                        conta,
                        c_id,
                        1 if esta_p else 0,
                        "pago" if esta_p else "pendente",
                        grp_fixa,
                        i + 1,
                        int(qtd_meses),
                        grupo_id_final,
                        subcat_id_final,
                        "fixa"
                    ))
                    t_id_novo = cur.lastrowid

                    if esta_p:
                        saldo_service.registrar_pagamento(
                            conn=conn,
                            transacao_id=t_id_novo,
                            data_pagamento=dt_str,
                            valor_pago=valor_rec,
                            conta_id=c_id,
                            afeta_saldo_bancario=1,
                            forma_pagamento="Débito",
                            observacao="Ocorrência inicial paga no ato do cadastro"
                        )

                conn.commit()
                conn.close()
                st.success(f"Despesa fixa '{desc}' agendada para os próximos {qtd_meses} ciclos com sucesso!")
                st.rerun()

@st.dialog("💰 Nova Entrada / Receita", width="large")
def modal_nova_receita():
    """Janela pop-up para cadastrar receitas, salários ou entradas extraordinárias."""
    st.markdown("Registre novos proventos, salários ou rendimentos.")
    contas = obter_contas_disponiveis()
    categorias = obter_categorias_disponiveis()
    
    with st.form("form_modal_receita", clear_on_submit=True):
        col1, col2 = st.columns([2, 1])
        desc = col1.text_input("Descrição", placeholder="Ex: Salário, Venda de item, Reembolso...")
        valor = col2.number_input("Valor Recebido (R$)", min_value=0.01, value=500.0, step=50.0)
        
        col3, col4 = st.columns(2)
        cat = col3.selectbox("Categoria", categorias, index=categorias.index("Salário Fernanda") if "Salário Fernanda" in categorias else 0)
        conta = col4.selectbox("Conta Destino", contas, index=0)
        
        col5, col6 = st.columns(2)
        data_rec = col5.date_input("Data de Recebimento", date.today())
        esta_pago = col6.checkbox("Já foi creditado na conta?", value=True)
        incluso_ajuste = col6.checkbox("Já contemplado no saldo se for data de ajuste?", value=False)
        
        st.divider()
        if st.form_submit_button("💾 Salvar Entrada", use_container_width=True, type="primary"):
            if not desc.strip():
                st.error("Por favor, informe a descrição da receita.")
                return
            conn = conectar()
            cur = conn.cursor()
            cur.execute("SELECT id FROM contas_config WHERE nome = ?", (conta,))
            c_row = cur.fetchone()
            c_id = c_row[0] if c_row else None

            data_str = data_rec.strftime("%Y-%m-%d")
            cur.execute("""
                INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario)
                VALUES (?, ?, ?, 'receita', ?, ?, ?, ?, 1)
            """, (data_str, desc.strip(), valor, cat, conta, c_id, 1 if esta_pago else 0))
            novo_id = cur.lastrowid

            if c_id and incluso_ajuste:
                ajuste_ativo = saldo_service.obter_ajuste_ativo(conn, c_id, data_limite=data_str)
                if ajuste_ativo and ajuste_ativo["data"] == data_str:
                    cur.execute("SELECT transacoes_contempladas_ids FROM ajustes_saldo WHERE id = ?", (ajuste_ativo["id"],))
                    raw_ids = cur.fetchone()[0]
                    ids_list = json.loads(raw_ids or '[]')
                    if novo_id not in ids_list:
                        ids_list.append(novo_id)
                        cur.execute("UPDATE ajustes_saldo SET transacoes_contempladas_ids = ? WHERE id = ?", (json.dumps(ids_list), ajuste_ativo["id"]))

            conn.commit()
            conn.close()
            st.success("Receita registrada com sucesso!")
            st.rerun()

@st.dialog("🚕 Registrar Turno (99 / Uber)", width="large")
def modal_novo_turno():
    """Janela pop-up para lançamento operacional do dia de corridas com período e horários."""
    st.markdown("Lance o resumo operacional do turno trabalhado. Os dados alimentam a inteligência de rentabilidade e produtividade.")
    st.info("💡 **Desacoplamento Financeiro:** Cadastrar um turno atualiza seus indicadores de produtividade (km, horas, R$/h, R$/km) e **nunca** cria movimentação bancária automática se o dinheiro já estiver refletido nas suas contas. Use a seção opcional abaixo apenas se houve nova entrada bancária efetiva.")
    contas = obter_contas_disponiveis()
    
    with st.form("form_modal_turno", clear_on_submit=True):
        st.markdown("##### 📊 1. Dados Operacionais do Turno")
        c1, c2, c3 = st.columns(3)
        data_t = c1.date_input("Data do Turno", date.today())
        horas_t = c2.number_input("Horas Trabalhadas", min_value=0.0, max_value=24.0, value=0.0, step=0.5, help="Tempo total trabalhado no turno")
        km_t = c3.number_input("KM Rodados no Dia", min_value=0.0, value=0.0, step=1.0, help="Quilometragem percorrida")
        
        c4, c5, c6 = st.columns(3)
        plataforma_t = c4.selectbox("Plataforma Principal", ["99", "Uber", "99 + Uber", "Outra"], index=0)
        bruto_t = c5.number_input("Ganho Bruto do App (R$)", min_value=0.0, value=0.0, step=5.0, help="Faturamento bruto apurado nos aplicativos")
        comb_estimado = c6.number_input("Combustível Consumido (R$)", min_value=0.0, value=0.0, step=5.0, help="Estimativa de consumo para cálculo do lucro operacional. NÃO debita do banco.")
        
        c7, c8 = st.columns(2)
        periodo_t = c7.selectbox(
            "Período Principal do Turno",
            ["Manhã (06h às 12h)", "Tarde (12h às 18h)", "Noite (18h às 00h)", "Madrugada (00h às 06h)", "Integral / Misto"],
            index=0
        )
        obs_t = c8.text_input("Observações", placeholder="Ex: Segunda-feira pós semana da criança, chuva...")
        
        st.divider()
        st.markdown("##### 🏦 2. Movimentação Financeira Bancária (Opcional)")
        st.caption("Marque apenas se este dinheiro acabou de entrar na sua conta/carteira e NÃO fazia parte do seu saldo anterior.")
        
        col_fin1, col_fin2 = st.columns(2)
        gerar_entrada_banco = col_fin1.checkbox("Creditar repasse em Conta Bancária?", value=False, help="Cria uma receita real vinculada ao turno na conta selecionada")
        gerar_dinheiro_mao = col_fin2.checkbox("Recebeu dinheiro físico em mãos?", value=False, help="Cria uma receita na Carteira física")
        
        valor_banco = 0.0
        conta_dest = contas[0] if contas else "Mercado Pago"
        if gerar_entrada_banco:
            cb1, cb2 = st.columns(2)
            conta_dest = cb1.selectbox("Conta de Crédito", contas, index=0)
            valor_banco = cb2.number_input("Valor Transferido para o Banco (R$)", min_value=0.0, value=0.0, step=5.0)
            
        valor_mao = 0.0
        if gerar_dinheiro_mao:
            valor_mao = st.number_input("Valor em Dinheiro Físico (R$)", min_value=0.0, value=0.0, step=5.0)
            
        st.divider()
        if st.form_submit_button("💾 Salvar Turno Operacional", use_container_width=True, type="primary"):
            if horas_t <= 0 and bruto_t <= 0 and km_t <= 0:
                st.warning("Preencha ao menos as horas, km ou ganho bruto para registrar o turno.")
                return
                
            data_iso = data_t.strftime("%Y-%m-%d")
            conn = conectar()
            cur = conn.cursor()
            
            # 1. Registra o turno com os dados operacionais desacoplados
            cur.execute("""
                INSERT INTO turnos (data, horas, km, ganho_bruto, combustivel, observacao, periodo, plataforma, valor_transferido_banco, dinheiro_fisico_recebido, status_conciliacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (data_iso, horas_t, km_t, bruto_t, comb_estimado, obs_t, periodo_t, plataforma_t, valor_banco, valor_mao, 'conciliado'))
            turno_id = cur.lastrowid
            
            # 2. SE e somente SE o usuário solicitou entrada bancária:
            if gerar_entrada_banco and valor_banco > 0:
                cur.execute("SELECT id FROM contas_config WHERE nome = ?", (conta_dest,))
                c_row = cur.fetchone()
                c_id = c_row[0] if c_row else None
                cur.execute("""
                    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
                    VALUES (?, ?, ?, 'receita', 'Renda Corridas (99/Uber)', ?, ?, 1, 1, ?)
                """, (data_iso, f"Repasse {plataforma_t} (Turno #{turno_id})", valor_banco, conta_dest, c_id, turno_id))
                
            # 3. SE o usuário solicitou dinheiro em mãos:
            if gerar_dinheiro_mao and valor_mao > 0:
                cur.execute("SELECT id FROM contas_config WHERE nome LIKE '%Dinheiro%' OR nome LIKE '%Carteira%'")
                cart_row = cur.fetchone()
                cart_id = cart_row[0] if cart_row else 2
                cur.execute("""
                    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
                    VALUES (?, ?, ?, 'receita', 'Renda Corridas (99/Uber)', 'Dinheiro / Carteira', ?, 1, 1, ?)
                """, (data_iso, f"Dinheiro Passageiro (Turno #{turno_id})", valor_mao, cart_id, turno_id))
                
            conn.commit()
            conn.close()
            st.success("Turno salvo com sucesso!")
            st.rerun()

@st.dialog("✏️ Editar Turno Operacional", width="large")
def modal_editar_turno(id_turno: int):
    """Permite editar os dados operacionais de um turno sem excluir movimentações bancárias existentes."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM turnos WHERE id = ?", (id_turno,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        st.error("Turno não encontrado.")
        return
        
    t_dict = dict(row)
    data_orig = datetime.strptime(t_dict["data"], "%Y-%m-%d").date() if isinstance(t_dict["data"], str) else t_dict["data"]
    
    with st.form("form_modal_edit_turno"):
        st.markdown(f"**Turno ID #{id_turno}** • Edição de Métricas Operacionais")
        c1, c2, c3 = st.columns(3)
        data_t = c1.date_input("Data do Turno", value=data_orig)
        horas_t = c2.number_input("Horas Trabalhadas", min_value=0.0, max_value=24.0, value=float(t_dict.get("horas") or 0.0), step=0.5)
        km_t = c3.number_input("KM Rodados", min_value=0.0, value=float(t_dict.get("km") or 0.0), step=1.0)
        
        c4, c5, c6 = st.columns(3)
        opcoes_plat = ["99", "Uber", "99 + Uber", "Outra"]
        p_val = t_dict.get("plataforma", "99")
        plat_idx = opcoes_plat.index(p_val) if p_val in opcoes_plat else 0
        plataforma_t = c4.selectbox("Plataforma", opcoes_plat, index=plat_idx)
        bruto_t = c5.number_input("Ganho Bruto (R$)", min_value=0.0, value=float(t_dict.get("ganho_bruto") or 0.0), step=5.0)
        comb_t = c6.number_input("Combustível Consumido (R$)", min_value=0.0, value=float(t_dict.get("combustivel") or 0.0), step=5.0, help="Métrica operacional de custo. Não altera lançamentos bancários.")
        
        per_lista = ["Manhã (06h às 12h)", "Tarde (12h às 18h)", "Noite (18h às 00h)", "Madrugada (00h às 06h)", "Integral / Misto"]
        p_per = t_dict.get("periodo", "Noite")
        per_idx = per_lista.index(p_per) if p_per in per_lista else 0
        periodo_t = st.selectbox("Período Principal", per_lista, index=per_idx)
        obs_t = st.text_input("Observações", value=str(t_dict.get("observacao") or ""))
        
        st.caption("ℹ️ A alteração deste turno atualiza os indicadores operacionais sem alterar ou apagar lançamentos financeiros.")
        
        if st.form_submit_button("💾 Salvar Alterações", use_container_width=True, type="primary"):
            data_iso = data_t.strftime("%Y-%m-%d")
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                UPDATE turnos
                SET data = ?, horas = ?, km = ?, ganho_bruto = ?, combustivel = ?, observacao = ?, periodo = ?, plataforma = ?
                WHERE id = ?
            """, (data_iso, horas_t, km_t, bruto_t, comb_t, obs_t, periodo_t, plataforma_t, id_turno))
            conn.commit()
            conn.close()
            st.success("Turno atualizado com sucesso!")
            st.rerun()

@st.dialog("🔧 Nova Despesa / Manutenção do Carro", width="large")
def modal_despesa_veiculo():
    """Pop-up para registrar manutenções, peças, seguro e documentos do veículo de trabalho."""
    st.markdown("Registre manutenções preventivas, corretivas ou taxas do veículo de trabalho.")
    contas = obter_contas_disponiveis()
    tipos_despesa = [
        "Troca de Óleo e Filtros",
        "Pneus e Alinhamento",
        "Freios e Suspensão",
        "Mecânica Geral",
        "Lavagem e Higienização",
        "Seguro do Carro",
        "IPVA / Licenciamento",
        "Alimentação no Turno",
        "Outros Gastos Operacionais"
    ]

    with st.form("form_despesa_carro", clear_on_submit=True):
        c1, c2 = st.columns([2, 1])
        desc = c1.text_input("Descrição do Serviço / Compra", placeholder="Ex: Troca de pastilhas de freio + fluido")
        valor = c2.number_input("Valor Pago (R$)", min_value=1.0, value=150.0, step=10.0)

        c3, c4 = st.columns(2)
        tipo = c3.selectbox("Tipo de Despesa", tipos_despesa)
        conta = c4.selectbox("Conta / Cartão Usado", contas, index=0)

        c5, c6 = st.columns(2)
        km_atual = c5.number_input("KM Atual do Carro (opcional)", min_value=0.0, value=85000.0, step=500.0)
        proxima_km = c6.number_input("Próxima Manutenção aos (KM opcional)", min_value=0.0, value=95000.0, step=500.0)

        data_desp = st.date_input("Data do Gasto", date.today())
        obs = st.text_input("Oficina / Peça / Observações", placeholder="Ex: Oficina do Zé - Garantia de 3 meses")

        st.divider()
        if st.form_submit_button("💾 Salvar Despesa do Veículo", use_container_width=True, type="primary"):
            if not desc.strip():
                st.error("Informe a descrição do serviço ou peça.")
                return
            conn = conectar()
            cur = conn.cursor()
            data_str = data_desp.strftime("%Y-%m-%d")

            cur.execute("""
                INSERT INTO despesas_veiculo (data, tipo, descricao, valor, km_atual, proxima_troca_km, conta, observacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (data_str, tipo, desc.strip(), valor, km_atual, proxima_km, conta, obs))

            # Determina a categoria correspondente para o extrato geral
            cat_extrato = "Impostos Veículo" if "IPVA" in tipo or "Licenciamento" in tipo else "Manutenção Veículo"
            cur.execute("""
                INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, pago)
                VALUES (?, ?, ?, 'despesa', ?, ?, 1)
            """, (data_str, f"Carro: {desc.strip()}", valor, cat_extrato, conta))

            conn.commit()
            conn.close()
            st.success("Despesa do veículo salva e integrada ao extrato geral!")
            st.rerun()

@st.dialog("⚡ Nova Compra Paga Leve (Pix 4x)", width="large")
def modal_paga_leve():
    """Janela pop-up para compra parcelada no formato Pagaleve (4 parcelas quinzenais)."""
    st.markdown("Gera automaticamente as 4 parcelas quinzenais (1ª efetivada hoje, restantes pendentes a cada 14 ou 15 dias).")
    contas = obter_contas_disponiveis()
    categorias = obter_categorias_disponiveis()
    
    with st.form("form_modal_pagaleve", clear_on_submit=True):
        c1, c2 = st.columns([2, 1])
        desc_pl = c1.text_input("Descrição da Compra", placeholder="Ex: Raia Fraldas, Medicamentos...")
        val_pl = c2.number_input("Valor Total da Compra (R$)", min_value=1.0, value=100.0, step=10.0)
        
        c3, c4 = st.columns(2)
        cat_pl = c3.selectbox("Categoria", categorias, index=categorias.index("Medicamentos") if "Medicamentos" in categorias else 0)
        conta_pl = c4.selectbox("Conta para Débito", contas, index=0)
        
        c5, c6 = st.columns(2)
        data_pl = c5.date_input("Data da Compra (1ª parcela)", date.today())
        intervalo_pl = c6.radio("Intervalo entre parcelas", [14, 15], index=0, horizontal=True)
        
        st.divider()
        if st.form_submit_button("⚡ Gerar as 4 Parcelas Automáticas", use_container_width=True, type="primary"):
            if not desc_pl.strip():
                st.error("Informe a descrição da compra.")
                return
            conn = conectar()
            cur = conn.cursor()
            
            cur.execute("SELECT id FROM contas_config WHERE nome = ?", (conta_pl,))
            c_row = cur.fetchone()
            c_id = c_row[0] if c_row else 1
            
            base = round(val_pl / 4, 2)
            dif = round(val_pl - (base * 4), 2)
            grp = f"pagaleve_{uuid.uuid4().hex[:6]}"
            
            for i in range(1, 5):
                venc = data_pl + timedelta(days=(i - 1) * intervalo_pl)
                v_parc = base + (dif if i == 1 else 0.0)
                pago_flag = 1 if i == 1 else 0
                st_pag = "pago" if pago_flag == 1 else "pendente"
                cur.execute("""
                    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, status_pagamento, grupo_parcelamento, afeta_saldo_bancario)
                    VALUES (?, ?, ?, 'despesa', ?, ?, ?, ?, ?, ?, 1)
                """, (venc.strftime("%Y-%m-%d"), f"{desc_pl.strip()} - Paga Leve {i}/4", v_parc, cat_pl, conta_pl, c_id, pago_flag, st_pag, grp))
                t_id_criado = cur.lastrowid
                
                # Se i == 1 (primeira parcela quitada no ato da compra), registra em pagamentos_despesas
                if i == 1:
                    saldo_service.registrar_pagamento(
                        conn=conn,
                        transacao_id=t_id_criado,
                        data_pagamento=data_pl.strftime("%Y-%m-%d"),
                        valor_pago=v_parc,
                        conta_id=c_id,
                        afeta_saldo_bancario=1,
                        considerado_no_marco=0,
                        forma_pagamento="Pix",
                        observacao=f"Entrada paga no ato (Paga Leve 1/4)"
                    )
                
            conn.commit()
            conn.close()
            st.success("4 parcelas criadas com sucesso no seu extrato!")
            st.rerun()

@st.dialog("🎯 Definir Limite de Gastos")
def modal_limite_gasto():
    """Pop-up para definir ou alterar o teto orçamentário de uma categoria."""
    categorias = obter_categorias_disponiveis()
    with st.form("form_modal_limite", clear_on_submit=True):
        cat = st.selectbox("Categoria", categorias)
        limite = st.number_input("Limite Mensal Máximo (R$)", min_value=10.0, value=500.0, step=50.0)
        if st.form_submit_button("Salvar Limite", use_container_width=True, type="primary"):
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO limites_categoria (categoria, limite) VALUES (?, ?)
                ON CONFLICT(categoria) DO UPDATE SET limite = excluded.limite
            """, (cat, limite))
            conn.commit()
            conn.close()
            st.success(f"Limite para {cat} atualizado para R$ {limite:,.2f}!")
            st.rerun()

@st.dialog("💳 Adicionar Cartão de Crédito")
def modal_novo_cartao():
    """Pop-up para cadastrar um novo cartão de crédito."""
    with st.form("form_modal_cartao", clear_on_submit=True):
        nome = st.text_input("Nome do Cartão", placeholder="Ex: Nubank Ultravioleta, C6 Bank...")
        bandeira = st.selectbox("Bandeira", ["Mastercard", "Visa", "Elo", "American Express", "Outra"])
        limite = st.number_input("Limite Total de Crédito (R$)", min_value=100.0, value=3000.0, step=100.0)
        c1, c2 = st.columns(2)
        fechamento = c1.number_input("Dia de Fechamento", min_value=1, max_value=31, value=5)
        vencimento = c2.number_input("Dia de Vencimento", min_value=1, max_value=31, value=12)
        
        if st.form_submit_button("Cadastrar Cartão", use_container_width=True, type="primary"):
            if not nome.strip():
                st.error("Informe o nome do cartão.")
                return
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO cartoes (nome, bandeira, limite_total, dia_fechamento, dia_vencimento)
                VALUES (?, ?, ?, ?, ?)
            """, (nome.strip(), bandeira, limite, fechamento, vencimento))
            conn.commit()
            conn.close()
            st.success("Cartão cadastrado com sucesso!")
            st.rerun()

@st.dialog("🏦 Adicionar Nova Conta / Carteira")
def modal_nova_conta():
    """Pop-up para cadastrar uma nova conta ou carteira com marco inicial contábil."""
    with st.form("form_modal_conta", clear_on_submit=True):
        nome = st.text_input("Nome da Conta", placeholder="Ex: Inter, Nubank, Itaú, Dinheiro...")
        tipo = st.selectbox("Tipo de Conta", ["Conta Corrente", "Conta Digital", "Carteira / Dinheiro", "Poupança / Reserva"])
        saldo_inicial = st.number_input("Saldo Inicial Real (R$)", value=0.0, step=50.0, help="Será registrado como Marco Inicial contábil da conta, sem gerar receita fictícia.")
        
        if st.form_submit_button("Criar Conta", use_container_width=True, type="primary"):
            if not nome.strip():
                st.error("Informe o nome da conta.")
                return
            conn = conectar()
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO contas_config (nome, tipo) VALUES (?, ?)", (nome.strip(), tipo))
            conn.commit()
            
            cur.execute("SELECT id FROM contas_config WHERE nome = ?", (nome.strip(),))
            c_row = cur.fetchone()
            if c_row and saldo_inicial != 0:
                c_id = c_row[0]
                saldo_service.registrar_ajuste(
                    conn,
                    conta_id=c_id,
                    data_ajuste=date.today().strftime("%Y-%m-%d"),
                    saldo_informado=saldo_service.to_decimal(saldo_inicial),
                    tipo="marco_inicial",
                    motivo="Marco inicial no cadastro da conta"
                )

            conn.close()
            st.success("Conta criada com sucesso!")
            st.rerun()

@st.dialog("⚖️ Ajustar Saldo / Marco Inicial", width="large")
def modal_ajustar_saldo(conta_id_pre=None):
    """Pop-up para definir marco inicial ou registrar ajuste de saldo bancário com auditoria."""
    conn = conectar()
    contas = saldo_service.obter_contas(conn)
    if not contas:
        st.warning("Nenhuma conta cadastrada.")
        conn.close()
        return

    nomes_map = {c["nome"]: c["id"] for c in contas}
    ids_map = {c["id"]: c["nome"] for c in contas}

    idx_inicial = 0
    if conta_id_pre and conta_id_pre in ids_map:
        idx_inicial = [c["id"] for c in contas].index(conta_id_pre)

    c1, c2 = st.columns(2)
    conta_nome_sel = c1.selectbox("Selecione a Conta", list(nomes_map.keys()), index=idx_inicial)
    conta_id_sel = nomes_map[conta_nome_sel]

    tipo_ajuste = c2.selectbox(
        "Tipo de Operação", 
        ["Ajuste de Saldo (Conciliação)", "Definir Marco Inicial"],
        help="Marco Inicial define o ponto de partida do histórico. Ajuste de Saldo concilia o saldo bancário real em uma data específica."
    )
    tipo_cod = "marco_inicial" if "Marco" in tipo_ajuste else "ajuste"

    col_d1, col_d2 = st.columns(2)
    data_ajuste = col_d1.date_input("Data de Referência do Saldo", date.today())
    data_ajuste_str = data_ajuste.strftime("%Y-%m-%d")

    # Calcula saldo do sistema na data de referência
    res_calculo = saldo_service.calcular_saldo_conta(conn, conta_id_sel, data_referencia=data_ajuste_str)
    saldo_calculado = res_calculo["saldo_atual"]

    col_d2.metric("Saldo Calculado pelo Sistema", f"R$ {float(saldo_calculado):,.2f}")

    # Lista transações daquela data para seleção de contempladas (Requisito 1)
    transacoes_dia = saldo_service.listar_transacoes_da_data(conn, conta_id_sel, data_ajuste_str)
    contempladas_selecionadas = []
    
    if transacoes_dia:
        st.markdown("###### 🔍 Lançamentos nesta data para esta conta")
        st.caption("Marque os lançamentos que **já estavam compensados no extrato** no momento em que você conferiu este saldo real:")
        for t in transacoes_dia:
            sinal = "+" if t["tipo"] == "receita" else "-"
            marcado = st.checkbox(
                f"{t['descricao']} ({sinal}R$ {float(t['valor']):,.2f})", 
                value=True, 
                key=f"chk_aj_{t['id']}"
            )
            if marcado:
                contempladas_selecionadas.append(t["id"])

    st.divider()

    c_s1, c_s2 = st.columns(2)
    saldo_real_input = c_s1.number_input(
        "Saldo Real Bancário (R$)", 
        value=float(saldo_calculado), 
        step=50.0,
        format="%.2f",
        help="Informe o saldo real exibido no aplicativo do banco nesta data."
    )
    saldo_real_dec = saldo_service.to_decimal(saldo_real_input)
    diferenca = saldo_real_dec - saldo_calculado

    cor_dif = "normal" if diferenca >= 0 else "inverse"
    c_s2.metric(
        "Diferença Apurada", 
        f"R$ {float(diferenca):,.2f}", 
        delta=f"R$ {float(diferenca):,.2f}",
        delta_color=cor_dif
    )

    motivo = st.text_input("Observação / Justificativa (Opcional)", placeholder="Ex: Conciliação extrato outubro, Marco inicial...")

    st.caption("🔒 Este ajuste será registrado como evento contábil e NÃO criará despesa nem receita familiar.")

    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("✅ Confirmar Ajuste", use_container_width=True, type="primary"):
        saldo_service.registrar_ajuste(
            conn,
            conta_id=conta_id_sel,
            data_ajuste=data_ajuste_str,
            saldo_informado=saldo_real_dec,
            tipo=tipo_cod,
            motivo=motivo.strip(),
            transacoes_contempladas_ids=contempladas_selecionadas
        )
        conn.close()
        st.success(f"Ajuste da conta {conta_nome_sel} salvo com sucesso!")
        st.rerun()

    if col_btn2.button("Cancelar", use_container_width=True):
        conn.close()
        st.rerun()

@st.dialog("🔁 Transferência entre Contas", width="large")
def modal_transferencia():
    """Pop-up para realizar transferência interna entre duas contas."""
    conn = conectar()
    contas = saldo_service.obter_contas(conn)
    if len(contas) < 2:
        st.warning("É necessário ter pelo menos 2 contas cadastradas para realizar transferências.")
        conn.close()
        return

    nomes = [c["nome"] for c in contas]
    mapa_id = {c["nome"]: c["id"] for c in contas}

    c1, c2 = st.columns(2)
    origem = c1.selectbox("Conta Origem (Saída)", nomes, index=0)
    destino_opcoes = [n for n in nomes if n != origem]
    destino = c2.selectbox("Conta Destino (Entrada)", destino_opcoes, index=0)

    col3, col4 = st.columns(2)
    valor = col3.number_input("Valor da Transferência (R$)", min_value=0.01, value=50.0, step=10.0)
    data_transf = col4.date_input("Data da Transferência", date.today())

    desc = st.text_input("Descrição", value=f"Transferência {origem} ➔ {destino}")

    st.caption("ℹ️ A transferência reduz o saldo da conta de origem e aumenta o da conta de destino sem criar receita ou despesa familiar.")

    if st.button("Confirmar Transferência", use_container_width=True, type="primary"):
        origem_id = mapa_id[origem]
        destino_id = mapa_id[destino]
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, conta_destino_id, pago, afeta_saldo_bancario)
            VALUES (?, ?, ?, 'transferencia', 'Transferência', ?, ?, ?, 1, 1)
        """, (data_transf.strftime("%Y-%m-%d"), desc.strip(), valor, origem, origem_id, destino_id))
        conn.commit()
        conn.close()
        st.success("Transferência realizada com sucesso!")
        st.rerun()
    conn.close()


# =============================================================================
# 5. BARRA DE AÇÕES RÁPIDAS
# =============================================================================
def render_barra_acoes_rapidas():
    """Barra compacta contendo os botões que abrem os modais pop-up."""
    with st.container(border=True):
        col_lbl, b1, b2, b3, b4 = st.columns([1.1, 1, 1, 1.2, 1.2], vertical_alignment="center")
        with col_lbl:
            st.markdown("⚡ **Lançamento Rápido:**")
        with b1:
            if st.button("🔴 + Despesa", use_container_width=True, help="Adicionar nova despesa simples"):
                modal_nova_despesa()
        with b2:
            if st.button("🟢 + Entrada", use_container_width=True, help="Adicionar nova receita/entrada"):
                modal_nova_receita()
        with b3:
            if st.button("🚕 + Turno 99/Uber", use_container_width=True, help="Registrar dia de corridas e combustível"):
                modal_novo_turno()
        with b4:
            if st.button("🔁 + Transferência", use_container_width=True, help="Transferência financeira entre contas bancárias"):
                modal_transferencia()


@st.dialog("🕊️ Nova Dívida Livre (Sem Vencimento Obrigatório)", width="large")
def modal_nova_divida_livre():
    """Janela para cadastrar dívida livre sem vencimento obrigatório e sem débito bancário automático."""
    st.caption("Cadastre compromissos familiares ou empréstimos pessoais com amortizações manuais voluntárias.")

    with st.form("form_nova_divida_livre"):
        c1, c2 = st.columns([2, 1])
        credor = c1.text_input("Credor / Beneficiário", placeholder="Ex: Pai, Rubens, Empréstimo Familiar...")
        descricao = c1.text_input("Descrição do Motivo / Objeto", placeholder="Ex: Troca do Carro, Ajuda Financeira...")
        valor_orig = c2.number_input("Valor Original (R$)", min_value=1.0, value=1000.0, step=100.0)
        data_ini = c2.date_input("Data de Início", date.today())

        c3, c4 = st.columns(2)
        meta_mensal = c3.number_input("Meta Voluntária Mensal (R$, opcional)", min_value=0.0, value=0.0, step=50.0, help="Referência de planejamento. NÃO gera cobranças no fluxo de caixa.")
        meta_semanal = c4.number_input("Meta Voluntária Semanal (R$, opcional)", min_value=0.0, value=0.0, step=25.0)

        obs = st.text_input("Observações", placeholder="Ex: Pagamentos serão feitos via PIX conforme disponibilidade")

        st.info("ℹ️ **Regra de Isolamento:** Esta dívida não criará transações bancárias, não movimentará saldos de contas e não é vinculada ao Paga Leve.")

        st.divider()
        if st.form_submit_button("💾 Salvar Dívida Livre", use_container_width=True, type="primary"):
            if not credor.strip() or not descricao.strip():
                st.error("Por favor, preencha o credor e a descrição.")
                return
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO dividas_gerenciamento (
                    credor, descricao, tipo_divida, valor_original, saldo_atual,
                    meta_voluntaria_mensal, meta_voluntaria_semanal, data_inicio, status, observacoes
                ) VALUES (?, ?, 'livre', ?, ?, ?, ?, ?, 'ativa', ?)
            """, (
                credor.strip(),
                descricao.strip(),
                float(valor_orig),
                float(valor_orig),
                float(meta_mensal),
                float(meta_semanal),
                data_ini.strftime("%Y-%m-%d"),
                obs.strip()
            ))
            conn.commit()
            conn.close()
            st.success("Dívida livre cadastrada com sucesso!")
            st.rerun()


@st.dialog("📋 Novo Acordo / Dívida Negociada", width="large")
def modal_novo_acordo_divida():
    """Janela para cadastrar acordo parcelado integrado ao calendário de fluxo de caixa."""
    st.caption("Cadastre acordos de dívidas com parcelas, datas e integração com contas a pagar existentes.")
    contas = obter_contas_disponiveis()

    with st.form("form_novo_acordo"):
        c1, c2 = st.columns([2, 1])
        credor = c1.text_input("Credor / Instituição", placeholder="Ex: BV Financeira, Banco, Particular...")
        descricao = c1.text_input("Descrição do Acordo", placeholder="Ex: Acordo Renegociação BV, Quitação Carro...")
        valor_total = c2.number_input("Valor Total Negociado (R$)", min_value=1.0, value=3000.0, step=100.0)
        data_pri = c2.date_input("Vencimento da 1ª Parcela", date.today())

        c3, c4, c5 = st.columns([1, 1, 1.2])
        num_parcelas = c3.number_input("Quantidade de Parcelas", min_value=1, max_value=72, value=6, step=1)
        periodicidade = c4.selectbox("Periodicidade", ["Mensal", "Quinzenal", "Semanal"], index=0)
        conta = c5.selectbox("Conta Padrão para Débito", contas, index=0)

        primeira_paga = st.checkbox("⚠️ 1ª Parcela já foi paga no ato da negociação hoje?", value=False)

        st.divider()
        if st.form_submit_button("💾 Salvar Acordo Negociado", use_container_width=True, type="primary"):
            if not credor.strip() or not descricao.strip():
                st.error("Por favor, preencha o credor e a descrição do acordo.")
                return

            conn = conectar()
            cur = conn.cursor()
            cur.execute("SELECT id FROM contas_config WHERE nome = ?", (conta,))
            c_row = cur.fetchone()
            c_id = c_row[0] if c_row else 1

            grp_acordo = f"acordo_{uuid.uuid4().hex[:8]}"
            datas_acordo = calcular_datas_recorrentes(data_pri, periodicidade, int(num_parcelas))
            val_parc_base = round(valor_total / num_parcelas, 2)
            dif_cent = round(valor_total - (val_parc_base * num_parcelas), 2)

            cur.execute("""
                INSERT INTO dividas_gerenciamento (
                    credor, descricao, tipo_divida, valor_original, saldo_atual,
                    acordo_parcelas, acordo_valor_parcela, acordo_grupo_parcelamento,
                    data_inicio, status
                ) VALUES (?, ?, 'negociada', ?, ?, ?, ?, ?, ?, 'ativa')
            """, (
                credor.strip(),
                descricao.strip(),
                float(valor_total),
                float(valor_total),
                int(num_parcelas),
                float(val_parc_base),
                grp_acordo,
                data_pri.strftime("%Y-%m-%d")
            ))

            for i, dt in enumerate(datas_acordo):
                v_efetivo = val_parc_base + (dif_cent if i == 0 else 0.0)
                esta_p = (i == 0 and primeira_paga)
                dt_str = dt.strftime("%Y-%m-%d")

                cur.execute("""
                    INSERT INTO transacoes (
                        data, descricao, valor, tipo, categoria, conta, conta_id, pago,
                        status_pagamento, afeta_saldo_bancario, grupo_parcelamento,
                        numero_parcela, total_parcelas_compra, status_rateio
                    ) VALUES (?, ?, ?, 'despesa', 'Dívidas', ?, ?, ?, ?, 1, ?, ?, ?, 'acordo_divida')
                """, (
                    dt_str,
                    f"{descricao.strip()} ({i+1}/{num_parcelas})",
                    v_efetivo,
                    conta,
                    c_id,
                    1 if esta_p else 0,
                    "pago" if esta_p else "pendente",
                    grp_acordo,
                    i + 1,
                    int(num_parcelas)
                ))
                t_novo_id = cur.lastrowid

                if esta_p:
                    saldo_service.registrar_pagamento(
                        conn=conn,
                        transacao_id=t_novo_id,
                        data_pagamento=dt_str,
                        valor_pago=v_efetivo,
                        conta_id=c_id,
                        afeta_saldo_bancario=1,
                        forma_pagamento="Pix",
                        observacao="Entrada / 1ª parcela do acordo paga na assinatura"
                    )

            conn.commit()
            conn.close()
            st.success(f"Acordo negociado em {num_parcelas}x registrado com sucesso!")
            st.rerun()


@st.dialog("💵 Registrar Amortização / Pagamento Manual", width="medium")
def modal_pagamento_manual_divida(id_divida: int):
    """Registra amortização manual em dívida livre sem criar débito bancário automático."""
    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM dividas_gerenciamento WHERE id = ?", (id_divida,))
    div = cur.fetchone()
    conn.close()

    if not div:
        st.error("Dívida não encontrada.")
        return

    st.markdown(f"### {div['descricao']}")
    st.caption(f"Credor: **{div['credor']}** • Saldo devedor atual: **{formatar_moeda_br(div['saldo_atual'])}**")

    with st.form(f"form_pag_manual_{id_divida}"):
        col1, col2 = st.columns(2)
        val_amortizar = col1.number_input(
            "Valor Amortizado (R$)",
            min_value=0.01,
            max_value=float(div["saldo_atual"]) if div["saldo_atual"] > 0 else 100000.0,
            value=min(float(div["saldo_atual"]), 500.0) if div["saldo_atual"] > 0 else 100.0,
            step=50.0
        )
        data_pag = col2.date_input("Data do Pagamento", date.today())
        obs = st.text_input("Observação / Comprovante", placeholder="Ex: PIX enviado no almoço, dinheiro em mãos...")

        st.info("ℹ️ **Sem Débito Bancário:** Este registro atualiza apenas o saldo devedor deste controle, sem movimentar suas contas no aplicativo.")

        st.divider()
        if st.form_submit_button("✅ Confirmar Pagamento Manual", use_container_width=True, type="primary"):
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO dividas_pagamentos_manuais (divida_id, data_pagamento, valor_pago, observacao)
                VALUES (?, ?, ?, ?)
            """, (id_divida, data_pag.strftime("%Y-%m-%d"), float(val_amortizar), obs.strip()))

            cur.execute("""
                UPDATE dividas_gerenciamento
                SET saldo_atual = MAX(0.0, saldo_atual - ?)
                WHERE id = ?
            """, (float(val_amortizar), id_divida))

            cur.execute("SELECT saldo_atual FROM dividas_gerenciamento WHERE id = ?", (id_divida,))
            novo_s = cur.fetchone()[0]
            if novo_s <= 0.001:
                cur.execute("UPDATE dividas_gerenciamento SET status = 'quitada' WHERE id = ?", (id_divida,))

            conn.commit()
            conn.close()
            st.success("Amortização registrada com sucesso!")
            st.rerun()


@st.dialog("🤝 Transformar em Acordo Negociado", width="large")
def modal_transformar_divida_negociada(id_divida: int):
    """Converte dívida livre em negociada gerando parcelas no fluxo de caixa e preservando histórico."""
    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM dividas_gerenciamento WHERE id = ?", (id_divida,))
    div = cur.fetchone()
    conn.close()

    if not div:
        st.error("Dívida não encontrada.")
        return

    st.markdown(f"### Acordo: {div['descricao']}")
    st.caption(f"Credor: **{div['credor']}** • Saldo devedor restante: **{formatar_moeda_br(div['saldo_atual'])}**")
    st.info("💡 Todo o histórico de pagamentos manuais anteriores será 100% preservado. O saldo restante será convertido em parcelas no calendário de fluxo de caixa.")

    contas = obter_contas_disponiveis()

    with st.form(f"form_converter_{id_divida}"):
        c1, c2 = st.columns(2)
        val_acordo = c1.number_input("Valor a Parcelar no Acordo (R$)", min_value=1.0, value=float(div["saldo_atual"]), step=50.0)
        num_parcelas = c2.number_input("Quantidade de Parcelas", min_value=1, max_value=60, value=6, step=1)

        c3, c4 = st.columns(2)
        data_pri = c3.date_input("Vencimento da 1ª Parcela", date.today() + timedelta(days=30))
        periodicidade = c4.selectbox("Periodicidade", ["Mensal", "Quinzenal", "Semanal"], index=0)

        conta = st.selectbox("Conta de Origem Padrão", contas, index=0)

        st.divider()
        if st.form_submit_button("✅ Gerar Acordo e Integrar ao Caixa", use_container_width=True, type="primary"):
            conn = conectar()
            cur = conn.cursor()
            cur.execute("SELECT id FROM contas_config WHERE nome = ?", (conta,))
            c_row = cur.fetchone()
            c_id = c_row[0] if c_row else 1

            grp_acordo = f"acordo_div_{id_divida}_{uuid.uuid4().hex[:6]}"
            datas_acordo = calcular_datas_recorrentes(data_pri, periodicidade, int(num_parcelas))
            val_parc_base = round(val_acordo / num_parcelas, 2)
            dif_cent = round(val_acordo - (val_parc_base * num_parcelas), 2)

            cur.execute("""
                UPDATE dividas_gerenciamento
                SET tipo_divida = 'negociada',
                    acordo_parcelas = ?,
                    acordo_valor_parcela = ?,
                    acordo_grupo_parcelamento = ?
                WHERE id = ?
            """, (int(num_parcelas), float(val_parc_base), grp_acordo, id_divida))

            for i, dt in enumerate(datas_acordo):
                v_efetivo = val_parc_base + (dif_cent if i == 0 else 0.0)
                dt_str = dt.strftime("%Y-%m-%d")

                cur.execute("""
                    INSERT INTO transacoes (
                        data, descricao, valor, tipo, categoria, conta, conta_id, pago,
                        status_pagamento, afeta_saldo_bancario, grupo_parcelamento,
                        numero_parcela, total_parcelas_compra, status_rateio
                    ) VALUES (?, ?, ?, 'despesa', 'Dívidas', ?, ?, 0, 'pendente', 1, ?, ?, ?, 'acordo_divida')
                """, (
                    dt_str,
                    f"Acordo {div['credor']} ({i+1}/{num_parcelas})",
                    v_efetivo,
                    conta,
                    c_id,
                    grp_acordo,
                    i + 1,
                    int(num_parcelas)
                ))

            conn.commit()
            conn.close()
            st.success("Acordo formalizado e integrado ao fluxo de caixa!")
            st.rerun()


@st.dialog("➕ Novo Grupo de Categorias", width="medium")
def modal_novo_grupo():
    """Cria um novo grupo principal na estrutura hierárquica (Cerbasi / Organizze)."""
    with st.form("form_novo_grupo_categoria"):
        nome = st.text_input("Nome do Grupo *", placeholder="Ex: Investimentos, Metas de Longo Prazo...").strip()
        c1, c2 = st.columns(2)
        tipo = c1.selectbox("Tipo de Grupo", ["despesa", "receita"], index=0)
        icone = c2.text_input("Ícone / Emoji", value="📁").strip()
        descricao = st.text_input("Descrição / Finalidade", placeholder="Ex: Metas futuras e investimentos").strip()

        st.divider()
        if st.form_submit_button("💾 Salvar Grupo", use_container_width=True, type="primary"):
            if not nome:
                st.error("Informe o nome do grupo.")
                return
            conn = conectar()
            cur = conn.cursor()
            try:
                cur.execute("SELECT COALESCE(MAX(ordem), 0) + 1 FROM grupos_categoria")
                proxima_ordem = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO grupos_categoria (nome, icone, tipo, ordem, descricao, ativo)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (nome, icone or "📁", tipo, proxima_ordem, descricao))
                conn.commit()
                conn.close()
                st.success(f"Grupo '{nome}' criado com sucesso!")
                st.rerun()
            except sqlite3.IntegrityError:
                conn.close()
                st.error("Já existe um grupo com este nome.")


@st.dialog("➕ Nova Subcategoria", width="medium")
def modal_nova_subcategoria(grupo_id_pre=None):
    """Cria nova subcategoria vinculada a um grupo existente."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, nome, icone FROM grupos_categoria WHERE ativo = 1 ORDER BY ordem ASC")
    grupos_db = cur.fetchall()
    conn.close()

    mapa_g = {f"{g[2]} {g[1]}": g[0] for g in grupos_db}
    nomes_g = list(mapa_g.keys())

    idx_padrao = 0
    if grupo_id_pre:
        for idx, (k, v) in enumerate(mapa_g.items()):
            if v == grupo_id_pre:
                idx_padrao = idx
                break

    with st.form("form_nova_subcat"):
        grupo_sel = st.selectbox("Grupo Principal", nomes_g, index=idx_padrao)
        c1, c2 = st.columns([1, 3])
        icone = c1.text_input("Ícone", value="•")
        nome = c2.text_input("Nome da Subcategoria", placeholder="Ex: Farmácia do Pedro, Manutenção Pneus...")

        c3, c4 = st.columns(2)
        natureza = c3.selectbox("Natureza do Gasto", ["variavel", "fixa", "eventual", "divida", "investimento", "receita"], index=0)
        finalidade = c4.selectbox("Finalidade", ["familiar", "profissional", "misto"], index=0)

        st.divider()
        if st.form_submit_button("💾 Salvar Subcategoria", use_container_width=True, type="primary"):
            if not nome.strip():
                st.error("Informe o nome da subcategoria.")
                return
            g_id = mapa_g[grupo_sel]
            conn = conectar()
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO subcategorias (grupo_id, nome, icone, natureza_padrao, finalidade)
                    VALUES (?, ?, ?, ?, ?)
                """, (g_id, nome.strip(), icone.strip(), natureza, finalidade))
                conn.commit()
                conn.close()
                st.success("Subcategoria cadastrada com sucesso!")
                st.rerun()
            except sqlite3.IntegrityError:
                conn.close()
                st.error("Já existe uma subcategoria com esse nome neste grupo.")


@st.dialog("🎯 Classificar Lançamento Pendente", width="large")
def modal_classificar_transacao(transacao_id: int):
    """Permite ao usuário classificar lançamento ambíguo sem forçar rateios fictícios."""
    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM transacoes WHERE id = ?", (transacao_id,))
    t_row = cur.fetchone()
    conn.close()

    if not t_row:
        st.error("Lançamento não encontrado.")
        return

    st.markdown(f"### 📋 {t_row['descricao']}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Valor", formatar_moeda_br(t_row['valor']))
    col1.caption(f"🗓️ Data: {t_row['data']}")
    col2.metric("Conta", t_row['conta'])
    col3.metric("Status Atual", t_row['status_rateio'])

    st.caption("Selecione o grupo e a subcategoria definitivos para este lançamento:")
    estrutura = obter_estrutura_categorias()
    nomes_grupos = [f"{g['icone']} {g['nome']}" for g in estrutura.values()]

    c_g, c_s = st.columns(2)
    g_sel = c_g.selectbox("Grupo", nomes_grupos)

    g_obj = next((g for g in estrutura.values() if f"{g['icone']} {g['nome']}" == g_sel), None)
    subs = g_obj["subcategorias"] if g_obj else []
    nomes_subs = [f"{s['icone']} {s['nome']}" for s in subs] if subs else ["Geral"]
    s_sel = c_s.selectbox("Subcategoria", nomes_subs)

    sub_obj = next((s for s in subs if f"{s['icone']} {s['nome']}" == s_sel), None)

    st.divider()
    if st.button("✅ Salvar Classificação Definitiva", type="primary", use_container_width=True):
        cat_final = sub_obj["nome"] if sub_obj else (g_obj["nome"] if g_obj else "Outros")
        g_id = g_obj["id"] if g_obj else None
        s_id = sub_obj["id"] if sub_obj else None
        nat = sub_obj["natureza"] if sub_obj else "variavel"

        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            UPDATE transacoes
            SET grupo_id = ?, subcategoria_id = ?, categoria = ?, natureza_gasto = ?, status_rateio = 'normal'
            WHERE id = ?
        """, (g_id, s_id, cat_final, nat, transacao_id))
        conn.commit()
        conn.close()
        st.success("Lançamento classificado com sucesso!")
        st.rerun()


# =============================================================================
# 6. PÁGINAS DO SISTEMA
# =============================================================================

@st.dialog("⚙️ Organizar Posição dos Blocos do Dashboard", width="large")
def modal_organizar_blocos():
    """Janela modal para reordenar blocos entre as colunas esquerda e direita e controlar visibilidade."""
    st.caption("Personalize como os blocos aparecem na sua tela inicial. Use os botões para subir, descer ou alternar blocos entre as colunas, e desmarque os que deseja ocultar.")

    nomes_blocos = {
        "contas": "🏦 Minhas Contas",
        "cartoes": "💳 Meus Cartões",
        "paga_leve": "⚡ Paga Leve",
        "limites": "🎯 Orçamento & Limites",
        "contas_pagar": "🚨 Contas a Pagar",
        "maiores_gastos": "📊 Maiores Gastos",
        "turnos": "🚕 Últimos Turnos (99/Uber)",
        "missao_ipva": "🎯 Missão IPVA 2025/2026",
        "caixa_7dias": "🗓️ Caixa Próximos 7 Dias",
        "projecao_mes": "📈 Projeção Fim do Mês",
        "capacidade_trabalho": "⏱️ Capacidade de Trabalho (App)"
    }

    col1, col2 = st.columns(2, gap="medium")
    vis_map = dict(st.session_state.get("blocos_visiveis", {}))
    precisa_salvar_vis = False

    with col1:
        st.markdown("#### ⬅️ Coluna Esquerda")
        esq_atuais = list(st.session_state.get("blocos_col_esq", []))
        if not esq_atuais:
            st.info("Nenhum bloco nesta coluna.")
        for i, b_id in enumerate(esq_atuais):
            with st.container(border=True):
                nome = nomes_blocos.get(b_id, b_id)
                st.markdown(f"**{nome}**")
                
                is_v = vis_map.get(b_id, True)
                novo_v = st.checkbox("👁️ Exibir bloco", value=is_v, key=f"mod_vis_{b_id}")
                if novo_v != is_v:
                    vis_map[b_id] = novo_v
                    precisa_salvar_vis = True

                c_up, c_down, c_swap = st.columns([1, 1, 1.4])
                with c_up:
                    if st.button("⬆️ Subir", key=f"mod_up_{b_id}", disabled=(i == 0), use_container_width=True):
                        mover_bloco(b_id, "subir")
                with c_down:
                    if st.button("⬇️ Descer", key=f"mod_down_{b_id}", disabled=(i == len(esq_atuais) - 1), use_container_width=True):
                        mover_bloco(b_id, "descer")
                with c_swap:
                    if st.button("➡️ P/ Direita", key=f"mod_swap_{b_id}", use_container_width=True):
                        mover_bloco(b_id, "trocar_coluna")

    with col2:
        st.markdown("#### ➡️ Coluna Direita")
        dir_atuais = list(st.session_state.get("blocos_col_dir", []))
        if not dir_atuais:
            st.info("Nenhum bloco nesta coluna.")
        for i, b_id in enumerate(dir_atuais):
            with st.container(border=True):
                nome = nomes_blocos.get(b_id, b_id)
                st.markdown(f"**{nome}**")
                
                is_v = vis_map.get(b_id, True)
                novo_v = st.checkbox("👁️ Exibir bloco", value=is_v, key=f"mod_vis_{b_id}")
                if novo_v != is_v:
                    vis_map[b_id] = novo_v
                    precisa_salvar_vis = True

                c_up, c_down, c_swap = st.columns([1, 1, 1.4])
                with c_up:
                    if st.button("⬆️ Subir", key=f"mod_up_{b_id}", disabled=(i == 0), use_container_width=True):
                        mover_bloco(b_id, "subir")
                with c_down:
                    if st.button("⬇️ Descer", key=f"mod_down_{b_id}", disabled=(i == len(dir_atuais) - 1), use_container_width=True):
                        mover_bloco(b_id, "descer")
                with c_swap:
                    if st.button("⬅️ P/ Esquerda", key=f"mod_swap_{b_id}", use_container_width=True):
                        mover_bloco(b_id, "trocar_coluna")

    if precisa_salvar_vis:
        st.session_state["blocos_visiveis"] = vis_map
        salvar_layout_dashboard(st.session_state["blocos_col_esq"], st.session_state["blocos_col_dir"], vis_map)
        st.rerun()

    st.divider()
    b_res, b_ok = st.columns([1, 1])
    with b_res:
        if st.button("🔄 Restaurar Layout Padrão", key="btn_reset_modal", use_container_width=True):
            restaurar_layout_padrao()
    with b_ok:
        if st.button("Concluído", type="primary", use_container_width=True):
            st.rerun()


def render_cabecalho_bloco(
    titulo: str,
    bloco_id: str,
    coluna: str,
    idx: int,
    total_na_coluna: int,
    tem_botao_acao: bool = False
):
    """
    Renderiza o cabeçalho estilizado do bloco do dashboard com:
    - Âncora oculta para o script de drag & drop
    - Ícone de arrastar '⠿'
    - Título do bloco
    - Botão de ação rápida (se aplicável, ex: + Conta, + Cartão)
    - Controles de reposicionamento (▲ Subir, ▼ Descer, ⇄ Trocar Coluna)
    """
    st.markdown(f'<div class="bloco-card-anchor" data-bloco="{bloco_id}" style="display:none;"></div>', unsafe_allow_html=True)
    if tem_botao_acao:
        c_title, c_act, c_ctrl = st.columns([1.8, 1.0, 1.1], vertical_alignment="center")
    else:
        c_title, c_ctrl = st.columns([2.9, 1.1], vertical_alignment="center")
        c_act = None

    with c_title:
        st.markdown(
            f"##### <span class='drag-handle' title='Clique e arraste para reposicionar'>⠿</span> {titulo}",
            unsafe_allow_html=True
        )

    with c_ctrl:
        c_up, c_down, c_swap = st.columns([1, 1, 1.2])
        with c_up:
            if st.button("▲", key=f"btn_up_{bloco_id}", help=f"Subir '{titulo}'", disabled=(idx == 0)):
                mover_bloco(bloco_id, "subir")
        with c_down:
            if st.button("▼", key=f"btn_down_{bloco_id}", help=f"Descer '{titulo}'", disabled=(idx == total_na_coluna - 1)):
                mover_bloco(bloco_id, "descer")
        with c_swap:
            outra = "Direita" if coluna == "esq" else "Esquerda"
            if st.button("⇄", key=f"btn_swap_{bloco_id}", help=f"Mover para Coluna {outra}"):
                mover_bloco(bloco_id, "trocar_coluna")

    return c_act


def render_conteudo_bloco_contas(df: pd.DataFrame, saldo_atual: float):
    """Renderiza a lista de contas e saldos no bloco utilizando o serviço centralizado de saldo."""
    conn = conectar()
    contas = saldo_service.obter_contas(conn)
    for c in contas:
        res_c = saldo_service.calcular_saldo_conta(conn, c["id"])
        saldo_c = float(res_c["saldo_atual"])
        cor_sld = "#10b981" if saldo_c >= 0 else "#ef4444"
        
        st.markdown(f"""
        <div class="row-item">
            <div><strong>🏦 {c["nome"]}</strong></div>
            <div style="color:{cor_sld}; font-weight:700;">R$ {saldo_c:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    conn.close()
    st.caption(f"Saldo total consolidado: **R$ {saldo_atual:,.2f}**")


def render_conteudo_bloco_cartoes(df: pd.DataFrame):
    """Renderiza o resumo do cartão no bloco."""
    conn = conectar()
    cartoes_df = pd.read_sql_query("SELECT * FROM cartoes LIMIT 1", conn)
    conn.close()

    if cartoes_df.empty:
        st.info("Nenhum cartão cadastrado ainda.")
    else:
        crd = cartoes_df.iloc[0]
        gastos_cartao = df[(df["descricao"].str.contains(crd["nome"], case=False, na=False)) | 
                           (df["conta"] == crd["nome"])]["valor"].sum()
        limite_disp = max(crd["limite_total"] - gastos_cartao, 0.0)

        st.markdown(f"""
        <div class="subcard-item">
            <div style="display:flex; justify-content:space-between; font-weight:600;">
                <span>💳 {crd['nome']} ({crd['bandeira']})</span>
                <span style="color:var(--text-muted); font-size:0.85rem;">Venc: dia {crd['dia_vencimento']}</span>
            </div>
            <div style="margin-top:6px; font-size:0.85rem; color:var(--text-muted); display:flex; justify-content:space-between;">
                <span>Limite Total: <strong>R$ {crd['limite_total']:,.2f}</strong></span>
                <span style="color:#10b981;">Disponível: <strong>R$ {limite_disp:,.2f}</strong></span>
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_conteudo_bloco_paga_leve(df: pd.DataFrame):
    """Renderiza o resumo do Paga Leve no bloco modular da Visão Geral."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT titular, tipo_limite, limite_total FROM pagaleve_contas WHERE ativo = 1")
    contas_pl = cur.fetchall()

    # Parcelas pendentes do Paga Leve
    cur.execute("""
        SELECT t.id, t.data, t.descricao, t.valor, COALESCE(t.titular, 'A Confirmar') as titular,
               t.numero_parcela, t.total_parcelas_compra, t.grupo_parcelamento
        FROM transacoes t
        WHERE (t.grupo_parcelamento LIKE 'pagaleve_%' OR t.descricao LIKE '%Paga Leve%')
          AND (t.pago IS NULL OR t.pago != 1)
        ORDER BY t.data ASC, t.id ASC
    """)
    parcelas_pendentes = cur.fetchall()
    conn.close()

    total_aberto = sum(p[3] for p in parcelas_pendentes)
    hoje = date.today()
    mes_atual_str = hoje.strftime("%Y-%m")
    vence_mes = sum(p[3] for p in parcelas_pendentes if str(p[1]).startswith(mes_atual_str))

    # Resumo das contas de Carlos e Fernanda
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        aberto_carlos = sum(p[3] for p in parcelas_pendentes if p[4] == "Carlos")
        st.markdown(f"""
        <div style="background-color:var(--bg-subcard); padding:8px 12px; border-radius:10px; border-left:3px solid #2563eb;">
            <div style="font-size:0.8rem; color:var(--text-muted); font-weight:600;">👤 Carlos (Limite: R$ 1.200)</div>
            <div style="font-size:0.95rem; font-weight:700; color:var(--text-primary); margin-top:2px;">
                {formatar_moeda_br(aberto_carlos)} <span style="font-size:0.75rem; font-weight:500; color:#10b981;">(Disp: {formatar_moeda_br(max(0.0, 1200.0 - aberto_carlos))})</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_c2:
        aberto_fernanda = sum(p[3] for p in parcelas_pendentes if p[4] == "Fernanda")
        aberto_confirmar = sum(p[3] for p in parcelas_pendentes if p[4] not in ("Carlos", "Fernanda"))
        st.markdown(f"""
        <div style="background-color:var(--bg-subcard); padding:8px 12px; border-radius:10px; border-left:3px solid #db2777;">
            <div style="font-size:0.8rem; color:var(--text-muted); font-weight:600;">👤 Fernanda (Sob Demanda)</div>
            <div style="font-size:0.95rem; font-weight:700; color:var(--text-primary); margin-top:2px;">
                {formatar_moeda_br(aberto_fernanda)} {"<span style='font-size:0.75rem; color:#f59e0b;'>(" + formatar_moeda_br(aberto_confirmar) + " a conf.)</span>" if aberto_confirmar > 0 else ""}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.markdown(f"""
    <div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom:6px;">
        <span>Total em Aberto: <strong>{formatar_moeda_br(total_aberto)}</strong> ({len(parcelas_pendentes)} parc.)</span>
        <span style="color:#f59e0b;">Neste Mês: <strong>{formatar_moeda_br(vence_mes)}</strong></span>
    </div>
    """, unsafe_allow_html=True)

    if not parcelas_pendentes:
        st.success("🎉 Nenhuma parcela Paga Leve pendente!")
    else:
        st.markdown("###### 🗓️ Próximos Vencimentos:")
        for p in parcelas_pendentes[:4]:
            p_id, p_data, p_desc, p_val, p_tit, p_num, p_tot, p_grp = p
            try:
                dt_br = datetime.strptime(str(p_data)[:10], "%Y-%m-%d").strftime("%d/%m")
            except Exception:
                dt_br = str(p_data)
            
            if p_tit == "Carlos":
                badge_tit = "<span style='background:#2563eb22; color:#2563eb; padding:2px 6px; border-radius:6px; font-size:0.75rem; font-weight:600;'>Carlos</span>"
            elif p_tit == "Fernanda":
                badge_tit = "<span style='background:#db277722; color:#db2777; padding:2px 6px; border-radius:6px; font-size:0.75rem; font-weight:600;'>Fernanda</span>"
            else:
                badge_tit = "<span style='background:#f59e0b22; color:#f59e0b; padding:2px 6px; border-radius:6px; font-size:0.75rem; font-weight:600;'>A Confirmar</span>"

            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; background-color:var(--bg-subcard); padding:6px 10px; border-radius:8px; margin-bottom:5px; font-size:0.84rem;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-weight:600; color:var(--text-muted);">{dt_br}</span>
                    <span style="font-weight:600; color:var(--text-primary);">{p_desc}</span>
                    {badge_tit}
                </div>
                <div style="font-weight:700; color:var(--text-primary);">{formatar_moeda_br(p_val)}</div>
            </div>
            """, unsafe_allow_html=True)

    if st.button("Abrir Gestão Paga Leve Completa ➔", key="btn_ir_pl_vg", use_container_width=True):
        st.session_state["pagina_ativa"] = "Paga Leve"
        st.rerun()


def render_conteudo_bloco_limites(df: pd.DataFrame):
    """Renderiza as barras de orçamento por categoria no bloco."""
    conn = conectar()
    limites_df = pd.read_sql_query("SELECT * FROM limites_categoria LIMIT 4", conn)
    conn.close()

    if limites_df.empty:
        st.caption("Nenhum limite estipulado.")
    else:
        for _, lim_row in limites_df.iterrows():
            cat = lim_row["categoria"]
            teto = lim_row["limite"]
            gasto_cat = df[(df["categoria"] == cat) & (df["tipo"] == "despesa")]["valor"].sum()
            pct = min(gasto_cat / teto, 1.0) if teto > 0 else 0
            ic = obter_icone_categoria(cat)

            st.markdown(f"""
            <div style="margin-top: 10px; margin-bottom: 2px;">
                <div style="display:flex; justify-content:space-between; font-size:0.86rem;">
                    <span>{ic} <strong>{cat}</strong></span>
                    <span style="color:var(--text-muted); font-size:0.84rem;">R$ {gasto_cat:,.2f} / R$ {teto:,.2f} <strong>({pct*100:.0f}%)</strong></span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.progress(pct)


def render_conteudo_bloco_contas_pagar(df: pd.DataFrame):
    """
    Renderiza as pendências e contas a pagar categorizadas:
    - Obrigações do mês atual (vencem hoje, atrasadas no mês, a vencer no mês)
    - Pendências de meses anteriores (dívidas antigas com inclusão voluntária na meta)
    - Contas futuras (próximos meses)
    """
    hoje = date.today()
    hoje_str = hoje.strftime("%Y-%m-%d")
    ano_atual = hoje.year
    mes_atual = hoje.month
    inicio_mes_str = f"{ano_atual}-{mes_atual:02d}-01"
    ultimo_dia = calendar.monthrange(ano_atual, mes_atual)[1]
    fim_mes_str = f"{ano_atual}-{mes_atual:02d}-{ultimo_dia:02d}"

    meses_nomes = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    nome_mes = meses_nomes.get(mes_atual, f"Mês {mes_atual}")

    # 1. Dívidas de Meses Anteriores (Regras 3 e 5)
    df_antigas = df[(df["tipo"] == "despesa") & (df["pago"] == 0) & (df["data"] < inicio_mes_str)].sort_values(by="data", ascending=True)
    if not df_antigas.empty:
        if "dividas_antigas_selecionadas" not in st.session_state:
            st.session_state["dividas_antigas_selecionadas"] = carregar_dividas_antigas_selecionadas()

        st.markdown(f"<div style='color:#dc2626; font-weight:700; margin-bottom:4px;'>📁 Pendências de Meses Anteriores ({len(df_antigas)})</div>", unsafe_allow_html=True)
        st.caption(f"Estas contas não entram automaticamente na meta de {nome_mes}. Marque para incluí-las no cálculo da meta de trabalho:")

        for _, r in df_antigas.iterrows():
            ic = obter_icone_categoria(r["categoria"])
            data_br = datetime.strptime(r["data"], "%Y-%m-%d").strftime("%d/%m/%Y")
            esta_inc = r["id"] in st.session_state["dividas_antigas_selecionadas"]

            c_chk, c_info, c_val = st.columns([0.8, 3.0, 1.6], vertical_alignment="center")
            with c_chk:
                marcado = st.checkbox(
                    "Incluir",
                    value=esta_inc,
                    key=f"chk_inc_antiga_{r['id']}",
                    label_visibility="collapsed",
                    help="Marcar para incluir esta dívida antiga na meta líquida de trabalho deste mês"
                )
                if marcado != esta_inc:
                    if marcado:
                        st.session_state["dividas_antigas_selecionadas"].add(r["id"])
                    else:
                        st.session_state["dividas_antigas_selecionadas"].discard(r["id"])
                    salvar_dividas_antigas_selecionadas(st.session_state["dividas_antigas_selecionadas"])
                    st.rerun()
            with c_info:
                st.markdown(f"{ic} <span style='color:var(--text-muted); font-size:0.85rem;'>{data_br}</span> • <strong>{r['descricao']}</strong>", unsafe_allow_html=True)
            with c_val:
                tag_meta = " :green[*(na meta)*]" if esta_inc else ""
                st.markdown(f"<span style='color:#ef4444; font-weight:700;'>R$ {r['valor']:,.2f}</span>{tag_meta}", unsafe_allow_html=True)
        st.divider()

    # 2. Obrigações Pertencentes a Outubro (Regras 1 e 2)
    vence_hoje = df[(df["tipo"] == "despesa") & (df["pago"] == 0) & (df["data"] == hoje_str)]
    vencidas_mes = df[(df["tipo"] == "despesa") & (df["pago"] == 0) & (df["data"] >= inicio_mes_str) & (df["data"] < hoje_str)].sort_values(by="data", ascending=True)
    proximas_mes = df[(df["tipo"] == "despesa") & (df["pago"] == 0) & (df["data"] > hoje_str) & (df["data"] <= fim_mes_str)].sort_values(by="data", ascending=True)

    if not vence_hoje.empty:
        st.markdown(f"<div style='color:#f59e0b; font-weight:700; margin-bottom:6px;'>⚠️ Vence Hoje ({hoje.strftime('%d/%m')})</div>", unsafe_allow_html=True)
        for _, r in vence_hoje.iterrows():
            ic = obter_icone_categoria(r["categoria"])
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; padding:4px 0;">
                <span>{ic} <strong>{r['descricao']}</strong></span>
                <span style="color:#f59e0b; font-weight:700;">R$ {r['valor']:,.2f}</span>
            </div>
            """, unsafe_allow_html=True)
        st.divider()

    if not vencidas_mes.empty:
        st.markdown(f"<div style='color:#ef4444; font-weight:700; margin-bottom:6px;'>❗ Atrasadas de {nome_mes} ({len(vencidas_mes)})</div>", unsafe_allow_html=True)
        for _, r in vencidas_mes.iterrows():
            ic = obter_icone_categoria(r["categoria"])
            data_br = datetime.strptime(r["data"], "%Y-%m-%d").strftime("%d/%m")
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; padding:4px 0;">
                <span>{ic} <span style="color:var(--text-muted);">{data_br}</span> • <strong>{r['descricao']}</strong></span>
                <span style="color:#ef4444; font-weight:700;">R$ {r['valor']:,.2f}</span>
            </div>
            """, unsafe_allow_html=True)
        st.divider()

    if not proximas_mes.empty:
        st.markdown(f"<div style='font-weight:600; margin-bottom:6px;'>⏳ A Vencer em {nome_mes} ({len(proximas_mes)})</div>", unsafe_allow_html=True)
        for _, r in proximas_mes.iterrows():
            ic = obter_icone_categoria(r["categoria"])
            data_br = datetime.strptime(r["data"], "%Y-%m-%d").strftime("%d/%m")
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; padding:4px 0;">
                <span>{ic} <span style="color:var(--text-muted);">{data_br}</span> • {r['descricao']}</span>
                <span style="font-weight:600; color:var(--text-primary);">R$ {r['valor']:,.2f}</span>
            </div>
            """, unsafe_allow_html=True)
    elif vence_hoje.empty and vencidas_mes.empty and df_antigas.empty:
        st.success("Tudo em dia! Nenhuma conta pendente para os próximos dias.")

    # 3. Contas de Meses Posteriores (Regra 4)
    df_futuras = df[(df["tipo"] == "despesa") & (df["pago"] == 0) & (df["data"] > fim_mes_str)].sort_values(by="data", ascending=True)
    if not df_futuras.empty:
        st.divider()
        st.markdown(f"<div style='color:var(--text-muted); font-weight:600; margin-bottom:6px;'>🗓️ Próximos Meses ({len(df_futuras)})</div>", unsafe_allow_html=True)
        st.caption("Despesas futuras programadas (não entram na meta deste mês):")
        for _, r in df_futuras.head(4).iterrows():
            ic = obter_icone_categoria(r["categoria"])
            data_br = datetime.strptime(r["data"], "%Y-%m-%d").strftime("%d/%m/%Y")
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; padding:3px 0; font-size:0.88rem;">
                <span>{ic} <span style="color:var(--text-muted);">{data_br}</span> • {r['descricao']}</span>
                <span style="color:var(--text-muted); font-weight:600;">R$ {r['valor']:,.2f}</span>
            </div>
            """, unsafe_allow_html=True)


def render_conteudo_bloco_maiores_gastos(df: pd.DataFrame):
    """Renderiza as principais despesas agrupadas por categoria no bloco."""
    df_desp = df[df["tipo"] == "despesa"]
    total_desp = df_desp["valor"].sum()
    if total_desp > 0:
        por_cat = df_desp.groupby("categoria")["valor"].sum().sort_values(ascending=False).head(5)
        for cat, val in por_cat.items():
            pct = (val / total_desp) * 100
            ic = obter_icone_categoria(cat)
            st.markdown(f"""
            <div style="margin-top: 10px; margin-bottom: 2px;">
                <div style="display:flex; justify-content:space-between; font-size:0.86rem;">
                    <span>{ic} <strong>{cat}</strong></span>
                    <span style="color:var(--text-muted); font-size:0.84rem;">R$ {val:,.2f} <strong>({pct:.1f}%)</strong></span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.progress(min(pct / 100, 1.0))
    else:
        st.info("Nenhuma despesa registrada no período.")


def render_conteudo_bloco_turnos(df_turnos: pd.DataFrame):
    """Renderiza os últimos turnos registrados de motorista no bloco."""
    if df_turnos.empty:
        st.info("Nenhum turno registrado ainda. Clique em '+ Turno 99/Uber' acima para registrar.")
        return
    ultimos = df_turnos.sort_values(by="data", ascending=False).head(3)
    for _, t in ultimos.iterrows():
        dt_format = datetime.strptime(t["data"], "%Y-%m-%d").strftime("%d/%m")
        liq = t["ganho_bruto"] - t["combustivel"]
        per = t.get("periodo", "Turno")
        st.markdown(f"🗓️ **{dt_format}** • {t['horas']}h ({per}) | Bruto: `R$ {t['ganho_bruto']:,.2f}` | Comb: `:red[R$ {t['combustivel']:,.2f}]` → Líquido: :green[**R$ {liq:,.2f}**]")


def render_conteudo_bloco_missao_ipva(df: pd.DataFrame):
    """Card resumido da Missão Prioritária (IPVA) para o Dashboard."""
    conn = conectar()
    missao = planejamento_service.obter_status_missao_ipva(conn, data_referencia=date.today())
    conn.close()

    if not missao.get("tem_missao"):
        st.info("Nenhuma missão prioritária ativa configurada.")
        return

    c1, c2 = st.columns([2.0, 1.2])
    with c1:
        st.markdown(f"**{missao['titulo']}**")
        dt_venc_fmt = datetime.strptime(missao['data_vencimento'], '%Y-%m-%d').strftime('%d/%m/%Y')
        st.caption(f"Vencimento: **{dt_venc_fmt}** ({missao['dias_restantes']} dias restantes)")
    with c2:
        st.markdown(f"<div style='text-align: right; font-weight: 700; font-size: 1.15rem; color: var(--text-primary);'>{formatar_moeda_br(missao['valor_nominal'])}</div>", unsafe_allow_html=True)
        if missao['valor_ja_pago'] > 0:
            st.caption(f"<div style='text-align: right;'>Pago: :green[{formatar_moeda_br(missao['valor_ja_pago'])}]</div>", unsafe_allow_html=True)

    pct = min(1.0, missao["percentual_coberto"] / 100.0)
    st.progress(pct, text=f"Cobertura: {missao['percentual_coberto']:.1f}% ({formatar_moeda_br(missao['valor_ja_pago'] + missao['valor_reservado'])})")

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.caption(f"🛡️ Reserva Virtual: **{formatar_moeda_br(missao['valor_reservado'])}**")
    with col_m2:
        st.caption(f"🎯 Falta Cobrir: **:orange[{formatar_moeda_br(missao['saldo_devedor_restante'])}]**")

    if st.button("Gerenciar Missão ➔", key="btn_ir_missao_vg", use_container_width=True):
        st.session_state["pagina_ativa"] = "🎯 Planejamento & Metas"
        st.rerun()


def render_conteudo_bloco_caixa_7dias(df: pd.DataFrame):
    """Card resumido da Necessidade de Caixa dos Próximos 7 Dias."""
    conn = conectar()
    caixa = planejamento_service.calcular_necessidade_caixa_7dias(conn, data_referencia=date.today())
    conn.close()

    nec = caixa["necessidade_adicional_caixa"]
    if nec > 0:
        st.markdown(f"**Necessidade Adicional:** <span style='font-size: 1.25rem; font-weight: 800; color: #ef4444;'>{formatar_moeda_br(nec)}</span>", unsafe_allow_html=True)
        dt_limite_fmt = datetime.strptime(caixa['data_limite_7d'], '%Y-%m-%d').strftime('%d/%m')
        st.caption(f"Dinheiro novo necessário para cobrir compromissos até **{dt_limite_fmt}**")
    else:
        st.markdown(f"**Situação:** <span style='font-size: 1.15rem; font-weight: 700; color: #10b981;'>✅ Caixa 100% Coberto</span>", unsafe_allow_html=True)
        st.caption("O saldo livre cobre com folga as obrigações dos próximos 7 dias.")

    c_c1, c_c2 = st.columns(2)
    with c_c1:
        st.caption(f"Obrigações 7d: **{formatar_moeda_br(caixa['total_confirmadas_7d'])}**")
        st.caption(f"Atrasadas Prioritárias: **{formatar_moeda_br(caixa['total_vencidas_prioritarias'])}**")
    with c_c2:
        st.caption(f"Saldo Livre: **{formatar_moeda_br(caixa['saldo_livre'])}**")
        st.caption(f"Gastos Essenciais: **{formatar_moeda_br(caixa['gastos_variaveis_semana'])}**")

    if caixa["total_pendente_confirmacao"] > 0:
        st.caption(f"ℹ️ *Acordo BV ({formatar_moeda_br(caixa['total_pendente_confirmacao'])}) em conciliação separada.*")

    if st.button("Ver Detalhes do Caixa ➔", key="btn_ir_caixa_vg", use_container_width=True):
        st.session_state["pagina_ativa"] = "🎯 Planejamento & Metas"
        st.rerun()


def render_conteudo_bloco_projecao_mes(df: pd.DataFrame):
    """Card de projeção de fechamento até o final do mês."""
    conn = conectar()
    proj = planejamento_service.calcular_projecao_mensal(conn, data_referencia=date.today())
    conn.close()

    saldo_proj = proj["saldo_final_projetado_sem_renda_app"]
    cor_proj = "#10b981" if saldo_proj >= 0 else "#ef4444"

    st.markdown(f"**Projeção Fim do Mês:** <span style='font-size: 1.2rem; font-weight: 800; color: {cor_proj};'>{formatar_moeda_br(saldo_proj)}</span>", unsafe_allow_html=True)
    dt_fim_fmt = datetime.strptime(proj['ultimo_dia_mes'], '%Y-%m-%d').strftime('%d/%m/%Y')
    st.caption(f"Fechamento até **{dt_fim_fmt}** (sem antecipar rendas incertas)")

    c_p1, c_p2 = st.columns(2)
    with c_p1:
        st.caption(f"Obrigações Mês: **{formatar_moeda_br(proj['total_obrigacoes_confirmadas'])}**")
        st.caption(f"Variáveis Estimadas: **{formatar_moeda_br(proj['total_variaveis_restantes'])}**")
    with c_p2:
        st.caption(f"Saldo Atual: **{formatar_moeda_br(proj['saldo_atual'])}**")
        st.caption(f"Reservas Alocadas: **{formatar_moeda_br(proj['total_reservas_virtuais'])}**")

    if st.button("Ver Planejamento Mensal ➔", key="btn_ir_proj_vg", use_container_width=True):
        st.session_state["pagina_ativa"] = "🎯 Planejamento & Metas"
        st.rerun()


def render_conteudo_bloco_capacidade_trabalho(df: pd.DataFrame, df_turnos: pd.DataFrame):
    """Card resumido de capacidade operacional do motorista."""
    conn = conectar()
    caixa = planejamento_service.calcular_necessidade_caixa_7dias(conn, data_referencia=date.today())
    cur = conn.cursor()
    cur.execute("SELECT dias_disponiveis, horas_disponiveis_dia, ganho_bruto_hora_estimado, combustivel_hora_estimado FROM planejamento_simulacao_trabalho ORDER BY id DESC LIMIT 1")
    row_sim = cur.fetchone()
    conn.close()

    if row_sim:
        dias, horas_dia, g_h, c_h = row_sim
    else:
        dias, horas_dia, g_h, c_h = 5, 4.0, 35.0, 10.0

    viab = planejamento_service.calcular_viabilidade_metas_trabalho(
        necessidade_financeira=caixa["necessidade_adicional_caixa"],
        dias_disponiveis=int(dias),
        horas_disponiveis_dia=float(horas_dia),
        ganho_bruto_hora=float(g_h),
        combustivel_hora=float(c_h)
    )

    cor_badge = "#10b981" if viab["status_viabilidade"] in ("coberta", "coberta_folga") else "#ef4444"
    st.markdown(f"**Viabilidade Semanal:** <span style='font-size: 0.92rem; font-weight: 700; color: {cor_badge};'>{viab['rotulo_viabilidade']}</span>", unsafe_allow_html=True)

    c_t1, c_t2 = st.columns(2)
    with c_t1:
        st.caption(f"Jornada Disponível: **{viab['horas_disponiveis_total']:.1f}h** ({dias}d x {horas_dia}h)")
    with c_t2:
        st.caption(f"Horas Necessárias: **{viab['horas_necessarias']:.1f}h**")

    st.caption(f"Rendimento Líquido Estimado: **{formatar_moeda_br(viab['ganho_liquido_hora'])}/h**")

    if st.button("Simulador Completo ➔", key="btn_ir_sim_vg", use_container_width=True):
        st.session_state["pagina_ativa"] = "🎯 Planejamento & Metas"
        st.rerun()


def render_bloco(bloco_id: str, coluna: str, idx: int, total_na_coluna: int, df: pd.DataFrame, df_turnos: pd.DataFrame, saldo_atual: float):
    """Renderiza um bloco modular no dashboard de acordo com seu ID e coluna."""
    with st.container(border=True, key=f"card_{bloco_id}"):
        if bloco_id == "contas":
            c_act = render_cabecalho_bloco("🏦 Minhas Contas", "contas", coluna, idx, total_na_coluna, tem_botao_acao=True)
            if c_act and c_act.button("+ Conta", key="btn_add_cta_vg", use_container_width=True):
                modal_nova_conta()
            render_conteudo_bloco_contas(df, saldo_atual)

        elif bloco_id == "cartoes":
            c_act = render_cabecalho_bloco("💳 Meus Cartões", "cartoes", coluna, idx, total_na_coluna, tem_botao_acao=True)
            if c_act and c_act.button("+ Cartão", key="btn_add_crd_vg", use_container_width=True):
                modal_novo_cartao()
            render_conteudo_bloco_cartoes(df)

        elif bloco_id == "paga_leve":
            c_act = render_cabecalho_bloco("⚡ Paga Leve (Pix 4x)", "paga_leve", coluna, idx, total_na_coluna, tem_botao_acao=True)
            if c_act and c_act.button("+ Compra", key="btn_add_pl_vg", use_container_width=True):
                modal_paga_leve()
            render_conteudo_bloco_paga_leve(df)

        elif bloco_id == "limites":
            render_cabecalho_bloco("🎯 Orçamento & Limites", "limites", coluna, idx, total_na_coluna)
            render_conteudo_bloco_limites(df)

        elif bloco_id == "contas_pagar":
            render_cabecalho_bloco("🚨 Contas a Pagar", "contas_pagar", coluna, idx, total_na_coluna)
            render_conteudo_bloco_contas_pagar(df)

        elif bloco_id == "maiores_gastos":
            render_cabecalho_bloco("📊 Maiores Gastos", "maiores_gastos", coluna, idx, total_na_coluna)
            render_conteudo_bloco_maiores_gastos(df)

        elif bloco_id == "turnos":
            render_cabecalho_bloco("🚕 Últimos Turnos (99/Uber)", "turnos", coluna, idx, total_na_coluna)
            render_conteudo_bloco_turnos(df_turnos)

        elif bloco_id == "missao_ipva":
            render_cabecalho_bloco("🎯 Missão: IPVA 2025/2026", "missao_ipva", coluna, idx, total_na_coluna)
            render_conteudo_bloco_missao_ipva(df)

        elif bloco_id == "caixa_7dias":
            render_cabecalho_bloco("🗓️ Caixa dos Próximos 7 Dias", "caixa_7dias", coluna, idx, total_na_coluna)
            render_conteudo_bloco_caixa_7dias(df)

        elif bloco_id == "projecao_mes":
            render_cabecalho_bloco("📈 Projeção Fim do Mês", "projecao_mes", coluna, idx, total_na_coluna)
            render_conteudo_bloco_projecao_mes(df)

        elif bloco_id == "capacidade_trabalho":
            render_cabecalho_bloco("⏱️ Capacidade de Trabalho (App)", "capacidade_trabalho", coluna, idx, total_na_coluna)
            render_conteudo_bloco_capacidade_trabalho(df, df_turnos)


def render_visao_geral(df: pd.DataFrame, df_turnos: pd.DataFrame):
    """
    PÁGINA 1: VISÃO GERAL
    Dashboard com KPIs executivos, resumo de contas, pendências imediatas e maiores gastos.
    Suporta reordenação interativa de blocos por botões (▲ ▼ ⇄), modal organizador e arrastar e soltar (Drag & Drop).
    """
    render_barra_acoes_rapidas()

    hoje = date.today()
    ano_atual = hoje.year
    mes_atual = hoje.month
    inicio_mes_str = f"{ano_atual}-{mes_atual:02d}-01"
    ultimo_dia_mes = calendar.monthrange(ano_atual, mes_atual)[1]
    fim_mes_str = f"{ano_atual}-{mes_atual:02d}-{ultimo_dia_mes:02d}"

    meses_nomes = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    nome_mes = meses_nomes.get(mes_atual, f"Mês {mes_atual}")

    # 1. Saldo em contas efetivado (disponível real) via Serviço Centralizado
    conn_saldo = conectar()
    res_saldo_consolidado = saldo_service.calcular_saldo_consolidado(conn_saldo)
    saldo_atual = float(res_saldo_consolidado["saldo_consolidado"])
    conn_saldo.close()

    # 2. Obrigações e receitas estritamente do mês atual (Outubro)
    df_outubro = df[(df["data"] >= inicio_mes_str) & (df["data"] <= fim_mes_str)]
    if "afeta_saldo_bancario" in df_outubro.columns:
        df_outubro_caixa = df_outubro[(df_outubro["afeta_saldo_bancario"] == 1) | (df_outubro["afeta_saldo_bancario"].isna())]
    else:
        df_outubro_caixa = df_outubro
    obrigacoes_outubro_pendentes = df_outubro_caixa[(df_outubro_caixa["tipo"] == "despesa") & (df_outubro_caixa["pago"] == 0)]["valor"].sum()
    receitas_outubro_pendentes = df_outubro[(df_outubro["tipo"] == "receita") & (df_outubro["pago"] == 0)]["valor"].sum()

    # 3. Previsão de fim de mês estritamente de Outubro (Regras 1, 6 e 10)
    # Sem dupla contagem: saldo disponível + receitas futuras de outubro - obrigações de outubro
    saldo_previsto_fim_mes = saldo_atual + receitas_outubro_pendentes - obrigacoes_outubro_pendentes

    # 4. Dívidas antigas (setembro para trás) voluntariamente selecionadas (Regras 3, 5 e 6)
    if "dividas_antigas_selecionadas" not in st.session_state:
        st.session_state["dividas_antigas_selecionadas"] = carregar_dividas_antigas_selecionadas()

    df_antigas_pend = df[(df["tipo"] == "despesa") & (df["pago"] == 0) & (df["data"] < inicio_mes_str)]
    ids_antigas_validos = set(df_antigas_pend["id"].tolist())
    st.session_state["dividas_antigas_selecionadas"] = st.session_state["dividas_antigas_selecionadas"].intersection(ids_antigas_validos)
    total_antigas_selecionadas = df_antigas_pend[df_antigas_pend["id"].isin(st.session_state["dividas_antigas_selecionadas"])]["valor"].sum()

    # 5. Cálculo dos dias restantes e dias de trabalho planejados (Regra 7)
    dias_calendario_restantes = max(1, ultimo_dia_mes - hoje.day + 1)
    if "dias_trabalho_planejados" not in st.session_state:
        st.session_state["dias_trabalho_planejados"] = carregar_dias_trabalho_planejados(dias_calendario_restantes)

    dias_trabalho = min(st.session_state["dias_trabalho_planejados"], dias_calendario_restantes)
    dias_trabalho = max(1, dias_trabalho)

    # 6. Meta líquida de trabalho (Regras 6, 8 e 9)
    # Total de obrigações consideradas na meta = obrigações de outubro + dívidas antigas incluídas voluntariamente
    total_obrigacoes_meta = obrigacoes_outubro_pendentes + total_antigas_selecionadas
    saldo_projetado_meta = saldo_atual + receitas_outubro_pendentes - total_obrigacoes_meta

    # Regra 9: Se já coberto, meta = R$ 0,00, sem exibir valor negativo
    falta_cobrir = max(0.0, -saldo_projetado_meta)
    meta_dia = falta_cobrir / dias_trabalho if dias_trabalho > 0 else 0.0

    # Linha de Métricas Estilo Cartões Modernos
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(
            label="🟢 Saldo em Contas (Efetivado)",
            value=f"R$ {saldo_atual:,.2f}",
            help="Soma de todas as receitas recebidas menos despesas já pagas em conta"
        )
    with m2:
        st.metric(
            label=f"📉 Obrigações {nome_mes} (Pendentes)",
            value=f"R$ {obrigacoes_outubro_pendentes:,.2f}",
            delta=f"- R$ {obrigacoes_outubro_pendentes:,.2f}" if obrigacoes_outubro_pendentes > 0 else None,
            delta_color="inverse",
            help=f"Total de contas com vencimento em {nome_mes} que ainda não foram pagas"
        )
    with m3:
        cor_previsto = "normal" if saldo_previsto_fim_mes >= 0 else "inverse"
        st.metric(
            label=f"🎯 Previsão Fim de {nome_mes}",
            value=f"R$ {saldo_previsto_fim_mes:,.2f}",
            delta="Superávit Previsto" if saldo_previsto_fim_mes >= 0 else "Déficit Previsto",
            delta_color=cor_previsto,
            help=f"Saldo atual + receitas a receber em {nome_mes} - obrigações de {nome_mes}"
        )
    with m4:
        st.metric(
            label=f"🚕 Meta Líquida/Dia ({dias_trabalho}d trab)",
            value=f"R$ {meta_dia:,.2f}/dia",
            delta=f"Falta rodar R$ {falta_cobrir:,.2f}" if falta_cobrir > 0 else "✅ 100% Coberto",
            delta_color="inverse" if falta_cobrir > 0 else "normal",
            help=f"Valor líquido diário necessário em {dias_trabalho} dias de trabalho para quitar as obrigações consideradas"
        )

    # Barra de Planejamento de Trabalho da Meta (Regras 7, 8, 9 e 10)
    with st.container(border=True):
        c_pl1, c_pl2, c_pl3 = st.columns([2.5, 1.2, 1.3], vertical_alignment="center")
        with c_pl1:
            st.markdown(f"**🚕 Planejamento de Trabalho & Meta ({nome_mes})**")
            info_antigas = f" | Dívidas antigas incluídas: **R$ {total_antigas_selecionadas:,.2f}**" if total_antigas_selecionadas > 0 else ""
            st.caption(f"Restam **{dias_calendario_restantes} dias corridos** no mês{info_antigas}. Defina quantos dias pretende trabalhar:")
        with c_pl2:
            dias_selecionados = st.number_input(
                "Dias de trabalho planejados:",
                min_value=1,
                max_value=dias_calendario_restantes,
                value=dias_trabalho,
                step=1,
                label_visibility="collapsed",
                key="num_dias_trabalho_input"
            )
            if dias_selecionados != st.session_state["dias_trabalho_planejados"]:
                st.session_state["dias_trabalho_planejados"] = dias_selecionados
                salvar_dias_trabalho_planejados(dias_selecionados)
                st.rerun()
        with c_pl3:
            if falta_cobrir > 0:
                st.markdown(f"**Líquido Total Necessário:** :red[R$ {falta_cobrir:,.2f}]")
                st.caption(f"Meta de trabalho: :orange[**R$ {meta_dia:,.2f} líq/dia**]")
            else:
                st.markdown(f"**Situação:** :green[**Obrigações já cobertas!**]")
                st.caption(f"Meta líquida necessária: :green[**R$ 0,00/dia**]")

    # Carrega ou sincroniza as posições salvas dos blocos
    if "blocos_col_esq" not in st.session_state or "blocos_col_dir" not in st.session_state:
        col_esq_carregada, col_dir_carregada, vis_carregada = carregar_layout_dashboard()
        st.session_state["blocos_col_esq"] = col_esq_carregada
        st.session_state["blocos_col_dir"] = col_dir_carregada
        st.session_state["blocos_visiveis"] = vis_carregada

    st.write("")

    # Barra de controle do painel de blocos
    col_dash_info, col_dash_actions = st.columns([2.8, 1.2], vertical_alignment="center")
    with col_dash_info:
        st.markdown("##### 📌 Painel de Controle Personalizável")
        st.caption("Reorganize os blocos usando os botões **▲ ▼ ⇄** em cada cartão ou pelo botão **'Organizar'**.")
    with col_dash_actions:
        b_org, b_rst = st.columns([1.3, 1.0])
        with b_org:
            if st.button("⚙️ Organizar", use_container_width=True, type="secondary", help="Abrir painel de organização de blocos"):
                modal_organizar_blocos()
        with b_rst:
            if st.button("🔄 Padrão", use_container_width=True, help="Restaurar posições originais dos blocos"):
                restaurar_layout_padrao()

    # Injeção do motor JavaScript de arrastar e soltar (Drag & Drop)
    injetar_script_cards_arrastaveis()

    col_esq, col_dir = st.columns([1.1, 1.4], gap="large")

    blocos_esq = [b for b in st.session_state["blocos_col_esq"] if st.session_state.get("blocos_visiveis", {}).get(b, True)]
    blocos_dir = [b for b in st.session_state["blocos_col_dir"] if st.session_state.get("blocos_visiveis", {}).get(b, True)]

    with col_esq:
        if not blocos_esq:
            st.info("Nenhum bloco na coluna esquerda. Mova blocos para cá usando '⇄' nos cartões da direita ou em '⚙️ Organizar'.")
        for idx, b_id in enumerate(blocos_esq):
            render_bloco(b_id, "esq", idx, len(blocos_esq), df, df_turnos, saldo_atual)

    with col_dir:
        if not blocos_dir:
            st.info("Nenhum bloco na coluna direita. Mova blocos para cá usando '⇄' nos cartões da esquerda ou em '⚙️ Organizar'.")
        for idx, b_id in enumerate(blocos_dir):
            render_bloco(b_id, "dir", idx, len(blocos_dir), df, df_turnos, saldo_atual)


def render_lancamentos(df: pd.DataFrame):
    """
    PÁGINA 2: LANÇAMENTOS (EXTRATO DETALHADO ESTILO ORGANIZZE)
    Extrato com filtros temporais (Diário, Semanal, Mensal e Todos),
    filtros por status/tipo/conta/busca e toggles interativos de pagamento.
    """
    render_barra_acoes_rapidas()

    meses_nomes = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    hoje = date.today()

    # Estado da escala temporal
    if "lancamentos_escala" not in st.session_state:
        st.session_state["lancamentos_escala"] = "🗓️ Mensal"

    # BARRA 1: FILTRO TEMPORAL (MENSAL, SEMANAL, DIÁRIO, TODOS)
    with st.container(border=True):
        c_escala, c_navegacao = st.columns([1.6, 2.8], vertical_alignment="center")
        
        with c_escala:
            escala_tempo = st.segmented_control(
                "Escala Temporal",
                options=["🗓️ Mensal", "📆 Semanal", "📅 Diário", "🌐 Todos"],
                default=st.session_state["lancamentos_escala"],
                label_visibility="collapsed"
            )
            if escala_tempo and escala_tempo != st.session_state["lancamentos_escala"]:
                st.session_state["lancamentos_escala"] = escala_tempo
                st.rerun()

        escala_atual = st.session_state["lancamentos_escala"]

        # Navegador contextual dependendo da escala escolhida
        with c_navegacao:
            if "Mensal" in escala_atual:
                if not df.empty and "data" in df.columns:
                    df_dt = pd.to_datetime(df["data"], errors="coerce").dropna()
                    if not df_dt.empty:
                        meses_periodos = df_dt.dt.to_period("M").drop_duplicates().sort_values(ascending=False)
                        opcoes_mes = [f"{meses_nomes[p.month]} / {p.year}" for p in meses_periodos]
                    else:
                        opcoes_mes = []
                else:
                    opcoes_mes = []

                mes_atual_str = f"{meses_nomes[hoje.month]} / {hoje.year}"
                if mes_atual_str not in opcoes_mes:
                    opcoes_mes.insert(0, mes_atual_str)

                c_m1, c_m2 = st.columns([2.4, 1.2], vertical_alignment="center")
                mes_selecionado = c_m1.selectbox("Mês de Referência", opcoes_mes, index=0, label_visibility="collapsed")
                c_m2.caption(f"🗓️ {mes_selecionado}")

            elif "Semanal" in escala_atual:
                segunda_atual = hoje - timedelta(days=hoje.weekday())
                domingo_atual = segunda_atual + timedelta(days=6)
                
                opcoes_semana = {
                    f"Semana Atual ({segunda_atual.strftime('%d/%m')} a {domingo_atual.strftime('%d/%m/%Y')})": (segunda_atual, domingo_atual),
                    f"Semana Passada ({(segunda_atual - timedelta(days=7)).strftime('%d/%m')} a {(domingo_atual - timedelta(days=7)).strftime('%d/%m/%Y')})": (segunda_atual - timedelta(days=7), domingo_atual - timedelta(days=7)),
                    f"Semana Retrasada ({(segunda_atual - timedelta(days=14)).strftime('%d/%m')} a {(domingo_atual - timedelta(days=14)).strftime('%d/%m/%Y')})": (segunda_atual - timedelta(days=14), domingo_atual - timedelta(days=14)),
                    f"Próxima Semana ({(segunda_atual + timedelta(days=7)).strftime('%d/%m')} a {(domingo_atual + timedelta(days=7)).strftime('%d/%m/%Y')})": (segunda_atual + timedelta(days=7), domingo_atual + timedelta(days=7)),
                }
                c_s1, c_s2 = st.columns([2.6, 1.2], vertical_alignment="center")
                semana_sel_label = c_s1.selectbox("Semana de Referência", list(opcoes_semana.keys()), index=0, label_visibility="collapsed")
                c_s2.caption("📆 Segunda a Domingo")

            elif "Diário" in escala_atual:
                c_d1, c_d2 = st.columns([2, 1.8], vertical_alignment="center")
                dia_selecionado = c_d1.date_input("Dia Específico", hoje, label_visibility="collapsed")
                c_d2.caption(f"📅 Visualizando: **{dia_selecionado.strftime('%d/%m/%Y')}**")

            else:
                st.caption("🌐 Exibindo todos os lançamentos históricos sem filtro de período.")

    # Barra de Filtros limpa e horizontal
    with st.container(border=True):
        f1, f2, f3, f4 = st.columns([1.5, 1.2, 1.5, 2])
        filtro_status = f1.segmented_control(
            "Status",
            options=["Todos", "Pagos (👍)", "Pendentes (👎)"],
            default="Todos",
            label_visibility="collapsed"
        )
        filtro_tipo = f2.selectbox(
            "Tipo",
            options=["Todos os Tipos", "Despesas", "Receitas"],
            label_visibility="collapsed"
        )
        contas_disponiveis = ["Todas as Contas"] + obter_contas_disponiveis()
        filtro_conta = f3.selectbox(
            "Conta",
            options=contas_disponiveis,
            label_visibility="collapsed"
        )
        busca = f4.text_input(
            "Busca",
            placeholder="🔍 Buscar lançamento por descrição...",
            label_visibility="collapsed"
        )

    # Aplicação dos filtros
    df_lista = df.copy()
    df_lista["dt"] = pd.to_datetime(df_lista["data"], errors="coerce")
    periodo_texto = "Período"

    if "Mensal" in escala_atual:
        nome_mes, ano_str = mes_selecionado.split(" / ")
        mapa_meses = {v: k for k, v in meses_nomes.items()}
        num_mes = mapa_meses[nome_mes]
        num_ano = int(ano_str)
        df_lista = df_lista[(df_lista["dt"].dt.month == num_mes) & (df_lista["dt"].dt.year == num_ano)]
        periodo_texto = mes_selecionado

    elif "Semanal" in escala_atual:
        inicio_sem, fim_sem = opcoes_semana[semana_sel_label]
        df_lista = df_lista[(df_lista["dt"].dt.date >= inicio_sem) & (df_lista["dt"].dt.date <= fim_sem)]
        periodo_texto = f"{inicio_sem.strftime('%d/%m')} a {fim_sem.strftime('%d/%m/%Y')}"

    elif "Diário" in escala_atual:
        df_lista = df_lista[df_lista["dt"].dt.date == dia_selecionado]
        periodo_texto = dia_selecionado.strftime("%d/%m/%Y")

    else:
        periodo_texto = "Histórico Completo"

    if filtro_status == "Pendentes (👎)":
        df_lista = df_lista[df_lista["pago"] == 0]
    elif filtro_status == "Pagos (👍)":
        df_lista = df_lista[df_lista["pago"] == 1]

    if filtro_tipo == "Despesas":
        df_lista = df_lista[df_lista["tipo"] == "despesa"]
    elif filtro_tipo == "Receitas":
        df_lista = df_lista[df_lista["tipo"] == "receita"]

    if filtro_conta != "Todas as Contas":
        df_lista = df_lista[df_lista["conta"] == filtro_conta]

    if busca.strip():
        df_lista = df_lista[df_lista["descricao"].str.contains(busca, case=False, na=False)]

    if df_lista.empty:
        st.info(f"Nenhum lançamento encontrado para **{periodo_texto}** com os filtros selecionados.")
        return

    # Divisão em duas colunas: Extrato à esquerda e Resumo Financeiro à direita
    col_extrato, col_resumo = st.columns([2.6, 1.1], gap="medium")

    with col_extrato:
        datas_unicas = df_lista["data"].dropna().unique()

        for data_atual in datas_unicas:
            try:
                data_formatada = pd.to_datetime(data_atual).strftime("%d/%m/%Y")
            except Exception:
                data_formatada = str(data_atual)
            st.markdown(f"<div class='dia-header'>📅 {data_formatada}</div>", unsafe_allow_html=True)

            itens_do_dia = df_lista[df_lista["data"] == data_atual]

            for _, item in itens_do_dia.iterrows():
                icone = obter_icone_categoria(item["categoria"])
                eh_receita = item["tipo"] == "receita"
                p_val = int(item["pago"]) if pd.notna(item["pago"]) else 0
                esta_pago = (p_val == 1)

                with st.container(border=True):
                    l1, l2, l3, l4, l5 = st.columns([3.5, 1.8, 1.6, 0.8, 0.6], vertical_alignment="center")

                    with l1:
                        if p_val == 1:
                            cor_tag = ":green[(Pago)]"
                        elif p_val == 2:
                            cor_tag = ":orange[(Parcial)]"
                        else:
                            cor_tag = ":orange[(Pendente)]"
                        st.markdown(f"**{icone} {item['descricao']}** {cor_tag}")
                        st.caption(f"Categoria: {item['categoria']} • Vencimento: {pd.to_datetime(item['data']).strftime('%d/%m/%Y')}")

                    with l2:
                        st.caption("Conta")
                        st.markdown(f"🏦 {item['conta']}")

                    with l3:
                        sinal = "+" if eh_receita else "-"
                        if eh_receita:
                            cor_val = "green"
                        else:
                            cor_val = "green" if p_val == 1 else ("orange" if p_val == 2 else "red")
                        st.markdown(f":{cor_val}[**{sinal} R$ {item['valor']:,.2f}**]")

                    with l4:
                        if eh_receita:
                            emoji_joinha = "👍" if esta_pago else "👎"
                            ajuda = "Marcar como Não Recebido" if esta_pago else "Marcar como Recebido"
                            if st.button(emoji_joinha, key=f"btn_pago_{item['id']}", help=ajuda):
                                alternar_status_pago(item["id"], item["pago"])
                                st.rerun()
                        else:
                            if p_val == 1:
                                if st.button("👍", key=f"btn_pago_{item['id']}", help="Ver histórico ou estornar pagamento"):
                                    modal_historico_pagamento(item["id"])
                            elif p_val == 2:
                                if st.button("⚡", key=f"btn_pago_{item['id']}", help="Pagamento parcial. Clique para quitar o restante ou ver histórico"):
                                    modal_historico_pagamento(item["id"])
                            else:
                                if st.button("👎", key=f"btn_pago_{item['id']}", help="Confirmar / Registrar Pagamento"):
                                    modal_registrar_pagamento(item["id"])

                    with l5:
                        if st.button("🗑️", key=f"btn_del_{item['id']}", help="Excluir lançamento"):
                            excluir_transacao(item["id"])
                            st.rerun()

            # Saldo acumulado até o final do dia
            df_ate_data = df[(df["data"] <= data_atual) & (df["pago"] == 1)]
            rec_ate = df_ate_data[df_ate_data["tipo"] == "receita"]["valor"].sum()
            desp_ate = df_ate_data[df_ate_data["tipo"] == "despesa"]["valor"].sum()
            saldo_no_dia = rec_ate - desp_ate

            st.markdown(
                f"<div class='saldo-dia'>Saldo efetivado até este dia: <span>R$ {saldo_no_dia:,.2f}</span></div>",
                unsafe_allow_html=True
            )

    with col_resumo:
        with st.container(border=True):
            st.markdown(f"##### 📌 Resumo ({periodo_texto})")
            
            rec_paga = df_lista[(df_lista["tipo"] == "receita") & (df_lista["pago"] == 1)]["valor"].sum()
            rec_tot = df_lista[df_lista["tipo"] == "receita"]["valor"].sum()
            
            desp_tot = df_lista[df_lista["tipo"] == "despesa"]["valor"].sum()
            
            conn_res = conectar()
            cur_res = conn_res.cursor()
            cur_res.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pagamentos_despesas'")
            tem_pag_tbl = cur_res.fetchone() is not None
            
            desp_paga = 0.0
            if tem_pag_tbl and "Mensal" in escala_atual:
                ano_mes_str = f"{num_ano}-{num_mes:02d}"
                cur_res.execute("""
                    SELECT COALESCE(SUM(valor_pago), 0)
                    FROM pagamentos_despesas
                    WHERE cancelado = 0 AND strftime('%Y-%m', data_pagamento) = ?
                """, (ano_mes_str,))
                desp_pags_mes = cur_res.fetchone()[0] or 0.0
                
                cur_res.execute("SELECT DISTINCT transacao_id FROM pagamentos_despesas WHERE cancelado = 0")
                ids_com_pag = set(r[0] for r in cur_res.fetchall())
                desp_legadas = df_lista[(df_lista["tipo"] == "despesa") & (df_lista["pago"] == 1) & (~df_lista["id"].isin(ids_com_pag))]["valor"].sum()
                desp_paga = float(desp_pags_mes) + float(desp_legadas)
            else:
                desp_paga = df_lista[(df_lista["tipo"] == "despesa") & (df_lista["pago"] == 1)]["valor"].sum()
            
            conn_res.close()
            
            saldo_atual_res = rec_paga - desp_paga
            contas_pend = df_lista[(df_lista["tipo"] == "despesa") & (df_lista["pago"] != 1)]["valor"].sum()
            saldo_previsto_res = saldo_atual_res - contas_pend

            st.markdown(f"**Receita Realizada:** :green[R$ {rec_paga:,.2f}]")
            st.caption(f"Previsto no período: R$ {rec_tot:,.2f}")
            st.write("")
            
            st.markdown(f"**Despesa Efetivamente Paga:** :red[- R$ {desp_paga:,.2f}]")
            st.caption(f"Total vencendo no período: - R$ {desp_tot:,.2f}")
            st.divider()

            st.markdown(f"#### Saldo Realizado: :blue[R$ {saldo_atual_res:,.2f}]")
            cor_prev = ":green" if saldo_previsto_res >= 0 else ":red"
            st.markdown(f"#### Saldo Previsto: {cor_prev}[R$ {saldo_previsto_res:,.2f}]")


# =============================================================================
# NOVA PÁGINA: CENTRAL DO MOTORISTA DE APP (UBER & 99)
# =============================================================================
def render_motorista_app(df_transacoes: pd.DataFrame, df_turnos: pd.DataFrame):
    """
    PÁGINA DEDICADA: CENTRAL DO MOTORISTA (UBER & 99)
    Controle operacional completo: turnos, manutenções, rendimento por hora/km,
    visão semanal/mensal/anual e inteligência de horários mais rentáveis.
    """
    # Cabeçalho da Central do Motorista
    c_titulo, c_b1, c_b2 = st.columns([2.5, 1.2, 1.4], vertical_alignment="center")
    with c_titulo:
        st.subheader("🚕 Gestão Operacional • Motorista de App (Uber / 99)")
        st.caption("Controle detalhado de faturamento, manutenções, lucro por hora e inteligência de rotina.")
    with c_b1:
        if st.button("🚕 + Lançar Turno", use_container_width=True, type="primary"):
            modal_novo_turno()
    with c_b2:
        if st.button("🔧 + Manutenção / Carro", use_container_width=True):
            modal_despesa_veiculo()

    # Carrega dados de despesas específicas do carro
    conn = conectar()
    df_manut = pd.read_sql_query("SELECT * FROM despesas_veiculo ORDER BY data DESC", conn)
    conn.close()

    # Filtro de Período de Análise
    with st.container(border=True):
        f_per, f_ano = st.columns([3, 1], vertical_alignment="center")
        periodo_analise = f_per.segmented_control(
            "Período de Análise",
            options=["Mês Atual (Outubro)", "Últimos 30 Dias", "Ano 2026", "Todo o Histórico"],
            default="Mês Atual (Outubro)",
            label_visibility="collapsed"
        )
        f_ano.caption("📅 Dados sincronizados com o veículo")

    # Filtragem temporal dos turnos
    df_t = df_turnos.copy()
    hoje = date.today()

    if not df_t.empty and "data" in df_t.columns:
        df_t["data_dt"] = pd.to_datetime(df_t["data"])
        if periodo_analise == "Mês Atual (Outubro)":
            df_t = df_t[(df_t["data_dt"].dt.month == hoje.month) & (df_t["data_dt"].dt.year == hoje.year)]
        elif periodo_analise == "Últimos 30 Dias":
            limite = hoje - timedelta(days=30)
            df_t = df_t[df_t["data_dt"].dt.date >= limite]
        elif periodo_analise == "Ano 2026":
            df_t = df_t[df_t["data_dt"].dt.year == 2026]

    # Cálculos operacionais dos turnos
    total_bruto = df_t["ganho_bruto"].sum() if not df_t.empty else 0.0
    total_combustivel = df_t["combustivel"].sum() if not df_t.empty else 0.0
    total_horas = df_t["horas"].sum() if not df_t.empty else 0.0
    total_km = df_t["km"].sum() if not df_t.empty else 0.0

    # Despesas do veículo no período (manutenções, seguro, etc.)
    df_m = df_manut.copy()
    if not df_m.empty:
        df_m["data_dt"] = pd.to_datetime(df_m["data"])
        if periodo_analise == "Mês Atual (Outubro)":
            df_m = df_m[(df_m["data_dt"].dt.month == hoje.month) & (df_m["data_dt"].dt.year == hoje.year)]
        elif periodo_analise == "Últimos 30 Dias":
            limite = hoje - timedelta(days=30)
            df_m = df_m[df_m["data_dt"].dt.date >= limite]
        elif periodo_analise == "Ano 2026":
            df_m = df_m[df_m["data_dt"].dt.year == 2026]
        total_manut = df_m["valor"].sum()
    else:
        total_manut = 0.0

    # Custos Operacionais Totais e Lucro Líquido Real
    custo_total_operacao = total_combustivel + total_manut
    lucro_liquido_real = total_bruto - custo_total_operacao
    margem_liquida = (lucro_liquido_real / total_bruto * 100) if total_bruto > 0 else 0.0

    # Rendimento por hora e por km
    bruto_hora = total_bruto / total_horas if total_horas > 0 else 0.0
    liquido_hora = lucro_liquido_real / total_horas if total_horas > 0 else 0.0
    custo_por_km = custo_total_operacao / total_km if total_km > 0 else 0.0
    lucro_por_km = lucro_liquido_real / total_km if total_km > 0 else 0.0

    # DASHBOARD DE KPIS PRINCIPAIS DO MOTORISTA
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric(
            label="💵 Faturamento Bruto",
            value=f"R$ {total_bruto:,.2f}",
            help="Soma de tudo o que entrou no aplicativo (Uber + 99)"
        )
    with k2:
        st.metric(
            label="⛽ Combustível + Manut.",
            value=f"R$ {custo_total_operacao:,.2f}",
            delta=f"- R$ {custo_total_operacao:,.2f}" if custo_total_operacao > 0 else None,
            delta_color="inverse",
            help="Gastos totais para trabalhar (Combustível + Oficina + Peças)"
        )
    with k3:
        cor_lucro = "normal" if lucro_liquido_real >= 0 else "inverse"
        st.metric(
            label="💰 Lucro Líquido Real",
            value=f"R$ {lucro_liquido_real:,.2f}",
            delta=f"Margem: {margem_liquida:.1f}%",
            delta_color=cor_lucro,
            help="O que realmente sobrou limpo no seu bolso após combustível e manutenções"
        )
    with k4:
        st.metric(
            label="⏱️ Lucro / Hora Líquida",
            value=f"R$ {liquido_hora:,.2f}/h",
            delta=f"Bruto: R$ {bruto_hora:,.2f}/h",
            help="Quanto você ganha limpo por cada hora de volante"
        )
    with k5:
        st.metric(
            label="🚗 Custo / KM Rodado",
            value=f"R$ {custo_por_km:,.2f}/km",
            delta=f"Lucro: R$ {lucro_por_km:,.2f}/km",
            delta_color="inverse",
            help="Custo real de rodagem por cada quilômetro percorrido"
        )

    st.write("")

    # ABAS DA CENTRAL DO MOTORISTA
    tab_turnos, tab_manutencao, tab_horarios, tab_periodos = st.tabs([
        "🕒 Turnos de Trabalho",
        "🔧 Manutenções & Despesas do Carro",
        "📈 Inteligência de Horários & Rentabilidade",
        "📅 Visão Temporal (Semanal / Mensal)"
    ])

    # ABA 1: TURNOS DE TRABALHO
    with tab_turnos:
        if df_t.empty:
            st.info("Nenhum turno registrado no período selecionado. Clique em '+ Lançar Turno' para adicionar seu dia de trabalho.")
        else:
            c_info1, c_info2 = st.columns([3, 1])
            with c_info1:
                st.markdown(f"**{len(df_t)} dias rodados** • Total de **{total_horas:.1f} horas** trabalhadas e **{total_km:,.0f} km** percorridos.")
            with c_info2:
                media_horas_dia = total_horas / len(df_t) if len(df_t) > 0 else 0
                st.caption(f"Média diária: **{media_horas_dia:.1f} horas/dia**")

            # Tabela organizada de turnos com opção de exclusão
            for _, t_row in df_t.sort_values(by="data", ascending=False).iterrows():
                dt_str = datetime.strptime(t_row["data"], "%Y-%m-%d").strftime("%d/%m/%Y")
                liq_t = t_row["ganho_bruto"] - t_row["combustivel"]
                ganho_h = liq_t / t_row["horas"] if t_row["horas"] > 0 else 0
                per_t = t_row.get("periodo", "Noite")

                with st.container(border=True):
                    col_t1, col_t2, col_t3, col_t4, col_t5, col_t6 = st.columns([2.4, 1.7, 1.7, 1.7, 0.6, 0.6], vertical_alignment="center")
                    with col_t1:
                        plat_nome = t_row.get("plataforma") or "99"
                        st.markdown(f"🗓️ **{dt_str}** • `{per_t}` • `{plat_nome}`")
                        obs_txt = t_row.get("observacao")
                        if obs_txt:
                            st.caption(f"📝 {obs_txt}")
                        else:
                            st.caption(f"Trabalho: {t_row['horas']} horas • {t_row['km']} km")
                    with col_t2:
                        st.caption("Faturamento Bruto")
                        st.markdown(f"**R$ {t_row['ganho_bruto']:,.2f}**")
                    with col_t3:
                        st.caption("Combustível")
                        st.markdown(f":red[- R$ {t_row['combustivel']:,.2f}]")
                    with col_t4:
                        st.caption("Lucro Líquido (R$/h)")
                        st.markdown(f":green[**R$ {liq_t:,.2f}**] `(R$ {ganho_h:.2f}/h)`")
                    with col_t5:
                        if st.button("✏️", key=f"edit_t_{t_row['id']}", help="Editar métricas operacionais deste turno"):
                            modal_editar_turno(t_row["id"])
                    with col_t6:
                        if st.button("🗑️", key=f"del_t_{t_row['id']}", help="Excluir este turno operacional (preserva extrato bancário)"):
                            excluir_turno(t_row["id"])
                            st.rerun()

    # ABA 2: MANUTENÇÕES E DESPESAS DO VEÍCULO
    with tab_manutencao:
        st.markdown("##### 🚗 Despesas Operacionais e Manutenções do Carro")
        st.caption("Acompanhe trocas de óleo, pneus, freios, seguros e impostos para não ser pego de surpresa.")

        m_col1, m_col2 = st.columns([1, 1])
        with m_col1:
            with st.container(border=True):
                st.markdown("###### 🚨 Alertas de Manutenção Preventiva")
                if not df_m.empty and df_m["proxima_troca_km"].notnull().any():
                    trocas = df_m[df_m["proxima_troca_km"] > 0].sort_values(by="proxima_troca_km", ascending=True)
                    for _, tr in trocas.head(3).iterrows():
                        st.markdown(f"🔧 **{tr['tipo']}**: Próxima revisão aos **{tr['proxima_troca_km']:,.0f} KM**")
                        st.caption(f"Última em {tr['data']} aos {tr['km_atual']:,.0f} KM • {tr['descricao']}")
                else:
                    st.info("Cadastre uma manutenção preventiva para acompanhar o alerta de próxima troca em KM.")

        with m_col2:
            with st.container(border=True):
                st.markdown("###### 📊 Resumo de Gastos com o Veículo")
                st.markdown(f"**Total de Gastos no Período:** :red[R$ {total_manut:,.2f}]")
                if not df_m.empty:
                    por_tipo = df_m.groupby("tipo")["valor"].sum()
                    for tp, val in por_tipo.items():
                        st.caption(f"• {tp}: **R$ {val:,.2f}**")

        st.write("")
        st.markdown("###### Histórico de Manutenções Registradas")
        if df_m.empty:
            st.info("Nenhuma manutenção ou despesa de veículo registrada ainda. Use o botão '+ Manutenção / Carro' acima.")
        else:
            for _, man_row in df_m.iterrows():
                dt_format = datetime.strptime(man_row["data"], "%Y-%m-%d").strftime("%d/%m/%Y")
                with st.container(border=True):
                    mc1, mc2, mc3, mc4 = st.columns([3, 1.5, 1.5, 0.6], vertical_alignment="center")
                    with mc1:
                        st.markdown(f"🔧 **{man_row['descricao']}**")
                        km_info = f"aos {man_row['km_atual']:,.0f} KM" if man_row['km_atual'] else ""
                        st.caption(f"{dt_format} • {man_row['tipo']} {km_info}")
                    with mc2:
                        st.caption("Conta de Pagamento")
                        st.markdown(f"🏦 {man_row['conta']}")
                    with mc3:
                        st.caption("Valor Pago")
                        st.markdown(f":red[**- R$ {man_row['valor']:,.2f}**]")
                    with mc4:
                        if st.button("🗑️", key=f"del_m_{man_row['id']}", help="Excluir registro"):
                            excluir_despesa_veiculo(man_row["id"])
                            st.rerun()

    # ABA 3: INTELIGÊNCIA DE HORÁRIOS & RENTABILIDADE
    with tab_horarios:
        st.markdown("##### 📈 Em qual horário você ganha mais por hora?")
        st.caption("Identifique qual período do dia entrega o maior retorno financeiro para otimizar sua rotina.")

        if df_t.empty:
            st.info("Cadastre turnos de trabalho para visualizar o comparativo de rentabilidade por período do dia.")
        else:
            # Agrupa dados por período do dia
            df_t["lucro_t"] = df_t["ganho_bruto"] - df_t["combustivel"]
            por_periodo = df_t.groupby("periodo").agg({
                "horas": "sum",
                "ganho_bruto": "sum",
                "combustivel": "sum",
                "lucro_t": "sum",
                "id": "count"
            }).reset_index()

            por_periodo["lucro_por_hora"] = por_periodo["lucro_t"] / por_periodo["horas"]
            por_periodo["bruto_por_hora"] = por_periodo["ganho_bruto"] / por_periodo["horas"]
            por_periodo = por_periodo.sort_values(by="lucro_por_hora", ascending=False)

            c_h1, c_h2 = st.columns([1.5, 1])
            with c_h1:
                st.markdown("###### Comparativo: Lucro Líquido Real por Hora (R$/h)")
                chart_data = por_periodo.set_index("periodo")["lucro_por_hora"]
                st.bar_chart(chart_data)

            with c_h2:
                st.markdown("###### Ranking de Rentabilidade")
                for rank, (_, row_p) in enumerate(por_periodo.iterrows(), start=1):
                    emoji_medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else "🥉")
                    with st.container(border=True):
                        st.markdown(f"**{emoji_medal} {row_p['periodo']}**")
                        st.markdown(f"Líquido: :green[**R$ {row_p['lucro_por_hora']:.2f} / hora**]")
                        st.caption(f"Faturamento: R$ {row_p['ganho_bruto']:,.2f} em {row_p['horas']:.1f}h ({row_p['id']} turnos)")

            st.write("")
            st.markdown("###### Composição dos Custos Operacionais")
            comp_custos = pd.DataFrame({
                "Categoria": ["Combustível", "Manutenções & Veículo"],
                "Valor": [total_combustivel, total_manut]
            })
            if comp_custos["Valor"].sum() > 0:
                st.bar_chart(comp_custos.set_index("Categoria")["Valor"])

    # ABA 4: VISÃO TEMPORAL (SEMANAL / MENSAL)
    with tab_periodos:
        st.markdown("##### 📅 Desempenho ao Longo do Tempo")
        st.caption("Acompanhe o faturamento semanal e a evolução dos seus ganhos.")

        if df_t.empty:
            st.info("Sem dados temporais disponíveis no período selecionado.")
        else:
            # Agrupamento semanal
            df_t["semana"] = df_t["data_dt"].dt.strftime("%Y - Sem %U")
            semanal = df_t.groupby("semana").agg({
                "ganho_bruto": "sum",
                "combustivel": "sum",
                "horas": "sum",
                "km": "sum"
            }).reset_index()
            semanal["lucro_liquido"] = semanal["ganho_bruto"] - semanal["combustivel"]
            semanal["ganho_hora"] = semanal["lucro_liquido"] / semanal["horas"]

            st.markdown("###### Faturamento Semanal (Bruto vs Líquido)")
            st.line_chart(semanal.set_index("semana")[["ganho_bruto", "lucro_liquido"]])

            st.write("")
            st.markdown("###### Tabela de Resumo Semanal")
            st.dataframe(
                semanal.rename(columns={
                    "semana": "Semana",
                    "ganho_bruto": "Faturamento Bruto (R$)",
                    "combustivel": "Combustível (R$)",
                    "lucro_liquido": "Lucro Líquido (R$)",
                    "horas": "Horas Rodadas",
                    "km": "KM Total",
                    "ganho_hora": "R$/Hora Líquida"
                }),
                use_container_width=True
            )


def render_cartoes(df: pd.DataFrame):
    """
    PÁGINA 4: CARTÕES DE CRÉDITO
    Visualização de cartões (1 de exemplo por padrão) e opção facilitada para cadastrar novos.
    """
    col_t1, col_t2 = st.columns([3, 1], vertical_alignment="center")
    with col_t1:
        st.subheader("💳 Meus Cartões de Crédito")
        st.caption("Acompanhe o limite disponível, fechamento de fatura e vencimentos.")
    with col_t2:
        if st.button("➕ Adicionar Cartão", use_container_width=True, type="primary"):
            modal_novo_cartao()

    conn = conectar()
    cartoes_df = pd.read_sql_query("SELECT * FROM cartoes", conn)
    conn.close()

    if cartoes_df.empty:
        st.info("Nenhum cartão cadastrado. Clique no botão acima para adicionar seu primeiro cartão.")
        return

    # Renderização organizada dos cartões em grade
    for i in range(0, len(cartoes_df), 2):
        linha_cartoes = cartoes_df.iloc[i:i+2]
        cols = st.columns(2)
        for idx, (_, crd) in enumerate(linha_cartoes.iterrows()):
            with cols[idx]:
                gastos_cartao = df[(df["descricao"].str.contains(crd["nome"], case=False, na=False)) | 
                                   (df["conta"] == crd["nome"])]["valor"].sum()
                limite_disp = max(crd["limite_total"] - gastos_cartao, 0.0)

                st.markdown(f"""
                <div class="cartao-credito-mockup">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:1.1rem; font-weight:700;">{crd['nome']}</span>
                        <span style="background:#2563eb; padding:2px 8px; border-radius:6px; font-size:0.75rem; color:#fff;">{crd['bandeira']}</span>
                    </div>
                    <div style="font-size:1.4rem; margin: 16px 0; letter-spacing: 2px;">💳 •••• •••• •••• 4028</div>
                    <div style="display:flex; justify-content:space-between; font-size:0.85rem; opacity:0.85;">
                        <div>Fecha dia: <strong>{crd['dia_fechamento']}</strong></div>
                        <div>Vence dia: <strong>{crd['dia_vencimento']}</strong></div>
                    </div>
                    <div style="margin-top:14px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.2); display:flex; justify-content:space-between;">
                        <div>Limite Total: <strong>R$ {crd['limite_total']:,.2f}</strong></div>
                        <div style="color:#34d399;">Disponível: <strong>R$ {limite_disp:,.2f}</strong></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Opção para excluir cartão
                if st.button(f"🗑️ Excluir {crd['nome']}", key=f"del_crd_{crd['id']}", help="Remover este cartão"):
                    excluir_cartao(crd["id"])
                    st.rerun()

    st.write("")
    st.divider()

    # Seção de faturas e compras parceladas no cartão
    st.markdown("##### 🛒 Compras Parceladas no Cartão de Crédito")
    parcelados = df[(df["grupo_parcelamento"].notnull()) & (~df["grupo_parcelamento"].str.startswith("pagaleve", na=False))]
    if not parcelados.empty:
        st.dataframe(
            parcelados[["data", "descricao", "valor", "categoria", "conta", "pago"]].rename(
                columns={"data": "Vencimento", "descricao": "Descrição", "valor": "Valor R$", "categoria": "Categoria", "conta": "Conta", "pago": "Pago (1=Sim)"}
            ),
            use_container_width=True
        )
    else:
        st.caption("Nenhuma compra parcelada em cartão de crédito registrada. Compras via Paga Leve (Pix 4x) são gerenciadas na página dedicada **Mais ➔ Paga Leve**.")


def render_contas(df: pd.DataFrame):
    """
    PÁGINA 5: CONTAS BANCÁRIAS E CARTEIRAS
    Visão geral de saldos reais por instituição financeira, saldo consolidado,
    conciliação/marcos iniciais, transferências e histórico auditável de ajustes.
    """
    conn = conectar()
    contas = saldo_service.obter_contas(conn)
    res_consolidado = saldo_service.calcular_saldo_consolidado(conn)
    saldo_total = float(res_consolidado["saldo_consolidado"])

    col_t1, col_t2, col_t3, col_t4 = st.columns([2.2, 1, 1.2, 1.2], vertical_alignment="center")
    with col_t1:
        st.subheader("🏦 Minhas Contas")
        st.caption(f"Saldo Consolidado Disponível: **R$ {saldo_total:,.2f}**")
    with col_t2:
        if st.button("➕ Nova Conta", use_container_width=True, type="secondary"):
            modal_nova_conta()
    with col_t3:
        if st.button("⚖️ Ajustar Saldo", use_container_width=True, type="primary"):
            modal_ajustar_saldo()
    with col_t4:
        if st.button("🔁 Transferência", use_container_width=True, type="secondary"):
            modal_transferencia()

    if not contas:
        st.info("Nenhuma conta bancária cadastrada no momento.")
        conn.close()
        return

    # Grid de cards com cada conta
    cols = st.columns(min(len(contas), 4))
    for idx, c in enumerate(contas):
        res_c = saldo_service.calcular_saldo_conta(conn, c["id"])
        saldo_c = float(res_c["saldo_atual"])
        rec_post = float(res_c["total_receitas_posteriores"])
        desp_post = float(res_c["total_despesas_posteriores"])
        cor_saldo = "#10b981" if saldo_c >= 0 else "#ef4444"

        with cols[idx % len(cols)]:
            with st.container(border=True):
                st.markdown(f"##### 🏦 {c['nome']}")
                st.markdown(f"<div style='font-size:1.6rem; font-weight:700; color:{cor_saldo}; margin: 4px 0;'>R$ {saldo_c:,.2f}</div>", unsafe_allow_html=True)
                
                if res_c["tem_marco"]:
                    data_marco_fmt = datetime.strptime(res_c["marco_data"], "%Y-%m-%d").strftime("%d/%m/%Y")
                    st.caption(f"🎯 **Marco:** R$ {float(res_c['marco_saldo']):,.2f} ({data_marco_fmt})")
                    st.caption(f"📈 Pós-corte: +R$ {rec_post:,.2f} | -R$ {desp_post:,.2f}")
                else:
                    st.caption("ℹ️ Nenhum marco definido (calculado pelo histórico)")

                if st.button("⚖️ Ajustar", key=f"btn_aj_card_{c['id']}", use_container_width=True):
                    modal_ajustar_saldo(conta_id_pre=c["id"])

    st.divider()

    # Extrato filtrado por conta selecionada
    st.markdown("##### 🔍 Extrato Individual por Conta")
    nomes_contas = [c["nome"] for c in contas]
    conta_sel = st.selectbox("Selecione a conta para visualizar:", nomes_contas)
    df_conta = df[df["conta"] == conta_sel]

    if df_conta.empty:
        st.info(f"Nenhuma movimentação registrada na conta {conta_sel}.")
    else:
        st.dataframe(
            df_conta[["data", "descricao", "tipo", "valor", "categoria", "pago"]].sort_values(by="data", ascending=False),
            use_container_width=True
        )

    # Seção de Auditoria e Histórico de Ajustes
    with st.expander("📋 Histórico e Auditoria de Ajustes de Saldo"):
        st.caption("Trilha contábil de conciliações e marcos iniciais. Cancelamentos são registrados via soft-delete para garantir transparência.")
        historico_ajustes = saldo_service.listar_historico_ajustes(conn)
        if not historico_ajustes:
            st.info("Nenhum ajuste ou marco financeiro registrado até o momento.")
        else:
            for aj in historico_ajustes:
                data_fmt = datetime.strptime(aj["data"], "%Y-%m-%d").strftime("%d/%m/%Y")
                eh_ativo = aj["status"] == "ativo"
                tag_status = "🟢 Ativo" if eh_ativo else f"🔴 Cancelado ({aj['cancelado_em'] or ''})"
                tipo_rotulo = "🎯 Marco Inicial" if aj["tipo"] == "marco_inicial" else "⚖️ Ajuste de Saldo"

                c_info1, c_info2, c_btn = st.columns([2.5, 2.5, 1.2], vertical_alignment="center")
                with c_info1:
                    st.markdown(f"**{tipo_rotulo} — {aj['conta_nome']}** ({data_fmt})")
                    st.caption(f"Status: **{tag_status}** | Registrado em: {aj['criado_em']}")
                    if aj["motivo"]:
                        st.caption(f"Motivo: *{aj['motivo']}*")
                with c_info2:
                    st.markdown(f"Saldo Informado: **R$ {float(aj['saldo_informado']):,.2f}**")
                    st.caption(f"Anterior calculado: R$ {float(aj['saldo_calculado']):,.2f} | Diferença: R$ {float(aj['diferenca']):,.2f}")
                    if aj.get("motivo_cancelamento"):
                        st.caption(f"Justificativa cancelamento: *{aj['motivo_cancelamento']}*")
                with c_btn:
                    if eh_ativo:
                        if st.button("Cancelar", key=f"btn_canc_aj_{aj['id']}", help="Cancelar contabilmente este ajuste", use_container_width=True):
                            saldo_service.cancelar_ajuste(conn, aj["id"], motivo_cancelamento="Cancelado pelo usuário na tela Contas")
                            st.success("Ajuste cancelado com sucesso!")
                            conn.close()
                            st.rerun()

                st.markdown("<hr style='margin: 8px 0; border: none; border-top: 1px dashed rgba(255,255,255,0.1);'>", unsafe_allow_html=True)

    conn.close()


def render_planejamento_metas(df: pd.DataFrame):
    """
    PÁGINA DEDICADA: PLANEJAMENTO FINANCEIRO INTELIGENTE & METAS
    Quatro áreas integradas:
    A. Minha Missão (IPVA 2025/2026 e Reservas Virtuais)
    B. Caixa da Semana e do Mês (Priorização, BV isolado, Memória de Cálculo)
    C. Despesas Variáveis (Previsão manual realista a partir de hoje e tetos orçamentários)
    D. Trabalho e Viabilidade Operacional (Simulador do motorista com cálculo rigoroso de déficit)
    """
    st.subheader("🎯 Planejamento Financeiro Inteligente & Metas")
    st.caption("Visão estratégica de curto e médio prazo, reservas protegidas e viabilidade operacional.")

    hoje = date.today()
    mes_ano_atual = hoje.strftime("%Y-%m")
    conn = conectar()

    tab_missao, tab_caixa, tab_variaveis, tab_trabalho = st.tabs([
        "🎯 A. Minha Missão",
        "🗓️ B. Caixa da Semana & Mês",
        "🛒 C. Despesas Variáveis",
        "🚕 D. Trabalho & Viabilidade"
    ])

    # =========================================================================
    # TAB A: MINHA MISSÃO (IPVA E RESERVA VIRTUAL)
    # =========================================================================
    with tab_missao:
        missao = planejamento_service.obter_status_missao_ipva(conn, mes_ano=mes_ano_atual, data_referencia=hoje)
        saldo_info = saldo_service.calcular_saldo_consolidado(conn, data_referencia=hoje)
        saldo_disp = saldo_info["saldo_consolidado"]

        if not missao.get("tem_missao"):
            st.warning("⚠️ Nenhuma obrigação identificada para o IPVA no sistema.")
        else:
            with st.container(border=True):
                col_m_tit, col_m_val = st.columns([2.5, 1.5], vertical_alignment="center")
                with col_m_tit:
                    st.markdown(f"### 🛡️ {missao['titulo']}")
                    dt_venc_fmt = datetime.strptime(missao['data_vencimento'], '%Y-%m-%d').strftime('%d/%m/%Y')
                    st.caption(f"Vencimento Oficial: **{dt_venc_fmt}** • Prazo Restante: **{missao['dias_restantes']} dias corridos**")
                with col_m_val:
                    st.markdown(
                        f"<div style='text-align: right;'><span style='font-size: 0.85rem; color: var(--text-muted);'>Valor Nominal</span><br>"
                        f"<b style='font-size: 1.6rem; color: var(--text-primary);'>{formatar_moeda_br(missao['valor_nominal'])}</b></div>",
                        unsafe_allow_html=True
                    )

                st.write("")
                pct_prog = min(1.0, missao["percentual_coberto"] / 100.0)
                st.progress(pct_prog, text=f"Progresso de Cobertura da Meta: {missao['percentual_coberto']:.1f}%")

                c_info1, c_info2, c_info3, c_info4 = st.columns(4)
                with c_info1:
                    st.metric("Efetivamente Pago", formatar_moeda_br(missao['valor_ja_pago']), help="Pagamentos reais já liquidados no banco")
                with c_info2:
                    st.metric("Reserva Virtual", formatar_moeda_br(missao['valor_reservado']), help="Parte do saldo bancário separada para a missão, sem movimentar dinheiro")
                with c_info3:
                    st.metric(
                        "Valor Restante a Cobrir",
                        formatar_moeda_br(missao['saldo_devedor_restante']),
                        delta=f"- {formatar_moeda_br(missao['saldo_devedor_restante'])}" if missao['saldo_devedor_restante'] > 0 else "Quitado/Coberto",
                        delta_color="inverse" if missao['saldo_devedor_restante'] > 0 else "normal"
                    )
                with c_info4:
                    st.metric("Meta por Turno", formatar_moeda_br(missao['meta_por_turno']), help=f"Considerando {missao['turnos_planejados']} turnos planejados")

                # Recalcula e alerta se o saldo bancário for menor que a reserva virtual
                if missao['valor_reservado'] > saldo_disp:
                    st.error(
                        f"⚠️ **Atenção ao Saldo Efetivo:** O saldo bancário total disponível é de {formatar_moeda_br(saldo_disp)}, "
                        f"inferior à reserva virtual configurada de {formatar_moeda_br(missao['valor_reservado'])}. "
                        f"A cobertura real da reserva foi ajustada temporariamente para {formatar_moeda_br(saldo_disp)}."
                    )

            st.write("")
            with st.container(border=True):
                st.markdown("#### ⚙️ Ajustar Reserva Virtual & Planejamento de Turnos")
                st.caption(
                    f"Saldo total em contas disponível para reserva: **{formatar_moeda_br(saldo_disp)}**. "
                    "As reservas não criam transações, não movimentam contas bancárias e não duplicam despesas."
                )

                col_f1, col_f2, col_f3 = st.columns([1.5, 1.2, 1.3])
                with col_f1:
                    reserva_max = float(max(Decimal("0.00"), saldo_disp))
                    reserva_val_inicial = float(min(saldo_disp, missao['valor_reservado']))
                    nova_reserva = st.number_input(
                        "Valor da Reserva Virtual (R$):",
                        min_value=0.0,
                        max_value=reserva_max,
                        value=reserva_val_inicial,
                        step=10.0,
                        format="%.2f",
                        key="input_reserva_missao"
                    )
                with col_f2:
                    novos_turnos = st.number_input(
                        "Turnos de trabalho planejados:",
                        min_value=1,
                        max_value=31,
                        value=int(missao['turnos_planejados']),
                        step=1,
                        key="input_turnos_missao"
                    )
                with col_f3:
                    st.write("")
                    st.write("")
                    if st.button("💾 Salvar Ajuste da Missão", type="primary", use_container_width=True, key="btn_salvar_missao"):
                        sucesso, msg = planejamento_service.atualizar_reserva_missao(
                            conn, missao["transacao_id"], Decimal(str(nova_reserva)), mes_ano_atual
                        )
                        cur_m = conn.cursor()
                        cur_m.execute("UPDATE planejamento_metas SET turnos_planejados = ? WHERE transacao_alvo_id = ? AND mes_ano = ?", (novos_turnos, missao["transacao_id"], mes_ano_atual))
                        conn.commit()
                        if sucesso:
                            st.toast(msg, icon="✅")
                        else:
                            st.error(msg)
                        st.rerun()

    # =========================================================================
    # TAB B: CAIXA DA SEMANA E DO MÊS
    # =========================================================================
    with tab_caixa:
        semana_ref_atual = hoje.strftime("%Y-W%W")
        caixa = planejamento_service.calcular_necessidade_caixa_7dias(conn, data_referencia=hoje, semana_ref=semana_ref_atual)
        proj_mes = planejamento_service.calcular_projecao_mensal(conn, data_referencia=hoje)

        if caixa["total_pendente_confirmacao"] > 0:
            st.warning(
                f"🚨 **Dados Incompletos sob Conciliação:** Existe fatura/acordo BV no valor nominal de "
                f"**{formatar_moeda_br(caixa['total_pendente_confirmacao'])}** pendente de confirmação das novas parcelas. "
                f"Este montante foi rigorosamente isolado e NÃO entra na necessidade imediata de caixa desta semana."
            )

        st.markdown("#### 🗓️ Necessidade de Caixa dos Próximos 7 Dias")
        st.caption(f"Período de referência: **{hoje.strftime('%d/%m/%Y')}** a **{datetime.strptime(caixa['data_limite_7d'], '%Y-%m-%d').strftime('%d/%m/%Y')}**")

        b1, b2, b3, b4 = st.columns(4)
        with b1:
            st.metric("Saldo Total em Bancos", formatar_moeda_br(caixa['saldo_total_disponivel']))
        with b2:
            st.metric("Reservas Virtuais (IPVA)", formatar_moeda_br(caixa['total_reservas_virtuais']), help="Valor do saldo comprometido com a missão, não disponível para despesas gerais")
        with b3:
            st.metric("Saldo Livre Real", formatar_moeda_br(caixa['saldo_livre']), help="Saldo bancário disponível descontadas as reservas virtuais")
        with b4:
            nec_7d = caixa['necessidade_adicional_caixa']
            st.metric("Necessidade Líquida 7d", formatar_moeda_br(nec_7d), delta="Falta cobrir" if nec_7d > 0 else "100% Coberto", delta_color="inverse" if nec_7d > 0 else "normal")

        st.write("")
        col_c_conf, col_c_atr = st.columns([1.1, 1.1], gap="medium")

        with col_c_conf:
            with st.container(border=True):
                st.markdown(f"**📌 Obrigações Confirmadas nos Próximos 7 Dias ({formatar_moeda_br(caixa['total_confirmadas_7d'])})**")
                if not caixa["obrigacoes_confirmadas_7d"]:
                    st.info("Nenhuma obrigação regular a vencer nos próximos 7 dias.")
                else:
                    for ob in caixa["obrigacoes_confirmadas_7d"]:
                        dt_fmt = datetime.strptime(ob["data"], "%Y-%m-%d").strftime("%d/%m") if isinstance(ob["data"], str) else str(ob["data"])
                        ic = obter_icone_categoria(ob["categoria"])
                        st.markdown(f"• **{dt_fmt}** • {ic} {ob['descricao']} — **{formatar_moeda_br(ob['saldo_devedor'])}** ({ob['conta']})")

                st.write("")
                st.markdown(f"**🛒 Consumo Variável Essencial Esperado:** **{formatar_moeda_br(caixa['gastos_variaveis_semana'])}**")
                st.caption("Provisão mínima semanal para necessidades básicas imediatas (ex: alimentação e farmácia).")

        with col_c_atr:
            with st.container(border=True):
                st.markdown("**⚠️ Contas Vencidas: Seleção de Prioridade da Semana**")
                st.caption("Marque as contas atrasadas que você pretende quitar nesta semana. As desmarcadas permanecerão reprogramadas sem inflar a meta imediata.")

                cur_atr = conn.cursor()
                cur_atr.execute("""
                    SELECT t.id, t.data, t.descricao, t.valor, t.categoria, COALESCE(t.status_conciliacao_fatura, 'normal')
                    FROM transacoes t
                    WHERE t.tipo = 'despesa' AND (t.pago IS NULL OR t.pago != 1) AND t.data < ?
                    ORDER BY t.data ASC
                """, (hoje.strftime("%Y-%m-%d"),))
                linhas_atrasadas = [r for r in cur_atr.fetchall() if r[5] != "pendente_confirmacao" and "Acordo BV" not in r[2]]

                cur_atr.execute("SELECT transacao_id, prioritaria FROM planejamento_prioridades_atrasados WHERE semana_ref = ?", (semana_ref_atual,))
                prio_db = {r[0]: r[1] for r in cur_atr.fetchall()}

                mudou_prio = False
                for r_at in linhas_atrasadas:
                    t_id, t_dt, t_desc, t_v, t_cat, _ = r_at
                    resumo_o = saldo_service.obter_resumo_obrigacao(conn, t_id)
                    s_dev = resumo_o["saldo_devedor"]
                    if s_dev <= Decimal("0.00"):
                        continue
                    dt_fmt = datetime.strptime(t_dt, "%Y-%m-%d").strftime("%d/%m") if isinstance(t_dt, str) else str(t_dt)
                    ic = obter_icone_categoria(t_cat)
                    checado = prio_db.get(t_id, 0) == 1

                    check_val = st.checkbox(
                        f"{ic} {t_desc} ({dt_fmt}) — {formatar_moeda_br(s_dev)}",
                        value=checado,
                        key=f"check_prio_{t_id}_{semana_ref_atual}"
                    )
                    if check_val != checado:
                        val_aloc = float(s_dev) if check_val else 0.0
                        cur_atr.execute("""
                            INSERT OR REPLACE INTO planejamento_prioridades_atrasados (semana_ref, transacao_id, prioritaria, valor_alocado)
                            VALUES (?, ?, ?, ?)
                        """, (semana_ref_atual, t_id, 1 if check_val else 0, val_aloc))
                        mudou_prio = True

                if mudou_prio:
                    conn.commit()
                    st.rerun()

                st.write("")
                c_sub1, c_sub2 = st.columns(2)
                with c_sub1:
                    st.caption(f"Atrasadas Prioritárias: **{formatar_moeda_br(caixa['total_vencidas_prioritarias'])}**")
                with c_sub2:
                    st.caption(f"Atrasadas Reprogramadas: **{formatar_moeda_br(caixa['total_vencidas_reprogramadas'])}**")

        st.write("")
        with st.expander("🔍 Memória de Cálculo e Detalhamento da Necessidade de Caixa"):
            st.markdown(f"""
            **Como foi calculada a sua necessidade dos próximos 7 dias:**
            1. **Compromissos Mínimos da Semana:**
               - Obrigações confirmadas nos próximos 7 dias: `{formatar_moeda_br(caixa['total_confirmadas_7d'])}`
               - Contas atrasadas priorizadas para esta semana: `+ {formatar_moeda_br(caixa['total_vencidas_prioritarias'])}`
               - Despesas variáveis essenciais esperadas: `+ {formatar_moeda_br(caixa['gastos_variaveis_semana'])}`
               - **Total de Compromissos Mínimos:** `{formatar_moeda_br(caixa['compromissos_minimos_semana'])}`

            2. **Recursos Disponíveis para Abater:**
               - Saldo Livre Efetivo (Saldo em contas `{formatar_moeda_br(caixa['saldo_total_disponivel'])}` - Reservas Virtuais `{formatar_moeda_br(caixa['total_reservas_virtuais'])}`): `- {formatar_moeda_br(caixa['saldo_livre'])}`
               - Entradas futuras confirmadas nos próximos 7 dias: `- {formatar_moeda_br(caixa['entradas_futuras_confirmadas'])}`

            3. **Resultado:**
               - **Necessidade Adicional de Caixa Líquido:** `{formatar_moeda_br(caixa['necessidade_adicional_caixa'])}`
            """)

    # =========================================================================
    # TAB C: DESPESAS VARIÁVEIS
    # =========================================================================
    with tab_variaveis:
        c_v_tit, c_v_btn = st.columns([3, 1], vertical_alignment="center")
        with c_v_tit:
            st.markdown("#### 🛒 Despesas Variáveis & Previsão de Consumo")
            st.caption(
                "Para Outubro/2026, informe previsões manuais realistas a partir de hoje até o final do mês. "
                "Compras efetuadas a partir de hoje abatem a previsão sem duplicação. Pagamentos de dívidas e cartões são rigorosamente excluídos."
            )
        with c_v_btn:
            if st.button("➕ Definir Limite Teto", use_container_width=True, type="secondary"):
                modal_limite_gasto()

        res_var = planejamento_service.calcular_despesas_variaveis_restantes(conn, mes_ano=mes_ano_atual, data_referencia=hoje)

        col_tot1, col_tot2 = st.columns(2)
        with col_tot1:
            st.metric("Consumo Esperado Restante no Mês", formatar_moeda_br(res_var['total_consumo_esperado_restante']), help="Soma das previsões que ainda não foram consumidas por compras pós-data atual")
        with col_tot2:
            st.metric("Provisão Essencial Semanal", formatar_moeda_br(res_var['total_essencial_semana']), help="Parcela semanal reservada para o caixa de 7 dias")

        st.write("")
        st.markdown("##### 📝 Previsões Manuais por Categoria")

        with st.container(border=True):
            cols_h = st.columns([2.0, 1.2, 1.2, 1.2, 1.2])
            cols_h[0].markdown("**Categoria**")
            cols_h[1].markdown("**Teto Máx. (Limite)**")
            cols_h[2].markdown("**Previsão Futura**")
            cols_h[3].markdown("**Realizado Pós-Hoje**")
            cols_h[4].markdown("**Consumo Restante**")

            categorias_editaveis = res_var["detalhe_categorias"]
            alteracoes_salvar = {}

            for item in categorias_editaveis:
                cat_nome = item["categoria"]
                ic = obter_icone_categoria(cat_nome)
                c_row = st.columns([2.0, 1.2, 1.2, 1.2, 1.2], vertical_alignment="center")

                c_row[0].markdown(f"**{ic} {cat_nome}**")
                c_row[1].markdown(f"`{formatar_moeda_br(item['teto_limite'])}`" if item['teto_limite'] > 0 else "—")

                val_in = c_row[2].number_input(
                    f"Previsão {cat_nome}",
                    min_value=0.0,
                    value=float(item["previsao_futura"]),
                    step=20.0,
                    label_visibility="collapsed",
                    key=f"prev_cat_{cat_nome}_{mes_ano_atual}"
                )
                alteracoes_salvar[cat_nome] = Decimal(str(val_in))

                c_row[3].markdown(f"{formatar_moeda_br(item['gasto_posterior_realizado'])}")
                c_row[4].markdown(f"**{formatar_moeda_br(item['consumo_restante'])}**")

            st.write("")
            if st.button("💾 Salvar Previsões Manuais de Despesas Variáveis", type="primary", use_container_width=True, key="btn_salvar_variaveis"):
                cur_v = conn.cursor()
                for c_name, c_val in alteracoes_salvar.items():
                    sem_val = float(c_val * Decimal("0.25")) if c_name in ("Supermercado", "Medicamentos", "Combustível") else 0.0
                    cur_v.execute("""
                        INSERT OR REPLACE INTO planejamento_previsao_variaveis (mes_ano, categoria, tipo_previsao, data_inicio, valor_previsto, essencial_semanal)
                        VALUES (?, ?, 'a_partir_de_hoje', ?, ?, ?)
                    """, (mes_ano_atual, c_name, hoje.strftime("%Y-%m-%d"), float(c_val), sem_val))
                conn.commit()
                st.toast("Previsões manuais atualizadas com sucesso!", icon="✅")
                st.rerun()

    # =========================================================================
    # TAB D: TRABALHO E VIABILIDADE
    # =========================================================================
    with tab_trabalho:
        st.markdown("#### 🚕 Viabilidade Operacional & Trabalho do Motorista")
        st.caption(
            "Simulador de metas de trabalho e viabilidade estrita. "
            "Valores simulados não criam turnos e não geram receitas bancárias automáticas."
        )

        caixa_atual = planejamento_service.calcular_necessidade_caixa_7dias(conn, data_referencia=hoje)
        missao_atual = planejamento_service.obter_status_missao_ipva(conn, data_referencia=hoje)
        proj_atual = planejamento_service.calcular_projecao_mensal(conn, data_referencia=hoje)

        c_alvo1, c_alvo2 = st.columns([2.0, 1.5], vertical_alignment="center")
        with c_alvo1:
            opcao_alvo = st.selectbox(
                "Qual meta financeira deseja avaliar a viabilidade?",
                options=[
                    "Necessidade de Caixa dos Próximos 7 Dias",
                    "Missão IPVA (Saldo Restante)",
                    "Déficit Projetado até o Fim do Mês",
                    "Outro Valor Personalizado"
                ],
                key="sel_opcao_alvo_viab"
            )

        with c_alvo2:
            if opcao_alvo == "Necessidade de Caixa dos Próximos 7 Dias":
                val_alvo_sugerido = float(caixa_atual["necessidade_adicional_caixa"])
            elif opcao_alvo == "Missão IPVA (Saldo Restante)":
                val_alvo_sugerido = float(missao_atual.get("saldo_devedor_restante", 0.0))
            elif opcao_alvo == "Déficit Projetado até o Fim do Mês":
                val_alvo_sugerido = float(proj_atual.get("necessidade_geral_fim_mes", 0.0))
            else:
                val_alvo_sugerido = 300.0

            val_simulado = st.number_input(
                "Valor Líquido Alvo (R$):",
                min_value=0.0,
                value=val_alvo_sugerido,
                step=50.0,
                format="%.2f",
                key="num_val_alvo_simulado"
            )

        with st.container(border=True):
            st.markdown("##### ⚙️ Parâmetros de Trabalho e Rendimento")
            col_p1, col_p2, col_p3, col_p4 = st.columns(4)

            with col_p1:
                dias_disp = st.number_input("Dias disponíveis:", min_value=1, max_value=31, value=5, step=1, key="sim_dias_disp")
            with col_p2:
                horas_dia = st.number_input("Horas de volante/dia:", min_value=0.5, max_value=16.0, value=4.0, step=0.5, key="sim_horas_dia")
            with col_p3:
                ganho_h = st.number_input("Ganho bruto est./hora:", min_value=1.0, value=35.0, step=1.0, format="%.2f", key="sim_ganho_h")
            with col_p4:
                comb_h = st.number_input("Combustível est./hora:", min_value=0.0, value=10.0, step=1.0, format="%.2f", key="sim_comb_h")

        viab = planejamento_service.calcular_viabilidade_metas_trabalho(
            necessidade_financeira=Decimal(str(val_simulado)),
            dias_disponiveis=int(dias_disp),
            horas_disponiveis_dia=float(horas_dia),
            ganho_bruto_hora=float(ganho_h),
            combustivel_hora=float(comb_h)
        )

        st.write("")
        if viab["status_viabilidade"] == "deficit":
            st.error(f"🔴 **{viab['rotulo_viabilidade']}**")
            st.markdown(
                f"> **Diagnóstico de Inviabilidade:** Para cobrir **{formatar_moeda_br(Decimal(str(val_simulado)))}**, "
                f"são necessárias **{viab['horas_necessarias']:.1f} horas** de trabalho líquido ({formatar_moeda_br(viab['ganho_liquido_hora'])}/h). "
                f"Sua jornada planejada disponibiliza apenas **{viab['horas_disponiveis_total']:.1f} horas**. "
                f"Existe um **déficit de {abs(viab['diferenca_horas']):.1f} horas** de volante."
            )
        else:
            st.success(f"🟢 **{viab['rotulo_viabilidade']}**")
            st.markdown(
                f"> **Diagnóstico de Viabilidade:** Meta plenamente atingível dentro da sua disponibilidade de **{viab['horas_disponiveis_total']:.1f} horas**. "
                f"São necessárias **{viab['horas_necessarias']:.1f} horas** de trabalho líquido ({formatar_moeda_br(viab['ganho_liquido_hora'])}/h)."
            )

        c_v1, c_v2, c_v3, c_v4 = st.columns(4)
        with c_v1:
            st.metric("Horas Disponíveis", f"{viab['horas_disponiveis_total']:.1f} h", help=f"{dias_disp} dias x {horas_dia} horas/dia")
        with c_v2:
            st.metric("Horas Necessárias", f"{viab['horas_necessarias']:.1f} h")
        with c_v3:
            st.metric(
                "Diferença de Jornada",
                f"{viab['diferenca_horas']:+.1f} h",
                delta="Folga" if viab['diferenca_horas'] >= 0 else "Déficit",
                delta_color="normal" if viab['diferenca_horas'] >= 0 else "inverse"
            )
        with c_v4:
            st.metric("Ganho Líq./Hora Est.", f"{formatar_moeda_br(viab['ganho_liquido_hora'])}/h", help=f"Bruto: {formatar_moeda_br(ganho_h)} - Combustível: {formatar_moeda_br(comb_h)}")

        st.caption("ℹ️ *Aviso:* Esta simulação é meramente analítica e projetual. Não altera saldos bancários e não cria turnos ou transações no banco de dados.")

    conn.close()


def render_limite_gastos(df: pd.DataFrame):
    """Encaminha para a nova central completa de Planejamento & Metas."""
    render_planejamento_metas(df)


def render_relatorios(df: pd.DataFrame, df_turnos: pd.DataFrame):
    """
    PÁGINA 7: RELATÓRIOS E INTELIGÊNCIA FINANCEIRA FAMILIAR
    Análise gráfica de receitas vs despesas familiares e demonstrativo mensal (DRE).
    """
    st.subheader("📊 Relatórios e Inteligência Financeira")
    st.caption("Visão analítica dos seus resultados financeiros gerais e demonstrativo mensal.")

    tab_geral, tab_dre = st.tabs([
        "📈 Despesas e Receitas Familiares",
        "📑 Demonstrativo Mensal (DRE)"
    ])

    with tab_geral:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 🍕 Despesas por Categoria")
            df_desp = df[df["tipo"] == "despesa"]
            if not df_desp.empty:
                por_cat = df_desp.groupby("categoria")["valor"].sum().reset_index()
                por_cat = por_cat.sort_values(by="valor", ascending=False)
                st.bar_chart(data=por_cat.set_index("categoria")["valor"])
            else:
                st.info("Sem dados de despesa.")

        with c2:
            st.markdown("##### ⚖️ Comparativo de Fluxo de Caixa")
            rec_total = df[df["tipo"] == "receita"]["valor"].sum()
            desp_total = df[df["tipo"] == "despesa"]["valor"].sum()
            comp_df = pd.DataFrame({
                "Fluxo": ["Receitas", "Despesas"],
                "Valor": [rec_total, desp_total]
            })
            st.bar_chart(data=comp_df.set_index("Fluxo")["Valor"])

    with tab_dre:
        st.markdown("##### 📑 Demonstrativo Sintético do Mês")
        rec_tot = df[df["tipo"] == "receita"]["valor"].sum()
        desp_tot = df[df["tipo"] == "despesa"]["valor"].sum()
        resultado = rec_tot - desp_tot

        with st.container(border=True):
            st.markdown(f"**(+) Total de Receitas:** :green[R$ {rec_tot:,.2f}]")
            st.markdown(f"**(-) Total de Despesas Operacionais:** :red[- R$ {desp_tot:,.2f}]")
            st.divider()
            cor_res = ":green" if resultado >= 0 else ":red"
            st.markdown(f"### Resultado Líquido: {cor_res}[R$ {resultado:,.2f}]")


# =============================================================================
# 7. PÁGINA DEDICADA: PAGA LEVE (PIX PARCELADO 4X)
# =============================================================================
def render_paga_leve(df: pd.DataFrame):
    """
    PÁGINA DEDICADA: PAGA LEVE (PIX PARCELADO 4X)
    Gestão completa com contas de Carlos e Fernanda, titular a confirmar,
    cartões compactos e expansíveis, e progresso baseado em dados comprovados.
    """
    col_t1, col_t2 = st.columns([3, 1], vertical_alignment="center")
    with col_t1:
        st.subheader("⚡ Paga Leve (Pix Parcelado 4x)")
        st.caption("Acompanhe suas compras parceladas quinzenais, contas de Carlos e Fernanda, titularidade e parcelas pendentes.")
    with col_t2:
        if st.button("➕ Nova Compra Paga Leve", use_container_width=True, type="primary"):
            modal_paga_leve()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Contas Paga Leve (Carlos e Fernanda)
    cur.execute("SELECT * FROM pagaleve_contas WHERE ativo = 1 ORDER BY id ASC")
    contas_pl = [dict(r) for r in cur.fetchall()]

    # 2. Compras cadastradas em pagaleve_compras
    cur.execute("SELECT * FROM pagaleve_compras ORDER BY id ASC")
    compras_db = {r["grupo_parcelamento"]: dict(r) for r in cur.fetchall()}

    conn.close()

    # Filtra lançamentos Paga Leve em transacoes
    df_pl = df[(df["grupo_parcelamento"].str.startswith("pagaleve", na=False)) | (df["descricao"].str.contains("Paga Leve", case=False, na=False))].copy()

    if df_pl.empty:
        st.info("Nenhuma compra parcelada Paga Leve registrada. Clique no botão acima para cadastrar.")
        return

    # Mapeia titular de cada lançamento considerando a compra se transacao não tiver titular definido
    def obter_titular_linha(row):
        t = row.get("titular")
        if t and t not in ("A Confirmar", "None", ""):
            return t
        grp = row.get("grupo_parcelamento")
        if grp in compras_db and compras_db[grp].get("titular") not in ("A Confirmar", "None", ""):
            return compras_db[grp]["titular"]
        return "A Confirmar"

    df_pl["titular_efetivo"] = df_pl.apply(obter_titular_linha, axis=1)

    aberto_carlos = df_pl[(df_pl["pago"] != 1) & (df_pl["titular_efetivo"] == "Carlos")]["valor"].sum()
    aberto_fernanda = df_pl[(df_pl["pago"] != 1) & (df_pl["titular_efetivo"] == "Fernanda")]["valor"].sum()
    aberto_confirmar = df_pl[(df_pl["pago"] != 1) & (df_pl["titular_efetivo"] == "A Confirmar")]["valor"].sum()

    col_acc1, col_acc2, col_acc3 = st.columns([1.5, 1.5, 1.2])
    with col_acc1:
        limite_carlos = 1200.0
        disp_carlos = max(0.0, limite_carlos - aberto_carlos)
        st.markdown(f"""
        <div style="background-color:var(--bg-subcard); padding:12px 16px; border-radius:12px; border-left:4px solid #2563eb;">
            <div style="font-size:0.85rem; color:var(--text-muted); font-weight:600;">👤 Conta Paga Leve — Carlos</div>
            <div style="font-size:1.25rem; font-weight:800; color:var(--text-primary); margin-top:2px;">
                {formatar_moeda_br(aberto_carlos)}
            </div>
            <div style="font-size:0.8rem; color:var(--text-muted); margin-top:4px;">
                Limite Total: <strong>{formatar_moeda_br(limite_carlos)}</strong> • Disponível: <strong style="color:#10b981;">{formatar_moeda_br(disp_carlos)}</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_acc2:
        st.markdown(f"""
        <div style="background-color:var(--bg-subcard); padding:12px 16px; border-radius:12px; border-left:4px solid #db2777;">
            <div style="font-size:0.85rem; color:var(--text-muted); font-weight:600;">👤 Conta Paga Leve — Fernanda</div>
            <div style="font-size:1.25rem; font-weight:800; color:var(--text-primary); margin-top:2px;">
                {formatar_moeda_br(aberto_fernanda)}
            </div>
            <div style="font-size:0.8rem; color:var(--text-muted); margin-top:4px;">
                Modalidade: <strong>Sob Demanda (Aprovada por Compra)</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_acc3:
        st.markdown(f"""
        <div style="background-color:var(--bg-subcard); padding:12px 16px; border-radius:12px; border-left:4px solid #f59e0b;">
            <div style="font-size:0.85rem; color:var(--text-muted); font-weight:600;">⚠️ Titular a Confirmar</div>
            <div style="font-size:1.25rem; font-weight:800; color:#f59e0b; margin-top:2px;">
                {formatar_moeda_br(aberto_confirmar)}
            </div>
            <div style="font-size:0.8rem; color:var(--text-muted); margin-top:4px;">
                Compras antigas pendentes de titular
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    # Filtro de titular
    c_flt, _ = st.columns([2.5, 2.5])
    with c_flt:
        filtro_titular = st.segmented_control(
            "Filtrar por Titular",
            options=["Todos (Consolidado)", "Carlos", "Fernanda", "A Confirmar"],
            default="Todos (Consolidado)",
            key="filtro_pl_titular"
        )

    # Agrupa por compra
    grupos = {}
    for _, row in df_pl.iterrows():
        grp = row["grupo_parcelamento"]
        if not grp or pd.isna(grp):
            grp = re.sub(r' - Paga Leve.*', '', row["descricao"], flags=re.I).strip()
        if grp not in grupos:
            grupos[grp] = []
        grupos[grp].append(row)

    compras = []
    total_parcelas_aberto = 0
    valor_total_aberto = 0.0
    valor_vence_mes = 0.0
    proximos_vencimentos = []
    hoje = date.today()
    mes_atual_str = hoje.strftime("%Y-%m")

    for g_id, itens in grupos.items():
        itens_sorted = sorted(itens, key=lambda x: (str(x["data"]), x["id"]))
        desc_base = re.sub(r' - Paga Leve.*', '', itens_sorted[0]["descricao"], flags=re.I).strip()

        # Dados comprovados da compra
        meta_compra = compras_db.get(g_id, {})
        titular_compra = meta_compra.get("titular", itens_sorted[0]["titular_efetivo"])

        # Aplica filtro de titular
        if filtro_titular == "Carlos" and titular_compra != "Carlos":
            continue
        elif filtro_titular == "Fernanda" and titular_compra != "Fernanda":
            continue
        elif filtro_titular == "A Confirmar" and titular_compra not in ("A Confirmar", "None", ""):
            continue

        valor_original_comprovado = meta_compra.get("valor_original", sum(r["valor"] for r in itens_sorted))
        total_parc_comprovado = meta_compra.get("total_parcelas", len(itens_sorted))

        tot_val = sum(r["valor"] for r in itens_sorted)
        tot_pago = sum(r["valor"] for r in itens_sorted if r["pago"] == 1)
        tot_aberto = sum(r["valor"] for r in itens_sorted if r["pago"] != 1)

        pendentes = [r for r in itens_sorted if r["pago"] != 1]
        prox_venc = min((r["data"] for r in pendentes), default=None)

        is_quitada = (tot_aberto <= 0.001)

        total_parcelas_aberto += len(pendentes)
        valor_total_aberto += tot_aberto

        for p in pendentes:
            if str(p["data"]).startswith(mes_atual_str):
                valor_vence_mes += p["valor"]
            proximos_vencimentos.append((p["data"], p["valor"], desc_base, titular_compra))

        # Calcula parcelas anteriores quitadas pré-banco
        parc_registradas = len(itens_sorted)
        parc_anteriores_quitadas = max(0, total_parc_comprovado - parc_registradas)
        valor_quitado_anterior = parc_anteriores_quitadas * (valor_original_comprovado / total_parc_comprovado if total_parc_comprovado > 0 else 0.0)

        progresso_comprovado_val = valor_quitado_anterior + tot_pago
        pct_progresso = min(1.0, progresso_comprovado_val / valor_original_comprovado) if valor_original_comprovado > 0 else 1.0

        compras.append({
            "grupo_id": g_id,
            "nome": desc_base,
            "categoria": itens_sorted[0]["categoria"],
            "conta": itens_sorted[0]["conta"],
            "titular": titular_compra,
            "valor_original_comprovado": valor_original_comprovado,
            "total_parc_comprovado": total_parc_comprovado,
            "parc_registradas": parc_registradas,
            "parc_anteriores_quitadas": parc_anteriores_quitadas,
            "total_pago": tot_pago,
            "total_aberto": tot_aberto,
            "pct_progresso": pct_progresso,
            "status": "Quitada" if is_quitada else "Ativa",
            "itens": itens_sorted,
            "prox_venc": prox_venc
        })

    # KPIs principais
    prox_venc_str = "Nenhum"
    if proximos_vencimentos:
        proximos_vencimentos.sort(key=lambda x: x[0])
        dt_prox, val_prox, nome_prox, tit_prox = proximos_vencimentos[0]
        try:
            dt_prox_br = datetime.strptime(dt_prox, "%Y-%m-%d").strftime("%d/%m")
        except Exception:
            dt_prox_br = dt_prox
        prox_venc_str = f"{dt_prox_br} ({formatar_moeda_br(val_prox)}) • {tit_prox}"

    ativas_cnt = sum(1 for c in compras if c["status"] == "Ativa")
    quitadas_cnt = sum(1 for c in compras if c["status"] == "Quitada")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Total em Aberto", formatar_moeda_br(valor_total_aberto), f"{total_parcelas_aberto} parcelas pendentes", delta_color="inverse")
    with k2:
        st.metric("Vence neste Mês", formatar_moeda_br(valor_vence_mes), f"Competência {hoje.strftime('%m/%Y')}", delta_color="inverse")
    with k3:
        st.metric("Próximo Vencimento", prox_venc_str)
    with k4:
        st.metric("Compras Listadas", f"{len(compras)} compras", f"{ativas_cnt} ativas • {quitadas_cnt} quitadas")

    st.write("")
    st.divider()

    tab_ativas, tab_quitadas, tab_todas = st.tabs([
        f"🛒 Compras em Andamento ({ativas_cnt})",
        f"📜 Histórico de Quitadas ({quitadas_cnt})",
        f"📋 Extrato Consolidado ({len(df_pl)} parcelas)"
    ])

    def render_cartao_compra_expandivel(c):
        with st.container(border=True):
            col_h1, col_h2, col_h3 = st.columns([2.5, 1.3, 1.2], vertical_alignment="center")
            with col_h1:
                ic = obter_icone_categoria(c["categoria"])
                tit_badge = (
                    "<span style='background:#2563eb22; color:#2563eb; padding:2px 8px; border-radius:8px; font-size:0.78rem; font-weight:700;'>👤 Carlos</span>"
                    if c["titular"] == "Carlos" else
                    ("<span style='background:#db277722; color:#db2777; padding:2px 8px; border-radius:8px; font-size:0.78rem; font-weight:700;'>👤 Fernanda</span>"
                     if c["titular"] == "Fernanda" else
                     "<span style='background:#f59e0b22; color:#f59e0b; padding:2px 8px; border-radius:8px; font-size:0.78rem; font-weight:700;'>⚠️ Titular a Confirmar</span>")
                )
                st.markdown(f"### {ic} {c['nome']} {tit_badge}", unsafe_allow_html=True)
                st.caption(f"Valor Original Comprovado: **{formatar_moeda_br(c['valor_original_comprovado'])}** ({c['total_parc_comprovado']}x) • Categoria: **{c['categoria']}**")

            with col_h2:
                st.markdown(f"**Saldo a Pagar:** {formatar_moeda_br(c['total_aberto'])}")
                if c["prox_venc"]:
                    try:
                        pv_br = datetime.strptime(str(c["prox_venc"])[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                    except Exception:
                        pv_br = str(c["prox_venc"])
                    st.caption(f"🗓️ Próx. Venc: **{pv_br}**")

            with col_h3:
                st.progress(c["pct_progresso"], text=f"{c['pct_progresso']*100:.0f}% quitado")

            if c["titular"] in ("A Confirmar", "None", ""):
                with st.expander("⚠️ Atribuir Titular desta Compra", expanded=False):
                    c_t1, c_t2, c_t3 = st.columns([1.5, 1, 1])
                    with c_t1:
                        st.caption("Selecione o titular definitivo:")
                    with c_t2:
                        if st.button("Atribuir a Carlos", key=f"btn_tit_carlos_{c['grupo_id']}", use_container_width=True):
                            conn_t = conectar()
                            conn_t.execute("UPDATE pagaleve_compras SET titular = 'Carlos' WHERE grupo_parcelamento = ?", (c["grupo_id"],))
                            conn_t.execute("UPDATE transacoes SET titular = 'Carlos' WHERE grupo_parcelamento = ?", (c["grupo_id"],))
                            conn_t.commit()
                            conn_t.close()
                            st.success("Titular atualizado para Carlos!")
                            st.rerun()
                    with c_t3:
                        if st.button("Atribuir a Fernanda", key=f"btn_tit_fer_{c['grupo_id']}", use_container_width=True):
                            conn_t = conectar()
                            conn_t.execute("UPDATE pagaleve_compras SET titular = 'Fernanda' WHERE grupo_parcelamento = ?", (c["grupo_id"],))
                            conn_t.execute("UPDATE transacoes SET titular = 'Fernanda' WHERE grupo_parcelamento = ?", (c["grupo_id"],))
                            conn_t.commit()
                            conn_t.close()
                            st.success("Titular atualizado para Fernanda!")
                            st.rerun()

            if c["parc_anteriores_quitadas"] > 0:
                st.info(f"ℹ️ **Histórico Comprovado:** {c['parc_anteriores_quitadas']} parcela(s) quitada(s) anteriormente fora do banco e {c['parc_registradas']} registradas ativas.")

            with st.expander(f"🔍 Ver Parcelas e Detalhes ({len(c['itens'])} parcelas no banco)", expanded=False):
                cols_p = st.columns(min(4, max(1, len(c["itens"]))))
                for idx, item_p in enumerate(c["itens"]):
                    c_target = cols_p[idx % len(cols_p)]
                    with c_target:
                        with st.container(border=True):
                            try:
                                dt_fmt = datetime.strptime(str(item_p["data"])[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                            except Exception:
                                dt_fmt = str(item_p["data"])

                            m = re.search(r'(\d+)/(\d+)', item_p["descricao"])
                            num_r = f"Parcela {m.group(1)}/{m.group(2)}" if m else f"Parcela {idx+1}"
                            p_val = int(item_p["pago"]) if pd.notna(item_p["pago"]) else 0

                            tag_st = ":green[**✅ Paga**]" if p_val == 1 else ":red[**⏳ Pendente**]"
                            st.markdown(f"**{num_r}**")
                            st.caption(f"🗓️ {dt_fmt}")
                            st.markdown(f"**{formatar_moeda_br(item_p['valor'])}**")
                            st.markdown(tag_st)

                            if p_val == 1:
                                if st.button("🔍 Detalhes", key=f"btn_det_pl_{item_p['id']}", use_container_width=True):
                                    modal_historico_pagamento(item_p["id"])
                            else:
                                if st.button("💳 Pagar", key=f"btn_pg_pl_{item_p['id']}", use_container_width=True, type="primary"):
                                    modal_registrar_pagamento(item_p["id"])

    with tab_ativas:
        compras_ativas = [c for c in compras if c["status"] == "Ativa"]
        if not compras_ativas:
            st.success("🎉 Nenhuma compra Paga Leve pendente para o filtro selecionado!")
        else:
            for c in compras_ativas:
                render_cartao_compra_expandivel(c)
                st.write("")

    with tab_quitadas:
        compras_quitadas = [c for c in compras if c["status"] == "Quitada"]
        if not compras_quitadas:
            st.info("Nenhuma compra quitada para o filtro selecionado.")
        else:
            for c in compras_quitadas:
                render_cartao_compra_expandivel(c)
                st.write("")

    with tab_todas:
        st.markdown("##### 📋 Listagem Geral de Parcelas Paga Leve")
        df_exib = df_pl[["data", "descricao", "valor", "titular_efetivo", "categoria", "conta", "pago"]].copy()
        df_exib["Status"] = df_exib["pago"].apply(lambda x: "Paga" if x == 1 else "Pendente")
        df_exib["Valor"] = df_exib["valor"].apply(formatar_moeda_br)
        df_exib["Vencimento"] = df_exib["data"].apply(lambda d: datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%d/%m/%Y") if pd.notna(d) else "")
        st.dataframe(
            df_exib.rename(columns={
                "descricao": "Descrição",
                "titular_efetivo": "Titular",
                "categoria": "Categoria",
                "conta": "Conta"
            })[["Vencimento", "Descrição", "Valor", "Titular", "Categoria", "Conta", "Status"]],
            use_container_width=True,
            hide_index=True
        )


def render_dividas(df: pd.DataFrame):
    """
    PÁGINA DEDICADA: DÍVIDAS E ACORDOS FAMILIARES
    Controle independente de dois modelos de dívida:
    1. Dívida Livre: credor, valor original, amortizações manuais, meta voluntária, sem movimentar contas bancárias.
    2. Dívida Negociada: acordos parcelados com vencimentos integrados às obrigações a pagar do fluxo de caixa.
    """
    col_t1, col_t2, col_t3 = st.columns([2.5, 1.2, 1.3], vertical_alignment="center")
    with col_t1:
        st.subheader("🤝 Gestão de Dívidas & Acordos")
        st.caption("Controle manual independente para dívidas livres e acordos parcelados integrados ao calendário de contas a pagar.")
    with col_t2:
        if st.button("➕ Nova Dívida Livre", use_container_width=True, type="primary"):
            modal_nova_divida_livre()
    with col_t3:
        if st.button("📑 Novo Acordo Negociado", use_container_width=True):
            modal_novo_acordo_divida()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT d.*,
               COALESCE((SELECT SUM(m.valor_pago) FROM dividas_pagamentos_manuais m WHERE m.divida_id = d.id AND m.cancelado = 0), 0.0) as total_manual_pago
        FROM dividas_gerenciamento d
        ORDER BY d.id DESC
    """)
    dividas_rows = [dict(r) for r in cur.fetchall()]

    for d in dividas_rows:
        if d["tipo_divida"] == "negociada" and d["acordo_grupo_parcelamento"]:
            cur.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN pago = 1 THEN valor ELSE 0.0 END), 0.0) as total_acordo_pago,
                    COALESCE(SUM(CASE WHEN pago != 1 THEN valor ELSE 0.0 END), 0.0) as total_acordo_aberto,
                    COUNT(CASE WHEN pago = 1 THEN 1 END) as parc_pagas,
                    COUNT(*) as parc_total
                FROM transacoes
                WHERE grupo_parcelamento = ?
            """, (d["acordo_grupo_parcelamento"],))
            ac_res = cur.fetchone()
            d["total_acordo_pago"] = ac_res[0]
            d["total_acordo_aberto"] = ac_res[1]
            d["parc_pagas"] = ac_res[2]
            d["parc_total"] = ac_res[3]
        else:
            d["total_acordo_pago"] = 0.0
            d["total_acordo_aberto"] = 0.0
            d["parc_pagas"] = 0
            d["parc_total"] = 0

    conn.close()

    dividas_livres = [d for d in dividas_rows if d["tipo_divida"] == "livre"]
    dividas_negociadas = [d for d in dividas_rows if d["tipo_divida"] == "negociada"]

    total_livres_orig = sum(d["valor_original"] for d in dividas_livres)
    total_livres_pago = sum(d["total_manual_pago"] for d in dividas_livres)
    total_livres_saldo = sum(d["saldo_atual"] for d in dividas_livres)

    total_neg_orig = sum(d["valor_original"] for d in dividas_negociadas)
    total_neg_pago = sum(d["total_manual_pago"] + d["total_acordo_pago"] for d in dividas_negociadas)
    total_neg_saldo = sum(max(0.0, d["valor_original"] - (d["total_manual_pago"] + d["total_acordo_pago"])) for d in dividas_negociadas)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Saldo Dívidas Livres", formatar_moeda_br(total_livres_saldo), f"{len(dividas_livres)} dívidas livres", delta_color="inverse")
    with k2:
        st.metric("Saldo Acordos Negociados", formatar_moeda_br(total_neg_saldo), f"{len(dividas_negociadas)} acordos ativos", delta_color="inverse")
    with k3:
        st.metric("Total Já Amortizado", formatar_moeda_br(total_livres_pago + total_neg_pago), "Pagamentos manuais + acordos")
    with k4:
        st.metric("Passivo Consolidado Total", formatar_moeda_br(total_livres_saldo + total_neg_saldo), "Compromissos familiares")

    st.write("")
    tab_livres, tab_negociadas = st.tabs([
        f"🕊️ Dívidas Livres ({len(dividas_livres)})",
        f"📋 Dívidas Negociadas / Acordos ({len(dividas_negociadas)})"
    ])

    with tab_livres:
        if not dividas_livres:
            st.info("Nenhuma dívida livre cadastrada ainda. Utilize o botão '+ Nova Dívida Livre' acima para cadastrar compromissos familiares (ex: troca do carro, pai, Rubens).")
        else:
            for d in dividas_livres:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2.5, 1.3, 1.2], vertical_alignment="center")
                    with c1:
                        st.markdown(f"### 🤝 {d['descricao']}")
                        st.caption(f"Credor: **{d['credor']}** • Data Início: **{d['data_inicio'] or '-'}**")
                    with c2:
                        st.markdown(f"**Valor Original:** {formatar_moeda_br(d['valor_original'])}")
                        st.markdown(f"**Saldo Devedor:** :orange[{formatar_moeda_br(d['saldo_atual'])}]")
                    with c3:
                        pct = min(1.0, (d['valor_original'] - d['saldo_atual']) / d['valor_original']) if d['valor_original'] > 0 else 1.0
                        st.progress(pct, text=f"{pct*100:.0f}% quitado")

                    c_b1, c_b2, c_b3 = st.columns([2, 1.2, 1.4], vertical_alignment="center")
                    with c_b1:
                        meta_txt = []
                        if d.get("meta_voluntaria_mensal", 0) > 0:
                            meta_txt.append(f"Meta Mensal: **{formatar_moeda_br(d['meta_voluntaria_mensal'])}**")
                        if d.get("meta_voluntaria_semanal", 0) > 0:
                            meta_txt.append(f"Meta Semanal: **{formatar_moeda_br(d['meta_voluntaria_semanal'])}**")
                        st.caption(" • ".join(meta_txt) if meta_txt else "Sem meta voluntária cadastrada (pagamentos livres).")

                    with c_b2:
                        if st.button("💵 Registrar Pagamento", key=f"btn_pg_div_{d['id']}", use_container_width=True, type="primary"):
                            modal_pagamento_manual_divida(d["id"])

                    with c_b3:
                        if st.button("🤝 Transformar em Acordo", key=f"btn_transf_div_{d['id']}", use_container_width=True):
                            modal_transformar_divida_negociada(d["id"])

                    conn_h = conectar()
                    conn_h.row_factory = sqlite3.Row
                    cur_h = conn_h.cursor()
                    cur_h.execute("""
                        SELECT * FROM dividas_pagamentos_manuais
                        WHERE divida_id = ? AND cancelado = 0
                        ORDER BY data_pagamento DESC, id DESC
                    """, (d["id"],))
                    pags_man = cur_h.fetchall()
                    conn_h.close()

                    with st.expander(f"📜 Histórico de Pagamentos Manuais ({len(pags_man)} registros)", expanded=False):
                        if not pags_man:
                            st.caption("Nenhum pagamento manual registrado ainda para esta dívida.")
                        else:
                            for pm in pags_man:
                                col_p1, col_p2, col_p3 = st.columns([1.5, 3, 1])
                                try:
                                    dt_p_br = datetime.strptime(str(pm["data_pagamento"])[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                                except Exception:
                                    dt_p_br = str(pm["data_pagamento"])
                                col_p1.markdown(f"🗓️ **{dt_p_br}**")
                                col_p2.markdown(f"**{formatar_moeda_br(pm['valor_pago'])}** — {pm['observacao'] or 'Sem observação'}")
                                with col_p3:
                                    if st.button("↩️ Estornar", key=f"btn_estorno_div_{pm['id']}", use_container_width=True):
                                        conn_est = conectar()
                                        cur_est = conn_est.cursor()
                                        cur_est.execute("""
                                            UPDATE dividas_pagamentos_manuais
                                            SET cancelado = 1, cancelado_em = CURRENT_TIMESTAMP, motivo_cancelamento = 'Estorno solicitado pelo usuário'
                                            WHERE id = ?
                                        """, (pm["id"],))
                                        cur_est.execute("""
                                            UPDATE dividas_gerenciamento
                                            SET saldo_atual = saldo_atual + ?, status = 'ativa'
                                            WHERE id = ?
                                        """, (pm["valor_pago"], d["id"]))
                                        conn_est.commit()
                                        conn_est.close()
                                        st.success("Pagamento estornado com sucesso!")
                                        st.rerun()

    with tab_negociadas:
        if not dividas_negociadas:
            st.info("Nenhum acordo negociado cadastrado ainda. Use o botão '📑 Novo Acordo Negociado' acima ou transforme uma dívida livre existente.")
        else:
            for d in dividas_negociadas:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2.5, 1.3, 1.2], vertical_alignment="center")
                    with c1:
                        st.markdown(f"### 📋 {d['descricao']}")
                        st.caption(f"Credor: **{d['credor']}** • Acordo: **{d['acordo_parcelas']}x de {formatar_moeda_br(d['acordo_valor_parcela'])}**")
                    with c2:
                        saldo_restante = max(0.0, d["valor_original"] - (d["total_manual_pago"] + d["total_acordo_pago"]))
                        st.markdown(f"**Valor Acordo:** {formatar_moeda_br(d['valor_original'])}")
                        st.markdown(f"**A Vencer:** :orange[{formatar_moeda_br(saldo_restante)}]")
                    with c3:
                        tot_pago = d["total_manual_pago"] + d["total_acordo_pago"]
                        pct = min(1.0, tot_pago / d['valor_original']) if d['valor_original'] > 0 else 1.0
                        st.progress(pct, text=f"{pct*100:.0f}% quitado")

                    conn_p = conectar()
                    conn_p.row_factory = sqlite3.Row
                    cur_p = conn_p.cursor()
                    cur_p.execute("""
                        SELECT * FROM transacoes
                        WHERE grupo_parcelamento = ?
                        ORDER BY data ASC, id ASC
                    """, (d["acordo_grupo_parcelamento"],))
                    parcelas_acordo = cur_p.fetchall()
                    conn_p.close()

                    with st.expander(f"🗓️ Parcelas do Acordo Integradas ao Caixa ({d['parc_pagas']}/{d['parc_total']} pagas)", expanded=False):
                        cols_ac = st.columns(min(4, max(1, len(parcelas_acordo))))
                        for idx, p_ac in enumerate(parcelas_acordo):
                            col_t = cols_ac[idx % len(cols_ac)]
                            with col_t:
                                with st.container(border=True):
                                    try:
                                        dt_ac_br = datetime.strptime(str(p_ac["data"])[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                                    except Exception:
                                        dt_ac_br = str(p_ac["data"])

                                    m = re.search(r'(\d+)/(\d+)', p_ac["descricao"])
                                    rot = f"Parcela {m.group(1)}/{m.group(2)}" if m else f"Parcela {idx+1}"
                                    pago_val = int(p_ac["pago"]) if pd.notna(p_ac["pago"]) else 0

                                    st.markdown(f"**{rot}**")
                                    st.caption(f"🗓️ {dt_ac_br}")
                                    st.markdown(f"**{formatar_moeda_br(p_ac['valor'])}**")
                                    st.markdown(":green[**✅ Paga**]" if pago_val == 1 else ":red[**⏳ Pendente**]")

                                    if pago_val != 1:
                                        if st.button("💳 Pagar", key=f"btn_pg_ac_{p_ac['id']}", use_container_width=True, type="primary"):
                                            modal_registrar_pagamento(p_ac["id"])
                                    else:
                                        if st.button("🔍 Ver", key=f"btn_det_ac_{p_ac['id']}", use_container_width=True):
                                            modal_historico_pagamento(p_ac["id"])


def render_categorias(df: pd.DataFrame):
    """
    PÁGINA DEDICADA: GESTÃO HIERÁRQUICA DE CATEGORIAS (CERBASI / ORGANIZZE)
    Visualização e edição da estrutura dos 16 grupos e 63 subcategorias,
    naturezas dos gastos e resolução controlada de lançamentos pendentes.
    """
    col_t1, col_t2, col_t3 = st.columns([2.5, 1.2, 1.3], vertical_alignment="center")
    with col_t1:
        st.subheader("📂 Categorias & Metodologia Cerbasi")
        st.caption("Estrutura hierárquica baseada na metodologia de Gustavo Cerbasi (16 grupos e subcategorias flexíveis).")
    with col_t2:
        if st.button("➕ Nova Subcategoria", use_container_width=True, type="primary"):
            modal_nova_subcategoria()
    with col_t3:
        if st.button("➕ Novo Grupo", use_container_width=True):
            modal_novo_grupo()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT g.*, COUNT(s.id) as total_subs
        FROM grupos_categoria g
        LEFT JOIN subcategorias s ON s.grupo_id = g.id
        GROUP BY g.id
        ORDER BY g.ordem ASC
    """)
    grupos_db = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT t.*
        FROM transacoes t
        WHERE t.status_rateio != 'normal'
        ORDER BY t.data ASC, t.id ASC
    """)
    pendentes_db = [dict(r) for r in cur.fetchall()]
    conn.close()

    total_subs = sum(g["total_subs"] for g in grupos_db)
    despesas_cnt = sum(1 for g in grupos_db if g["tipo"] == "despesa")
    receitas_cnt = sum(1 for g in grupos_db if g["tipo"] == "receita")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Grupos Principais", f"{len(grupos_db)} grupos", f"{despesas_cnt} despesas • {receitas_cnt} receitas")
    with k2:
        st.metric("Subcategorias Ativas", f"{total_subs} subcategorias", "Estrutura Cerbasi")
    with k3:
        st.metric("Lançamentos Pendentes", f"{len(pendentes_db)} itens", "Aguardando confirmação", delta_color="inverse")
    with k4:
        st.metric("Metodologia", "Gustavo Cerbasi", "Orçamento em pirâmide")

    st.write("")
    tab_estrutura, tab_pendentes = st.tabs([
        f"📁 Hierarquia de Categorias ({len(grupos_db)} grupos)",
        f"⚠️ Lançamentos com Pendência de Classificação ({len(pendentes_db)})"
    ])

    with tab_estrutura:
        st.caption("Clique no grupo para visualizar ou editar suas subcategorias. É possível adicionar novas, renomear ou desativar sem apagar o histórico.")
        
        conn_s = conectar()
        conn_s.row_factory = sqlite3.Row
        cur_s = conn_s.cursor()

        for g in grupos_db:
            cur_s.execute("""
                SELECT * FROM subcategorias
                WHERE grupo_id = ?
                ORDER BY ordem ASC, nome ASC
            """, (g["id"],))
            subs = cur_s.fetchall()

            status_g = "Ativo" if g.get("ativo", 1) == 1 else "Inativo"
            tipo_rot = "Despesa" if g["tipo"] == "despesa" else "Receita"

            with st.expander(f"{g['icone']} **{g['nome']}** — {len(subs)} subcategorias ({tipo_rot})", expanded=False):
                st.caption(f"Descrição: *{g.get('descricao', 'Sem descrição')}*")

                if not subs:
                    st.info("Nenhuma subcategoria cadastrada neste grupo.")
                else:
                    dados_subs = []
                    for s in subs:
                        st_s = "✅ Ativa" if s["ativo"] == 1 else "❌ Inativa"
                        dados_subs.append({
                            "Ícone": s["icone"],
                            "Subcategoria": s["nome"],
                            "Natureza": s["natureza_padrao"].capitalize(),
                            "Finalidade": s["finalidade"].capitalize(),
                            "Status": st_s
                        })
                    st.dataframe(pd.DataFrame(dados_subs), use_container_width=True, hide_index=True)

                c_act1, _ = st.columns([1.5, 1.5])
                with c_act1:
                    if st.button(f"+ Subcategoria em '{g['nome']}'", key=f"btn_add_sub_{g['id']}", use_container_width=True):
                        modal_nova_subcategoria(g["id"])

        conn_s.close()

    with tab_pendentes:
        st.markdown("##### ⚠️ Lançamentos com Pendência de Confirmação ou Rateio")
        st.caption("Estes lançamentos foram preservados sem imposição de dados ou rateios fictícios. Você pode atribuir o grupo e subcategoria corretos a qualquer momento.")

        if not pendentes_db:
            st.success("🎉 Todos os lançamentos do banco estão classificados com sucesso!")
        else:
            for p in pendentes_db:
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([1.2, 2.5, 1.5, 1.3], vertical_alignment="center")
                    try:
                        dt_p = datetime.strptime(str(p["data"])[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                    except Exception:
                        dt_p = str(p["data"])

                    col1.markdown(f"🗓️ **{dt_p}**")
                    col2.markdown(f"**{p['descricao']}**<br><span style='font-size:0.8rem; color:var(--text-muted);'>Conta: {p['conta']}</span>", unsafe_allow_html=True)
                    
                    st_badge = (
                        "<span style='background:#f59e0b22; color:#f59e0b; padding:2px 6px; border-radius:6px; font-size:0.75rem; font-weight:600;'>Pendente Rateio</span>"
                        if p["status_rateio"] == "pendente_rateio" else
                        ("<span style='background:#3b82f622; color:#3b82f6; padding:2px 6px; border-radius:6px; font-size:0.75rem; font-weight:600;'>Pendente Confirmação</span>"
                         if p["status_rateio"] == "pendente_confirmacao" else
                         f"<span style='background:#8b5cf622; color:#8b5cf6; padding:2px 6px; border-radius:6px; font-size:0.75rem; font-weight:600;'>{p['status_rateio']}</span>")
                    )
                    col3.markdown(f"**{formatar_moeda_br(p['valor'])}**<br>{st_badge}", unsafe_allow_html=True)

                    with col4:
                        if st.button("🎯 Classificar", key=f"btn_classif_{p['id']}", use_container_width=True, type="primary"):
                            modal_classificar_transacao(p["id"])


# =============================================================================
# 8. PÁGINA DEDICADA: CONFIGURAÇÕES & GESTÃO DO SISTEMA
# =============================================================================
def render_configuracoes(df: pd.DataFrame, df_turnos: pd.DataFrame):
    """
    PÁGINA DEDICADA: CONFIGURAÇÕES & GESTÃO DO SISTEMA
    Configurações gerais, integridade do banco SQLite, histórico de conciliações,
    gerenciamento de layout e download de backup integral.
    """
    st.subheader("⚙️ Configurações & Gestão do Sistema")
    st.caption("Administração da Central Financeira, segurança de dados, conciliações e personalização.")

    sec1, sec2 = st.columns(2, gap="medium")

    with sec1:
        with st.container(border=True):
            st.markdown("#### 🏛️ Identidade & Personalização")
            st.markdown(f"**Nome da Aplicação:** `{APP_TITLE}`")
            st.caption("Nome provisório definido no código. Para alterar, basta atualizar a constante `APP_TITLE`.")
            st.markdown(f"**Subtítulo / Usuário:** `{APP_SUBTITLE}`")
            st.markdown(f"**Tema Ativo:** {st.session_state.get('tema', 'Claro')}")
            st.divider()
            st.markdown("##### 🔀 Organização do Dashboard")
            st.caption("Personalize a ordem e posição dos blocos na sua Visão Geral.")
            if st.button("⚙️ Organizar Posição dos Blocos", use_container_width=True):
                modal_organizar_blocos()

        with st.container(border=True):
            st.markdown("#### ⚖️ Conciliação & Marcos Iniciais")
            st.caption("O sistema utiliza conciliação por marcos de corte (19/10/2026). Registre novos marcos ou confira o histórico:")
            if st.button("➕ Conciliar Saldo / Definir Novo Marco", use_container_width=True, type="primary"):
                modal_ajustar_saldo()

            conn = conectar()
            ajustes = saldo_service.obter_historico_ajustes(conn)
            conn.close()

            if ajustes:
                st.markdown("###### 📜 Histórico de Ajustes e Marcos Ativos:")
                for aj in ajustes[:3]:
                    dt_aj = datetime.strptime(aj["data"], "%Y-%m-%d").strftime("%d/%m/%Y")
                    st.caption(f"🏦 **{aj['conta_nome']}** • {dt_aj} • R$ {aj['saldo_informado']:,.2f} ({aj['tipo']})")

    with sec2:
        with st.container(border=True):
            st.markdown("#### 🏦 Contas & Cartões Cadastrados")
            st.caption("Gerencie contas correntes, carteiras e cartões de crédito:")
            c_btn_c1, c_btn_c2 = st.columns(2)
            with c_btn_c1:
                if st.button("➕ Nova Conta Bancária", use_container_width=True):
                    modal_nova_conta()
            with c_btn_c2:
                if st.button("➕ Novo Cartão", use_container_width=True):
                    modal_novo_cartao()

            conn = conectar()
            contas = saldo_service.obter_contas(conn)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM cartoes")
            num_cartoes = cur.fetchone()[0]
            conn.close()

            st.markdown(f"• **Contas Ativas ({len(contas)}):** {', '.join(c['nome'] for c in contas)}")
            st.markdown(f"• **Cartões de Crédito:** {num_cartoes} cadastrado(s)")

        with st.container(border=True):
            st.markdown("#### 💾 Segurança, Integridade & Backups")
            conn = conectar()
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            check_status = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM transacoes")
            cnt_trans = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM pagamentos_despesas")
            cnt_pags = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM turnos")
            cnt_turnos = cur.fetchone()[0]
            conn.close()

            if check_status == "ok":
                st.success("✅ Integridade do Banco SQLite: 100% OK")
            else:
                st.error(f"⚠️ Atenção: {check_status}")

            st.caption(f"Registros ativos: **{cnt_trans} transações** • **{cnt_pags} pagamentos auditados** • **{cnt_turnos} turnos de motorista**.")
            st.divider()

            # Botão de download de backup em tempo real
            if os.path.exists(DB_NAME):
                with open(DB_NAME, "rb") as f_db:
                    db_bytes = f_db.read()
                st.download_button(
                    label="💾 Baixar Backup do Banco de Dados (.db)",
                    data=db_bytes,
                    file_name=f"financas_casa_backup_{date.today().strftime('%Y%m%d')}.db",
                    mime="application/x-sqlite3",
                    use_container_width=True
                )


# =============================================================================
# 9. PONTO DE ENTRADA PRINCIPAL (MAIN)
# =============================================================================
def main():
    # Configuração de Página Streamlit
    st.set_page_config(
        page_title=f"{APP_TITLE} • Gestor Pessoal",
        layout="wide",
        page_icon="💼",
        initial_sidebar_state="collapsed"
    )

    # Estado de Tema (Padrão: Modo Claro)
    if "tema" not in st.session_state:
        st.session_state["tema"] = "Claro"

    # Aplicação imediata dos estilos CSS com correção de cortes e legibilidade
    aplicar_estilos_tema(st.session_state["tema"])

    # Inicializa tabelas e migrações no banco de dados
    inicializar_banco()

    # Controle de Estado da Navegação
    if "pagina_ativa" not in st.session_state:
        st.session_state["pagina_ativa"] = "Visão Geral"

    PAGINAS_PRINCIPAIS = [
        "Visão Geral",
        "Lançamentos",
        "Contas",
        "Cartões",
        "Motorista App",
        "Mais ▾"
    ]

    PAGINAS_MAIS = [
        "Paga Leve",
        "Dívidas",
        "Categorias",
        "🎯 Planejamento & Metas",
        "Planejamento & Metas",
        "Orçamento / Limites",
        "Relatórios",
        "Configurações"
    ]

    # Determina qual item do menu principal deve estar ativo
    if st.session_state["pagina_ativa"] in PAGINAS_MAIS:
        item_principal_ativo = "Mais ▾"
    elif st.session_state["pagina_ativa"] in PAGINAS_PRINCIPAIS:
        item_principal_ativo = st.session_state["pagina_ativa"]
    else:
        item_principal_ativo = "Visão Geral"
        st.session_state["pagina_ativa"] = "Visão Geral"

    # Cabeçalho Superior: Logotipo sem corte + Navegação nítida + Seletor de Tema
    col_logo, col_nav, col_tema = st.columns([1.1, 2.8, 1.1], vertical_alignment="center")
    
    with col_logo:
        st.markdown(f"""
        <div style="padding-top: 2px; overflow: visible;">
            <div style="font-size: 1.45rem; font-weight: 800; line-height: 1.25; color: var(--text-primary); display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1.35rem;">💼</span> {APP_TITLE}
            </div>
            <div style="color: var(--text-muted); font-size: 0.82rem; margin-top: 2px; font-weight: 500;">
                Carlos • {date.today().strftime('%d/%m/%Y')}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_nav:
        escolha = st.segmented_control(
            "Navegação Principal",
            options=PAGINAS_PRINCIPAIS,
            default=item_principal_ativo,
            label_visibility="collapsed"
        )
        if escolha and escolha != item_principal_ativo:
            if escolha == "Mais ▾":
                if st.session_state["pagina_ativa"] not in PAGINAS_MAIS:
                    st.session_state["pagina_ativa"] = "🎯 Planejamento & Metas"
                st.rerun()
            else:
                st.session_state["pagina_ativa"] = escolha
                st.rerun()

    with col_tema:
        # Seletor dinâmico de tema (Claro / Noturno) com container flex responsivo
        st.markdown('<div class="header-theme-wrapper">', unsafe_allow_html=True)
        tema_default = "☀️ Claro" if st.session_state["tema"] == "Claro" else "🌙 Noturno"
        escolha_tema = st.segmented_control(
            "Tema da Interface",
            options=["☀️ Claro", "🌙 Noturno"],
            default=tema_default,
            label_visibility="collapsed"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        if escolha_tema:
            novo_tema = "Claro" if "Claro" in escolha_tema else "Noturno"
            if st.session_state["tema"] != novo_tema:
                st.session_state["tema"] = novo_tema
                st.rerun()

    # Submenu contextual para o item "Mais ▾"
    if item_principal_ativo == "Mais ▾" or st.session_state["pagina_ativa"] in PAGINAS_MAIS:
        with st.container(border=True):
            sub_col1, sub_col2 = st.columns([4.2, 1.0], vertical_alignment="center")
            with sub_col1:
                opcoes_sub = [
                    "🎯 Planejamento & Metas",
                    "⚡ Paga Leve",
                    "🤝 Dívidas",
                    "📂 Categorias",
                    "📊 Relatórios",
                    "⚙️ Configurações"
                ]
                mapa_sub = {
                    "🎯 Planejamento & Metas": "🎯 Planejamento & Metas",
                    "⚡ Paga Leve": "Paga Leve",
                    "🤝 Dívidas": "Dívidas",
                    "📂 Categorias": "Categorias",
                    "🎯 Orçamento / Limites": "🎯 Planejamento & Metas",
                    "Orçamento / Limites": "🎯 Planejamento & Metas",
                    "📊 Relatórios": "Relatórios",
                    "⚙️ Configurações": "Configurações"
                }
                sub_default = next((opt for opt, val in mapa_sub.items() if val == st.session_state["pagina_ativa"]), "🎯 Planejamento & Metas")
                escolha_sub = st.segmented_control(
                    "Submenu Mais",
                    options=opcoes_sub,
                    default=sub_default,
                    label_visibility="collapsed"
                )
                if escolha_sub and mapa_sub.get(escolha_sub) != st.session_state["pagina_ativa"]:
                    st.session_state["pagina_ativa"] = mapa_sub[escolha_sub]
                    st.rerun()
            with sub_col2:
                st.markdown(f"""
                <div class="sub-menu-indicator" style="text-align: right; color: var(--text-muted); font-size: 0.82rem; font-weight: 500;">
                    📂 Seção: <b style="color: var(--text-primary);">{st.session_state['pagina_ativa']}</b>
                </div>
                """, unsafe_allow_html=True)

    st.write("") # Espaçador visual

    # Carregamento dos dados atualizados do banco SQLite
    conn = conectar()
    df_transacoes = pd.read_sql_query("SELECT * FROM transacoes ORDER BY data ASC, id ASC", conn)
    df_turnos = pd.read_sql_query("SELECT * FROM turnos ORDER BY data DESC", conn)
    conn.close()

    # Roteamento de Páginas
    pagina = st.session_state["pagina_ativa"]

    if pagina == "Visão Geral":
        render_visao_geral(df_transacoes, df_turnos)
    elif pagina == "Lançamentos":
        render_lancamentos(df_transacoes)
    elif pagina == "Contas":
        render_contas(df_transacoes)
    elif pagina == "Cartões":
        render_cartoes(df_transacoes)
    elif pagina == "Motorista App":
        render_motorista_app(df_transacoes, df_turnos)
    elif pagina == "Paga Leve":
        render_paga_leve(df_transacoes)
    elif pagina == "Dívidas":
        render_dividas(df_transacoes)
    elif pagina == "Categorias":
        render_categorias(df_transacoes)
    elif pagina in ("🎯 Planejamento & Metas", "Planejamento & Metas", "Orçamento / Limites", "Orçamento / Limites de Gastos", "Limite de Gastos"):
        render_planejamento_metas(df_transacoes)
    elif pagina == "Relatórios":
        render_relatorios(df_transacoes, df_turnos)
    elif pagina == "Configurações":
        render_configuracoes(df_transacoes, df_turnos)
    else:
        render_visao_geral(df_transacoes, df_turnos)


if __name__ == "__main__":
    main()