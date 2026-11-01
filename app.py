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
DB_NAME = os.environ.get("OIKOS_DB_PATH", "financas_remodelacao.db")
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


def parse_moeda_centavos(val_str: Any) -> float:
    """
    Converte texto com digitação rápida por centavos ou formato monetário brasileiro para float.
    Exemplos:
    - Digitar '5' -> 0.05 (R$ 0,05)
    - Digitar '500' -> 5.00 (R$ 5,00)
    - Digitar '1170' -> 11.70 (R$ 11,70)
    - 'R$ 55,05' -> 55.05
    """
    if val_str is None:
        return 0.0
    if isinstance(val_str, (int, float)):
        return round(float(val_str), 2)
    s = str(val_str).strip()
    if not s:
        return 0.0
    m_uma_casa = re.search(r"[,.](\d)$", s)
    if m_uma_casa:
        s = s + "0"
    digits = re.sub(r"\D", "", s)
    if not digits:
        return 0.0
    return round(int(digits) / 100.0, 2)


def input_moeda_centavos(
    label: str,
    valor_inicial: float = 0.0,
    key: Optional[str] = None,
    help: Optional[str] = None,
    disabled: bool = False,
    mostrar_preview: bool = True
) -> float:
    """
    Entrada monetária brasileira rápida por centavos compatível com Streamlit.
    Exemplos de digitação rápida: '5' ➔ R$ 0,05 | '500' ➔ R$ 5,00 | '1170' ➔ R$ 11,70.
    """
    val_init_flt = float(valor_inicial) if (valor_inicial is not None and not pd.isna(valor_inicial)) else 0.0
    val_formatado = formatar_moeda_br(val_init_flt) if val_init_flt > 0 else "R$ 0,00"
    ajuda_padrao = help or "💡 Digitação rápida por centavos: '5' ➔ R$ 0,05 | '500' ➔ R$ 5,00 | '1170' ➔ R$ 11,70."
    
    txt = st.text_input(
        label,
        value=val_formatado,
        key=key,
        help=ajuda_padrao,
        disabled=disabled
    )
    val_float = parse_moeda_centavos(txt)
    if mostrar_preview and txt.strip() and not txt.startswith("R$"):
        st.caption(f"Valor apurado: **{formatar_moeda_br(val_float)}**")
    return val_float


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
            padding-top: 0.6rem !important;
            padding-bottom: 1.5rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            max-width: 1440px !important;
            overflow: visible !important;
        }}

        @media (max-width: 768px) {{
            .block-container {{
                padding-top: 0.4rem !important;
                padding-bottom: 1.2rem !important;
                padding-left: 0.85rem !important;
                padding-right: 0.85rem !important;
            }}
        }}

        /* Redução de espaçamentos verticais excessivos */
        div[data-testid="stVerticalBlock"] {{
            gap: 0.75rem !important;
        }}
        hr, div[data-testid="stDivider"] {{
            margin-top: 8px !important;
            margin-bottom: 8px !important;
            border-color: var(--border-color) !important;
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

        /* Cards de Métricas (KPIs) - Compacto, altura uniforme, espaço reservado e responsivo */
        div[data-testid="stMetric"] {{
            background-color: var(--bg-card) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 12px !important;
            padding: 10px 14px !important;
            box-shadow: var(--card-shadow) !important;
            overflow: visible !important;
            min-height: 104px !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: flex-start !important;
            box-sizing: border-box !important;
        }}
        /* Uniformidade estrita dos 5 cards superiores da Visão Geral */
        div[data-testid="column"]:has(div[class*="st-key-btn_kpi_"]) div[data-testid="stMetric"] {{
            min-height: 104px !important;
            height: 104px !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: flex-start !important;
            box-sizing: border-box !important;
        }}
        div[data-testid="stMetric"] label {{
            color: var(--text-muted) !important;
            font-size: 0.82rem !important;
            font-weight: 600 !important;
            white-space: normal !important;
            word-break: break-word !important;
            overflow: visible !important;
        }}
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
            color: var(--text-primary) !important;
            font-weight: 800 !important;
            white-space: normal !important;
            word-break: break-word !important;
            font-size: 1.25rem !important;
            line-height: 1.2 !important;
            overflow: visible !important;
            text-overflow: clip !important;
        }}
        div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {{
            white-space: normal !important;
            word-break: break-word !important;
            font-size: 0.78rem !important;
            line-height: 1.2 !important;
            overflow: visible !important;
            text-overflow: clip !important;
            margin-top: 2px !important;
        }}

        /* Botões dos 5 Indicadores Superiores: discretos, integrados e perfeitamente alinhados na mesma linha */
        div[class*="st-key-btn_kpi_"] {{
            margin-top: 6px !important;
            margin-bottom: 2px !important;
            width: 100% !important;
        }}
        div[class*="st-key-btn_kpi_"] button {{
            width: 100% !important;
            height: 28px !important;
            min-height: 28px !important;
            padding: 2px 6px !important;
            font-size: 0.75rem !important;
            font-weight: 500 !important;
            border-radius: 6px !important;
            background-color: var(--bg-subcard) !important;
            border: 1px solid var(--border-color) !important;
            color: var(--text-muted) !important;
            box-shadow: none !important;
        }}
        div[class*="st-key-btn_kpi_"] button:hover {{
            background-color: var(--bg-card) !important;
            border-color: #3b82f6 !important;
            color: var(--text-primary) !important;
            transform: none !important;
        }}

        /* Responsividade para celular dos 5 KPIs e botões de detalhes */
        @media (max-width: 768px) {{
            div[data-testid="column"]:has(div[class*="st-key-btn_kpi_"]) div[data-testid="stMetric"] {{
                min-height: 94px !important;
                height: auto !important;
                padding: 8px 12px !important;
                margin-bottom: 4px !important;
            }}
            div[class*="st-key-btn_kpi_"] {{
                margin-top: 2px !important;
                margin-bottom: 12px !important;
            }}
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
        div[class*="st-key-btn_quick_"] button {{
            padding: 1px 6px !important;
            min-height: 24px !important;
            height: 24px !important;
            font-size: 0.72rem !important;
            line-height: 1 !important;
            border-radius: 6px !important;
            background-color: transparent !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            color: var(--text-muted) !important;
        }}
        div[class*="st-key-btn_quick_"] button:hover {{
            border-color: #3b82f6 !important;
            color: var(--text-primary) !important;
            background-color: rgba(59, 130, 246, 0.1) !important;
        }}
        div[class*="st-key-card_"] {{
            transition: box-shadow 0.2s ease, border-color 0.2s ease;
        }}
        div[class*="st-key-card_"]:hover {{
            border-color: rgba(59, 130, 246, 0.45) !important;
        }}

        /* CONTAS A PAGAR COMPACTO: Linha única com Ação Estilo Organizze */
        div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-btn_baixa_cp_"]) {{
            gap: 4px !important;
            padding-top: 2px !important;
            padding-bottom: 2px !important;
            align-items: center !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            transition: background 0.15s ease;
        }}

        div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-btn_baixa_cp_"]):hover {{
            background-color: rgba(255, 255, 255, 0.02);
            border-radius: 6px;
        }}

        div[class*="st-key-btn_baixa_cp_"] {{
            display: flex !important;
            justify-content: flex-end !important;
            align-items: center !important;
            margin: 0 !important;
            padding: 0 !important;
        }}

        div[class*="st-key-btn_baixa_cp_"] button {{
            background-color: transparent !important;
            border: 1px solid rgba(156, 163, 175, 0.25) !important;
            color: var(--text-muted, #9ca3af) !important;
            border-radius: 8px !important;
            padding: 1px 4px !important;
            min-height: 25px !important;
            height: 25px !important;
            width: 28px !important;
            min-width: 28px !important;
            font-size: 0.82rem !important;
            line-height: 1 !important;
            opacity: 0.35 !important;
            box-shadow: none !important;
            transition: opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1), transform 0.15s ease, background-color 0.15s ease, border-color 0.15s ease !important;
        }}

        /* Hover no Desktop: Transição suave e destaque estilo Organizze */
        div[class*="st-key-btn_baixa_cp_"] button:hover {{
            opacity: 1.0 !important;
            border-color: #10b981 !important;
            color: #10b981 !important;
            background-color: rgba(16, 185, 129, 0.15) !important;
            transform: scale(1.08) !important;
            box-shadow: 0 2px 6px rgba(16, 185, 129, 0.25) !important;
        }}

        /* Em telas móveis e touch: sempre perfeitamente visível e clicável */
        @media (hover: none), (max-width: 768px) {{
            div[class*="st-key-btn_baixa_cp_"] button {{
                opacity: 0.85 !important;
                border-color: rgba(156, 163, 175, 0.45) !important;
                min-height: 28px !important;
                height: 28px !important;
                width: 30px !important;
                min-width: 30px !important;
                background-color: rgba(255, 255, 255, 0.04) !important;
            }}
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
        ('status_conciliacao', "TEXT DEFAULT 'conciliado'"),
        ('km_inicial', "REAL"),
        ('km_final', "REAL"),
        ('ganho_dinheiro_pix', "REAL DEFAULT 0"),
        ('ganho_online', "REAL DEFAULT 0"),
        ('status_turno', "TEXT DEFAULT 'encerrado'"),
        ('combustivel_consumido_estimado', "REAL DEFAULT 0"),
        ('created_at', "TEXT")
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

    # 2.1 Marco de Produção Acumulada do Motorista (histórico operacional sem efeito financeiro em saldos)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS motorista_marco_producao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plataforma TEXT NOT NULL DEFAULT '99',
        data_corte DATE NOT NULL,
        faturamento_bruto REAL NOT NULL,
        recebido_dinheiro_pix REAL NOT NULL,
        recebido_online REAL NOT NULL,
        observacao TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        revisao INTEGER DEFAULT 1,
        status TEXT DEFAULT 'ativo'
    );
    """)
    for col, col_def in [
        ('revisao', 'INTEGER DEFAULT 1'),
        ('status', "TEXT DEFAULT 'ativo'")
    ]:
        try:
            cur.execute(f"ALTER TABLE motorista_marco_producao ADD COLUMN {col} {col_def}")
        except Exception:
            pass
    try:
        cur.execute("UPDATE motorista_marco_producao SET revisao = 1 WHERE revisao IS NULL")
        cur.execute("UPDATE motorista_marco_producao SET status = 'ativo' WHERE status IS NULL")
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

def normalizar_id_bloco(bloco_id: str) -> str:
    """Normaliza identificadores e aliases de blocos do dashboard para um identificador canônico."""
    if not bloco_id:
        return ""
    b = str(bloco_id).strip().lower()
    mapa = {
        "bloco_cartoes": "cartoes",
        "cartao": "cartoes",
        "cartoes": "cartoes",
        "contas_a_pagar": "contas_pagar",
        "contas_pagar": "contas_pagar",
        "conta_pagar": "contas_pagar",
        "missao_ipva": "missao_semana",
        "missao": "missao_semana",
        "missao_semana": "missao_semana",
        "ultimos_turnos": "turnos",
        "turnos": "turnos",
        "turno": "turnos",
        "contas": "contas",
        "paga_leve": "paga_leve",
        "limites": "limites",
        "maiores_gastos": "maiores_gastos"
    }
    return mapa.get(b, b)


def carregar_layout_dashboard() -> Tuple[List[str], List[str], Dict[str, bool]]:
    """Carrega as posições salvas dos blocos do banco de dados SQLite ou retorna o padrão funcional Organizze."""
    padrao_esq = ["contas", "cartoes"]
    padrao_dir = ["contas_pagar", "missao_semana", "turnos"]
    padrao_visiveis = {
        "contas": True,
        "cartoes": True,
        "contas_pagar": True,
        "missao_semana": True,
        "turnos": True,
        "paga_leve": False,
        "limites": False,
        "maiores_gastos": False
    }
    
    conn = conectar()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS config_dashboard (chave TEXT PRIMARY KEY, valor TEXT)")
    cur.execute("SELECT chave, valor FROM config_dashboard")
    configs = dict(cur.fetchall())
    conn.close()
    
    blocos_removidos = {"caixa_7dias", "projecao_mes", "capacidade_trabalho"}
    todos_blocos = [
        "contas", "cartoes", "missao_semana", "contas_pagar", "turnos",
        "paga_leve", "limites", "maiores_gastos"
    ]

    raw_esq = [normalizar_id_bloco(b) for b in configs.get("col_esq", "").split(",") if b.strip()] if configs.get("col_esq") else padrao_esq
    raw_dir = [normalizar_id_bloco(b) for b in configs.get("col_dir", "").split(",") if b.strip()] if configs.get("col_dir") else padrao_dir

    col_esq = [b for b in raw_esq if b not in blocos_removidos and b in todos_blocos]
    col_dir = [b for b in raw_dir if b not in blocos_removidos and b in todos_blocos]

    # Deduplicar preservando a ordem
    col_esq = list(dict.fromkeys(col_esq))
    # Garantir que nenhum bloco duplicado permaneça na coluna direita se já estiver na esquerda
    col_dir = [b for b in list(dict.fromkeys(col_dir)) if b not in col_esq]

    if not col_esq:
        col_esq = ["contas", "cartoes"]
    if not col_dir:
        col_dir = ["contas_pagar", "missao_semana", "turnos"]

    visiveis = padrao_visiveis.copy()
    if "visiveis" in configs and configs["visiveis"]:
        import json
        try:
            vis_salvas = json.loads(configs["visiveis"])
            for k, v in vis_salvas.items():
                k_norm = normalizar_id_bloco(k)
                if k_norm not in blocos_removidos and k_norm in todos_blocos:
                    visiveis[k_norm] = v
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
    bloco_id = normalizar_id_bloco(bloco_id)

    col_esq = [normalizar_id_bloco(b) for b in st.session_state.get("blocos_col_esq", ["contas", "cartoes"])]
    col_dir = [normalizar_id_bloco(b) for b in st.session_state.get("blocos_col_dir", ["contas_pagar", "missao_semana", "turnos"])]
    
    col_esq = list(dict.fromkeys(col_esq))
    col_dir = [b for b in list(dict.fromkeys(col_dir)) if b not in col_esq]

    visiveis = dict(st.session_state.get("blocos_visiveis", {}))
    
    if bloco_id in col_esq:
        origem = col_esq
        destino = col_dir
    elif bloco_id in col_dir:
        origem = col_dir
        destino = col_esq
    else:
        col_dir.append(bloco_id)
        st.session_state["blocos_col_esq"] = col_esq
        st.session_state["blocos_col_dir"] = col_dir
        salvar_layout_dashboard(col_esq, col_dir, visiveis)
        st.rerun()
        return

    if direcao == "trocar_coluna":
        while bloco_id in origem:
            origem.remove(bloco_id)
        if bloco_id not in destino:
            destino.append(bloco_id)
    elif direcao == "subir":
        vis_origem = [b for b in origem if visiveis.get(b, True)]
        if bloco_id in vis_origem:
            v_idx = vis_origem.index(bloco_id)
            if v_idx > 0:
                vizinho = vis_origem[v_idx - 1]
                i1, i2 = origem.index(bloco_id), origem.index(vizinho)
                origem[i1], origem[i2] = origem[i2], origem[i1]
        else:
            idx = origem.index(bloco_id)
            if idx > 0:
                origem[idx], origem[idx - 1] = origem[idx - 1], origem[idx]
    elif direcao == "descer":
        vis_origem = [b for b in origem if visiveis.get(b, True)]
        if bloco_id in vis_origem:
            v_idx = vis_origem.index(bloco_id)
            if v_idx < len(vis_origem) - 1:
                vizinho = vis_origem[v_idx + 1]
                i1, i2 = origem.index(bloco_id), origem.index(vizinho)
                origem[i1], origem[i2] = origem[i2], origem[i1]
        else:
            idx = origem.index(bloco_id)
            if idx < len(origem) - 1:
                origem[idx], origem[idx + 1] = origem[idx + 1], origem[idx]
        
    st.session_state["blocos_col_esq"] = col_esq
    st.session_state["blocos_col_dir"] = col_dir
    salvar_layout_dashboard(col_esq, col_dir, visiveis)
    st.rerun()


def restaurar_layout_padrao():
    """Restaura a distribuição padrão funcional dos blocos."""
    padrao_esq = ["contas", "cartoes"]
    padrao_dir = ["contas_pagar", "missao_semana", "turnos"]
    padrao_vis = {
        "contas": True,
        "cartoes": True,
        "contas_pagar": True,
        "missao_semana": True,
        "turnos": True,
        "paga_leve": False,
        "limites": False,
        "maiores_gastos": False
    }
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

def carregar_margem_liquida_planejada(padrao: float = 65.0) -> float:
    """Carrega a margem líquida estimada do motorista (em %) salva no banco."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS config_dashboard (chave TEXT PRIMARY KEY, valor TEXT)")
    cur.execute("SELECT valor FROM config_dashboard WHERE chave = 'margem_liquida_estimada'")
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        return padrao
    try:
        val = float(row[0])
        return max(40.0, min(95.0, val))
    except Exception:
        return padrao

def salvar_margem_liquida_planejada(margem_pct: float) -> None:
    """Salva a margem líquida estimada do motorista no SQLite."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS config_dashboard (chave TEXT PRIMARY KEY, valor TEXT)")
    cur.execute("INSERT OR REPLACE INTO config_dashboard (chave, valor) VALUES ('margem_liquida_estimada', ?)", (str(margem_pct),))
    conn.commit()
    conn.close()


def obter_marco_producao_99() -> Optional[Dict[str, Any]]:
    """
    Retorna o marco de produção acumulada ATIVO cadastrado para a 99.
    IMPORTANTE: É apenas histórico operacional de produção, sem qualquer efeito financeiro em saldos de contas.
    """
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS motorista_marco_producao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plataforma TEXT NOT NULL DEFAULT '99',
        data_corte DATE NOT NULL,
        faturamento_bruto REAL NOT NULL,
        recebido_dinheiro_pix REAL NOT NULL,
        recebido_online REAL NOT NULL,
        observacao TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        revisao INTEGER DEFAULT 1,
        status TEXT DEFAULT 'ativo'
    );
    """)
    try:
        cur.execute("""
            SELECT id, plataforma, data_corte, faturamento_bruto, recebido_dinheiro_pix, recebido_online, observacao, revisao, status, created_at
            FROM motorista_marco_producao
            WHERE plataforma = '99' AND status = 'ativo'
            ORDER BY id DESC LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            cur.execute("""
                SELECT id, plataforma, data_corte, faturamento_bruto, recebido_dinheiro_pix, recebido_online, observacao, revisao, status, created_at
                FROM motorista_marco_producao
                WHERE plataforma = '99'
                ORDER BY id DESC LIMIT 1
            """)
            row = cur.fetchone()
    except Exception:
        row = None
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "plataforma": row[1],
        "data_corte": str(row[2]),
        "faturamento_bruto": float(row[3]),
        "recebido_dinheiro_pix": float(row[4]),
        "recebido_online": float(row[5]),
        "observacao": row[6] or "",
        "revisao": int(row[7]) if row[7] is not None else 1,
        "status": row[8] or "ativo",
        "created_at": str(row[9]) if row[9] is not None else ""
    }


def obter_historico_marcos_99() -> List[Dict[str, Any]]:
    """Retorna todas as revisões históricas do marco da 99 para auditoria."""
    conn = conectar()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, revisao, data_corte, faturamento_bruto, recebido_dinheiro_pix, recebido_online, observacao, status, created_at
            FROM motorista_marco_producao
            WHERE plataforma = '99'
            ORDER BY id DESC
        """)
        rows = cur.fetchall()
    except Exception:
        rows = []
    conn.close()
    res = []
    for r in rows:
        res.append({
            "id": r[0],
            "revisao": r[1] or 1,
            "data_corte": str(r[2]),
            "faturamento_bruto": float(r[3]),
            "recebido_dinheiro_pix": float(r[4]),
            "recebido_online": float(r[5]),
            "observacao": r[6] or "",
            "status": r[7] or "substituido",
            "created_at": str(r[8])
        })
    return res


def salvar_marco_producao_99(
    data_corte: str,
    faturamento_bruto: float,
    recebido_dinheiro_pix: float,
    recebido_online: float,
    observacao: str = ""
) -> None:
    """
    Salva uma nova revisão do marco de produção acumulada da 99 no SQLite.
    Regras estritas:
    - O novo marco substitui o anterior como referência ativa, arquivando o anterior como 'substituido' (histórico auditável).
    - Não gera transações financeiras nem altera saldos bancários ou carteira.
    - Preserva rigorosamente os valores informados e a divergência de centavos.
    """
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS motorista_marco_producao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plataforma TEXT NOT NULL DEFAULT '99',
        data_corte DATE NOT NULL,
        faturamento_bruto REAL NOT NULL,
        recebido_dinheiro_pix REAL NOT NULL,
        recebido_online REAL NOT NULL,
        observacao TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        revisao INTEGER DEFAULT 1,
        status TEXT DEFAULT 'ativo'
    );
    """)

    cur.execute("SELECT id, revisao FROM motorista_marco_producao WHERE plataforma = '99' ORDER BY id DESC LIMIT 1")
    row_prev = cur.fetchone()
    nova_revisao = 1
    if row_prev:
        rev_anterior = row_prev[1] if row_prev[1] is not None else 1
        nova_revisao = rev_anterior + 1
        cur.execute("UPDATE motorista_marco_producao SET status = 'substituido', updated_at = CURRENT_TIMESTAMP WHERE plataforma = '99' AND status = 'ativo'")

    cur.execute("""
        INSERT INTO motorista_marco_producao (
            plataforma, data_corte, faturamento_bruto, recebido_dinheiro_pix, recebido_online, observacao, revisao, status
        ) VALUES ('99', ?, ?, ?, ?, ?, ?, 'ativo')
    """, (data_corte, faturamento_bruto, recebido_dinheiro_pix, recebido_online, observacao, nova_revisao))

    conn.commit()
    conn.close()


def excluir_marco_producao_99() -> None:
    """Remove todos os marcos da 99 (redefinição total)."""
    conn = conectar()
    conn.execute("DELETE FROM motorista_marco_producao WHERE plataforma = '99'")
    conn.commit()
    conn.close()


@st.dialog("🚩 Marco de Produção Acumulada 99")
def modal_dialog_marco_producao_99():
    """
    Modal interativo para cadastrar, atualizar e auditar o marco de produção da 99.
    Permite atualizar o total acumulado (ex: de R$ 1.340,40 para R$ 1.600,00) sem reconstruir turnos esquecidos.
    """
    marco_atual = obter_marco_producao_99()
    historico = obter_historico_marcos_99()

    data_corte_padrao = datetime.strptime(marco_atual["data_corte"], "%Y-%m-%d").date() if marco_atual else date(2026, 10, 20)
    fat_padrao = marco_atual["faturamento_bruto"] if marco_atual else 1340.40
    din_padrao = marco_atual["recebido_dinheiro_pix"] if marco_atual else 369.25
    onl_padrao = marco_atual["recebido_online"] if marco_atual else 971.14
    obs_padrao = marco_atual["observacao"] if marco_atual else "Marco de produção real até 20/10/2026"
    revisao_atual = marco_atual["revisao"] if marco_atual else 1

    st.markdown("##### 🚕 Referência Operacional de Faturamento Acumulado (99)")
    st.caption("Cadastre ou atualize seu faturamento acumulado sem precisar lançar individualmente os turnos esquecidos.")

    if marco_atual:
        st.markdown(f"""
        <div style="background-color: var(--bg-subcard); border-left: 4px solid #3b82f6; padding: 6px 12px; margin-bottom: 10px; font-size: 0.83rem;">
            <strong>Marco Ativo (Rev {revisao_atual}):</strong> {formatar_moeda_br(fat_padrao)} até {data_corte_padrao.strftime('%d/%m/%Y')}
            <br><span style="color:var(--text-muted);">Um novo valor informado substituirá esta referência e iniciará a Revisão {revisao_atual + 1}, mantendo o histórico auditável.</span>
        </div>
        """, unsafe_allow_html=True)

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        nova_data_corte = st.date_input("Nova Data de Corte:", value=data_corte_padrao, format="DD/MM/YYYY")
    with col_d2:
        novo_fat_bruto = st.number_input("Novo Faturamento Bruto Acumulado (R$):", min_value=0.0, value=float(fat_padrao), step=10.0, format="%.2f")

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        novo_rec_din = st.number_input("Dinheiro / Pix Recebido (R$):", min_value=0.0, value=float(din_padrao), step=10.0, format="%.2f", help="Modalidade de recebimento operacional das viagens, NÃO é saldo disponível na carteira física.")
    with col_m2:
        novo_rec_onl = st.number_input("Online Recebido (R$):", min_value=0.0, value=float(onl_padrao), step=10.0, format="%.2f", help="Recebimentos digitais no aplicativo 99.")

    # Verificação da divergência de centavos sem arredondamento forçado
    soma_partes = round(novo_rec_din + novo_rec_onl, 2)
    divergencia = round(novo_fat_bruto - soma_partes, 2)

    if abs(divergencia) > 0.0001:
        st.warning(
            f"⚠️ **Divergência detectada nas modalidades da 99:**\n\n"
            f"- Faturamento Bruto informado: **{formatar_moeda_br(novo_fat_bruto)}**\n"
            f"- Soma das modalidades: **{formatar_moeda_br(soma_partes)}** ({formatar_moeda_br(novo_rec_din)} Dinheiro/Pix + {formatar_moeda_br(novo_rec_onl)} Online)\n"
            f"- Diferença de centavos: **{divergencia:+.2f}**. Valores preservados exatamente como informados, sem correção artificial."
        )

    # Detecção e prevenção contra retrocesso acidental de data ou valor
    if marco_atual:
        data_corte_str_nova = nova_data_corte.strftime("%Y-%m-%d")
        if novo_fat_bruto < fat_padrao or data_corte_str_nova < marco_atual["data_corte"]:
            st.error(
                f"🚨 **Alerta de Retrocesso / Ajuste Redutor:**\n\n"
                f"O valor informado (**{formatar_moeda_br(novo_fat_bruto)}**) ou a nova data (**{nova_data_corte.strftime('%d/%m/%Y')}**) "
                f"é menor/anterior à referência ativa anterior (**{formatar_moeda_br(fat_padrao)}** em **{data_corte_padrao.strftime('%d/%m/%Y')}**)."
            )
            confirmar_retrocesso = st.checkbox("Confirmo que desejo registrar este recuo/ajuste redutor no histórico auditável.", key="chk_confirma_retrocesso_marco")
        else:
            confirmar_retrocesso = True
    else:
        confirmar_retrocesso = True

    nova_obs = st.text_input("Observação da Revisão:", value=obs_padrao)

    st.info(
        "💡 **Rigor Contábil & Regras de Não Duplicação:**\n"
        "1. **Isolamento Total:** Este marco não cria lançamentos nem altera saldo no Mercado Pago ou Carteira.\n"
        "2. **Não Duplicação:** Turnos com data até a data de corte (como o de 19/10 de R$ 17,60) **não são somados novamente**.\n"
        "3. **Turnos Posteriores:** Turnos com data posterior à data de corte somarão normalmente ao acumulado.\n"
        "4. **Turnos Antigos:** Turnos passados cadastrados depois enriquecem o histórico de km/combustível sem duplicar o faturamento."
    )

    if historico:
        with st.expander(f"📋 Histórico Auditável de Revisões ({len(historico)} registradas)", expanded=False):
            df_hist = pd.DataFrame(historico)
            df_hist_show = df_hist[["revisao", "data_corte", "faturamento_bruto", "status", "observacao", "created_at"]].copy()
            df_hist_show["faturamento_bruto"] = df_hist_show["faturamento_bruto"].apply(formatar_moeda_br)
            df_hist_show.columns = ["Rev.", "Corte", "Bruto Acumulado", "Status", "Observação", "Data Registro"]
            st.dataframe(df_hist_show, width="stretch")

    c_salvar, c_cancel, c_del = st.columns([1.6, 1.1, 1.3])
    with c_salvar:
        pode_salvar = confirmar_retrocesso
        btn_label = f"💾 Gravar Revisão {revisao_atual + 1}" if marco_atual else "💾 Gravar Marco Inicial"
        if st.button(btn_label, type="primary", use_container_width=True, disabled=not pode_salvar):
            salvar_marco_producao_99(
                data_corte=nova_data_corte.strftime("%Y-%m-%d"),
                faturamento_bruto=novo_fat_bruto,
                recebido_dinheiro_pix=novo_rec_din,
                recebido_online=novo_rec_onl,
                observacao=nova_obs
            )
            st.success("Marco de produção atualizado com sucesso! (Revisão gravada)")
            st.rerun()
    with c_cancel:
        if st.button("Fechar", use_container_width=True):
            st.rerun()
    with c_del:
        if marco_atual:
            if st.button("🗑️ Resetar Marco", use_container_width=True, help="Remove todos os marcos e volta a considerar apenas turnos manuais"):
                excluir_marco_producao_99()
                st.warning("Marco de produção removido.")
                st.rerun()


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
    """Retorna lista única de contas registradas (contas principais para despesas e receitas correntes)."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT conta FROM transacoes WHERE conta IS NOT NULL AND conta != '' AND conta NOT LIKE 'Cofrinho%'")
    contas_db = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT nome FROM contas_config WHERE tipo != 'cofrinho' OR tipo IS NULL")
    contas_cfg = [r[0] for r in cur.fetchall()]
    conn.close()
    contas_unificadas = list(dict.fromkeys(contas_cfg + contas_db))
    return contas_unificadas if contas_unificadas else ["Mercado Pago", "Dinheiro / Carteira"]

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
        conn_m = conectar()
        cur_m = conn_m.cursor()
        cur_m.execute("SELECT MAX(data) FROM ajustes_saldo WHERE status = 'ativo'")
        row_m = cur_m.fetchone()
        marco_data = row_m[0] if (row_m and row_m[0]) else "2026-10-21"
        conn_m.close()

        marco_data_br = datetime.strptime(marco_data, "%Y-%m-%d").strftime("%d/%m/%Y")
        
        considerado_no_marco = 0
        if data_pag_str == marco_data:
            st.info(f"⚠️ **Pagamento na Data do Marco de Conciliação ({marco_data_br}):**")
            momento_sel = st.radio(
                "Em que momento este pagamento ocorreu?",
                [
                    "Depois do corte de saldo (debitar do saldo atual em caixa)",
                    "Antes do corte de saldo (já estava pago/embutido no saldo inicial reconciliado)"
                ],
                index=0
            )
            if "Antes" in momento_sel:
                considerado_no_marco = 1
        elif data_pag_str < marco_data:
            st.info(f"💡 **Pagamento Retroativo:** Como este pagamento ocorreu antes do marco ativo ({marco_data_br}), a obrigação será quitada dando baixa nas pendências do mês de outubro, sem debitar novamente o saldo bancário conciliado.")
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


@st.dialog("⚡ Baixar Conta a Pagar", width="small")
def modal_baixa_rapida_conta(id_transacao: int):
    """Modal leve e rápido (st.dialog) para confirmação de baixa / pagamento de obrigação."""
    conn = conectar()
    resumo = saldo_service.obter_resumo_obrigacao(conn, id_transacao)
    contas_raw = saldo_service.obter_contas(conn)
    saldos_contas = {c["id"]: saldo_service.calcular_saldo_conta(conn, c["id"])["saldo_atual"] for c in contas_raw}
    
    cur_m = conn.cursor()
    cur_m.execute("SELECT MAX(data) FROM ajustes_saldo WHERE status = 'ativo'")
    row_m = cur_m.fetchone()
    marco_data = row_m[0] if (row_m and row_m[0]) else "2026-10-21"
    conn.close()

    if not resumo:
        st.error("Obrigação não encontrada.")
        return

    st.markdown(f"#### 💳 {resumo['descricao']}")
    val_devedor = float(resumo["saldo_devedor"])
    data_venc_br = datetime.strptime(resumo['data_vencimento'], "%Y-%m-%d").strftime("%d/%m/%Y")
    st.caption(f"🗓️ Vencimento Original: **{data_venc_br}** • Saldo devedor: **{formatar_moeda_br(val_devedor)}**")

    # Contas de saída: Mercado Pago ou Carteira como padrão
    mapa_contas = {}
    lista_nomes = []
    idx_padrao = 0
    for i, c in enumerate(contas_raw):
        s_val = saldos_contas.get(c["id"], Decimal("0.00"))
        rotulo = f"{c['nome']} (Disp: R$ {s_val:,.2f})"
        mapa_contas[rotulo] = c
        lista_nomes.append(rotulo)
        if c["id"] == resumo.get("conta_id"):
            idx_padrao = i
        elif idx_padrao == 0 and "Mercado Pago" in c["nome"]:
            idx_padrao = i

    with st.form(f"form_baixa_rapida_{id_transacao}"):
        conta_sel_rotulo = st.selectbox("Conta de saída:", lista_nomes, index=idx_padrao)
        conta_obj = mapa_contas[conta_sel_rotulo]

        c_dt, c_vl = st.columns(2)
        with c_dt:
            data_pag = st.date_input("Data do pagamento:", date.today())
        with c_vl:
            val_pago = st.number_input("Valor pago (R$):", min_value=0.01, value=val_devedor, step=5.0, format="%.2f")

        data_pag_str = data_pag.strftime("%Y-%m-%d")
        marco_data_br = datetime.strptime(marco_data, "%Y-%m-%d").strftime("%d/%m/%Y")
        considerado_no_marco = 0
        if data_pag_str < marco_data:
            st.info(f"💡 **Pagamento Retroativo:** Anterior ao corte ({marco_data_br}). A conta será quitada dando baixa imediata sem debitar novamente o saldo conciliado atual.")
            considerado_no_marco = 1
        elif data_pag_str == marco_data:
            momento_sel = st.radio(
                "Momento do pagamento em relação ao corte de caixa:",
                [
                    "Depois do fechamento (debitar do caixa atual)",
                    "Antes do fechamento (já estava pago no saldo inicial reconciliado)"
                ],
                index=0
            )
            if "Antes" in momento_sel:
                considerado_no_marco = 1
        else:
            st.caption(f"🏦 Debita da conta {conta_obj['nome']} na data do pagamento.")

        st.write("")
        if st.form_submit_button("✅ Confirmar Baixa Imediata", type="primary", use_container_width=True):
            if val_pago <= 0:
                st.error("O valor pago deve ser maior que zero.")
                return

            tipo_ajuste = "normal"
            valor_encargos = 0.0
            valor_desconto = 0.0
            if val_pago > val_devedor + 0.001:
                tipo_ajuste = "com_juros"
                valor_encargos = val_pago - val_devedor
            elif val_pago < val_devedor - 0.001:
                tipo_ajuste = "normal"

            conn = conectar()
            try:
                saldo_service.registrar_pagamento(
                    conn=conn,
                    transacao_id=id_transacao,
                    data_pagamento=data_pag_str,
                    valor_pago=float(val_pago),
                    conta_id=conta_obj["id"],
                    afeta_saldo_bancario=1,
                    considerado_no_marco=considerado_no_marco,
                    forma_pagamento="Pix",
                    tipo_ajuste_valor=tipo_ajuste,
                    valor_encargos=valor_encargos,
                    valor_desconto=valor_desconto
                )
                conn.close()
                st.success(f"Conta baixada com sucesso!")
                st.rerun()
            except Exception as e:
                conn.close()
                st.error(f"Erro ao registrar baixa: {e}")


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
            valor = input_moeda_centavos("Valor (R$)", valor_inicial=50.0, key="modal_desp_unica_val", mostrar_preview=False)

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
        valor_total = input_moeda_centavos("Valor Total da Compra (R$)", valor_inicial=300.0, key="parc_val_tot", mostrar_preview=False)

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
        valor_rec = input_moeda_centavos("Valor por Ciclo (R$)", valor_inicial=120.0, key="fixa_val", mostrar_preview=False)

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
        valor = input_moeda_centavos("Valor Recebido (R$)", valor_inicial=500.0, key="modal_rec_val", mostrar_preview=False)
        
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

def obter_turno_aberto(conn=None) -> Optional[Dict[str, Any]]:
    """Retorna o turno com status 'aberto' atualmente ativo no banco, se houver."""
    close_conn = False
    if conn is None:
        conn = conectar()
        close_conn = True
    cur = conn.cursor()
    cur.execute("SELECT * FROM turnos WHERE status_turno = 'aberto' ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    res = dict(row) if row else None
    if close_conn:
        conn.close()
    return res


def iniciar_turno(
    data_str: str,
    hora_ini: str,
    km_ini: float,
    plataforma: str = "99",
    periodo: Optional[str] = None,
    obs: str = ""
) -> int:
    """Grava a abertura de um turno no SQLite com persistência real."""
    if not periodo:
        try:
            h = int(hora_ini.split(":")[0])
            if 6 <= h < 12:
                periodo = "Manhã (06h às 12h)"
            elif 12 <= h < 18:
                periodo = "Tarde (12h às 18h)"
            elif 18 <= h < 24:
                periodo = "Noite (18h às 00h)"
            else:
                periodo = "Madrugada (00h às 06h)"
        except Exception:
            periodo = "Integral / Misto"

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO turnos (data, hora_inicio, km_inicial, ganho_bruto, horas, km, 
                           plataforma, periodo, observacao, status_turno, combustivel, combustivel_consumido_estimado)
        VALUES (?, ?, ?, 0.0, 0.0, 0.0, ?, ?, ?, 'aberto', 0.0, 0.0)
    """, (data_str, hora_ini, float(km_ini), plataforma, periodo, obs.strip()))
    turno_id = cur.lastrowid
    conn.commit()
    conn.close()
    return turno_id


def encerrar_turno(
    turno_id: int,
    hora_fim: str,
    km_final: float,
    ganho_dinheiro_pix: float,
    ganho_online: float,
    comb_estimado: float = 0.0,
    obs: Optional[str] = None,
    financeiro_op: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """
    Encerra o turno aberto calculando duração em horas e quilômetros rodados.
    NÃO cria receitas bancárias automaticamente sem autorização explícita do usuário.
    """
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM turnos WHERE id = ?", (turno_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "Turno não encontrado."

    t_dict = dict(row)
    km_ini = float(t_dict.get("km_inicial") or 0.0)
    if float(km_final) < km_ini:
        conn.close()
        return False, f"KM final ({km_final:,.0f}) não pode ser menor que o KM inicial ({km_ini:,.0f})."

    km_rodado = max(0.0, round(float(km_final) - km_ini, 1))

    # Cálculo de duração
    hora_ini = t_dict.get("hora_inicio") or "00:00"
    try:
        t_ini = datetime.strptime(hora_ini, "%H:%M")
        t_fim = datetime.strptime(hora_fim, "%H:%M")
        if t_fim >= t_ini:
            duracao_seg = (t_fim - t_ini).total_seconds()
        else:
            duracao_seg = (t_fim - t_ini).total_seconds() + 86400
        duracao_horas = max(0.1, round(duracao_seg / 3600.0, 2))
    except Exception:
        duracao_horas = float(t_dict.get("horas") or 1.0)

    ganho_bruto_total = round(float(ganho_dinheiro_pix) + float(ganho_online), 2)
    obs_final = obs.strip() if obs is not None else str(t_dict.get("observacao") or "")

    cur.execute("""
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
            combustivel_consumido = ?,
            combustivel_consumido_estimado = ?,
            observacao = ?
        WHERE id = ?
    """, (hora_fim, float(km_final), km_rodado, duracao_horas,
          float(ganho_dinheiro_pix), float(ganho_online), ganho_bruto_total,
          float(ganho_dinheiro_pix), float(comb_estimado), float(comb_estimado), float(comb_estimado),
          obs_final, turno_id))
    conn.commit()

    # Contabilização financeira opcional solicitada pelo usuário
    msg_fin = ""
    if financeiro_op and (financeiro_op.get("modo") not in (None, "nenhum") or financeiro_op.get("online_creditado")):
        ok_fin, msg_fin_resp = saldo_service.registrar_recebimento_turno(conn, turno_id, financeiro_op)
        if ok_fin and msg_fin_resp:
            msg_fin = f" • {msg_fin_resp}"

    conn.close()
    return True, f"Turno encerrado com sucesso! ({km_rodado:,.1f} km em {duracao_horas:.1f}h • Total Bruto: R$ {ganho_bruto_total:,.2f}){msg_fin}"


@st.dialog("▶️ Iniciar Turno 99", width="medium")
def modal_iniciar_turno():
    """Janela pop-up para iniciar um turno de trabalho na 99 / Uber com persistência."""
    st.markdown("##### 🚕 Abertura de Turno Operacional")
    st.caption("Grave o início da jornada. O turno ficará ativo e persistido mesmo se você fechar o navegador.")

    # Busca último KM final cadastrado para sugerir como KM inicial
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT km_final FROM turnos WHERE km_final IS NOT NULL AND km_final > 0 ORDER BY id DESC LIMIT 1")
    row_km = cur.fetchone()
    km_sugerido = float(row_km[0]) if row_km else 85000.0
    conn.close()

    agora = datetime.now()
    hora_str = agora.strftime("%H:%M")

    with st.form("form_iniciar_turno"):
        c1, c2 = st.columns(2)
        data_t = c1.date_input("Data de Início", date.today())
        hora_t = c2.text_input("Horário Inicial (HH:MM)", value=hora_str, help="Horário em que começou a rodar")

        c3, c4 = st.columns(2)
        km_ini = c3.number_input("KM Inicial (Hodômetro)", min_value=0.0, value=km_sugerido, step=1.0, help="Quilometragem do painel no início do turno")
        plat = c4.selectbox("Plataforma", ["99", "Uber", "99 + Uber", "Outra"], index=0)

        # Sugestão de período pelo horário
        h_atual = agora.hour
        per_idx = 0 if 6 <= h_atual < 12 else (1 if 12 <= h_atual < 18 else (2 if 18 <= h_atual < 24 else 3))
        periodos_op = ["Manhã (06h às 12h)", "Tarde (12h às 18h)", "Noite (18h às 00h)", "Madrugada (00h às 06h)", "Integral / Misto"]
        periodo_sel = st.selectbox("Período do Turno", periodos_op, index=per_idx)
        obs_ini = st.text_input("Observação Inicial (opcional)", placeholder="Ex: Manhã ensolarada, trânsito normal...")

        st.divider()
        if st.form_submit_button("🟢 Confirmar Início de Turno", use_container_width=True, type="primary"):
            data_iso = data_t.strftime("%Y-%m-%d")
            t_id = iniciar_turno(data_iso, hora_t.strip(), km_ini, plat, periodo_sel, obs_ini)
            st.success(f"Turno #{t_id} iniciado com sucesso! Boas corridas.")
            st.rerun()


@st.dialog("🏁 Encerrar Turno 99", width="medium")
def modal_encerrar_turno(id_turno: int):
    """Janela pop-up para encerramento do turno ativo com apuração operacional e destino de ganhos opcional."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM turnos WHERE id = ?", (id_turno,))
    row = cur.fetchone()
    if not row:
        conn.close()
        st.error("Turno não encontrado.")
        return

    t_dict = dict(row)
    km_ini = float(t_dict.get("km_inicial") or 0.0)
    hora_ini = t_dict.get("hora_inicio") or "00:00"
    data_t = t_dict.get("data") or str(date.today())

    st.markdown(f"##### 🏁 Encerramento de Turno #{id_turno}")
    st.info(f"📍 **Início:** {data_t} às **{hora_ini}** • KM Inicial: **{km_ini:,.0f} KM** ({t_dict.get('periodo', 'Turno')})")

    agora = datetime.now()
    hora_fim_padrao = agora.strftime("%H:%M")

    c1, c2 = st.columns(2)
    hora_fim = c1.text_input("Horário Final (HH:MM)", value=hora_fim_padrao, help="Horário em que encerrou o turno")
    km_fim = c2.number_input("KM Final (Hodômetro)", min_value=km_ini, value=max(km_ini, km_ini + 15.0), step=1.0, help="Quilometragem do painel no encerramento")

    km_est = max(0.0, km_fim - km_ini)
    st.caption(f"🛣️ *KM Estimado Rodado: {km_est:.1f} km*")

    st.divider()
    st.markdown("###### 💵 Faturamento Bruto do Turno (Separado)")
    cg1, cg2 = st.columns(2)
    din_pix = cg1.number_input("Dinheiro / Pix em Mãos (R$)", min_value=0.0, value=0.0, step=5.0, help="Valores recebidos diretamente de passageiros")
    onl = cg2.number_input("Ganhos Online no App (R$)", min_value=0.0, value=0.0, step=5.0, help="Saldo acumulado na carteira da 99")

    bruto_tot = din_pix + onl
    st.markdown(f"**Total Bruto Apurado:** :green[**R$ {bruto_tot:,.2f}**]")

    st.divider()
    st.markdown("###### ⛽ Consumo Operacional Estimado (Quilometragem)")
    comb_sug = round(km_est * 0.38, 2)
    comb_est = st.number_input("Consumo Estimado de Combustível (R$)", min_value=0.0, value=float(comb_sug), step=5.0, 
                               help="Custo estimado do combustível consumido neste turno. NÃO debita do banco nem desconta o abastecimento cheio.")
    st.caption("🛡️ *Separação Contábil: Os abastecimentos reais continuam sendo despesas no caixa quando pagos. Aqui calculamos apenas a estimativa proporcional de rodagem.*")

    obs_enc = st.text_input("Observações Finais", value=str(t_dict.get("observacao") or ""))

    st.divider()
    st.markdown("###### 🏦 Destino dos Ganhos (Opcional - Nunca Automático)")
    st.caption("Escolha se deseja registrar a entrada bancária agora ou manter apenas o registro operacional do turno.")

    contas = saldo_service.obter_contas(conn, incluir_cofrinhos=False)
    nomes_contas = [c["nome"] for c in contas]
    mapa_contas = {c["nome"]: c["id"] for c in contas}
    rec_avulsas = saldo_service.obter_transacoes_receita_para_vinculo(conn)

    opcoes_modo = [
        "⏸️ Não contabilizar agora (Deixar pendente)",
        "💵 Depositar Dinheiro/Pix em conta única",
        "🔀 Dividir recebimento entre contas",
        "🔗 Vincular a uma entrada / Pix já cadastrada no extrato"
    ]
    modo_sel = st.selectbox("Destino do Dinheiro/Pix", opcoes_modo, index=0)

    config_fin: Dict[str, Any] = {"modo": "nenhum"}

    if modo_sel == "⏸️ Não contabilizar agora (Deixar pendente)":
        st.caption("🔒 *Nenhuma movimentação bancária será criada agora. O faturamento bruto é preservado no turno.*")
        config_fin = {"modo": "nenhum"}

    elif modo_sel == "💵 Depositar Dinheiro/Pix em conta única":
        c_u1, c_u2 = st.columns(2)
        idx_cart = 0
        for i, n in enumerate(nomes_contas):
            if "Carteira" in n or "Dinheiro" in n:
                idx_cart = i
                break
        c_sel = c_u1.selectbox("Conta Destino", nomes_contas, index=idx_cart)
        val_u = c_u2.number_input("Valor a Creditar (R$)", min_value=0.01, value=din_pix if din_pix > 0 else 10.0, step=5.0)
        config_fin = {"modo": "conta_unica", "conta_id": mapa_contas[c_sel], "valor": val_u}

    elif modo_sel == "🔀 Dividir recebimento entre contas":
        st.caption("Distribua o recebimento entre duas contas (ex: parte na Carteira, parte no Mercado Pago):")
        cd1, cd2 = st.columns(2)
        c1_sel = cd1.selectbox("Conta 1", nomes_contas, index=0)
        v1 = cd2.number_input("Valor Conta 1 (R$)", min_value=0.0, value=round(din_pix / 2, 2), step=5.0)

        cd3, cd4 = st.columns(2)
        idx_c2 = 1 if len(nomes_contas) > 1 else 0
        c2_sel = cd3.selectbox("Conta 2", nomes_contas, index=idx_c2)
        v2 = cd4.number_input("Valor Conta 2 (R$)", min_value=0.0, value=round(din_pix - v1, 2), step=5.0)

        st.caption(f"Soma informada: **R$ {v1 + v2:,.2f}** (Dinheiro/Pix do turno: R$ {din_pix:,.2f})")
        config_fin = {
            "modo": "divisao",
            "divisoes": [
                {"conta_id": mapa_contas[c1_sel], "valor": v1},
                {"conta_id": mapa_contas[c2_sel], "valor": v2}
            ]
        }

    elif modo_sel == "🔗 Vincular a uma entrada / Pix já cadastrada no extrato":
        if not rec_avulsas:
            st.info("Nenhuma receita recente não vinculada encontrada no extrato.")
            config_fin = {"modo": "nenhum"}
        else:
            opcoes_rec = {f"#{r['id']} • {r['data']} • R$ {r['valor']:,.2f} ({r['descricao']} - {r['conta']})": r["id"] for r in rec_avulsas}
            rec_escolhida = st.selectbox("Selecione a entrada correspondente", list(opcoes_rec.keys()))
            config_fin = {"modo": "vincular", "transacao_id": opcoes_rec[rec_escolhida]}

    if onl > 0:
        st.write("")
        creditar_onl = st.checkbox("Ganhos Online (99Pay) já caíram na conta bancária hoje?", value=False)
        if creditar_onl:
            c_onl1, c_onl2 = st.columns(2)
            idx_mp = 0
            for i, n in enumerate(nomes_contas):
                if "Mercado Pago" in n:
                    idx_mp = i
                    break
            c_onl_sel = c_onl1.selectbox("Conta de Crédito Online", nomes_contas, index=idx_mp)
            v_onl = c_onl2.number_input("Valor Online Creditado (R$)", min_value=0.01, value=onl, step=5.0)
            config_fin["online_creditado"] = True
            config_fin["online_conta_id"] = mapa_contas[c_onl_sel]
            config_fin["online_valor"] = v_onl

    conn.close()

    st.divider()
    if st.button("🏁 Confirmar Encerramento do Turno", use_container_width=True, type="primary"):
        ok, msg = encerrar_turno(id_turno, hora_fim.strip(), km_fim, din_pix, onl, comb_est, obs_enc, config_fin)
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)


@st.dialog("💵 Contabilizar Recebimento do Turno", width="large")
def modal_contabilizar_turno(id_turno: int):
    """
    Interface simplificada e segura para contabilização financeira de turnos.
    - Dois cards compactos: Dinheiro/Pix e Online.
    - Diferenciação clara entre Editar, Desvincular e Estornar.
    - Teto estrito: recebimentos não podem ultrapassar o faturamento bruto.
    - Prevenção de duplicidades e suporte a encerramento sem crédito imediato.
    """
    conn = conectar()
    info = saldo_service.obter_recebimentos_turno(conn, id_turno)
    
    if "erro" in info:
        st.error(info["erro"])
        conn.close()
        return

    tid = info["turno_id"]
    dt_str = info["data"]
    din_pix = info["ganho_dinheiro_pix"]
    onl = info["ganho_online"]
    bruto = info["ganho_bruto"]
    tr_vinc = info["transacoes"]
    tot_cont = info["total_contabilizado"]
    restante = info["restante_elegivel"]
    excedente = info["excedente"]
    status = info["status"]

    st.markdown(f"#### 💵 Recebimento Financeiro • Turno #{tid} ({dt_str})")

    # CARDS COMPACTOS: DINHEIRO/PIX E ONLINE
    c_card1, c_card2, c_card3 = st.columns([1.5, 1.5, 1.8])
    with c_card1:
        st.markdown(f"""
        <div style="background-color: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 10px 14px;">
            <div style="color: var(--text-muted); font-size: 0.78rem; text-transform: uppercase; font-weight: 600;">💵 Dinheiro / Pix</div>
            <div style="font-size: 1.25rem; font-weight: 700; color: var(--text-primary);">{formatar_moeda_br(din_pix)}</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">Recebido em mãos na corrida</div>
        </div>
        """, unsafe_allow_html=True)

    with c_card2:
        st.markdown(f"""
        <div style="background-color: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 10px 14px;">
            <div style="color: var(--text-muted); font-size: 0.78rem; text-transform: uppercase; font-weight: 600;">📱 Ganhos Online (99Pay)</div>
            <div style="font-size: 1.25rem; font-weight: 700; color: #2563eb;">{formatar_moeda_br(onl)}</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">Saldo no aplicativo da 99</div>
        </div>
        """, unsafe_allow_html=True)

    with c_card3:
        eh_inc = (status == "incorporado_marco" or info.get("eh_incorporado_marco", False))
        if eh_inc:
            cor_status = "#3b82f6"
            rotulo_status = "🏛️ INCORPORADO AO MARCO"
        elif status == "excedente":
            cor_status = "#ef4444"
            rotulo_status = "🚨 EXCEDENTE"
        elif status == "integral":
            cor_status = "#10b981"
            rotulo_status = "✅ CONCILIADO"
        elif status == "parcial":
            cor_status = "#f59e0b"
            rotulo_status = "⚠️ PARCIAL"
        else:
            cor_status = "#f59e0b"
            rotulo_status = "⏳ PENDENTE"

        st.markdown(f"""
        <div style="background-color: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 10px 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: var(--text-muted); font-size: 0.78rem; text-transform: uppercase; font-weight: 600;">Bruto: {formatar_moeda_br(bruto)}</span>
                <span style="background: {cor_status}; color: #ffffff; font-size: 0.7rem; font-weight: 700; padding: 2px 7px; border-radius: 8px;">{rotulo_status}</span>
            </div>
            <div style="font-size: 1.1rem; font-weight: 700; margin-top: 3px;">No Banco: {formatar_moeda_br(tot_cont)}</div>
            <div style="font-size: 0.78rem; color: var(--text-muted);">Disponível p/ creditar: <b>{formatar_moeda_br(restante)}</b></div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    # AVISO DE TURNO INCORPORADO AO MARCO
    if eh_inc:
        st.info(
            f"🏛️ **Turno Incorporado ao Marco de Saldo:** Este turno ({dt_str}) foi realizado em data anterior "
            f"ao corte oficial da conciliação bancária (21/10/2026). Seus ganhos operacionais de **{formatar_moeda_br(bruto)}** "
            f"já foram recebidos no passado e estão contemplados no saldo inicial conciliado em caixa. "
            f"Por segurança contábil, novas movimentações financeiras para este turno estão bloqueadas para evitar duplicidades."
        )

    # ALERTA DE EXCEDENTE / DUPLICIDADE (CASO #41 + #42)
    if status == "excedente":
        st.error(
            f"🚨 **Inconsistência Financeira Detectada:** O total de recebimentos vinculados ({formatar_moeda_br(tot_cont)}) "
            f"ultrapassa o faturamento bruto do turno ({formatar_moeda_br(bruto)}) em **{formatar_moeda_br(excedente)}**! "
            f"Para corrigir a duplicidade e restaurar os saldos bancários reais, use o botão **'↩️ Estornar / Remover do Extrato'** na movimentação incorreta abaixo."
        )

    # SEÇÃO DE MOVIMENTAÇÕES EXISTENTES
    contas = saldo_service.obter_contas(conn, incluir_cofrinhos=False)
    nomes_contas = [c["nome"] for c in contas]
    mapa_contas = {c["nome"]: c["id"] for c in contas}

    if tr_vinc:
        st.markdown("###### 📋 Movimentações Vinculadas a Este Turno")
        for tv in tr_vinc:
            with st.container(border=True):
                r_c1, r_c2, r_c3, r_c4 = st.columns([3.2, 1.2, 1.4, 1.6], vertical_alignment="center")
                with r_c1:
                    st.markdown(f"**#{tv['id']} • {tv['descricao']}**")
                    st.caption(f"🗓️ Data: {tv['data']} • Conta: **{tv['conta']}** • Valor: **{formatar_moeda_br(tv['valor'])}**")
                
                with r_c2:
                    edit_key = f"toggle_edit_{tv['id']}"
                    btn_edit_txt = "✖️ Fechar" if st.session_state.get(edit_key, False) else "✏️ Editar"
                    if st.button(btn_edit_txt, key=f"btn_togg_{tv['id']}", use_container_width=True, help="Corrigir valor ou conta destino desta movimentação"):
                        st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                        st.rerun()

                with r_c3:
                    if st.button("🔗 Desvincular", key=f"btn_desv_tr_{tv['id']}", use_container_width=True, help="Desassocia do turno mas mantém a quantia no extrato bancário. Não use para duplicidades!"):
                        ok_d, msg_d = saldo_service.desvincular_recebimento_turno(conn, tv["id"])
                        conn.close()
                        if ok_d:
                            st.info(msg_d)
                            st.rerun()
                        else:
                            st.error(msg_d)

                with r_c4:
                    if st.button("↩️ Estornar", key=f"btn_est_tr_{tv['id']}", type="primary", use_container_width=True, help="Exclui a movimentação duplicada do extrato e corrige o saldo bancário"):
                        ok_e, msg_e = saldo_service.estornar_recebimento_turno(conn, tv["id"], turno_id=tid)
                        conn.close()
                        if ok_e:
                            st.success(msg_e)
                            st.rerun()
                        else:
                            st.error(msg_e)

                # Sub-formulário expansível de edição
                if st.session_state.get(f"toggle_edit_{tv['id']}", False):
                    with st.container(border=True):
                        st.markdown(f"**✏️ Editar Recebimento #{tv['id']}**")
                        e_c1, e_c2, e_c3 = st.columns([1.5, 1.5, 1.2])
                        idx_c_orig = nomes_contas.index(tv["conta"]) if tv["conta"] in nomes_contas else 0
                        nova_c_sel = e_c1.selectbox("Conta Destino", nomes_contas, index=idx_c_orig, key=f"sel_c_ed_{tv['id']}")
                        novo_val = input_moeda_centavos("Novo Valor (R$)", valor_inicial=float(tv["valor"]), key=f"num_val_ed_{tv['id']}", mostrar_preview=False)
                        e_c3.write("")
                        if e_c3.button("💾 Salvar Alteração", key=f"btn_salv_ed_{tv['id']}", type="primary", use_container_width=True):
                            ok_edit, msg_edit = saldo_service.editar_recebimento_turno(
                                conn, tv["id"], novo_val, mapa_contas[nova_c_sel]
                            )
                            conn.close()
                            if ok_edit:
                                st.session_state[f"toggle_edit_{tv['id']}"] = False
                                st.success(msg_edit)
                                st.rerun()
                            else:
                                st.error(msg_edit)

    st.write("")

    # SEÇÃO PARA CONTABILIZAR RESTANTE ELEGÍVEL (BLOQUEADA PARA TURNOS INCORPORADOS AO MARCO)
    if restante > 0.009 and not eh_inc:
        st.markdown(f"###### ➕ Contabilizar Recebimento Elegível ({formatar_moeda_br(restante)} disponíveis)")
        
        opcoes_modo = [
            "💵 Conta única (Recomendado)",
            "🔀 Dividir entre contas",
            "🔗 Vincular lançamento existente no extrato",
            "⏸️ Não contabilizar no banco agora"
        ]
        modo_sel = st.radio("Forma de Contabilização:", opcoes_modo, index=0, horizontal=False)

        config_rec: Dict[str, Any] = {}
        
        if modo_sel == "💵 Conta única (Recomendado)":
            col_u1, col_u2 = st.columns([1.8, 1.4])
            
            # Padrão preferido: Mercado Pago se configurado ou primeiro da lista
            idx_pref = 0
            for i, n in enumerate(nomes_contas):
                if "Mercado Pago" in n:
                    idx_pref = i
                    break
            
            # Se dinheiro/pix for 0, previne sugerir Carteira
            if din_pix == 0.0 and "Carteira" in nomes_contas[idx_pref]:
                for i, n in enumerate(nomes_contas):
                    if "Mercado Pago" in n or "Banco" in n:
                        idx_pref = i
                        break

            with col_u1:
                c_sel = st.selectbox("Conta Destino do Crédito", nomes_contas, index=idx_pref, key="vg_rec_conta_unica")
                if din_pix == 0.0 and ("Carteira" in c_sel or "Dinheiro" in c_sel):
                    st.warning("⚠️ O turno teve R$ 0,00 em Dinheiro físico. O crédito em Carteira não é recomendado.")

            with col_u2:
                # Opção de Valor Integral
                usar_integral = st.checkbox(f"⚡ Valor integral ({formatar_moeda_br(restante)})", value=True, key="chk_val_integral")
                if usar_integral:
                    val_u = restante
                    st.caption(f"Valor preenchido automaticamente: **{formatar_moeda_br(val_u)}**")
                else:
                    val_u = input_moeda_centavos("Valor a Creditar (R$)", valor_inicial=float(restante), key="num_val_custom", mostrar_preview=False)

            config_rec = {"modo": "conta_unica", "conta_id": mapa_contas[c_sel], "valor": val_u}

        elif modo_sel == "🔀 Dividir recebimento entre contas":
            st.caption(f"Distribua até **{formatar_moeda_br(restante)}** entre duas contas:")
            cd1, cd2 = st.columns(2)
            c1_sel = cd1.selectbox("Conta 1", nomes_contas, index=0, key="div_c1")
            v1_def = round(restante / 2.0, 2)
            v1 = input_moeda_centavos("Valor Conta 1 (R$)", valor_inicial=float(v1_def), key="div_v1", mostrar_preview=False)

            cd3, cd4 = st.columns(2)
            idx_c2 = 1 if len(nomes_contas) > 1 else 0
            c2_sel = cd3.selectbox("Conta 2", nomes_contas, index=idx_c2, key="div_c2")
            v2_def = max(0.0, round(restante - v1, 2))
            v2 = input_moeda_centavos("Valor Conta 2 (R$)", valor_inicial=float(v2_def), key="div_v2", mostrar_preview=False)

            soma_div = round(v1 + v2, 2)
            st.caption(f"Total distribuído: **{formatar_moeda_br(soma_div)}** de **{formatar_moeda_br(restante)}** elegíveis")
            config_rec = {
                "modo": "divisao",
                "divisoes": [
                    {"conta_id": mapa_contas[c1_sel], "valor": v1},
                    {"conta_id": mapa_contas[c2_sel], "valor": v2}
                ]
            }

        elif modo_sel == "🔗 Vincular lançamento existente no extrato":
            rec_avulsas = saldo_service.obter_transacoes_receita_para_vinculo(conn)
            if not rec_avulsas:
                st.info("Nenhuma receita recente sem vínculo encontrada no extrato.")
                config_rec = {"modo": "nenhum"}
            else:
                opcoes_rec = {f"#{r['id']} • {r['data']} • {formatar_moeda_br(r['valor'])} ({r['descricao']} - {r['conta']})": r["id"] for r in rec_avulsas}
                rec_escolhida = st.selectbox("Selecione o lançamento correspondente:", list(opcoes_rec.keys()), key="sel_tr_vinc_turno")
                config_rec = {"modo": "vincular", "transacao_id": opcoes_rec[rec_escolhida]}

        else:
            st.caption("ℹ️ O turno permanecerá gravado operacionalmente e com status pendente de conciliação bancária.")
            config_rec = {"modo": "nenhum"}

        # LEMBRETE OPCIONAL DE REPASSE (NÃO CRIA MOVIMENTAÇÃO BANCÁRIA)
        st.write("")
        lembrete_onl = st.checkbox("🔔 Lembrete: Repasse 99Pay pendente (Apenas anotação operacional, NÃO movimenta saldo bancário)", value=False, help="Marque se você aguarda a 99 transferir este valor nos próximos dias.")
        if lembrete_onl:
            st.caption("🛡️ *Garantia: O lembrete não altera os saldos das suas contas bancárias até você confirmar a entrada.*")

        st.divider()
        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn1:
            if st.button("💾 Confirmar Recebimento do Turno", use_container_width=True, type="primary", key="btn_confirmar_rec_t"):
                if modo_sel == "⏸️ Não contabilizar no banco agora":
                    conn.close()
                    st.info("Turno encerrado operacionalmente sem movimentação bancária imediata.")
                    st.rerun()
                else:
                    ok_g, msg_g = saldo_service.registrar_recebimento_turno(conn, id_turno, config_rec)
                    conn.close()
                    if ok_g:
                        st.success(msg_g)
                        st.rerun()
                    else:
                        st.error(msg_g)
        with col_btn2:
            if st.button("Fechar", use_container_width=True, key="btn_fechar_modal_rec"):
                conn.close()
                st.rerun()

    else:
        if status != "excedente":
            st.success(f"✅ **Turno 100% Contabilizado:** O faturamento bruto de {formatar_moeda_br(bruto)} já foi totalmente conciliado.")
        conn.close()



@st.dialog("⛽ Registrar / Editar Abastecimento (Drivvo)", width="large")
def modal_registrar_abastecimento(id_abast_editar: Optional[int] = None, vincular_transacao_id: Optional[int] = None):
    """Janela pop-up para registrar ou vincular abastecimento do veículo estilo Drivvo."""
    st.markdown("##### ⛽ Abastecimento do Veículo • Gestão Drivvo")
    st.caption("Acompanhe o consumo do carro mantendo a Central Financeira como fonte bancária única.")

    conn = conectar()
    contas = saldo_service.obter_contas(conn, incluir_cofrinhos=False)
    nomes_contas = [c["nome"] for c in contas]
    mapa_contas = {c["nome"]: c["id"] for c in contas}

    despesas_avulsas = saldo_service.obter_despesas_combustivel_sem_abastecimento(conn)

    # Sugestão de hodômetro baseada no maior valor registrado
    cur = conn.cursor()
    cur.execute("SELECT max(coalesce(hodometro, 0)) FROM veiculo_abastecimentos")
    r_km = cur.fetchone()
    km_max_abast = float(r_km[0]) if r_km and r_km[0] else 0.0

    cur.execute("SELECT max(coalesce(km_final, km_inicial, 0)) FROM turnos")
    r_kmt = cur.fetchone()
    km_max_turno = float(r_kmt[0]) if r_kmt and r_kmt[0] else 0.0

    km_sugerido = max(km_max_abast, km_max_turno, 187290.0)

    # Se estiver editando um registro existente de veiculo_abastecimentos
    dados_edicao = None
    if id_abast_editar:
        cur.execute("SELECT * FROM veiculo_abastecimentos WHERE id = ?", (id_abast_editar,))
        r_ed = cur.fetchone()
        if r_ed:
            dados_edicao = dict(r_ed)

    # Se estiver vinculando a uma transação existente
    dados_tr_vinc = None
    if vincular_transacao_id:
        cur.execute("SELECT id, data, valor, conta, conta_id, descricao FROM transacoes WHERE id = ?", (vincular_transacao_id,))
        r_tr = cur.fetchone()
        if r_tr:
            dados_tr_vinc = dict(r_tr)
    conn.close()

    tr_id_final = None
    dt_padrao = date.today()
    val_bruto_padrao = 100.0
    desconto_padrao = 0.0
    val_pago_padrao = 100.0
    litros_padrao = 0.0
    tanque_cheio_padrao = True
    posto_padrao = ""
    obs_padrao = ""
    conta_padrao_idx = 0
    for i, n in enumerate(nomes_contas):
        if "Carteira" in n or "Dinheiro" in n:
            conta_padrao_idx = i
            break

    if dados_edicao:
        st.info(f"✏️ **Editando Abastecimento #{dados_edicao['id']} ({dados_edicao['data']})** • Confirme os dados reais do veículo.")
        tr_id_final = dados_edicao.get("transacao_id")
        try:
            dt_padrao = datetime.strptime(dados_edicao["data"], "%Y-%m-%d").date()
        except Exception:
            dt_padrao = date.today()
        km_sugerido = float(dados_edicao["hodometro"]) if dados_edicao.get("hodometro") is not None else km_sugerido
        val_bruto_padrao = float(dados_edicao.get("valor_bruto") or 100.0)
        desconto_padrao = float(dados_edicao.get("desconto") or 0.0)
        val_pago_padrao = float(dados_edicao.get("valor_pago") or 90.48)
        litros_padrao = float(dados_edicao["litros"]) if dados_edicao.get("litros") is not None else 0.0
        tanque_cheio_padrao = bool(dados_edicao.get("tanque_cheio") == 1) if dados_edicao.get("tanque_cheio") is not None else True
        posto_padrao = dados_edicao.get("posto") or ""
        obs_padrao = dados_edicao.get("observacao") or ""
        if dados_edicao.get("conta") in nomes_contas:
            conta_padrao_idx = nomes_contas.index(dados_edicao["conta"])
    elif vincular_transacao_id or dados_tr_vinc:
        st.caption("🔗 **Vinculação de despesa existente no extrato:**")
        lista_op = {}
        if dados_tr_vinc:
            chave_direta = f"#{dados_tr_vinc['id']} • {dados_tr_vinc['data']} • R$ {dados_tr_vinc['valor']:,.2f} ({dados_tr_vinc['conta']}) - {dados_tr_vinc['descricao']}"
            lista_op[chave_direta] = dados_tr_vinc
        for d in despesas_avulsas:
            chave = f"#{d['id']} • {d['data']} • R$ {d['valor']:,.2f} ({d['conta']}) - {d['descricao']}"
            if chave not in lista_op:
                lista_op[chave] = d

        sel_tr_str = st.selectbox("Selecione a despesa do extrato:", list(lista_op.keys()))
        obj_tr = lista_op[sel_tr_str]
        tr_id_final = obj_tr["id"]
        try:
            dt_padrao = datetime.strptime(obj_tr["data"], "%Y-%m-%d").date()
        except Exception:
            dt_padrao = date.today()
        val_pago_padrao = float(obj_tr["valor"])
        val_bruto_padrao = float(obj_tr["valor"])
        if obj_tr.get("conta") in nomes_contas:
            conta_padrao_idx = nomes_contas.index(obj_tr["conta"])
    else:
        opcoes_tipo = ["➕ Novo Abastecimento (Gera despesa única no extrato)", "🔗 Vincular a uma Despesa de Combustível já existente no extrato"]
        tipo_reg = st.radio("Tipo de Registro", opcoes_tipo, index=0)
        if tipo_reg == "🔗 Vincular a uma Despesa de Combustível já existente no extrato":
            if not despesas_avulsas:
                st.info("Nenhuma despesa de combustível sem vínculo encontrada no extrato.")
            else:
                lista_op = {f"#{d['id']} • {d['data']} • R$ {d['valor']:,.2f} ({d['conta']}) - {d['descricao']}": d for d in despesas_avulsas}
                sel_tr_str = st.selectbox("Selecione a despesa de combustível existente:", list(lista_op.keys()))
                obj_tr = lista_op[sel_tr_str]
                tr_id_final = obj_tr["id"]
                try:
                    dt_padrao = datetime.strptime(obj_tr["data"], "%Y-%m-%d").date()
                except Exception:
                    dt_padrao = date.today()
                val_pago_padrao = float(obj_tr["valor"])
                val_bruto_padrao = float(obj_tr["valor"])
                if obj_tr.get("conta") in nomes_contas:
                    conta_padrao_idx = nomes_contas.index(obj_tr["conta"])
                st.caption("🛡️ *Garantia: Ao salvar, este abastecimento será associado a essa despesa existente sem criar saída bancária duplicada.*")

    st.write("")
    st.markdown("###### 🚗 Dados do Veículo & Valores da Bomba")
    c1, c2, c3 = st.columns(3)
    data_abast = c1.date_input("Data do Abastecimento", dt_padrao)
    comb_opcoes = ["Etanol", "Gasolina Comum", "Gasolina Aditivada", "GNV", "Diesel"]
    comb_idx = 0
    if dados_edicao and dados_edicao.get("combustivel") in comb_opcoes:
        comb_idx = comb_opcoes.index(dados_edicao["combustivel"])
    combustivel = c2.selectbox("Combustível", comb_opcoes, index=comb_idx)
    posto = c3.text_input("Posto / Bandeira (opcional)", value=posto_padrao, placeholder="Ex: Posto Ipiranga, Shell, Petrobras...")

    # LINHA PRINCIPAL DE CÁLCULO: PREÇO POR LITRO E VALOR BRUTO NA BOMBA
    c4, c5, c6 = st.columns(3)
    preco_litro_sugerido = float(dados_edicao.get("preco_litro") or 0.0) if dados_edicao else 0.0
    if preco_litro_sugerido <= 0.0 and val_bruto_padrao > 0 and litros_padrao > 0:
        preco_litro_sugerido = round(val_bruto_padrao / litros_padrao, 3)
    if preco_litro_sugerido <= 0.0:
        preco_litro_sugerido = 3.590 if "Etanol" in combustivel else 5.890

    preco_litro = c4.number_input(
        "Preço por Litro na Bomba (R$/L)",
        min_value=0.001,
        value=preco_litro_sugerido,
        step=0.01,
        format="%.3f",
        help="Preço unitário por litro registrado no visor da bomba."
    )

    valor_bruto = input_moeda_centavos(
        "Valor Bruto na Bomba (R$)",
        valor_inicial=val_bruto_padrao,
        key="abast_val_bruto_moeda",
        help="Valor total do combustível abastecido antes de qualquer cupom ou desconto."
    )

    # Cálculo automático de litros com permissão de ajuste manual
    litros_calc = round(valor_bruto / preco_litro, 3) if preco_litro > 0 else 0.0
    litros_inicial = litros_padrao if (dados_edicao and litros_padrao > 0) else (litros_calc if litros_calc > 0 else 0.0)

    litros = c6.number_input(
        "Litros Abastecidos (L)",
        min_value=0.0,
        value=float(litros_inicial),
        step=0.5,
        format="%.3f",
        help="Calculado automaticamente a partir de Valor Bruto / Preço por Litro. Ajuste manualmente se o visor marcou ligeiramente diferente."
    )

    # LINHA DE PAGAMENTO E CUPOM / DESCONTO
    c7, c8, c9 = st.columns(3)
    desconto = input_moeda_centavos(
        "Cupom / Desconto (R$)",
        valor_inicial=desconto_padrao,
        key="abast_desconto_moeda",
        help="Desconto obtido (ex: ShellBox, Premmia, cupom). Abate do valor pago SEM alterar a quantidade física de litros abastecida."
    )

    val_pago_calc = max(0.0, round(valor_bruto - desconto, 2))
    valor_pago = input_moeda_centavos(
        "Valor Efetivamente Pago (R$)",
        valor_inicial=float(val_pago_calc if tr_id_final is None and not dados_edicao else val_pago_padrao),
        key="abast_pago_moeda",
        help="Valor real debitado do bolso ou conta bancária."
    )

    conta_sel = c9.selectbox("Conta Utilizada", nomes_contas, index=conta_padrao_idx)

    # DADOS INDEPENDENTES DO VEÍCULO: HODÔMETRO E TANQUE CHEIO
    c10, c11, c12 = st.columns(3)
    hodometro = c10.number_input(
        "Hodômetro (KM do Painel)",
        min_value=0.0,
        value=km_sugerido,
        step=10.0,
        help="KM registrado no painel. Informação independente dos litros e do valor pago. Deixe 0 se ainda for confirmar."
    )
    tanque_cheio = c11.checkbox(
        "Tanque Cheio? (Encheu até o automático)",
        value=tanque_cheio_padrao,
        help="Indica se o abastecimento foi completo até o desarme. Não interfere no cálculo financeiro."
    )
    obs = c12.text_input("Observações", value=obs_padrao, placeholder="Ex: Cupom de R$ 9,52 pago em dinheiro físico")

    # Resumo em tempo real e verificação de arredondamento
    if litros > 0 and preco_litro > 0:
        calc_bomba = round(litros * preco_litro, 2)
        dif_arred = round(abs(calc_bomba - valor_bruto), 2)
        preco_real_litro = round(valor_pago / litros, 3)

        msg_feedback = (
            f"📊 **Resumo:** {litros:.3f} L a {formatar_moeda_br(preco_litro)}/L = **{formatar_moeda_br(valor_bruto)}** na bomba • "
            f"Desconto: **{formatar_moeda_br(desconto)}** ➔ **Pago: {formatar_moeda_br(valor_pago)}** ({formatar_moeda_br(preco_real_litro)}/L real)"
        )
        if dif_arred > 0.05:
            msg_feedback += f" • ⚠️ *Diferença de arredondamento da bomba: {formatar_moeda_br(dif_arred)}.*"
        st.info(msg_feedback)
    else:
        st.caption("ℹ️ *Informe o preço por litro e o valor bruto para cálculo automático de litros.*")

    st.divider()
    if st.button("💾 Salvar Abastecimento", use_container_width=True, type="primary"):
        conn = conectar()
        c_id = mapa_contas.get(conta_sel, 2)
        dados_salvar = {
            "id": id_abast_editar,
            "data": data_abast.strftime("%Y-%m-%d"),
            "hodometro": hodometro if hodometro > 0 else None,
            "combustivel": combustivel,
            "litros": litros if litros > 0 else None,
            "valor_bruto": valor_bruto,
            "desconto": desconto,
            "valor_pago": valor_pago,
            "conta": conta_sel,
            "conta_id": c_id,
            "tanque_cheio": 1 if tanque_cheio else 0,
            "posto": posto,
            "observacao": obs,
            "transacao_id": tr_id_final
        }
        ok, msg = saldo_service.salvar_abastecimento_veiculo(conn, dados_salvar)
        conn.close()
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)


@st.dialog("🔄 Transferir Dinheiro ➔ Mercado Pago", width="medium")
def modal_transferencia_dinheiro_mercado_pago():
    """Pop-up rápido para transferir dinheiro recebido de corridas para o Mercado Pago sem criar receita duplicada."""
    st.markdown("##### 🔄 Depósito / Transferência Interna")
    st.caption("Mova dinheiro em mãos (Carteira) para sua conta do Mercado Pago sem criar uma segunda receita.")
    
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id FROM contas_config WHERE nome LIKE '%Carteira%' OR tipo = 'dinheiro' LIMIT 1")
    r_cart = cur.fetchone()
    cart_id = r_cart[0] if r_cart else 2
    saldo_cart = float(saldo_service.calcular_saldo_conta(conn, cart_id)["saldo_atual"])
    conn.close()

    st.info(f"💵 Saldo em mãos atual (Carteira): **R$ {saldo_cart:,.2f}**")

    c1, c2 = st.columns(2)
    valor_transf = input_moeda_centavos("Valor a Transferir (R$)", valor_inicial=min(saldo_cart, 50.0) if saldo_cart > 0 else 50.0, key="transf_mp_cart_val", mostrar_preview=False)
    data_transf = c2.date_input("Data da Transferência", date.today())
    obs = st.text_input("Descrição", value="Depósito Dinheiro Corridas ➔ Mercado Pago")

    st.caption("ℹ️ *A transferência reduz o saldo da Carteira e aumenta o Mercado Pago, sem gerar receita ou despesa.*")

    if st.button("Confirmar Transferência para Mercado Pago", use_container_width=True, type="primary"):
        conn = conectar()
        ok, msg = saldo_service.transferir_dinheiro_para_mercado_pago(conn, valor_transf, data_transf.strftime("%Y-%m-%d"), obs)
        conn.close()
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)


@st.dialog("🚕 + Lançar Turno", width="large")
def modal_novo_turno():
    """Janela pop-up para lançamento operacional de turno trabalhado (hoje ou data anterior)."""
    st.markdown("##### 🚕 + Lançar Turno de Trabalho")
    st.caption("O campo de data determina se é um turno de hoje ou data anterior. Permite múltiplos turnos no mesmo dia.")
    st.info("💡 **Desacoplamento:** O registro operacional não debita nem credita contas bancárias automaticamente sem confirmação.")
    
    with st.form("form_modal_turno", clear_on_submit=True):
        st.markdown("###### 📊 1. Dados Operacionais do Turno")
        c1, c2, c3 = st.columns(3)
        data_t = c1.date_input("Data do Turno", date.today())
        hora_ini = c2.text_input("Horário Inicial", value="07:00")
        hora_fim = c3.text_input("Horário Final", value="12:00")

        c4, c5, c6 = st.columns(3)
        km_ini = c4.number_input("KM Inicial", min_value=0.0, value=85000.0, step=1.0)
        km_fim = c5.number_input("KM Final", min_value=0.0, value=85070.0, step=1.0)
        plataforma_t = c6.selectbox("Plataforma", ["99", "Uber", "99 + Uber", "Outra"], index=0)

        c7, c8, c9 = st.columns(3)
        din_pix = input_moeda_centavos("Dinheiro / Pix (R$)", valor_inicial=0.0, key="novo_t_din_pix", help="Digite em centavos (ex: 500 para R$ 5,00)")
        onl = input_moeda_centavos("Ganhos Online (R$)", valor_inicial=0.0, key="novo_t_onl", help="Digite em centavos (ex: 5505 para R$ 55,05)")
        comb_estimado = input_moeda_centavos("Combustível Consumido (R$)", valor_inicial=25.0, key="novo_t_comb", help="Consumo estimado operacional.")

        c10, c11 = st.columns(2)
        periodo_t = c10.selectbox(
            "Período Principal",
            ["Manhã (06h às 12h)", "Tarde (12h às 18h)", "Noite (18h às 00h)", "Madrugada (00h às 06h)", "Integral / Misto"],
            index=0
        )
        obs_t = c11.text_input("Observações", placeholder="Ex: Movimento bom na manhã")

        st.divider()
        if st.form_submit_button("💾 Salvar Turno", use_container_width=True, type="primary"):
            data_iso = data_t.strftime("%Y-%m-%d")
            km_rodado = max(0.0, km_fim - km_ini) if km_fim >= km_ini else 0.0
            bruto_t = din_pix + onl

            try:
                t1 = datetime.strptime(hora_ini.strip(), "%H:%M")
                t2 = datetime.strptime(hora_fim.strip(), "%H:%M")
                dur_s = (t2 - t1).total_seconds() if t2 >= t1 else (t2 - t1).total_seconds() + 86400
                horas_calc = max(0.1, round(dur_s / 3600.0, 2))
            except Exception:
                horas_calc = 4.0

            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO turnos (data, hora_inicio, hora_fim, km_inicial, km_final, horas, km, 
                                   ganho_dinheiro_pix, ganho_online, ganho_bruto, combustivel, combustivel_consumido, 
                                   combustivel_consumido_estimado, observacao, periodo, plataforma, 
                                   dinheiro_fisico_recebido, status_turno, status_conciliacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'encerrado', 'conciliado')
            """, (data_iso, hora_ini.strip(), hora_fim.strip(), km_ini, km_fim, horas_calc, km_rodado,
                  din_pix, onl, bruto_t, comb_estimado, comb_estimado, comb_estimado, obs_t, periodo_t, plataforma_t,
                  din_pix))
            conn.commit()
            conn.close()
            st.success("Turno salvo com sucesso!")
            st.rerun()


@st.dialog("✏️ Editar Turno Operacional", width="large")
def modal_editar_turno(id_turno: int):
    """Permite corrigir horários, quilometragens e valores esquecidos ou informados incorretamente."""
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
        st.markdown(f"**Turno ID #{id_turno}** • Correção de Horários e Quilometragem")
        c1, c2, c3 = st.columns(3)
        data_t = c1.date_input("Data do Turno", value=data_orig)
        hora_ini = c2.text_input("Horário Inicial (HH:MM)", value=str(t_dict.get("hora_inicio") or "07:00"))
        hora_fim = c3.text_input("Horário Final (HH:MM)", value=str(t_dict.get("hora_fim") or "12:00"))

        c4, c5, c6 = st.columns(3)
        km_ini = c4.number_input("KM Inicial", min_value=0.0, value=float(t_dict.get("km_inicial") or 0.0), step=1.0)
        km_fim = c5.number_input("KM Final", min_value=0.0, value=float(t_dict.get("km_final") or (km_ini + float(t_dict.get("km") or 0.0))), step=1.0)
        opcoes_plat = ["99", "Uber", "99 + Uber", "Outra"]
        p_val = t_dict.get("plataforma", "99")
        plat_idx = opcoes_plat.index(p_val) if p_val in opcoes_plat else 0
        plataforma_t = c6.selectbox("Plataforma", opcoes_plat, index=plat_idx)

        c7, c8, c9 = st.columns(3)
        val_din_pix_init = float(t_dict.get("ganho_dinheiro_pix") or t_dict.get("dinheiro_fisico_recebido") or 0.0)
        din_pix = input_moeda_centavos("Dinheiro / Pix (R$)", valor_inicial=val_din_pix_init, key=f"edit_t_din_pix_{id_turno}", mostrar_preview=False)
        val_onl_init = float(t_dict.get("ganho_online") or max(0.0, float(t_dict.get("ganho_bruto") or 0.0) - val_din_pix_init))
        onl = input_moeda_centavos("Ganhos Online (R$)", valor_inicial=val_onl_init, key=f"edit_t_onl_{id_turno}", mostrar_preview=False)
        val_comb_init = float(t_dict.get("combustivel_consumido_estimado") or t_dict.get("combustivel") or 0.0)
        comb_t = input_moeda_centavos("Combustível Consumido (R$)", valor_inicial=val_comb_init, key=f"edit_t_comb_{id_turno}", mostrar_preview=False, help="Consumo operacional estimado.")

        c10, c11 = st.columns(2)
        per_lista = ["Manhã (06h às 12h)", "Tarde (12h às 18h)", "Noite (18h às 00h)", "Madrugada (00h às 06h)", "Integral / Misto"]
        p_per = t_dict.get("periodo", "Noite")
        per_idx = per_lista.index(p_per) if p_per in per_lista else 0
        periodo_t = c10.selectbox("Período Principal", per_lista, index=per_idx)
        obs_t = c11.text_input("Observações", value=str(t_dict.get("observacao") or ""))

        # Preview dinâmico
        km_calc = max(0.0, km_fim - km_ini) if km_fim >= km_ini else float(t_dict.get("km") or 0.0)
        bruto_calc = din_pix + onl
        st.caption(f"📊 *Recálculo automático: {km_calc:.1f} KM rodados • Ganho Bruto Total: R$ {bruto_calc:,.2f}*")

        st.caption("ℹ️ A alteração deste turno atualiza os indicadores operacionais sem alterar lançamentos financeiros.")
        
        if st.form_submit_button("💾 Salvar Alterações", use_container_width=True, type="primary"):
            data_iso = data_t.strftime("%Y-%m-%d")
            try:
                t1 = datetime.strptime(hora_ini.strip(), "%H:%M")
                t2 = datetime.strptime(hora_fim.strip(), "%H:%M")
                dur_s = (t2 - t1).total_seconds() if t2 >= t1 else (t2 - t1).total_seconds() + 86400
                horas_calc = max(0.1, round(dur_s / 3600.0, 2))
            except Exception:
                horas_calc = float(t_dict.get("horas") or 1.0)

            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                UPDATE turnos
                SET data = ?, hora_inicio = ?, hora_fim = ?, km_inicial = ?, km_final = ?,
                    horas = ?, km = ?, ganho_dinheiro_pix = ?, ganho_online = ?, ganho_bruto = ?,
                    combustivel = ?, combustivel_consumido = ?, combustivel_consumido_estimado = ?,
                    observacao = ?, periodo = ?, plataforma = ?, dinheiro_fisico_recebido = ?
                WHERE id = ?
            """, (data_iso, hora_ini.strip(), hora_fim.strip(), km_ini, km_fim,
                  horas_calc, km_calc, din_pix, onl, bruto_calc,
                  comb_t, comb_t, comb_t, obs_t, periodo_t, plataforma_t, din_pix, id_turno))
            conn.commit()
            conn.close()
            st.success("Turno atualizado com sucesso!")
            st.rerun()


@st.dialog("🐷 Transferência para Cofrinho (Mercado Pago)", width="medium")
def modal_transferir_cofrinho(cofrinho_id_pre=None, tipo_op_pre="guardar"):
    """
    Janela pop-up para movimentação interna entre a conta livre Mercado Pago e os cofrinhos.
    Registra apenas uma transferência entre origem e destino, reduzindo a origem e aumentando o destino sem receita/despesa.
    """
    conn = conectar()
    cofrinhos = planejamento_service.obter_cofrinhos(conn)
    s_mp = saldo_service.calcular_saldo_conta(conn, 1)
    saldo_mp_livre = float(s_mp["saldo_atual"])

    if not cofrinhos:
        st.warning("Nenhum cofrinho cadastrado no momento.")
        conn.close()
        return

    mapa_cofs = {c["id"]: c for c in cofrinhos}
    nomes_cofs = [c["nome"] for c in cofrinhos]

    idx_pre = 0
    if cofrinho_id_pre and cofrinho_id_pre in mapa_cofs:
        idx_pre = [c["id"] for c in cofrinhos].index(cofrinho_id_pre)

    opcoes_acao = ["➕ Guardar no Cofrinho (Aporte)", "➖ Resgatar para Mercado Pago (Retirada)"]
    idx_acao = 0 if tipo_op_pre == "guardar" else 1

    tipo_op = st.radio("Operação:", opcoes_acao, index=idx_acao, horizontal=True)
    eh_guardar = "Guardar" in tipo_op

    c_sel_nome = st.selectbox("Selecione o Cofrinho:", nomes_cofs, index=idx_pre)
    cof_obj = next(c for c in cofrinhos if c["nome"] == c_sel_nome)
    saldo_cof_atual = float(cof_obj["saldo_confirmado"])

    st.markdown(f"""
    <div style="background-color: var(--bg-subcard); border: 1px solid var(--border-color); border-radius: 8px; padding: 8px 12px; margin-bottom: 12px; font-size: 0.84rem;">
        <div>🏦 <strong>Mercado Pago (Livre Disponível):</strong> <span style="font-weight:700;">{formatar_moeda_br(saldo_mp_livre)}</span></div>
        <div style="margin-top: 4px;">🐷 <strong>{cof_obj['nome']} (Saldo Atual):</strong> <span style="font-weight:700; color: #f59e0b;">{formatar_moeda_br(saldo_cof_atual)}</span> • Meta: {formatar_moeda_br(float(cof_obj['meta_valor']))}</div>
    </div>
    """, unsafe_allow_html=True)

    val_max = saldo_mp_livre if eh_guardar else saldo_cof_atual
    c_val, c_dt = st.columns(2)
    valor_t = c_val.number_input("Valor da Transferência (R$)", min_value=0.01, value=min(10.0, max(0.01, val_max)) if val_max > 0 else 5.0, step=5.0)
    data_t = c_dt.date_input("Data da Movimentação", date.today())

    sugestao_desc = f"Aporte {cof_obj['nome']}" if eh_guardar else f"Resgate {cof_obj['nome']}"
    desc_t = st.text_input("Descrição", value=sugestao_desc)

    st.caption("ℹ️ *A transferência interna não gera receita nem despesa. Reduz o saldo da conta de origem e aumenta o saldo do destino.*")

    btn_lbl = f"➕ Confirmar Aporte de {formatar_moeda_br(valor_t)}" if eh_guardar else f"➖ Confirmar Resgate de {formatar_moeda_br(valor_t)}"
    if st.button(btn_lbl, use_container_width=True, type="primary"):
        data_iso = data_t.strftime("%Y-%m-%d")
        if eh_guardar:
            ok, msg = saldo_service.transferir_para_cofrinho(conn, cof_obj["id"], valor_t, data_iso, desc_t)
        else:
            ok, msg = saldo_service.retirar_de_cofrinho(conn, cof_obj["id"], valor_t, data_iso, desc_t)
        conn.close()
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)
    else:
        conn.close()


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


@st.dialog("✏️ Atualizar Disponibilidade Paga Leve", width="small")
def modal_atualizar_disponibilidade_pagaleve(titular: str = "Carlos"):
    """Permite informar manualmente a disponibilidade observada no aplicativo Paga Leve."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT limite_total, disponibilidade_atual FROM pagaleve_contas WHERE titular = ?", (titular,))
    row = cur.fetchone()
    conn.close()

    val_atual = float(row[1]) if row and row[1] is not None else 0.0

    st.caption(f"Informe a disponibilidade atual consultada no app Paga Leve para {titular}. Esta informação é apenas para seu controle e não altera saldos bancários.")

    with st.form("form_disp_pagaleve"):
        novo_disp = st.number_input("Disponibilidade Atual (R$)", min_value=0.0, value=val_atual, step=10.0)
        c_salvar, c_limpar = st.columns(2)
        salvar = c_salvar.form_submit_button("💾 Salvar", type="primary", use_container_width=True)
        limpar = c_limpar.form_submit_button("🔄 Deixar sob consulta", use_container_width=True)

        if salvar:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("UPDATE pagaleve_contas SET disponibilidade_atual = ? WHERE titular = ?", (novo_disp, titular))
            conn.commit()
            conn.close()
            st.success("Disponibilidade atualizada com sucesso!")
            st.rerun()

        if limpar:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("UPDATE pagaleve_contas SET disponibilidade_atual = NULL WHERE titular = ?", (titular,))
            conn.commit()
            conn.close()
            st.info("Disponibilidade redefinida para 'sob consulta'.")
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
    valor = input_moeda_centavos("Valor da Transferência (R$)", valor_inicial=50.0, key="modal_transf_geral_val", mostrar_preview=False)
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
        
        # Sincroniza tabela cofrinhos se envolver subcontas de cofrinhos
        for c_id in (origem_id, destino_id):
            cur.execute("SELECT id FROM cofrinhos WHERE conta_config_id = ?", (c_id,))
            r_cof = cur.fetchone()
            if r_cof:
                res_c = saldo_service.calcular_saldo_conta(conn, c_id)
                cur.execute("UPDATE cofrinhos SET saldo_confirmado = ?, data_atualizacao = ? WHERE id = ?",
                            (float(res_c["saldo_atual"]), data_transf.strftime("%Y-%m-%d"), r_cof[0]))

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
        "missao_semana": "🎯 Missão Ativa da Semana",
        "missao_ipva": "🎯 Missão Ativa da Semana",
        "contas_pagar": "🚨 Contas a Pagar",
        "turnos": "🚕 Últimos Turnos (99/Uber)",
        "paga_leve": "⚡ Paga Leve",
        "limites": "🎯 Orçamento & Limites",
        "maiores_gastos": "📊 Maiores Gastos"
    }

    col1, col2 = st.columns(2, gap="medium")
    vis_map = dict(st.session_state.get("blocos_visiveis", {}))
    precisa_salvar_vis = False

    with col1:
        st.markdown("#### ⬅️ Coluna Esquerda")
        esq_atuais = [normalizar_id_bloco(b) for b in st.session_state.get("blocos_col_esq", []) if b not in ("caixa_7dias", "projecao_mes", "capacidade_trabalho")]
        esq_atuais = list(dict.fromkeys(esq_atuais))
        if not esq_atuais:
            st.info("Nenhum bloco nesta coluna.")
        for i, b_id in enumerate(esq_atuais):
            with st.container(border=True):
                nome = nomes_blocos.get(b_id, b_id)
                st.markdown(f"**{nome}**")
                
                is_v = vis_map.get(b_id, True)
                novo_v = st.checkbox("👁️ Exibir bloco", value=is_v, key=f"mod_vis_{b_id}_esq_{i}")
                if novo_v != is_v:
                    vis_map[b_id] = novo_v
                    precisa_salvar_vis = True

                c_up, c_down, c_swap = st.columns([1, 1, 1.4])
                with c_up:
                    if st.button("⬆️ Subir", key=f"mod_up_{b_id}_esq_{i}", disabled=(i == 0), use_container_width=True):
                        mover_bloco(b_id, "subir")
                with c_down:
                    if st.button("⬇️ Descer", key=f"mod_down_{b_id}_esq_{i}", disabled=(i == len(esq_atuais) - 1), use_container_width=True):
                        mover_bloco(b_id, "descer")
                with c_swap:
                    if st.button("➡️ P/ Direita", key=f"mod_swap_{b_id}_esq_{i}", use_container_width=True):
                        mover_bloco(b_id, "trocar_coluna")

    with col2:
        st.markdown("#### ➡️ Coluna Direita")
        dir_atuais = [normalizar_id_bloco(b) for b in st.session_state.get("blocos_col_dir", []) if b not in ("caixa_7dias", "projecao_mes", "capacidade_trabalho")]
        dir_atuais = [b for b in list(dict.fromkeys(dir_atuais)) if b not in esq_atuais]
        if not dir_atuais:
            st.info("Nenhum bloco nesta coluna.")
        for i, b_id in enumerate(dir_atuais):
            with st.container(border=True):
                nome = nomes_blocos.get(b_id, b_id)
                st.markdown(f"**{nome}**")
                
                is_v = vis_map.get(b_id, True)
                novo_v = st.checkbox("👁️ Exibir bloco", value=is_v, key=f"mod_vis_{b_id}_dir_{i}")
                if novo_v != is_v:
                    vis_map[b_id] = novo_v
                    precisa_salvar_vis = True

                c_up, c_down, c_swap = st.columns([1, 1, 1.4])
                with c_up:
                    if st.button("⬆️ Subir", key=f"mod_up_{b_id}_dir_{i}", disabled=(i == 0), use_container_width=True):
                        mover_bloco(b_id, "subir")
                with c_down:
                    if st.button("⬇️ Descer", key=f"mod_down_{b_id}_dir_{i}", disabled=(i == len(dir_atuais) - 1), use_container_width=True):
                        mover_bloco(b_id, "descer")
                with c_swap:
                    if st.button("⬅️ P/ Esquerda", key=f"mod_swap_{b_id}_dir_{i}", use_container_width=True):
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
    bid = normalizar_id_bloco(bloco_id)
    st.markdown(f'<div class="bloco-card-anchor" data-bloco="{bid}" style="display:none;"></div>', unsafe_allow_html=True)
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
            if st.button("▲", key=f"btn_up_{bid}_{coluna}_{idx}", help=f"Subir '{titulo}'", disabled=(idx == 0)):
                mover_bloco(bid, "subir")
        with c_down:
            if st.button("▼", key=f"btn_down_{bid}_{coluna}_{idx}", help=f"Descer '{titulo}'", disabled=(idx == total_na_coluna - 1)):
                mover_bloco(bid, "descer")
        with c_swap:
            outra = "Direita" if coluna == "esq" else "Esquerda"
            if st.button("⇄", key=f"btn_swap_{bid}_{coluna}_{idx}", help=f"Mover para Coluna {outra}"):
                mover_bloco(bid, "trocar_coluna")

    return c_act


def render_conteudo_bloco_contas(df: pd.DataFrame, saldo_atual: float):
    """Renderiza a lista enxuta de contas, destacando Mercado Pago e Carteira e agrupando cofrinhos zerados."""
    conn = conectar()
    contas = saldo_service.obter_contas(conn)
    
    principais = []
    reservas_ativas = []
    cofrinhos_zerados = []
    
    for c in contas:
        res_c = saldo_service.calcular_saldo_conta(conn, c["id"])
        saldo_c = float(res_c["saldo_atual"])
        c_tipo = c.get("tipo", "digital")
        c_nome = c["nome"]
        
        info = {
            "id": c["id"],
            "nome": c_nome,
            "saldo": saldo_c,
            "tipo": c_tipo
        }
        
        if c_tipo == "cofrinho" or "Cofrinho" in c_nome:
            if saldo_c > 0:
                reservas_ativas.append(info)
            else:
                cofrinhos_zerados.append(info)
        else:
            principais.append(info)
    conn.close()

    # 1. Contas Principais em Destaque (Mercado Pago, Dinheiro/Carteira)
    for c in principais:
        cor_sld = "#10b981" if c["saldo"] >= 0 else "#ef4444"
        ic = "💵" if any(x in c["nome"].lower() for x in ["dinheiro", "carteira"]) else "🏦"
        st.markdown(f"""
        <div class="row-item" style="display:flex; justify-content:space-between; align-items:center; padding:5px 0;">
            <div><strong>{ic} {c["nome"]}</strong></div>
            <div style="color:{cor_sld}; font-weight:700; font-size:0.96rem;">{formatar_moeda_br(c["saldo"])}</div>
        </div>
        """, unsafe_allow_html=True)

    # 2. Reservas que tenham valor alocado
    for r in reservas_ativas:
        st.markdown(f"""
        <div class="row-item" style="display:flex; justify-content:space-between; align-items:center; padding:5px 0;">
            <div><span>🛡️ <strong>{r["nome"]}</strong></span> <span style="font-size:0.75rem; color:#3b82f6; background:rgba(59,130,246,0.12); padding:1px 6px; border-radius:4px;">Reserva</span></div>
            <div style="color:#3b82f6; font-weight:700; font-size:0.92rem;">{formatar_moeda_br(r["saldo"])}</div>
        </div>
        """, unsafe_allow_html=True)

    # 3. Saldo Total Consolidado
    st.markdown(f"""
    <div style="margin-top:6px; padding-top:6px; border-top:1px solid rgba(255,255,255,0.06); display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:0.86rem; color:var(--text-muted);">Saldo Disponível em Caixa:</span>
        <span style="color:#10b981; font-weight:800; font-size:1.02rem;">{formatar_moeda_br(saldo_atual)}</span>
    </div>
    """, unsafe_allow_html=True)

    # 4. Cofrinhos Zerados Agrupados (não poluem o card)
    if cofrinhos_zerados:
        with st.expander(f"📁 Cofrinhos Zerados ({len(cofrinhos_zerados)})", expanded=False):
            for cz in cofrinhos_zerados:
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; font-size:0.82rem; color:var(--text-muted); padding:2px 0;">
                    <span>🏷️ {cz["nome"]}</span>
                    <span>R$ 0,00</span>
                </div>
                """, unsafe_allow_html=True)


def render_conteudo_bloco_cartoes(df: pd.DataFrame):
    """Renderiza o resumo dos cartões de crédito no bloco."""
    conn = conectar()
    try:
        cartoes_df = pd.read_sql_query("SELECT * FROM cartoes", conn)
    except Exception:
        cartoes_df = pd.DataFrame()
    finally:
        conn.close()

    if cartoes_df.empty:
        st.info("Nenhum cartão cadastrado ainda.")
        return

    for _, crd in cartoes_df.iterrows():
        gastos_cartao = 0.0
        nome_crd = str(crd.get("nome", "")).strip()
        if not df.empty and "valor" in df.columns and nome_crd:
            try:
                m_desc = df["descricao"].astype(str).str.contains(re.escape(nome_crd), case=False, na=False) if "descricao" in df.columns else False
            except Exception:
                m_desc = False
            m_conta = (df["conta"].astype(str) == nome_crd) if "conta" in df.columns else False
            gastos_cartao = float(df[m_desc | m_conta]["valor"].sum())
        
        lim_total = float(crd.get("limite_total") or 0.0)
        limite_disp = max(lim_total - gastos_cartao, 0.0)
        bandeira = crd.get("bandeira", "Visa")
        venc = crd.get("dia_vencimento", "-")

        st.markdown(f"""
        <div class="subcard-item" style="margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; font-weight:600;">
                <span>💳 {nome_crd} ({bandeira})</span>
                <span style="color:var(--text-muted); font-size:0.85rem;">Venc: dia {venc}</span>
            </div>
            <div style="margin-top:6px; font-size:0.85rem; color:var(--text-muted); display:flex; justify-content:space-between;">
                <span>Limite Total: <strong>{formatar_moeda_br(lim_total)}</strong></span>
                <span style="color:#10b981;">Disponível: <strong>{formatar_moeda_br(limite_disp)}</strong></span>
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_conteudo_bloco_paga_leve(df: pd.DataFrame):
    """Renderiza o resumo do Paga Leve no bloco modular da Visão Geral."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT titular, tipo_limite, limite_total, disponibilidade_atual FROM pagaleve_contas WHERE ativo = 1")
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

    conta_carlos = next((c for c in contas_pl if c[0] == "Carlos"), None)
    limite_carlos = float(conta_carlos[2]) if conta_carlos and conta_carlos[2] is not None else 300.0
    disp_manual_carlos = conta_carlos[3] if conta_carlos and len(conta_carlos) > 3 and conta_carlos[3] is not None else None

    # Resumo das contas de Carlos e Fernanda
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        aberto_carlos = sum(p[3] for p in parcelas_pendentes if p[4] == "Carlos")
        txt_disp = f"Disp: {formatar_moeda_br(disp_manual_carlos)}" if disp_manual_carlos is not None else "Disp: sob consulta"
        st.markdown(f"""
        <div style="background-color:var(--bg-subcard); padding:8px 12px; border-radius:10px; border-left:3px solid #2563eb;">
            <div style="font-size:0.8rem; color:var(--text-muted); font-weight:600;">👤 Carlos (Ref: {formatar_moeda_br(limite_carlos)})</div>
            <div style="font-size:0.95rem; font-weight:700; color:var(--text-primary); margin-top:2px;">
                {formatar_moeda_br(aberto_carlos)} <span style="font-size:0.75rem; font-weight:500; color:#10b981;">({txt_disp})</span>
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
                    <span style="color:var(--text-muted); font-size:0.84rem;">{formatar_moeda_br(gasto_cat)} / {formatar_moeda_br(teto)} <strong>({pct*100:.0f}%)</strong></span>
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

    def fmt_data_segura(d, fmt="%d/%m/%Y"):
        try:
            return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime(fmt)
        except Exception:
            return str(d)[:10]

    meses_nomes = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    nome_mes = meses_nomes.get(mes_atual, f"Mês {mes_atual}")

    # 1. Dívidas de Meses Anteriores (Regras 3 e 5)
    df_antigas = df[(df["tipo"] == "despesa") & (df["pago"] == 0) & (df["data"] < inicio_mes_str)].sort_values(by="data", ascending=True) if not df.empty else pd.DataFrame()
    if not df_antigas.empty:
        if "dividas_antigas_selecionadas" not in st.session_state:
            st.session_state["dividas_antigas_selecionadas"] = carregar_dividas_antigas_selecionadas()

        st.markdown(f"<div style='color:#dc2626; font-weight:700; margin-bottom:4px;'>📁 Pendências de Meses Anteriores ({len(df_antigas)})</div>", unsafe_allow_html=True)
        st.caption(f"Estas contas não entram automaticamente na meta de {nome_mes}. Marque para incluí-las no cálculo da meta de trabalho:")

        for _, r in df_antigas.iterrows():
            ic = obter_icone_categoria(r["categoria"])
            data_br = fmt_data_segura(r["data"], "%d/%m/%Y")
            esta_inc = r["id"] in st.session_state["dividas_antigas_selecionadas"]

            c_chk, c_info, c_val, c_btn = st.columns([0.6, 2.7, 1.3, 0.45], vertical_alignment="center")
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
                st.markdown(f"<div style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:0.88rem;'>{ic} <span style='color:var(--text-muted); font-size:0.82rem;'>{data_br}</span> • <strong>{r['descricao']}</strong></div>", unsafe_allow_html=True)
            with c_val:
                tag_meta = " <span style='color:#10b981; font-weight:600; font-size:0.75rem;'>(na meta)</span>" if esta_inc else ""
                st.markdown(f"<div style='text-align:right; white-space:nowrap;'><span style='color:#ef4444; font-weight:700; font-size:0.88rem;'>{formatar_moeda_br(r['valor'])}</span>{tag_meta}</div>", unsafe_allow_html=True)
            with c_btn:
                if st.button("👍", key=f"btn_baixa_cp_antiga_{r['id']}", help=f"Dar baixa / Pagar {r['descricao']}"):
                    modal_baixa_rapida_conta(r['id'])
        st.divider()

    # 2. Obrigações Pertencentes a Outubro (Regras 1 e 2)
    vence_hoje = df[(df["tipo"] == "despesa") & (df["pago"] == 0) & (df["data"] == hoje_str)] if not df.empty else pd.DataFrame()
    vencidas_mes = df[(df["tipo"] == "despesa") & (df["pago"] == 0) & (df["data"] >= inicio_mes_str) & (df["data"] < hoje_str)].sort_values(by="data", ascending=True) if not df.empty else pd.DataFrame()
    proximas_mes = df[(df["tipo"] == "despesa") & (df["pago"] == 0) & (df["data"] > hoje_str) & (df["data"] <= fim_mes_str)].sort_values(by="data", ascending=True) if not df.empty else pd.DataFrame()

    if not vence_hoje.empty:
        st.markdown(f"<div style='color:#f59e0b; font-weight:700; margin-bottom:6px;'>⚠️ Vence Hoje ({hoje.strftime('%d/%m')})</div>", unsafe_allow_html=True)
        for _, r in vence_hoje.iterrows():
            ic = obter_icone_categoria(r["categoria"])
            c_info, c_val, c_btn = st.columns([3.3, 1.3, 0.45], vertical_alignment="center")
            with c_info:
                st.markdown(f"<div style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:0.88rem;'>{ic} <strong>{r['descricao']}</strong></div>", unsafe_allow_html=True)
            with c_val:
                st.markdown(f"<div style='text-align:right; color:#f59e0b; font-weight:700; font-size:0.88rem; white-space:nowrap;'>{formatar_moeda_br(r['valor'])}</div>", unsafe_allow_html=True)
            with c_btn:
                if st.button("👍", key=f"btn_baixa_cp_hoje_{r['id']}", help=f"Dar baixa / Pagar {r['descricao']}"):
                    modal_baixa_rapida_conta(r['id'])
        st.divider()

    if not vencidas_mes.empty:
        st.markdown(f"<div style='color:#ef4444; font-weight:700; margin-bottom:6px;'>❗ Atrasadas de {nome_mes} ({len(vencidas_mes)})</div>", unsafe_allow_html=True)
        for _, r in vencidas_mes.iterrows():
            ic = obter_icone_categoria(r["categoria"])
            data_br = fmt_data_segura(r["data"], "%d/%m")
            c_info, c_val, c_btn = st.columns([3.3, 1.3, 0.45], vertical_alignment="center")
            with c_info:
                st.markdown(f"<div style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:0.88rem;'>{ic} <span style='color:var(--text-muted); font-size:0.82rem;'>{data_br}</span> • <strong>{r['descricao']}</strong></div>", unsafe_allow_html=True)
            with c_val:
                st.markdown(f"<div style='text-align:right; color:#ef4444; font-weight:700; font-size:0.88rem; white-space:nowrap;'>{formatar_moeda_br(r['valor'])}</div>", unsafe_allow_html=True)
            with c_btn:
                if st.button("👍", key=f"btn_baixa_cp_venc_{r['id']}", help=f"Dar baixa / Pagar {r['descricao']}"):
                    modal_baixa_rapida_conta(r['id'])
        st.divider()

    if not proximas_mes.empty:
        st.markdown(f"<div style='font-weight:600; margin-bottom:6px;'>⏳ A Vencer em {nome_mes} ({len(proximas_mes)})</div>", unsafe_allow_html=True)
        for _, r in proximas_mes.iterrows():
            ic = obter_icone_categoria(r["categoria"])
            data_br = fmt_data_segura(r["data"], "%d/%m")
            c_info, c_val, c_btn = st.columns([3.3, 1.3, 0.45], vertical_alignment="center")
            with c_info:
                st.markdown(f"<div style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:0.88rem;'>{ic} <span style='color:var(--text-muted); font-size:0.82rem;'>{data_br}</span> • {r['descricao']}</div>", unsafe_allow_html=True)
            with c_val:
                st.markdown(f"<div style='text-align:right; color:var(--text-primary); font-weight:600; font-size:0.88rem; white-space:nowrap;'>{formatar_moeda_br(r['valor'])}</div>", unsafe_allow_html=True)
            with c_btn:
                if st.button("👍", key=f"btn_baixa_cp_prox_{r['id']}", help=f"Dar baixa / Pagar {r['descricao']}"):
                    modal_baixa_rapida_conta(r['id'])
    elif vence_hoje.empty and vencidas_mes.empty and df_antigas.empty:
        st.success("Tudo em dia! Nenhuma conta pendente para os próximos dias.")

    # 3. Contas de Meses Posteriores (Regra 4)
    df_futuras = df[(df["tipo"] == "despesa") & (df["pago"] == 0) & (df["data"] > fim_mes_str)].sort_values(by="data", ascending=True) if not df.empty else pd.DataFrame()
    if not df_futuras.empty:
        st.divider()
        st.markdown(f"<div style='color:var(--text-muted); font-weight:600; margin-bottom:6px;'>🗓️ Próximos Meses ({len(df_futuras)})</div>", unsafe_allow_html=True)
        st.caption("Despesas futuras programadas (não entram na meta deste mês):")
        for _, r in df_futuras.head(4).iterrows():
            ic = obter_icone_categoria(r["categoria"])
            data_br = fmt_data_segura(r["data"], "%d/%m/%Y")
            c_info, c_val, c_btn = st.columns([3.3, 1.3, 0.45], vertical_alignment="center")
            with c_info:
                st.markdown(f"<div style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:0.86rem;'>{ic} <span style='color:var(--text-muted); font-size:0.80rem;'>{data_br}</span> • {r['descricao']}</div>", unsafe_allow_html=True)
            with c_val:
                st.markdown(f"<div style='text-align:right; color:var(--text-muted); font-weight:600; font-size:0.86rem; white-space:nowrap;'>{formatar_moeda_br(r['valor'])}</div>", unsafe_allow_html=True)
            with c_btn:
                if st.button("👍", key=f"btn_baixa_cp_fut_{r['id']}", help=f"Dar baixa / Pagar {r['descricao']}"):
                    modal_baixa_rapida_conta(r['id'])


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
                    <span style="color:var(--text-muted); font-size:0.84rem;">{formatar_moeda_br(val)} <strong>({pct:.1f}%)</strong></span>
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
        try:
            dt_format = datetime.strptime(str(t["data"])[:10], "%Y-%m-%d").strftime("%d/%m")
        except Exception:
            dt_format = str(t.get("data", ""))[:5]
        g_bruto = float(t.get("ganho_bruto") or 0.0)
        c_comb = float(t.get("combustivel") or 0.0)
        liq = g_bruto - c_comb
        per = t.get("periodo", "Turno")
        h_val = float(t.get("horas") or 0.0)
        duracao_txt = f"{h_val:.1f}h *(a confirmar)*" if (str(t.get("data")) in ("2026-10-20", "2026-10-21") or h_val < 1.0) else f"{h_val:.1f}h"
        st.markdown(
            f"🗓️ **{dt_format}** • {duracao_txt} ({per}) | "
            f"Bruto: `{formatar_moeda_br(g_bruto)}` | "
            f"Comb: :red[{formatar_moeda_br(c_comb)}] → "
            f"Líq: :green[**{formatar_moeda_br(liq)}**]"
        )


def render_conteudo_bloco_missao_semana(df: pd.DataFrame):
    """Card resumido da Missão Ativa da Semana (IPVA ou desafio escolhido) para o Dashboard."""
    conn = conectar()
    hoje = date.today()
    mes_str = hoje.strftime("%Y-%m")
    try:
        missao = planejamento_service.obter_missao_ativa_semana(conn, mes_ano=mes_str, data_referencia=hoje)
    except Exception:
        missao = {"tem_missao": False}
    finally:
        conn.close()

    if not missao or not missao.get("tem_missao"):
        st.info("Nenhuma missão prioritária ativa configurada para esta semana.")
        return

    c1, c2 = st.columns([2.0, 1.2])
    with c1:
        st.markdown(f"**🎯 {missao['titulo']}**")
        try:
            dt_venc_fmt = datetime.strptime(str(missao['data_vencimento'])[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
        except Exception:
            dt_venc_fmt = str(missao.get('data_vencimento', ''))
        st.caption(f"Vencimento: **{dt_venc_fmt}** ({missao.get('dias_restantes', 0)} dias restantes)")
    with c2:
        st.markdown(f"<div style='text-align: right; font-weight: 700; font-size: 1.15rem; color: var(--text-primary);'>{formatar_moeda_br(missao['valor_nominal'])}</div>", unsafe_allow_html=True)
        if missao['valor_ja_pago'] > 0:
            st.markdown(f"<div style='text-align: right; font-size: 0.85rem; color: var(--text-muted);'>Pago: <span style='color:#10b981; font-weight:600;'>{formatar_moeda_br(missao['valor_ja_pago'])}</span></div>", unsafe_allow_html=True)

    pct = min(1.0, float(missao.get("percentual_coberto", 0)) / 100.0)
    coberto_tot = float(missao.get('valor_ja_pago', 0)) + float(missao.get('valor_reservado', 0))
    st.progress(pct, text=f"Cobertura: {pct*100:.0f}% ({formatar_moeda_br(coberto_tot)})")

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.caption(f"🛡️ Reserva / Pago: **{formatar_moeda_br(coberto_tot)}**")
    with col_m2:
        st.caption(f"🎯 Falta Cobrir: :orange[**{formatar_moeda_br(missao['saldo_devedor_restante'])}**]")

    if st.button("Gerenciar Missões ➔", key="btn_ir_missao_vg", use_container_width=True):
        st.session_state["pagina_ativa"] = "🎯 Planejamento & Metas"
        st.rerun()


def render_conteudo_bloco_missao_ipva(df: pd.DataFrame):
    """Alias retrocompatível para Missão Ativa da Semana."""
    render_conteudo_bloco_missao_semana(df)


def render_bloco(bloco_id: str, coluna: str, idx: int, total_na_coluna: int, df: pd.DataFrame, df_turnos: pd.DataFrame, saldo_atual: float):
    """Renderiza um bloco modular no dashboard de acordo com seu ID e coluna com isolamento de falhas individual."""
    # Blocos redundantes eliminados da Visão Geral (geridos pela Meta Integrada e Meta da Semana)
    if bloco_id in ("caixa_7dias", "projecao_mes", "capacidade_trabalho"):
        return

    bid = normalizar_id_bloco(bloco_id)

    try:
        with st.container(border=True, key=f"card_{bid}_{coluna}_{idx}"):
            if bid == "contas":
                c_act = render_cabecalho_bloco("🏦 Minhas Contas", bid, coluna, idx, total_na_coluna, tem_botao_acao=True)
                if c_act and c_act.button("+ Conta", key=f"btn_add_cta_{coluna}_{idx}", use_container_width=True):
                    modal_nova_conta()
                render_conteudo_bloco_contas(df, saldo_atual)

            elif bid == "cartoes":
                c_act = render_cabecalho_bloco("💳 Meus Cartões", bid, coluna, idx, total_na_coluna, tem_botao_acao=True)
                if c_act and c_act.button("+ Cartão", key=f"btn_add_crd_{coluna}_{idx}", use_container_width=True):
                    modal_novo_cartao()
                render_conteudo_bloco_cartoes(df)

            elif bid == "missao_semana":
                render_cabecalho_bloco("🎯 Missão Ativa da Semana", bid, coluna, idx, total_na_coluna)
                render_conteudo_bloco_missao_semana(df)

            elif bid == "contas_pagar":
                render_cabecalho_bloco("🚨 Contas a Pagar", bid, coluna, idx, total_na_coluna)
                render_conteudo_bloco_contas_pagar(df)

            elif bid == "turnos":
                render_cabecalho_bloco("🚕 Últimos Turnos (99/Uber)", bid, coluna, idx, total_na_coluna)
                render_conteudo_bloco_turnos(df_turnos)

            elif bid == "paga_leve":
                c_act = render_cabecalho_bloco("⚡ Paga Leve (Pix 4x)", bid, coluna, idx, total_na_coluna, tem_botao_acao=True)
                if c_act and c_act.button("+ Compra", key=f"btn_add_pl_{coluna}_{idx}", use_container_width=True):
                    modal_paga_leve()
                render_conteudo_bloco_paga_leve(df)

            elif bid == "limites":
                render_cabecalho_bloco("🎯 Orçamento & Limites", bid, coluna, idx, total_na_coluna)
                render_conteudo_bloco_limites(df)

            elif bid == "maiores_gastos":
                render_cabecalho_bloco("📊 Maiores Gastos", bid, coluna, idx, total_na_coluna)
                render_conteudo_bloco_maiores_gastos(df)
            else:
                st.info(f"Bloco não reconhecido: {bid}")
    except Exception as e:
        with st.container(border=True, key=f"card_err_{bid}_{coluna}_{idx}"):
            render_cabecalho_bloco(f"Bloco {bid}", bid, coluna, idx, total_na_coluna)
            st.warning(f"Não foi possível carregar os dados deste bloco no momento ({e}).")


def render_painel_prioridades_operacional(df: pd.DataFrame, df_turnos: pd.DataFrame):
    """
    PAINEL OPERACIONAL DE PRIORIDADES, CAIXA E METAS DE TRABALHO
    Responde diretamente às 5 perguntas prioritárias da Central Financeira:
    1. Quanto a família recebeu de renda efetiva neste mês.
    2. Quanto o motorista recebeu na 99, separando bruto e líquido.
    3. Quanto temos disponível em caixa real (Mercado Pago + Carteira).
    4. O que precisamos pagar nesta semana (hoje + 6 dias) e no restante do mês.
    5. Quanto preciso produzir por dia e por hora, considerando disponibilidade de trabalho.
    """
    hoje = date.today()
    hoje_str = hoje.strftime("%Y-%m-%d")
    # Contando hoje mais seis dias (7 dias continuos)
    limite_7d = hoje + timedelta(days=6)
    limite_7d_str = limite_7d.strftime("%Y-%m-%d")
    ano_atual = hoje.year
    mes_atual = hoje.month
    inicio_mes_str = f"{ano_atual}-{mes_atual:02d}-01"
    ultimo_dia = calendar.monthrange(ano_atual, mes_atual)[1]
    fim_mes = date(ano_atual, mes_atual, ultimo_dia)
    fim_mes_str = fim_mes.strftime("%Y-%m-%d")
    dias_corridos_restantes = max(1, (fim_mes - hoje).days + 1)

    conn = conectar()

    # 1. Saldos detalhados por conta via serviço centralizado
    contas = saldo_service.obter_contas(conn)
    saldos_contas = []
    for c in contas:
        s = saldo_service.calcular_saldo_conta(conn, c['id'])
        saldos_contas.append({
            "id": c["id"],
            "nome": c["nome"],
            "saldo": float(s["saldo_atual"])
        })
    saldo_consolidado_info = saldo_service.calcular_saldo_consolidado(conn)
    saldo_total_disponivel = float(saldo_consolidado_info["saldo_consolidado"])
    mp_val = next((c['saldo'] for c in saldos_contas if 'Mercado' in c['nome']), 0.0)
    cart_val = next((c['saldo'] for c in saldos_contas if 'Dinheiro' in c['nome'] or 'Carteira' in c['nome']), 0.0)

    # 2. Renda do Mês
    df_rec = df[(df["tipo"] == "receita") & (df["data"] >= inicio_mes_str) & (df["data"] <= fim_mes_str)].copy() if not df.empty else pd.DataFrame()
    rec_recebidas = df_rec[df_rec["pago"] == 1] if not df_rec.empty else pd.DataFrame()
    rec_previstas = df_rec[df_rec["pago"] == 0] if not df_rec.empty else pd.DataFrame()

    # Salário Fernanda
    sal_fernanda_row = pd.DataFrame()
    if not rec_recebidas.empty:
        sal_fernanda_row = rec_recebidas[
            rec_recebidas["descricao"].str.contains("Fernanda", case=False, na=False) |
            rec_recebidas["categoria"].str.contains("Fernanda", case=False, na=False)
        ]
    val_sal_fernanda = float(sal_fernanda_row["valor"].sum()) if not sal_fernanda_row.empty else 3523.43

    # Renda e Produção Familiar (Integração com Marco Real da 99)
    marco_99 = obter_marco_producao_99()
    if marco_99:
        data_corte_marco = str(marco_99["data_corte"])
        fat_bruto_marco = float(marco_99["faturamento_bruto"])
        din_marco = float(marco_99["recebido_dinheiro_pix"])
        onl_marco = float(marco_99["recebido_online"])
        divergencia_centavo = round(fat_bruto_marco - (din_marco + onl_marco), 2)
        revisao_marco = marco_99.get("revisao", 1)

        # Turnos com data <= data_corte_marco já estão no marco e NÃO somam novamente
        turnos_inclusos = df_turnos[df_turnos["data"] <= data_corte_marco] if not df_turnos.empty else pd.DataFrame()
        bruto_inclusos = float(turnos_inclusos["ganho_bruto"].sum()) if not turnos_inclusos.empty else 0.0
        comb_inclusos = float(turnos_inclusos["combustivel"].sum()) if not turnos_inclusos.empty else 0.0

        # Turnos posteriores à data de corte somam normalmente
        turnos_post = df_turnos[df_turnos["data"] > data_corte_marco] if not df_turnos.empty else pd.DataFrame()
        bruto_post = float(turnos_post["ganho_bruto"].sum()) if not turnos_post.empty else 0.0
        comb_post = float(turnos_post["combustivel"].sum()) if not turnos_post.empty else 0.0

        total_bruto_99 = fat_bruto_marco + bruto_post
        custos_op_conhecidos_99 = comb_inclusos + comb_post
        liq_turnos_apuravel = total_bruto_99 - custos_op_conhecidos_99
    else:
        df_turnos_out = df_turnos[df_turnos["data"] >= inicio_mes_str].copy() if not df_turnos.empty else pd.DataFrame()
        total_bruto_99 = float(df_turnos_out["ganho_bruto"].sum()) if not df_turnos_out.empty else 0.0
        custos_op_conhecidos_99 = float(df_turnos_out["combustivel"].sum()) if not df_turnos_out.empty else 0.0
        liq_turnos_apuravel = total_bruto_99 - custos_op_conhecidos_99
        turnos_inclusos = pd.DataFrame()
        turnos_post = pd.DataFrame()
        bruto_inclusos = 0.0
        bruto_post = 0.0
        fat_bruto_marco = 0.0
        data_corte_marco = hoje_str
        din_marco = 0.0
        onl_marco = 0.0
        divergencia_centavo = 0.0
        revisao_marco = 1

    # Empréstimos recebidos segregados
    emp_recebidos = pd.DataFrame()
    if not rec_recebidas.empty:
        emp_recebidos = rec_recebidas[
            rec_recebidas["categoria"].str.contains("Empréstimo|Aporte|Outras Dívidas", case=False, na=False)
        ]
    val_emp_recebidos = float(emp_recebidos["valor"].sum()) if not emp_recebidos.empty else 0.0

    # Total Combinado de Referência: Salário Líquido Fernanda (R$ 3.523,43) + Produção Bruta 99 (R$ 1.340,40) = R$ 4.863,83
    total_renda_e_producao_familiar = val_sal_fernanda + total_bruto_99
    total_rec_previstas = float(rec_previstas["valor"].sum()) if not rec_previstas.empty else 0.0

    # Descontos em folha da Fernanda (segregados do caixa, sem debitar banco nem somar de volta)
    df_folha = pd.DataFrame()
    if not df.empty:
        df_folha = df[(df["data"] >= inicio_mes_str) & (df["data"] <= fim_mes_str) & (
            (df["descricao"].str.contains("Desconto em Folha|Odontol", case=False, na=False)) |
            (df["categoria"].str.contains("Odontol", case=False, na=False)) |
            (df["afeta_saldo_bancario"] == 0 if "afeta_saldo_bancario" in df.columns else False)
        )]
    tot_folha = float(df_folha["valor"].sum()) if not df_folha.empty else 598.11

    # 3. Filtragem de compromissos pendentes
    df_desp = df[(df["tipo"] == "despesa") & (df["pago"] == 0)].copy() if not df.empty else pd.DataFrame()
    if "afeta_saldo_bancario" in df_desp.columns:
        df_caixa = df_desp[(df_desp["afeta_saldo_bancario"] == 1) | (df_desp["afeta_saldo_bancario"].isna())].copy()
    else:
        df_caixa = df_desp.copy()

    # Separação estrita dos períodos
    vencidas = df_caixa[(df_caixa["data"] < hoje_str) & (df_caixa["data"] >= inicio_mes_str)].sort_values("data") if not df_caixa.empty else pd.DataFrame()
    vencem_hoje = df_caixa[df_caixa["data"] == hoje_str] if not df_caixa.empty else pd.DataFrame()
    prox_7d = df_caixa[(df_caixa["data"] >= hoje_str) & (df_caixa["data"] <= limite_7d_str)].sort_values("data") if not df_caixa.empty else pd.DataFrame()
    restante_mes = df_caixa[(df_caixa["data"] > limite_7d_str) & (df_caixa["data"] <= fim_mes_str)].sort_values("data") if not df_caixa.empty else pd.DataFrame()

    tot_vencidas = float(vencidas["valor"].sum()) if not vencidas.empty else 0.0
    tot_hoje = float(vencem_hoje["valor"].sum()) if not vencem_hoje.empty else 0.0
    tot_7d = float(prox_7d["valor"].sum()) if not prox_7d.empty else 0.0
    tot_restante_mes = float(restante_mes["valor"].sum()) if not restante_mes.empty else 0.0
    tot_caixa_pendente_mes = tot_vencidas + tot_7d + tot_restante_mes

    # Destaque específico do Acordo BV (22/10)
    bv_row = df_caixa[df_caixa["descricao"].str.contains("BV", case=False, na=False)] if not df_caixa.empty else pd.DataFrame()
    val_bv_nominal = float(bv_row["valor"].iloc[0]) if not bv_row.empty else 1428.82
    val_bv_ref_outubro = 1921.22
    tot_7d_sem_bv = max(0.0, tot_7d - val_bv_nominal)

    # Missão IPVA via serviço
    missao_ipva = planejamento_service.obter_status_missao_ipva(conn)
    val_ipva = float(missao_ipva["valor_nominal"]) if missao_ipva.get("tem_missao") else 431.11
    missao_ativa = missao_ipva.get("is_ativa", True)
    missao_concluida = missao_ipva.get("is_concluida", False)
    missao_status = missao_ipva.get("status", "ativa")
    missao_prioridade = missao_ipva.get("prioridade", "alta")

    # Cofrinhos reais
    cofrinhos = planejamento_service.obter_cofrinhos(conn)
    tot_cofrinhos_confirmado = sum(float(c["saldo_confirmado"]) for c in cofrinhos)

    conn.close()

    # --- RENDERIZAÇÃO VISUAL SIMPLIFICADA E OBJETIVA ---
    # Controle do drill-down interativo dos indicadores
    if "vg_detalhe_ativo" not in st.session_state:
        st.session_state["vg_detalhe_ativo"] = None
    det_ativo = st.session_state["vg_detalhe_ativo"]

    # =========================================================================
    # [ NÍVEL 1: CABEÇALHO COMPACTO DA CASA ]
    # Receita Mensal: R$ 4.918 | Despesa Mensal: R$ 6.737 | Caixa Disponível: R$ 47,00
    # =========================================================================
    receita_familiar_liquida = val_sal_fernanda
    faturamento_liquido_99 = total_bruto_99
    receita_mensal_total = receita_familiar_liquida + faturamento_liquido_99

    tot_desp_pagas_mes = float(df[(df["tipo"] == "despesa") & (df["pago"] == 1) & (df["data"] >= inicio_mes_str) & (df["data"] <= fim_mes_str)]["valor"].sum()) if not df.empty else 0.0
    tot_desp_pendentes_mes = tot_caixa_pendente_mes
    despesa_mensal_total = tot_desp_pagas_mes + tot_desp_pendentes_mes

    val_rec_disp = formatar_moeda_br(receita_mensal_total).split(',')[0]
    val_desp_disp = formatar_moeda_br(despesa_mensal_total).split(',')[0]
    val_cxa_disp = formatar_moeda_br(saldo_total_disponivel)
    sub_rec_disp = f"Fernanda {formatar_moeda_br(receita_familiar_liquida).split(',')[0]} • 99 {formatar_moeda_br(faturamento_liquido_99).split(',')[0]}"
    sub_desp_disp = f"Pagas {formatar_moeda_br(tot_desp_pagas_mes).split(',')[0]} • A Pagar {formatar_moeda_br(tot_desp_pendentes_mes).split(',')[0]}"
    sub_cxa_disp = f"Mercado Pago {formatar_moeda_br(mp_val).split(',')[0]} • Carteira {formatar_moeda_br(cart_val).split(',')[0]}"

    with st.container(border=True):
        col_tit_vg, col_sub_vg = st.columns([1.8, 2.2], vertical_alignment="center")
        with col_tit_vg:
            st.markdown("<h4 style='margin:0; font-size:1.10rem;'>🎯 Visão Geral Operacional</h4>", unsafe_allow_html=True)
        dias_semana_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
        nome_dia_hoje = dias_semana_pt[hoje.weekday()]
        with col_sub_vg:
            st.markdown(f"<div style='text-align:right; color:var(--text-muted); font-size:0.82rem;'>📅 <strong>{nome_dia_hoje}, {hoje.strftime('%d/%m/%Y')}</strong></div>", unsafe_allow_html=True)

        c_n1_rec, c_n1_desp, c_n1_cxa = st.columns(3, vertical_alignment="center")
        with c_n1_rec:
            st.markdown(f"""
            <div style="padding:2px 0;">
                <div style="font-size:0.82rem; color:var(--text-muted); font-weight:600;">📈 Receita Mensal: <span style="font-size:1.20rem; font-weight:800; color:#10b981;">{val_rec_disp}</span></div>
                <div style="font-size:0.75rem; color:var(--text-muted);">{sub_rec_disp}</div>
            </div>
            """, unsafe_allow_html=True)
            btn_txt_rec = "▲ Fechar" if det_ativo == "renda" else "▾ Detalhes da Renda"
            if st.button(btn_txt_rec, key="btn_n1_renda", use_container_width=True):
                st.session_state["vg_detalhe_ativo"] = None if det_ativo == "renda" else "renda"
                st.rerun()

        with c_n1_desp:
            st.markdown(f"""
            <div style="padding:2px 0;">
                <div style="font-size:0.82rem; color:var(--text-muted); font-weight:600;">📉 Despesa Mensal: <span style="font-size:1.20rem; font-weight:800; color:#ef4444;">{val_desp_disp}</span></div>
                <div style="font-size:0.75rem; color:var(--text-muted);">{sub_desp_disp}</div>
            </div>
            """, unsafe_allow_html=True)
            btn_txt_desp = "▲ Fechar" if det_ativo in ("despesas", "vencidas", "prox_7d", "restante") else "▾ Detalhes das Despesas"
            if st.button(btn_txt_desp, key="btn_n1_desp", use_container_width=True):
                st.session_state["vg_detalhe_ativo"] = None if det_ativo in ("despesas", "vencidas", "prox_7d", "restante") else "despesas"
                st.rerun()

        with c_n1_cxa:
            st.markdown(f"""
            <div style="padding:2px 0;">
                <div style="font-size:0.82rem; color:var(--text-muted); font-weight:600;">🏦 Caixa Disponível: <span style="font-size:1.20rem; font-weight:800; color:#3b82f6;">{val_cxa_disp}</span></div>
                <div style="font-size:0.75rem; color:var(--text-muted);">{sub_cxa_disp}</div>
            </div>
            """, unsafe_allow_html=True)
            btn_txt_cxa = "▲ Fechar" if det_ativo == "caixa" else "▾ Detalhes do Caixa"
            if st.button(btn_txt_cxa, key="btn_n1_cxa", use_container_width=True):
                st.session_state["vg_detalhe_ativo"] = None if det_ativo == "caixa" else "caixa"
                st.rerun()

        # Detalhamentos quando acionados pelos botões do Nível 1
        if det_ativo == "renda":
            with st.container(border=True):
                col_dh, col_dc = st.columns([5, 1], vertical_alignment="center")
                with col_dh:
                    st.markdown("<h5 style='margin:0;'>👥 Renda e Produção Familiar (Outubro)</h5>", unsafe_allow_html=True)
                    st.caption(f"Saldo Real em Contas: **{formatar_moeda_br(saldo_total_disponivel)}** (MP: {formatar_moeda_br(mp_val)} | Carteira: {formatar_moeda_br(cart_val)})")
                with col_dc:
                    if st.button("✖️ Fechar", key="btn_close_renda", use_container_width=True):
                        st.session_state["vg_detalhe_ativo"] = None
                        st.rerun()

                total_familiar_mes = val_sal_fernanda + total_bruto_99
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric(
                        label="👩‍💼 Salário Fernanda",
                        value=formatar_moeda_br(val_sal_fernanda)
                    )
                    st.caption("Líquido recebido")
                with m2:
                    st.metric(
                        label="🚕 Faturamento 99 (Outubro)",
                        value=formatar_moeda_br(total_bruto_99)
                    )
                    st.caption("Produção total do mês comprovada no app")
                with m3:
                    st.metric(
                        label="💰 Total Familiar no Mês",
                        value=formatar_moeda_br(total_familiar_mes)
                    )
                    st.caption("Receita total consolidada")

        elif det_ativo == "despesas":
            with st.container(border=True):
                col_dh, col_dc = st.columns([5, 1])
                with col_dh:
                    st.markdown(f"##### 📉 Despesas de Outubro ({formatar_moeda_br(despesa_mensal_total)})")
                    st.caption("Visão consolidada de todas as obrigações pagas e pendentes de outubro.")
                with col_dc:
                    if st.button("✖️ Fechar", key="btn_close_despesas", width="stretch"):
                        st.session_state["vg_detalhe_ativo"] = None
                        st.rerun()

                cd1, cd2, cd3, cd4 = st.columns(4)
                with cd1:
                    st.metric("🚨 Atrasadas", formatar_moeda_br(tot_vencidas), f"{len(vencidas)} contas", delta_color="inverse")
                    if tot_vencidas > 0 and st.button("Abrir Atrasadas", key="btn_dsp_venc"):
                        st.session_state["vg_detalhe_ativo"] = "vencidas"
                        st.rerun()
                with cd2:
                    st.metric("⏳ Próximos 7 Dias", formatar_moeda_br(tot_7d), f"{len(prox_7d)} contas", delta_color="inverse")
                    if st.button("Abrir 7 Dias", key="btn_dsp_7d"):
                        st.session_state["vg_detalhe_ativo"] = "prox_7d"
                        st.rerun()
                with cd3:
                    st.metric("🗓️ Restante do Mês", formatar_moeda_br(tot_restante_mes), f"{len(restante_mes)} contas")
                    if st.button("Abrir Restante", key="btn_dsp_rest"):
                        st.session_state["vg_detalhe_ativo"] = "restante"
                        st.rerun()
                with cd4:
                    st.metric("✅ Já Pagas no Mês", formatar_moeda_br(tot_desp_pagas_mes), "Liquidadas em conta", delta_color="normal")

        elif det_ativo == "caixa":
            with st.container(border=True):
                col_dh, col_dc = st.columns([5, 1])
                with col_dh:
                    st.markdown("##### 🏦 Composição dos Saldos em Caixa (Conciliado em 19/10/2026)")
                with col_dc:
                    if st.button("✖️ Fechar", key="btn_close_caixa", width="stretch"):
                        st.session_state["vg_detalhe_ativo"] = None
                        st.rerun()
                b1, b2, b3 = st.columns(3)
                with b1:
                    st.metric("Mercado Pago", formatar_moeda_br(mp_val))
                with b2:
                    st.metric("Dinheiro / Carteira", formatar_moeda_br(cart_val))
                with b3:
                    st.metric("Consolidado Livre", formatar_moeda_br(saldo_total_disponivel))
                st.caption("🛡️ *Garantia Contábil: Nenhum limite de cartão de crédito ou limite Paga Leve foi incluído nestes saldos.*")

        elif det_ativo == "vencidas":
            with st.container(border=True):
                col_dh, col_dc = st.columns([5, 1])
                with col_dh:
                    st.markdown(f"##### 🚨 Contas Vencidas ({len(vencidas)} contas • Total: {formatar_moeda_br(tot_vencidas)})")
                with col_dc:
                    if st.button("✖️ Fechar", key="btn_close_vencidas", width="stretch"):
                        st.session_state["vg_detalhe_ativo"] = None
                        st.rerun()
                if not vencidas.empty:
                    df_v_show = vencidas[["data", "descricao", "categoria", "valor", "conta"]].copy()
                    df_v_show["valor"] = df_v_show["valor"].apply(formatar_moeda_br)
                    df_v_show.columns = ["Vencimento", "Descrição", "Categoria", "Valor", "Conta"]
                    st.dataframe(df_v_show, width="stretch")
                    st.caption("⚠️ *Priorize serviços essenciais (Copasa, Cemig SIM) e medicamentos para manter o funcionamento da casa.*")
                    
                    st.write("")
                    col_act_v1, col_act_v2, col_act_v3 = st.columns([3, 1.5, 1.5], vertical_alignment="center")
                    with col_act_v1:
                        ids_vencidas = vencidas["id"].tolist()
                        mapa_vencidas = {row["id"]: f"{row['descricao']} ({formatar_moeda_br(row['valor'])}) - Venc: {row['data'][-2:]}/{row['data'][5:7]}" for _, row in vencidas.iterrows()}
                        sel_vencida_id = st.selectbox(
                            "Selecionar Conta Atrasada para Ação:",
                            options=ids_vencidas,
                            format_func=lambda tid: mapa_vencidas.get(tid, f"Conta #{tid}"),
                            key="sel_vencida_acao"
                        )
                    with col_act_v2:
                        st.write("")
                        if st.button("💳 Pagar Conta", key="btn_pagar_vencida_vg", type="primary", use_container_width=True):
                            modal_registrar_pagamento(sel_vencida_id)
                    with col_act_v3:
                        st.write("")
                        if st.button("🎯 Definir como Missão", key="btn_missao_vencida_vg", type="secondary", use_container_width=True, help="Adiciona esta conta atrasada como a Missão da Semana no lugar do IPVA"):
                            conn_vm = conectar()
                            ok_m, msg_m = planejamento_service.definir_missao_ativa_semana(conn_vm, sel_vencida_id)
                            conn_vm.close()
                            if ok_m:
                                st.success(msg_m)
                                st.rerun()
                            else:
                                st.error(msg_m)
                else:
                    st.success("Nenhuma conta atrasada!")

        elif det_ativo == "prox_7d":
            with st.container(border=True):
                col_dh, col_dc = st.columns([5, 1])
                with col_dh:
                    st.markdown(f"##### ⏳ Contas dos Próximos 7 Dias (20 a 26/10 • {len(prox_7d)} contas • Total: {formatar_moeda_br(tot_7d)})")
                with col_dc:
                    if st.button("✖️ Fechar", key="btn_close_prox7d", width="stretch"):
                        st.session_state["vg_detalhe_ativo"] = None
                        st.rerun()
                if not prox_7d.empty:
                    df_p_show = prox_7d[["data", "descricao", "categoria", "valor", "conta"]].copy()
                    df_p_show["valor"] = df_p_show["valor"].apply(formatar_moeda_br)
                    df_p_show.columns = ["Vencimento", "Descrição", "Categoria", "Valor", "Conta"]
                    st.dataframe(df_p_show, width="stretch")
                    st.caption(f"ℹ️ *Inclui a parcela 4/24 do Acordo BV (22/10, {formatar_moeda_br(val_bv_nominal)}). Sem o BV, totaliza {formatar_moeda_br(tot_7d_sem_bv)}.*")
                else:
                    st.info("Nenhuma conta prevista para os próximos 7 dias.")

        elif det_ativo == "restante":
            with st.container(border=True):
                col_dh, col_dc = st.columns([5, 1])
                with col_dh:
                    st.markdown(f"##### 🗓️ Contas do Restante do Mês (27 a 31/10 • {len(restante_mes)} contas • Total: {formatar_moeda_br(tot_restante_mes)})")
                with col_dc:
                    if st.button("✖️ Fechar", key="btn_close_restante", width="stretch"):
                        st.session_state["vg_detalhe_ativo"] = None
                        st.rerun()
                if not restante_mes.empty:
                    df_r_show = restante_mes[["data", "descricao", "categoria", "valor", "conta"]].copy()
                    df_r_show["valor"] = df_r_show["valor"].apply(formatar_moeda_br)
                    df_r_show.columns = ["Vencimento", "Descrição", "Categoria", "Valor", "Conta"]
                    st.dataframe(df_r_show, width="stretch")
                    st.caption(f"ℹ️ *Inclui a Cemig (27/10, R$ 93,95) e o Parcelamento IPVA 2025/2026 (29/10, {formatar_moeda_br(val_ipva)}).*")
                else:
                    st.info("Nenhuma conta prevista para o restante do mês.")

    # =========================================================================
    # [ NÍVEL 2: O FOCO DE HOJE (CARD ÚNICO DE AÇÃO) ]
    # Meta Hoje: R$ 175,00 (5h)  |  Faturado: R$ 0,00  |  [ ▶ Iniciar Turno ]
    # (Com um botão discreto "⚙ Ajustar Planejamento Semanal/Mensal" que só expande os seletores se você quiser mexer)
    # =========================================================================
    turno_aberto_vg = obter_turno_aberto()
    df_t_hoje_enc = df_turnos[(df_turnos["data"] == hoje_str) & (df_turnos.get("status_turno", "encerrado") != "aberto")] if not df_turnos.empty else pd.DataFrame()
    qtd_t_hoje = len(df_t_hoje_enc)
    km_t_hoje = float(df_t_hoje_enc["km"].sum()) if not df_t_hoje_enc.empty else 0.0
    bruto_t_hoje = float(df_t_hoje_enc["ganho_bruto"].sum()) if not df_t_hoje_enc.empty else 0.0
    horas_t_hoje = float(df_t_hoje_enc["horas"].sum()) if not df_t_hoje_enc.empty else 0.0

    horas_hoje = float(st.session_state.get("vg_horas_hoje_in", 5.0))
    taxa_bruta_mercado = 35.0
    meta_bruta_hoje = horas_hoje * taxa_bruta_mercado
    restante_bruto_hoje = max(0.0, meta_bruta_hoje - bruto_t_hoje)
    horas_restantes_hoje = restante_bruto_hoje / taxa_bruta_mercado if restante_bruto_hoje > 0 else 0.0
    cor_fat = "#10b981" if bruto_t_hoje >= meta_bruta_hoje and meta_bruta_hoje > 0 else ("var(--text-primary)" if bruto_t_hoje > 0 else "var(--text-muted)")

    with st.container(border=True):
        col_f1, col_f2, col_f3 = st.columns([1.5, 1.5, 1.2], vertical_alignment="center")
        with col_f1:
            st.markdown(f"""
            <div style="font-size:0.82rem; color:var(--text-muted); font-weight:600;">🎯 Meta Hoje:</div>
            <div style="font-size:1.30rem; font-weight:800; color:var(--text-primary);">
                {formatar_moeda_br(meta_bruta_hoje)} <span style="font-size:0.85rem; font-weight:600; color:var(--text-muted);">({horas_hoje:.0f}h)</span>
            </div>
            """, unsafe_allow_html=True)
        with col_f2:
            txt_fat_sub = f"{qtd_t_hoje} turno(s) • {horas_t_hoje:.1f}h" if bruto_t_hoje > 0 else "Nenhum faturamento ainda hoje"
            st.markdown(f"""
            <div style="font-size:0.82rem; color:var(--text-muted); font-weight:600;">🚕 Faturado:</div>
            <div style="font-size:1.30rem; font-weight:800; color:{cor_fat};">
                {formatar_moeda_br(bruto_t_hoje)}
            </div>
            <div style="font-size:0.75rem; color:var(--text-muted);">{txt_fat_sub}</div>
            """, unsafe_allow_html=True)
        with col_f3:
            if turno_aberto_vg:
                plat_i = turno_aberto_vg.get("plataforma") or "99"
                h_ini = turno_aberto_vg.get("hora_inicio") or "00:00"
                st.caption(f"🟢 Turno ativo ({plat_i} às {h_ini})")
                if st.button("🏁 Encerrar Turno", key="btn_foco_encerrar", use_container_width=True, type="primary"):
                    modal_encerrar_turno(turno_aberto_vg["id"])
            else:
                if st.button("▶ Iniciar Turno", key="btn_foco_iniciar", use_container_width=True, type="primary"):
                    modal_iniciar_turno()

        # Botão discreto para expandir os seletores de planejamento e métricas
        with st.expander("⚙ Ajustar Planejamento Semanal / Mensal", expanded=False):
            marco_99 = obter_marco_producao_99()
            margem_salva = carregar_margem_liquida_planejada(65.0)
            dias_disp_mes_salvo = carregar_dias_trabalho_planejados(min(8, dias_corridos_restantes))
            deficit_liquido_mes = max(0.0, tot_caixa_pendente_mes - saldo_total_disponivel)

            col_in1, col_in2, col_in3, col_in4, col_in5 = st.columns([1.1, 1.0, 1.1, 1.2, 1.1], vertical_alignment="center")
            with col_in1:
                horas_hoje_in = st.number_input(
                    "⏱️ Horas hoje:",
                    min_value=0.5,
                    max_value=16.0,
                    value=horas_hoje,
                    step=0.5,
                    help="Horas reais que você tem disponíveis para rodar hoje (ex: 4h ou 5h).",
                    key="vg_horas_hoje_in"
                )
            with col_in2:
                dias_semana = st.number_input(
                    "📆 Dias semana:",
                    min_value=1,
                    max_value=7,
                    value=5,
                    step=1,
                    help="Quantidade de dias que planeja trabalhar nesta semana corrente.",
                    key="vg_dias_semana_in"
                )
            with col_in3:
                horas_dia_semana = st.number_input(
                    "⏱️ Horas/dia:",
                    min_value=1.0,
                    max_value=16.0,
                    value=5.0,
                    step=0.5,
                    help="Média diária de horas planejadas para a semana.",
                    key="vg_horas_semana_in"
                )
            with col_in4:
                dias_disp_mes_in = st.number_input(
                    f"🗓️ Dias mês ({dias_corridos_restantes}d rest.):",
                    min_value=1,
                    max_value=dias_corridos_restantes,
                    value=min(dias_disp_mes_salvo, dias_corridos_restantes),
                    step=1,
                    key="vg_dias_mes_in"
                )
                if dias_disp_mes_in != dias_disp_mes_salvo:
                    salvar_dias_trabalho_planejados(dias_disp_mes_in)
                    dias_disp_mes_salvo = dias_disp_mes_in
            with col_in5:
                margem_num = st.number_input(
                    "Margem Líq. (%):",
                    min_value=40.0,
                    max_value=95.0,
                    value=float(margem_salva),
                    step=5.0,
                    format="%.0f",
                    key="vg_margem_liq_num_input"
                )
                if margem_num != margem_salva:
                    salvar_margem_liquida_planejada(margem_num)
                margem_liq_pct = margem_num / 100.0

            # Controles de Missão e Acordo BV
            conn_meta = conectar()
            opcoes_missoes_semana = planejamento_service.obter_opcoes_missoes_semana(conn_meta, f"{ano_atual}-{mes_atual:02d}")
            missao_atual_info = planejamento_service.obter_missao_ativa_semana(conn_meta, f"{ano_atual}-{mes_atual:02d}", hoje)

            c_ctrl_mis, c_ctrl_bv = st.columns([2.5, 1.5], vertical_alignment="center")
            with c_ctrl_mis:
                lista_tids_sem = [0] + [op["transacao_id"] for op in opcoes_missoes_semana]
                mapa_rotulos_sem = {0: "⚪ Nenhuma Missão Extra (Apenas despesas regulares)"}
                idx_sel_mis = 0
                t_id_ativa_atual = missao_atual_info.get("transacao_id")
                for i_op, op in enumerate(opcoes_missoes_semana):
                    mapa_rotulos_sem[op["transacao_id"]] = op["rotulo"]
                    if op["transacao_id"] == t_id_ativa_atual:
                        idx_sel_mis = i_op + 1

                sel_m_semana = st.selectbox(
                    "🎯 Missão / Desafio Ativo para esta Semana:",
                    options=lista_tids_sem,
                    index=idx_sel_mis,
                    format_func=lambda tid: mapa_rotulos_sem.get(tid, f"Obrigação #{tid}"),
                    help="Selecione um desafio para compor a meta semanal de trabalho (ex: IPVA ou uma conta atrasada escolhida voluntariamente).",
                    key="vg_sel_missao_semana"
                )
                if sel_m_semana != (t_id_ativa_atual or 0):
                    planejamento_service.definir_missao_ativa_semana(conn_meta, sel_m_semana, f"{ano_atual}-{mes_atual:02d}")
                    conn_meta.close()
                    st.rerun()

            with c_ctrl_bv:
                st.write("")
                incluir_bv_semana = st.checkbox(
                    f"Incluir Acordo BV ({formatar_moeda_br(val_bv_nominal)}) na semana",
                    value=False,
                    help="Por regra, o Acordo BV permanece na Projeção Mensal para não sobrecarregar as horas de trabalho da semana.",
                    key="vg_chk_incluir_bv"
                )

            # Cálculo formal da necessidade de caixa da semana via serviço
            nec_sem = planejamento_service.calcular_necessidade_caixa_7dias(
                conn_meta,
                data_referencia=hoje,
                incluir_bv_semana=incluir_bv_semana,
                missao_transacao_id=sel_m_semana
            )
            conn_meta.close()

            meta_liq_semana = float(nec_sem["necessidade_adicional_caixa"])
            tot_regulares_semana = float(nec_sem["total_confirmadas_7d"])
            val_missao_semana = float(nec_sem["valor_missao_semana"])
            val_bv_semana = float(nec_sem["valor_bv_semana"])
            saldo_livre_sem = float(nec_sem["saldo_livre"])

            inicio_sem = hoje - timedelta(days=hoje.weekday())
            fim_sem = inicio_sem + timedelta(days=6)
            ini_sem_s = inicio_sem.strftime("%Y-%m-%d")
            fim_sem_s = fim_sem.strftime("%Y-%m-%d")
            
            df_t_sem = df_turnos[(df_turnos["data"] >= ini_sem_s) & (df_turnos["data"] <= fim_sem_s)] if not df_turnos.empty else pd.DataFrame()
            bruto_real_semana = float(df_t_sem["ganho_bruto"].sum()) if not df_t_sem.empty else 0.0
            horas_real_semana = float(df_t_sem["horas"].sum()) if not df_t_sem.empty else 0.0

            meta_bruta_semana = meta_liq_semana / margem_liq_pct
            horas_nec_semana = meta_bruta_semana / taxa_bruta_mercado
            capacidade_semana = dias_semana * horas_dia_semana
            dif_horas_semana = capacidade_semana - horas_nec_semana
            pct_semana = min(100.0, (bruto_real_semana / meta_bruta_semana) * 100) if meta_bruta_semana > 0 else 0.0

            meta_liq_mes = deficit_liquido_mes
            meta_bruta_mes = meta_liq_mes / margem_liq_pct
            horas_nec_mes = meta_bruta_mes / taxa_bruta_mercado
            meta_bruta_dia_mes = meta_bruta_mes / dias_disp_mes_salvo if dias_disp_mes_salvo > 0 else meta_bruta_mes

            st.divider()

            # Três Cartões Integrados: Hoje | Semana | Mês
            c_cd_hoje, c_cd_sem, c_cd_mes = st.columns(3)
            with c_cd_hoje:
                with st.container(border=True):
                    st.markdown(f"**📅 Meta de Hoje ({horas_hoje:.1f}h)**")
                    st.caption("Meta para as horas declaradas hoje.")
                    st.metric("Alvo Hoje", formatar_moeda_br(meta_bruta_hoje), f"{horas_hoje:.1f}h a R$ 35/h")
                    st.metric("Faturado Hoje", formatar_moeda_br(bruto_t_hoje), f"{qtd_t_hoje} turno(s)")
            with c_cd_sem:
                with st.container(border=True):
                    st.markdown(f"**📆 Meta da Semana ({inicio_sem.strftime('%d/%m')} a {fim_sem.strftime('%d/%m')})**")
                    st.caption("Flexibilidade de compensar horas.")
                    st.metric("Alvo Semana", formatar_moeda_br(meta_bruta_semana), f"{formatar_moeda_br(meta_liq_semana)} líq.")
                    st.metric("Horas Necessárias", f"{horas_nec_semana:.1f}h", f"Capacidade: {capacidade_semana:.1f}h")
            with c_cd_mes:
                with st.container(border=True):
                    st.markdown(f"**🗓️ Meta do Mês (até 31/10)**")
                    st.caption(f"{dias_corridos_restantes}d corridos restantes.")
                    st.metric("Déficit Mês", formatar_moeda_br(deficit_liquido_mes), "Líquido a cobrir")
                    st.metric("Alvo Bruto Total", formatar_moeda_br(meta_bruta_mes), f"{formatar_moeda_br(meta_bruta_dia_mes)}/dia")

            st.divider()

            # Painel do Motorista (Produção & Eficiência)
            filtro_painel = st.segmented_control(
                "Visualizar Painel:",
                options=["Hoje", "Semana", "Mês"],
                default="Hoje",
                key="vg_painel_motorista_sel_seg",
                label_visibility="collapsed"
            )
            sel_p = filtro_painel or "Hoje"

            df_comb_trans = df[
                (df["tipo"] == "despesa") & 
                (df["pago"] == 1) & 
                (df["categoria"].str.contains("Combust", case=False, na=False) | df["descricao"].str.contains("Abastecimento", case=False, na=False))
            ] if not df.empty else pd.DataFrame()

            if sel_p == "Hoje":
                df_t_p = df_turnos[df_turnos["data"] == hoje_str] if not df_turnos.empty else pd.DataFrame()
                bruto_real = float(df_t_p["ganho_bruto"].sum()) if not df_t_p.empty else 0.0
                comb_estimado = float(df_t_p["combustivel"].sum()) if not df_t_p.empty else 0.0
                horas_real = float(df_t_p["horas"].sum()) if not df_t_p.empty else 0.0
                km_real = float(df_t_p["km"].sum()) if not df_t_p.empty else 0.0
                qtd_t_p = len(df_t_p)
                rotulo_periodo = f"Hoje ({hoje.strftime('%d/%m/%Y')})"
                comb_posto_real = float(df_comb_trans[df_comb_trans["data"] == hoje_str]["valor"].sum()) if not df_comb_trans.empty else 0.0
            elif sel_p == "Semana":
                df_t_p = df_turnos[(df_turnos["data"] >= ini_sem_s) & (df_turnos["data"] <= fim_sem_s)] if not df_turnos.empty else pd.DataFrame()
                bruto_real = float(df_t_p["ganho_bruto"].sum()) if not df_t_p.empty else 0.0
                comb_estimado = float(df_t_p["combustivel"].sum()) if not df_t_p.empty else 0.0
                horas_real = float(df_t_p["horas"].sum()) if not df_t_p.empty else 0.0
                km_real = float(df_t_p["km"].sum()) if not df_t_p.empty else 0.0
                qtd_t_p = len(df_t_p)
                rotulo_periodo = f"Semana ({inicio_sem.strftime('%d/%m')} a {fim_sem.strftime('%d/%m')})"
                comb_posto_real = float(df_comb_trans[(df_comb_trans["data"] >= ini_sem_s) & (df_comb_trans["data"] <= fim_sem_s)]["valor"].sum()) if not df_comb_trans.empty else 0.0
            else:
                if marco_99:
                    fat_marco = float(marco_99["faturamento_bruto"])
                    corte_marco_str = str(marco_99["data_corte"])
                    turnos_pos = df_turnos[(df_turnos["data"] > corte_marco_str) & (df_turnos["data"] >= inicio_mes_str)] if not df_turnos.empty else pd.DataFrame()
                    bruto_pos = float(turnos_pos["ganho_bruto"].sum()) if not turnos_pos.empty else 0.0
                    bruto_real = fat_marco + bruto_pos
                    comb_estimado = float(df_turnos[df_turnos["data"] >= inicio_mes_str]["combustivel"].sum()) if not df_turnos.empty else 0.0
                    horas_real = float(df_turnos[df_turnos["data"] >= inicio_mes_str]["horas"].sum()) if not df_turnos.empty else 0.0
                    km_real = float(df_turnos[df_turnos["data"] >= inicio_mes_str]["km"].sum()) if not df_turnos.empty else 0.0
                    qtd_t_p = len(df_turnos[df_turnos["data"] >= inicio_mes_str]) if not df_turnos.empty else 0
                else:
                    df_t_p = df_turnos[df_turnos["data"] >= inicio_mes_str] if not df_turnos.empty else pd.DataFrame()
                    bruto_real = float(df_t_p["ganho_bruto"].sum()) if not df_t_p.empty else 0.0
                    comb_estimado = float(df_t_p["combustivel"].sum()) if not df_t_p.empty else 0.0
                    horas_real = float(df_t_p["horas"].sum()) if not df_t_p.empty else 0.0
                    km_real = float(df_t_p["km"].sum()) if not df_t_p.empty else 0.0
                    qtd_t_p = len(df_t_p)
                rotulo_periodo = f"Acumulado Mês ({hoje.strftime('%B/%Y')})"
                comb_posto_real = float(df_comb_trans[(df_comb_trans["data"] >= inicio_mes_str) & (df_comb_trans["data"] <= fim_mes_str)]["valor"].sum()) if not df_comb_trans.empty else 0.0

            rendimento_km = round(bruto_real / km_real, 2) if km_real > 0 else 0.0
            custo_km_est = round(comb_estimado / km_real, 2) if km_real > 0 else 0.0
            prod_hora = round(bruto_real / horas_real, 2) if horas_real > 0 else 0.0

            p1, p2, p3, p4 = st.columns(4)
            with p1:
                st.metric("🚕 Faturamento", formatar_moeda_br(bruto_real), f"{qtd_t_p} turno(s)")
            with p2:
                st.metric("⛽ Posto", formatar_moeda_br(comb_posto_real), "Real debitado" if comb_posto_real > 0 else "Sem gasto")
            with p3:
                st.metric("⚡ Rendimento/KM", f"{formatar_moeda_br(rendimento_km)}/km", f"Custo: {formatar_moeda_br(custo_km_est)}/km")
            with p4:
                st.metric("⏱️ Produtividade", f"{horas_real:.1f}h • {km_real:,.0f} km", f"{formatar_moeda_br(prod_hora)}/h")




def render_visao_geral(df: pd.DataFrame, df_turnos: pd.DataFrame):
    """
    PÁGINA 1: VISÃO GERAL
    Dashboard com KPIs executivos, resumo de contas, pendências imediatas e maiores gastos.
    Suporta reordenação interativa de blocos por botões (▲ ▼ ⇄), modal organizador e arrastar e soltar (Drag & Drop).
    """
    render_barra_acoes_rapidas()

    # PAINEL OPERACIONAL DE PRIORIDADES, CAIXA E METAS DO MOTORISTA 99
    render_painel_prioridades_operacional(df, df_turnos)

    # 1. Saldo em contas efetivado (disponível real) via Serviço Centralizado para os blocos
    conn_saldo = conectar()
    res_saldo_consolidado = saldo_service.calcular_saldo_consolidado(conn_saldo)
    saldo_atual = float(res_saldo_consolidado["saldo_consolidado"])
    conn_saldo.close()

    # Carrega ou sincroniza as posições salvas dos blocos
    if "blocos_col_esq" not in st.session_state or "blocos_col_dir" not in st.session_state:
        col_esq_carregada, col_dir_carregada, vis_carregada = carregar_layout_dashboard()
        st.session_state["blocos_col_esq"] = col_esq_carregada
        st.session_state["blocos_col_dir"] = col_dir_carregada
        st.session_state["blocos_visiveis"] = vis_carregada

    # Higienizar e normalizar listas no session_state para evitar duplicações e cross-column duplicates
    raw_esq_ss = [normalizar_id_bloco(b) for b in st.session_state.get("blocos_col_esq", []) if b not in ("caixa_7dias", "projecao_mes", "capacidade_trabalho")]
    raw_dir_ss = [normalizar_id_bloco(b) for b in st.session_state.get("blocos_col_dir", []) if b not in ("caixa_7dias", "projecao_mes", "capacidade_trabalho")]
    
    esq_dedup = list(dict.fromkeys(raw_esq_ss))
    dir_dedup = [b for b in list(dict.fromkeys(raw_dir_ss)) if b not in esq_dedup]

    if not esq_dedup:
        esq_dedup = ["contas", "cartoes"]
    if not dir_dedup:
        dir_dedup = ["contas_pagar", "missao_semana", "turnos"]

    st.session_state["blocos_col_esq"] = esq_dedup
    st.session_state["blocos_col_dir"] = dir_dedup

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
    filtros por status/tipo/conta/busca, ordenação por data e toggles interativos.
    """
    render_barra_acoes_rapidas()

    # BLOCO SUPERIOR: SALDO ATUAL EM CAIXA (INDEPENDENTE DO PERÍODO SELECIONADO)
    conn_caixa = conectar()
    dados_saldo_caixa = saldo_service.calcular_saldo_consolidado(conn_caixa)
    conn_caixa.close()

    saldo_livre = float(dados_saldo_caixa.get("saldo_consolidado", 0.0))
    saldo_reservas = float(dados_saldo_caixa.get("saldo_reservas", 0.0))
    saldo_total = float(dados_saldo_caixa.get("saldo_total_com_reservas", 0.0))
    contas_detalhe = dados_saldo_caixa.get("contas", [])

    with st.container(border=True):
        sc1, sc2, sc3, sc4 = st.columns([1.5, 1.3, 1.3, 1.5], vertical_alignment="center")
        with sc1:
            st.markdown("🏦 **Saldo Atual em Caixa**")
            st.caption("Disponibilidade real em contas (independe dos filtros abaixo)")
        with sc2:
            cor_livre = "green" if saldo_livre >= 0 else "red"
            st.markdown(f"💵 Dinheiro Livre: :{cor_livre}[**R$ {saldo_livre:,.2f}**]")
            st.caption("Mercado Pago + Carteira")
        with sc3:
            st.markdown(f"🐖 Reservas: :orange[**R$ {saldo_reservas:,.2f}**]")
            st.caption("Cofrinhos e guardados")
        with sc4:
            with st.popover("🔍 Ver Distribuição de Contas", use_container_width=True):
                st.markdown("##### 🏛️ Distribuição Atual por Contas")
                st.markdown("**💵 Dinheiro Livre / Movimentação Imediata:**")
                for c in contas_detalhe:
                    if c.get("incluir_saldo_consolidado") == 1:
                        cor_c = "green" if float(c["saldo_atual"]) >= 0 else "red"
                        st.markdown(f"- **{c['conta_nome']}:** :{cor_c}[R$ {float(c['saldo_atual']):,.2f}]")
                st.divider()
                st.markdown("**🐖 Reservas & Cofrinhos:**")
                for c in contas_detalhe:
                    if c.get("incluir_saldo_consolidado") != 1:
                        st.markdown(f"- **{c['conta_nome']}:** R$ {float(c['saldo_atual']):,.2f}")
                st.caption("ℹ️ Saldos calculados a partir dos marcos iniciais e transações efetivadas.")

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

    # Barra de Filtros com Ordenação por Data
    with st.container(border=True):
        f1, f2, f3, f4, f5 = st.columns([1.3, 1.1, 1.3, 1.4, 1.9])
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
        ordem_data = f4.selectbox(
            "Ordenação",
            options=["⬇️ Mais recentes primeiro", "⬆️ Mais antigos primeiro"],
            index=0,
            label_visibility="collapsed",
            help="Altera a ordem cronológica de exibição das transações."
        )
        busca = f5.text_input(
            "Busca",
            placeholder="🔍 Buscar descrição...",
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

    # ORDENAÇÃO POR DATA
    ordem_asc = (ordem_data == "⬆️ Mais antigos primeiro")
    df_lista = df_lista.sort_values(by=["data", "id"], ascending=[ordem_asc, ordem_asc])

    # Divisão em duas colunas: Extrato à esquerda e Resumo Financeiro à direita
    col_extrato, col_resumo = st.columns([2.6, 1.1], gap="medium")

    with col_extrato:
        datas_unicas = sorted(df_lista["data"].dropna().unique(), reverse=(not ordem_asc))

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

            # Saldo acumulado histórico até o final do dia
            df_ate_data = df[(df["data"] <= data_atual) & (df["pago"] == 1)]
            rec_ate = df_ate_data[df_ate_data["tipo"] == "receita"]["valor"].sum()
            desp_ate = df_ate_data[df_ate_data["tipo"] == "despesa"]["valor"].sum()
            saldo_no_dia = rec_ate - desp_ate

            st.markdown(
                f"<div class='saldo-dia'>Saldo acumulado histórico até este dia: <span>R$ {saldo_no_dia:,.2f}</span></div>",
                unsafe_allow_html=True
            )

    with col_resumo:
        with st.container(border=True):
            st.markdown(f"##### 📌 Balanço do Período ({periodo_texto})")
            
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

            st.markdown(f"#### Resultado Líquido: :blue[R$ {saldo_atual_res:,.2f}]")
            cor_prev = ":green" if saldo_previsto_res >= 0 else ":red"
            st.markdown(f"#### Previsão para Período: {cor_prev}[R$ {saldo_previsto_res:,.2f}]")
            st.caption("ℹ️ **Nota de Integridade:** Este valor representa exclusivamente o resultado operacional do período filtrado. Não deve ser confundido com o saldo bancário disponível em caixa.")


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
    turno_aberto_app = obter_turno_aberto()

    c_titulo, c_b1, c_b2, c_b3, c_b4 = st.columns([2.0, 1.1, 1.2, 1.3, 1.1], vertical_alignment="center")
    with c_titulo:
        st.subheader("🚕 Gestão Operacional & Veículo • Motorista 99 / Uber")
        st.caption("Faturamento das corridas, abastecimentos (Drivvo) e separação entre caixa real e consumo de rodagem.")
    with c_b1:
        if turno_aberto_app:
            if st.button("🏁 Encerrar", use_container_width=True, type="primary"):
                modal_encerrar_turno(turno_aberto_app["id"])
        else:
            if st.button("▶️ Iniciar", use_container_width=True, type="primary"):
                modal_iniciar_turno()
    with c_b2:
        if st.button("⛽ + Abastecer", use_container_width=True, help="Registrar ou vincular abastecimento do veículo (Drivvo)"):
            modal_registrar_abastecimento()
    with c_b3:
        if st.button("🔄 Dinheiro ➔ MP", use_container_width=True, help="Transferir dinheiro das corridas para o Mercado Pago sem duplicar receita"):
            modal_transferencia_dinheiro_mercado_pago()
    with c_b4:
        if st.button("🔧 + Manutenção", use_container_width=True, help="Registrar manutenção do veículo"):
            modal_despesa_veiculo()

    # Se houver turno aberto, exibe banner destacado no topo da Central do Motorista
    if turno_aberto_app:
        h_ini = turno_aberto_app.get("hora_inicio") or "00:00"
        km_ini = float(turno_aberto_app.get("km_inicial") or 0.0)
        dt_ini = turno_aberto_app.get("data") or str(date.today())
        with st.container(border=True):
            col_ab1, col_ab2, col_ab3 = st.columns([2.8, 1.2, 1.0], vertical_alignment="center")
            with col_ab1:
                st.markdown(f"🟢 **Turno 99 Aberto e Ativo no Momento**")
                st.markdown(f"Iniciado às **{h_ini}** em **{dt_ini}** • KM Inicial: **{km_ini:,.0f} KM** • Período: `{turno_aberto_app.get('periodo', '99')}`")
                st.caption("🛡️ *Persistência garantida no SQLite mesmo ao fechar ou recarregar o navegador.*")
            with col_ab2:
                if st.button("🏁 Encerrar Turno Ativo", key="btn_encerrar_banner_mot", use_container_width=True, type="primary"):
                    modal_encerrar_turno(turno_aberto_app["id"])
            with col_ab3:
                if st.button("✏️ Ajustar", key="btn_ajustar_banner_mot", use_container_width=True):
                    modal_editar_turno(turno_aberto_app["id"])

    # Carrega dados de despesas específicas do carro
    conn = conectar()
    df_manut = pd.read_sql_query("SELECT * FROM despesas_veiculo ORDER BY data DESC", conn)
    metricas_comb = saldo_service.obter_metricas_combustivel(conn)
    conn.close()

    # Filtro de Período de Análise
    with st.container(border=True):
        f_per, f_ano = st.columns([3, 1], vertical_alignment="center")
        periodo_analise = f_per.segmented_control(
            "Período de Análise",
            options=["Hoje", "Esta Semana", "Mês Atual (Outubro)", "Últimos 30 Dias", "Ano 2026", "Todo o Histórico"],
            default="Mês Atual (Outubro)",
            label_visibility="collapsed"
        )
        f_ano.caption("📅 Dados sincronizados com o veículo")

    # Filtragem temporal dos turnos
    df_t = df_turnos.copy()
    hoje = date.today()
    hoje_str = hoje.strftime("%Y-%m-%d")

    if not df_t.empty and "data" in df_t.columns:
        df_t["data_dt"] = pd.to_datetime(df_t["data"])
        if periodo_analise == "Hoje":
            df_t = df_t[df_t["data"] == hoje_str]
        elif periodo_analise == "Esta Semana":
            inicio_sem = (hoje - timedelta(days=hoje.weekday())).strftime("%Y-%m-%d")
            fim_sem = (hoje + timedelta(days=6 - hoje.weekday())).strftime("%Y-%m-%d")
            df_t = df_t[(df_t["data"] >= inicio_sem) & (df_t["data"] <= fim_sem)]
        elif periodo_analise == "Mês Atual (Outubro)":
            df_t = df_t[(df_t["data_dt"].dt.month == hoje.month) & (df_t["data_dt"].dt.year == hoje.year)]
        elif periodo_analise == "Últimos 30 Dias":
            limite = hoje - timedelta(days=30)
            df_t = df_t[df_t["data_dt"].dt.date >= limite]
        elif periodo_analise == "Ano 2026":
            df_t = df_t[df_t["data_dt"].dt.year == 2026]

    # Despesas de veículo filtradas pelo período selecionado
    df_m = df_manut.copy()
    if not df_m.empty and "data" in df_m.columns:
        df_m["data_dt"] = pd.to_datetime(df_m["data"])
        if periodo_analise == "Hoje":
            df_m = df_m[df_m["data"] == hoje_str]
        elif periodo_analise == "Esta Semana":
            inicio_sem = (hoje - timedelta(days=hoje.weekday())).strftime("%Y-%m-%d")
            fim_sem = (hoje + timedelta(days=6 - hoje.weekday())).strftime("%Y-%m-%d")
            df_m = df_m[(df_m["data"] >= inicio_sem) & (df_m["data"] <= fim_sem)]
        elif periodo_analise == "Mês Atual (Outubro)":
            df_m = df_m[(df_m["data_dt"].dt.month == hoje.month) & (df_m["data_dt"].dt.year == hoje.year)]
        elif periodo_analise == "Últimos 30 Dias":
            df_m = df_m[df_m["data_dt"].dt.date >= hoje - timedelta(days=30)]
        elif periodo_analise == "Ano 2026":
            df_m = df_m[df_m["data_dt"].dt.year == 2026]
    total_manut = float(df_m["valor"].sum()) if not df_m.empty and "valor" in df_m.columns else 0.0

    # Para métricas de desempenho consolidadas, computa apenas turnos encerrados
    df_t_fechados = df_t[df_t.get("status_turno", "encerrado") != "aberto"] if not df_t.empty else pd.DataFrame()

    # Cálculos operacionais dos turnos encerrados
    total_bruto = float(df_t_fechados["ganho_bruto"].sum()) if not df_t_fechados.empty else 0.0
    total_combustivel = float(df_t_fechados["combustivel"].sum()) if not df_t_fechados.empty else 0.0
    total_horas = float(df_t_fechados["horas"].sum()) if not df_t_fechados.empty else 0.0
    total_km = float(df_t_fechados["km"].sum()) if not df_t_fechados.empty else 0.0

    # Verifica se há turnos com durações pendentes de confirmação (ex: 0.1h ou 0.68h em 20 e 21/10)
    turnos_horas_unconfirmed = []
    if not df_t_fechados.empty and "horas" in df_t_fechados.columns:
        for _, tr_chk in df_t_fechados.iterrows():
            h_chk = float(tr_chk.get("horas") or 0.0)
            if 0 < h_chk < 1.0 or tr_chk.get("data") in ("2026-10-20", "2026-10-21"):
                turnos_horas_unconfirmed.append(tr_chk)
    tem_horas_a_confirmar = len(turnos_horas_unconfirmed) > 0

    # Filtra abastecimentos do veículo no período selecionado
    lista_abast = metricas_comb.get("abastecimentos_veiculo", [])
    abast_periodo_pago = 0.0
    abast_periodo_litros = 0.0
    for ab in lista_abast:
        dt_ab = ab["data"]
        incluir = False
        try:
            dt_obj = datetime.strptime(dt_ab, "%Y-%m-%d").date()
            if periodo_analise == "Hoje":
                incluir = (dt_obj == hoje)
            elif periodo_analise == "Esta Semana":
                incluir = (hoje - timedelta(days=hoje.weekday()) <= dt_obj <= hoje + timedelta(days=6 - hoje.weekday()))
            elif periodo_analise == "Mês Atual (Outubro)":
                incluir = (dt_obj.month == hoje.month and dt_obj.year == hoje.year)
            elif periodo_analise == "Últimos 30 Dias":
                incluir = (dt_obj >= hoje - timedelta(days=30))
            elif periodo_analise == "Ano 2026":
                incluir = (dt_obj.year == 2026)
            else:
                incluir = True
        except Exception:
            incluir = True
        if incluir:
            abast_periodo_pago += ab["valor_pago"]
            if ab.get("litros") is not None:
                abast_periodo_litros += ab["litros"]

    # 1. Resultado de Caixa após Abastecimentos (Fluxo real imediato)
    resultado_caixa = round(total_bruto - abast_periodo_pago, 2)

    # 2. Resultado Operacional Estimado (Eficiência das corridas pelo consumo de km)
    resultado_operacional_est = round(total_bruto - total_combustivel, 2)
    margem_op = (resultado_operacional_est / total_bruto * 100) if total_bruto > 0 else 0.0

    # Rendimento por hora e por km
    bruto_hora = total_bruto / total_horas if total_horas > 0 else 0.0
    liquido_hora = resultado_operacional_est / total_horas if total_horas > 0 else 0.0
    custo_por_km = total_combustivel / total_km if total_km > 0 else 0.0

    # DASHBOARD DE KPIS PRINCIPAIS DO MOTORISTA (SEGREGAÇÃO CONTÁBIL ESTRITA)
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric(
            label="💵 Faturamento Bruto",
            value=f"R$ {total_bruto:,.2f}",
            help="Soma do faturamento apurado nos turnos encerrados (Uber + 99)."
        )
    with k2:
        st.metric(
            label="⛽ Abastecido Real (Caixa)",
            value=f"R$ {abast_periodo_pago:,.2f}",
            delta=f"- R$ {abast_periodo_pago:,.2f}" if abast_periodo_pago > 0 else "R$ 0,00",
            delta_color="inverse",
            help="Total efetivamente desembolsado em postos no período (saída real do caixa/bancos). O abastecimento dura múltiplos turnos sem nova cobrança bancária."
        )
    with k3:
        st.metric(
            label="📏 Consumo Estimado (KM)",
            value=f"R$ {total_combustivel:,.2f}",
            delta=f"{total_km:.0f} km rodados",
            help="Consumo proporcional à quilometragem rodada nos turnos. NÃO debita do caixa nem duplica o abastecimento."
        )
    with k4:
        cor_cx = "normal" if resultado_caixa >= 0 else "inverse"
        st.metric(
            label="💼 Caixa após Abastecer",
            value=f"R$ {resultado_caixa:,.2f}",
            delta="Fluxo de caixa imediato",
            delta_color=cor_cx,
            help="Faturamento bruto menos abastecimentos pagos. Mostra quanto sobrou em dinheiro/bancos após abastecer no período."
        )
    with k5:
        cor_op = "normal" if resultado_operacional_est >= 0 else "inverse"
        delta_k5 = "⚠️ Horas a confirmar" if tem_horas_a_confirmar else f"R$ {liquido_hora:,.2f}/h est."
        delta_cor_k5 = "off" if tem_horas_a_confirmar else cor_op
        help_k5 = (
            "Faturamento bruto menos consumo estimado de rodagem. Mede a eficiência das corridas por km. "
            "Aviso: O cálculo de rendimento por hora (R$/h) está temporariamente pausado porque os turnos de 20 e 21/10 (0,68h e 0,1h) possuem durações aguardando confirmação do motorista."
            if tem_horas_a_confirmar else
            "Faturamento bruto menos consumo estimado de rodagem. Mede a eficiência das corridas por km. NÃO é lucro líquido completo."
        )
        st.metric(
            label="📊 Resultado Op. Estimado",
            value=f"R$ {resultado_operacional_est:,.2f}",
            delta=delta_k5,
            delta_color=delta_cor_k5,
            help=help_k5
        )

    st.info("💡 **Separação Contábil:** O **Resultado de Caixa** reflete o fluxo financeiro imediato (faturamento menos dinheiro gasto em postos). O **Resultado Operacional Estimado** mede a rentabilidade da rodagem pelo desgaste de combustível por KM. Nenhum dos dois constitui lucro líquido completo, pois custos fixos, manutenção e impostos devem ser avaliados separadamente.")

    st.write("")

    # ABAS DA CENTRAL DO MOTORISTA
    tab_turnos, tab_abastecimentos, tab_manutencao, tab_horarios, tab_periodos = st.tabs([
        "🕒 Turnos de Trabalho",
        "⛽ Gestão de Abastecimentos (Drivvo)",
        "🔧 Manutenções & Despesas do Carro",
        "📈 Inteligência de Horários & Rentabilidade",
        "📅 Visão Temporal (Semanal / Mensal)"
    ])

    # ABA 1: TURNOS DE TRABALHO
    with tab_turnos:
        c_top_t1, c_top_t2 = st.columns([3, 1.2], vertical_alignment="center")
        with c_top_t1:
            if not df_t_fechados.empty:
                media_h = total_horas / len(df_t_fechados) if len(df_t_fechados) > 0 else 0
                st.markdown(f"**{len(df_t_fechados)} turno(s) concluído(s)** • Total: **{total_horas:.1f} horas** • **{total_km:,.0f} km** percorridos (Média: **{media_h:.1f}h/turno**).")
            else:
                st.info("Nenhum turno concluído no período.")
        with c_top_t2:
            if st.button("➕ + Lançar Turno", key="btn_novo_t_retroativo", use_container_width=True, help="Lançar turno trabalhado (hoje ou data anterior)"):
                modal_novo_turno()

        if not df_t.empty:
            # Lista de turnos (com status aberto em destaque e suporte a múltiplos turnos por dia)
            for _, t_row in df_t.sort_values(by="data", ascending=False).iterrows():
                is_aberto = (t_row.get("status_turno") == "aberto")
                dt_str = datetime.strptime(t_row["data"], "%Y-%m-%d").strftime("%d/%m/%Y")
                per_t = t_row.get("periodo", "Turno")
                plat_nome = t_row.get("plataforma") or "99"

                if is_aberto:
                    with st.container(border=True):
                        c_ab_card1, c_ab_card2, c_ab_card3 = st.columns([3, 1.5, 0.6], vertical_alignment="center")
                        with c_ab_card1:
                            st.markdown(f"🟢 **TURNO EM ANDAMENTO** • 🗓️ **{dt_str}** • `{per_t}` • `{plat_nome}`")
                            st.caption(f"Início: às **{t_row.get('hora_inicio', '--:--')}** • KM Inicial: **{float(t_row.get('km_inicial') or 0):,.0f} KM**")
                        with c_ab_card2:
                            if st.button("🏁 Encerrar", key=f"enc_row_{t_row['id']}", use_container_width=True, type="primary"):
                                modal_encerrar_turno(t_row["id"])
                        with c_ab_card3:
                            if st.button("✏️", key=f"edit_row_ab_{t_row['id']}", help="Editar horário ou KM inicial"):
                                modal_editar_turno(t_row["id"])
                else:
                    liq_t = float(t_row["ganho_bruto"]) - float(t_row["combustivel"])
                    ganho_h = liq_t / float(t_row["horas"]) if float(t_row["horas"]) > 0 else 0
                    km_ini_row = float(t_row.get("km_inicial") or 0)
                    km_fim_row = float(t_row.get("km_final") or (km_ini_row + float(t_row.get("km") or 0)))
                    din_pix_row = float(t_row.get("ganho_dinheiro_pix") or t_row.get("dinheiro_fisico_recebido") or 0.0)
                    onl_row = float(t_row.get("ganho_online") or max(0.0, float(t_row.get("ganho_bruto") or 0.0) - din_pix_row))

                    # Verifica se há transação bancária vinculada a este turno
                    conn_vt = conectar()
                    cur_vt = conn_vt.cursor()
                    cur_vt.execute("SELECT id, descricao, valor, conta FROM transacoes WHERE turno_id = ?", (t_row['id'],))
                    tr_vinculadas = cur_vt.fetchall()

                    cur_vt.execute("SELECT MAX(data) FROM ajustes_saldo WHERE status = 'ativo'")
                    r_ms = cur_vt.fetchone()
                    marco_corte_saldo = r_ms[0] if r_ms and r_ms[0] else None

                    cur_vt.execute("SELECT MAX(data_corte) FROM motorista_marco_producao WHERE status = 'ativo'")
                    r_mp = cur_vt.fetchone()
                    marco_corte_prod = r_mp[0] if r_mp and r_mp[0] else None
                    conn_vt.close()

                    st_c_db = str(t_row.get("status_conciliacao") or "")
                    eh_incorporado_m = (not tr_vinculadas) and (
                        st_c_db in ("incorporado_marco", "incorporado")
                        or (marco_corte_saldo and str(t_row["data"]) < marco_corte_saldo)
                        or (marco_corte_prod and str(t_row["data"]) <= marco_corte_prod)
                    )

                    with st.container(border=True):
                        col_t1, col_t2, col_t3, col_t4, col_b1, col_b2, col_b3 = st.columns([2.4, 1.8, 1.4, 1.8, 0.6, 0.5, 0.5], vertical_alignment="center")
                        with col_t1:
                            h_num = float(t_row.get("horas") or 0.0)
                            pendente_h = (t_row["data"] in ("2026-10-20", "2026-10-21") or h_num < 1.0)
                            tag_h = " :orange[*(⚠️ Duração a confirmar)*]" if pendente_h else ""
                            st.markdown(f"🗓️ **{dt_str}** • `{per_t}` • `{plat_nome}`{tag_h}")
                            h_ini_txt = str(t_row.get("hora_inicio") or "")
                            h_fim_txt = str(t_row.get("hora_fim") or "")
                            horarios_str = f"({h_ini_txt} às {h_fim_txt})" if h_ini_txt and h_fim_txt else ""
                            km_info_str = f"Hodômetro: {km_ini_row:,.0f} ➔ {km_fim_row:,.0f} ({t_row['km']:.1f} km)" if km_fim_row > 0 else f"{t_row['km']:.1f} km"
                            obs_txt = t_row.get("observacao")
                            aviso_ed = " • *Horário a confirmar; clique em ✏️ para ajustar.*" if pendente_h else ""
                            if obs_txt:
                                st.caption(f"Trabalho: **{t_row['horas']}h** {horarios_str} • {km_info_str}{aviso_ed}\n\n📝 *{obs_txt}*")
                            else:
                                st.caption(f"Trabalho: **{t_row['horas']}h** {horarios_str} • {km_info_str}{aviso_ed}")
                        with col_t2:
                            st.caption("Faturamento Bruto")
                            st.markdown(f"**R$ {t_row['ganho_bruto']:,.2f}**")
                            st.caption(f"Pix/Din: {formatar_moeda_br(din_pix_row)} | App: {formatar_moeda_br(onl_row)}")
                        with col_t3:
                            st.caption("Comb. Consumido")
                            st.markdown(f":red[- R$ {t_row['combustivel']:,.2f}]")
                            st.caption("estimado no turno")
                        with col_t4:
                            st.caption("Status Financeiro")
                            if tr_vinculadas:
                                st.markdown(f":green[**✅ R$ {sum(tv[2] for tv in tr_vinculadas):,.2f}**]")
                                st.caption(f"Extrato: {', '.join(tv[3] for tv in tr_vinculadas)}")
                            elif eh_incorporado_m:
                                st.markdown(":blue[🏛️ Incorporado ao Marco]")
                                st.caption("Contemplado no saldo inicial")
                            else:
                                st.markdown(":orange[⏸️ Pendente]")
                                st.caption("Não contabilizado no banco")
                        with col_b1:
                            if eh_incorporado_m:
                                st.button("🔒", key=f"rec_t_{t_row['id']}", disabled=True, help=f"Turno de {t_row['data']} anterior ao corte: produção já incorporada ao saldo do marco de 21/10/2026.")
                            else:
                                if st.button("💵", key=f"rec_t_{t_row['id']}", help="Contabilizar ou vincular recebimento financeiro deste turno"):
                                    modal_contabilizar_turno(t_row["id"])
                        with col_b2:
                            if st.button("✏️", key=f"edit_t_{t_row['id']}", help="Editar horários, quilometragens ou valores deste turno"):
                                modal_editar_turno(t_row["id"])
                        with col_b3:
                            if st.button("🗑️", key=f"del_t_{t_row['id']}", help="Excluir este turno operacional (preserva extrato bancário)"):
                                excluir_turno(t_row["id"])
                                st.rerun()

    # ABA 2: GESTÃO DE ABASTECIMENTOS (DRIVVO)
    with tab_abastecimentos:
        c_top_ab1, c_top_ab2 = st.columns([3, 1.3], vertical_alignment="center")
        with c_top_ab1:
            st.markdown("##### ⛽ Controle de Abastecimentos do Veículo (Estilo Drivvo)")
            st.caption("Acompanhe hodômetro, litros, preços por litro e cupons de desconto. A Central Financeira permanece como fonte bancária única.")
        with c_top_ab2:
            if st.button("➕ + Novo Abastecimento", key="btn_novo_abast_tab", use_container_width=True, type="primary"):
                modal_registrar_abastecimento()

        # Totais por Dia, Semana e Mês
        with st.container(border=True):
            st.markdown("###### 📊 Totais de Abastecimento Efetivamente Pago vs Consumo dos Turnos")
            c_p1, c_p2, c_p3 = st.columns(3)
            with c_p1:
                st.markdown(f"**Hoje ({hoje.strftime('%d/%m')})**")
                st.markdown(f"⛽ Pago no Posto: :red[**R$ {metricas_comb['hoje']['pago_real']:,.2f}**] ({metricas_comb['hoje']['litros']:.1f}L)")
                st.markdown(f"📏 Consumo Est. Turnos: **R$ {metricas_comb['hoje']['consumo_estimado']:,.2f}** ({metricas_comb['hoje']['km_rodado']:.1f} km)")
                st.caption(f"Caixa após Abast: **R$ {metricas_comb['hoje']['resultado_caixa']:,.2f}** | Op. Est: **R$ {metricas_comb['hoje']['resultado_operacional_estimado']:,.2f}**")
            with c_p2:
                st.markdown(f"**Esta Semana (Seg a Dom)**")
                st.markdown(f"⛽ Pago no Posto: :red[**R$ {metricas_comb['semana']['pago_real']:,.2f}**] ({metricas_comb['semana']['litros']:.1f}L)")
                st.markdown(f"📏 Consumo Est. Turnos: **R$ {metricas_comb['semana']['consumo_estimado']:,.2f}** ({metricas_comb['semana']['km_rodado']:.1f} km)")
                st.caption(f"Caixa após Abast: **R$ {metricas_comb['semana']['resultado_caixa']:,.2f}** | Op. Est: **R$ {metricas_comb['semana']['resultado_operacional_estimado']:,.2f}**")
            with c_p3:
                st.markdown(f"**Este Mês ({hoje.strftime('%B/%Y')})**")
                st.markdown(f"⛽ Pago no Posto: :red[**R$ {metricas_comb['mes']['pago_real']:,.2f}**] ({metricas_comb['mes']['litros']:.1f}L)")
                st.markdown(f"📏 Consumo Est. Turnos: **R$ {metricas_comb['mes']['consumo_estimado']:,.2f}** ({metricas_comb['mes']['km_rodado']:.1f} km)")
                st.caption(f"Caixa após Abast: **R$ {metricas_comb['mes']['resultado_caixa']:,.2f}** | Op. Est: **R$ {metricas_comb['mes']['resultado_operacional_estimado']:,.2f}**")

        # Alerta se houver despesas de combustível sem vínculo
        despesas_avulsas = metricas_comb.get("despesas_sem_vinculo_veiculo", [])
        if despesas_avulsas:
            with st.container(border=True):
                st.warning(f"⚠️ **{len(despesas_avulsas)} despesa(s) de combustível no extrato aguardando dados do veículo (hodômetro / litros):**")
                for dav in despesas_avulsas:
                    c_av1, c_av2, c_av3 = st.columns([3, 2, 1.2], vertical_alignment="center")
                    with c_av1:
                        st.markdown(f"• **{dav['descricao']}** ({dav['data']})")
                        st.caption(f"Extrato: R$ {dav['valor']:,.2f} em {dav['conta']}")
                    with c_av2:
                        st.caption("Pendente de detalhes do hodômetro/litros")
                    with c_av3:
                        if st.button("🔗 Vincular", key=f"btn_vinc_av_{dav['id']}", help="Completar dados de hodômetro e litros sem duplicar despesa"):
                            modal_registrar_abastecimento(vincular_transacao_id=dav["id"])

        st.write("")
        st.markdown("###### 📜 Histórico de Abastecimentos Registrados")
        abasts_lista = metricas_comb.get("abastecimentos_veiculo", [])
        if not abasts_lista:
            st.info("Nenhum abastecimento detalhado registrado ainda. Clique em '+ Novo Abastecimento' acima.")
        else:
            for ab in abasts_lista:
                dt_f = datetime.strptime(ab["data"], "%Y-%m-%d").strftime("%d/%m/%Y") if isinstance(ab["data"], str) else str(ab["data"])
                if ab.get("tanque_cheio") == 1:
                    tanque_badge = "⛽ Tanque Cheio"
                elif ab.get("tanque_cheio") == 0:
                    tanque_badge = "⛽ Parcial"
                else:
                    tanque_badge = "⏳ Tanque a confirmar"
                posto_txt = f" • 📍 {ab['posto']}" if ab.get("posto") else ""
                
                with st.container(border=True):
                    cab1, cab2, cab3, cab4, cab5 = st.columns([2.5, 2.0, 2.0, 2.2, 0.8], vertical_alignment="center")
                    with cab1:
                        st.markdown(f"🗓️ **{dt_f}** • `{ab['combustivel']}` • `{tanque_badge}`{posto_txt}")
                        if ab.get("hodometro") is not None and ab["hodometro"] > 0:
                            st.caption(f"Hodômetro: **{ab['hodometro']:,.0f} KM**")
                        else:
                            st.caption("Hodômetro: :orange[**⏳ Pendente de confirmação**]")
                    with cab2:
                        st.caption("Volume & Preço")
                        if ab.get("litros") is not None and ab["litros"] > 0:
                            st.markdown(f"**{ab['litros']:.2f} Litros**")
                            preco_efetivo = (ab['valor_pago'] / ab['litros'])
                            prc_bomba = ab['preco_litro'] if ab.get('preco_litro') else (ab['valor_bruto'] / ab['litros'])
                            st.caption(f"R$ {prc_bomba:.3f}/L bomba (R$ {preco_efetivo:.3f}/L real)")
                        else:
                            st.markdown(":orange[**⏳ Litros a confirmar**]")
                            st.caption("Preço/L pendente")
                    with cab3:
                        st.caption("Bruto & Desconto")
                        st.markdown(f"Bruto: R$ {ab['valor_bruto']:,.2f}")
                        if ab["desconto"] > 0:
                            st.caption(f"Cupom: :green[- R$ {ab['desconto']:,.2f}]")
                        else:
                            st.caption("Sem desconto")
                    with cab4:
                        st.caption("Efetivamente Pago")
                        st.markdown(f":red[**R$ {ab['valor_pago']:,.2f}**]")
                        st.caption(f"Conta: {ab['conta']}")
                        if ab.get("transacao_id"):
                            st.caption(f"🔗 Despesa Extrato #{ab['transacao_id']}")
                        if ab.get("observacao"):
                            st.caption(f"📝 *{ab['observacao']}*")
                    with cab5:
                        c_ed_ab, c_del_ab = st.columns(2)
                        with c_ed_ab:
                            if st.button("✏️", key=f"edit_ab_{ab['id']}", help="Editar ou confirmar dados reais do veículo (hodômetro e litros)"):
                                modal_registrar_abastecimento(id_abast_editar=ab["id"])
                        with c_del_ab:
                            if st.button("🗑️", key=f"del_ab_{ab['id']}", help="Remover registro de abastecimento"):
                                conn_del = conectar()
                                saldo_service.excluir_abastecimento_veiculo(conn_del, ab["id"], excluir_transacao_financeira=False)
                                conn_del.close()
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
            if tem_horas_a_confirmar:
                st.warning("⚠️ **Estimativa por hora pausada para registros sob auditoria:** Os turnos de 20/10 e 21/10 (0,68h e 0,1h) possuem durações aguardando confirmação. O ranking de R$/h está temporariamente pausado para esses registros para evitar distorções estatísticas.")

            # Considera apenas turnos com horários confirmados (horas >= 1.0 e fora de 20/21/10 a menos que ajustados)
            df_t_conf = df_t[~df_t["data"].isin(["2026-10-20", "2026-10-21"]) & (df_t["horas"] >= 1.0)].copy()
            if df_t_conf.empty:
                st.info("ℹ️ Os turnos existentes estão com horários aguardando confirmação. O ranking comparativo será reativado quando houver turnos com jornada confirmada.")
            else:
                df_t_conf["lucro_t"] = df_t_conf["ganho_bruto"] - df_t_conf["combustivel"]
                por_periodo = df_t_conf.groupby("periodo").agg({
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
    contas = saldo_service.obter_contas(conn, incluir_cofrinhos=True)
    res_consolidado = saldo_service.calcular_saldo_consolidado(conn)
    saldo_livre = float(res_consolidado["saldo_consolidado"])
    saldo_reservas = float(res_consolidado.get("saldo_reservas", 0.0))
    saldo_total_geral = float(res_consolidado.get("saldo_total_com_reservas", saldo_livre))

    col_t1, col_t2, col_t3, col_t4 = st.columns([2.0, 1.1, 1.2, 1.2], vertical_alignment="center")
    with col_t1:
        st.subheader("🏦 Contas & Cofrinhos")
        st.caption(f"Livre: **{formatar_moeda_br(saldo_livre)}** • Reservas: **{formatar_moeda_br(saldo_reservas)}** • Total: **{formatar_moeda_br(saldo_total_geral)}**")
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

    contas_principais = [c for c in contas if c.get("tipo") != "cofrinho"]
    cofrinhos_contas = [c for c in contas if c.get("tipo") == "cofrinho"]

    # 1. Contas Principais Livres (Mercado Pago e Carteira)
    st.markdown("##### 💳 Contas Correntes & Caixa Livre")
    cols_princ = st.columns(max(1, min(len(contas_principais), 3)))
    for idx, c in enumerate(contas_principais):
        res_c = saldo_service.calcular_saldo_conta(conn, c["id"])
        saldo_c = float(res_c["saldo_atual"])
        rec_post = float(res_c["total_receitas_posteriores"])
        desp_post = float(res_c["total_despesas_posteriores"])
        cor_saldo = "#10b981" if saldo_c >= 0 else "#ef4444"

        with cols_princ[idx % len(cols_princ)]:
            with st.container(border=True):
                st.markdown(f"##### 🏦 {c['nome']}")
                st.markdown(f"<div style='font-size:1.6rem; font-weight:700; color:{cor_saldo}; margin: 4px 0;'>R$ {saldo_c:,.2f}</div>", unsafe_allow_html=True)
                
                if res_c["tem_marco"]:
                    data_marco_fmt = datetime.strptime(res_c["marco_data"], "%Y-%m-%d").strftime("%d/%m/%Y")
                    st.caption(f"🎯 **Marco:** R$ {float(res_c['marco_saldo']):,.2f} ({data_marco_fmt})")
                    st.caption(f"📈 Pós-corte: +R$ {rec_post:,.2f} | -R$ {desp_post:,.2f}")
                else:
                    st.caption("ℹ️ Saldo calculado pelo histórico")

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("⚖️ Ajustar", key=f"btn_aj_card_{c['id']}", use_container_width=True):
                        modal_ajustar_saldo(conta_id_pre=c["id"])
                with col_btn2:
                    if st.button("🔁 Transferir", key=f"btn_tr_card_{c['id']}", use_container_width=True):
                        modal_transferencia()

    # 2. Cofrinhos do Mercado Pago como Subcontas Vinculadas
    st.write("")
    st.markdown("##### 🐷 Cofrinhos do Mercado Pago (Subcontas Vinculadas)")
    st.caption("Movimentados por transferências internas: reduzem o saldo livre do Mercado Pago e aumentam o cofrinho sem criar receita/despesa.")

    cur_cof = conn.cursor()
    cur_cof.execute("SELECT id, nome, meta_valor, conta_config_id, incluir_saldo_consolidado FROM cofrinhos ORDER BY id ASC")
    cofs_db = cur_cof.fetchall()

    if cofs_db:
        cols_cof = st.columns(min(len(cofs_db), 3))
        for idx_cof, c_row in enumerate(cofs_db):
            cof_id, cof_nome, cof_meta, cof_cc_id, cof_inc = c_row
            res_cof = saldo_service.calcular_saldo_conta(conn, cof_cc_id) if cof_cc_id else {"saldo_atual": Decimal("0.00")}
            saldo_cof = float(res_cof["saldo_atual"])
            meta_cof_flt = float(cof_meta or 0.0)
            pct_cof = min(1.0, saldo_cof / meta_cof_flt) if meta_cof_flt > 0 else 0.0

            with cols_cof[idx_cof % len(cols_cof)]:
                with st.container(border=True):
                    st.markdown(f"**🐷 {cof_nome}**")
                    st.markdown(f"<div style='font-size:1.35rem; font-weight:700; color:#f59e0b;'>R$ {saldo_cof:,.2f}</div>", unsafe_allow_html=True)
                    if meta_cof_flt > 0:
                        st.progress(pct_cof, text=f"Meta: R$ {meta_cof_flt:,.2f} ({int(pct_cof*100)}%)")
                    else:
                        st.caption("Sem meta financeira definida")

                    if "IPVA" in cof_nome.upper():
                        st.caption("🎯 *Fundo IPVA: Alimenta automaticamente a Missão IPVA.*")

                    col_c_b1, col_c_b2 = st.columns(2)
                    with col_c_b1:
                        if st.button("➕ Guardar", key=f"btn_g_cof_{cof_id}", use_container_width=True, type="primary"):
                            modal_transferir_cofrinho(cofrinho_id_pre=cof_id, tipo_op_pre="guardar")
                    with col_c_b2:
                        if st.button("➖ Resgatar", key=f"btn_r_cof_{cof_id}", use_container_width=True):
                            modal_transferir_cofrinho(cofrinho_id_pre=cof_id, tipo_op_pre="resgatar")

                    inc_atual = (cof_inc == 1)
                    chk_inc = st.checkbox("Incluir no Saldo Consolidado Livre", value=inc_atual, key=f"chk_inc_cof_{cof_id}",
                                          help="Se marcado, este saldo soma no saldo disponível familiar. Se desmarcado, fica apenas nas reservas.")
                    if chk_inc != inc_atual:
                        saldo_service.configurar_saldo_consolidado_cofrinho(conn, cof_id, chk_inc)
                        st.rerun()

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

    tab_missao, tab_cofrinhos, tab_caixa, tab_variaveis, tab_trabalho = st.tabs([
        "🎯 A. Minha Missão",
        "🐷 B. Cofrinhos Mercado Pago",
        "🗓️ C. Caixa da Semana & Mês",
        "🛒 D. Despesas Variáveis",
        "🚕 E. Trabalho & Viabilidade"
    ])

    # =========================================================================
    # TAB A: MINHA MISSÃO (IPVA E RESERVA VIRTUAL)
    # =========================================================================
    with tab_missao:
        missao = planejamento_service.obter_missao_ativa_semana(conn, mes_ano=mes_ano_atual, data_referencia=hoje)
        saldo_info = saldo_service.calcular_saldo_consolidado(conn, data_referencia=hoje)
        saldo_disp = saldo_info["saldo_consolidado"]

        with st.container(border=True):
            st.markdown("#### 🎯 Definir Obrigação como Missão Ativa da Semana")
            st.caption("Vincule o IPVA ou qualquer conta atrasada (ex: Copasa, CEMIG SIM, Fatura Claro) como o desafio ativo que compõe a meta semanal de trabalho.")
            opcoes_mis = planejamento_service.obter_opcoes_missoes_semana(conn, mes_ano_atual)
            t_id_ativa = missao.get("transacao_id")
            lista_tids = [0] + [op["transacao_id"] for op in opcoes_mis]
            mapa_rotulos = {0: "⚪ Nenhuma Missão Extra (Apenas despesas regulares)"}
            idx_m_atual = 0
            for i_m, op in enumerate(opcoes_mis):
                mapa_rotulos[op["transacao_id"]] = op["rotulo"]
                if op["transacao_id"] == t_id_ativa:
                    idx_m_atual = i_m + 1

            col_m_s1, col_m_s2 = st.columns([3.5, 1.2], vertical_alignment="center")
            with col_m_s1:
                sel_m_id = st.selectbox(
                    "Obrigação / Desafio da Semana:",
                    options=lista_tids,
                    index=idx_m_atual,
                    format_func=lambda tid: mapa_rotulos.get(tid, f"Obrigação #{tid}"),
                    key="tab_missao_seletor_ativo"
                )
            with col_m_s2:
                st.write("")
                if st.button("🚀 Ativar nesta Semana", key="btn_ativar_missao_tab", type="primary", use_container_width=True):
                    ok_m, msg_m = planejamento_service.definir_missao_ativa_semana(conn, sel_m_id, mes_ano_atual)
                    if ok_m:
                        st.success(msg_m)
                        st.rerun()
                    else:
                        st.error(msg_m)

        if not missao.get("tem_missao"):
            st.info("ℹ️ Nenhuma missão ativa selecionada para esta semana.")
        else:
            with st.container(border=True):
                col_m_tit, col_m_val = st.columns([2.5, 1.5], vertical_alignment="center")
                with col_m_tit:
                    st.markdown(f"### 🛡️ {missao['titulo']}")
                    dt_venc_fmt = datetime.strptime(missao['data_vencimento'], '%Y-%m-%d').strftime('%d/%m/%Y')
                    st.caption(f"Vencimento Oficial: **{dt_venc_fmt}** • Prazo Restante: **{missao['dias_restantes']} dias corridos** • Status: **{missao.get('status', 'ativa').upper()}**")
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
                st.markdown("#### ⚙️ Configuração & Parâmetros da Missão")
                st.caption(
                    f"Saldo total em contas disponível para reserva: **{formatar_moeda_br(saldo_disp)}**. "
                    "Ajuste valor alvo, data limite, turnos planejados, horas e status operacional da missão."
                )

                with st.form("form_editar_missao_completa_pm"):
                    fm_c1, fm_c2, fm_c3, fm_c4 = st.columns(4)
                    with fm_c1:
                        novo_tit_missao = st.text_input("Título da Missão:", value=str(missao.get("titulo", "Parcelamento IPVA 2025 e 2026")))
                    with fm_c2:
                        novo_val_missao = st.number_input("Valor Alvo (R$):", value=float(missao.get("valor_nominal", 431.11)), step=10.0)
                    with fm_c3:
                        novo_venc_missao = st.date_input(
                            "Data Limite:",
                            value=datetime.strptime(str(missao.get("data_vencimento", "2026-10-29")), "%Y-%m-%d").date()
                        )
                    with fm_c4:
                        lista_prioridades = ["alta", "critica", "media", "baixa"]
                        m_prio = missao.get("prioridade", "alta")
                        idx_prio = lista_prioridades.index(m_prio) if m_prio in lista_prioridades else 0
                        nova_prioridade = st.selectbox("Prioridade:", lista_prioridades, index=idx_prio)

                    fm_c5, fm_c6, fm_c7, fm_c8 = st.columns(4)
                    with fm_c5:
                        novos_turnos = st.number_input("Turnos Planejados:", min_value=1, max_value=31, value=int(missao.get("turnos_planejados", 5)))
                    with fm_c6:
                        novas_horas_turno = st.number_input("Horas por Turno:", min_value=1.0, max_value=12.0, value=float(missao.get("horas_por_turno", 4.0)), step=0.5)
                    with fm_c7:
                        reserva_max = float(max(Decimal("0.00"), saldo_disp))
                        reserva_val_inicial = float(min(saldo_disp, missao.get("valor_reservado", Decimal("0.00"))))
                        nova_reserva = st.number_input(
                            "Reserva Virtual (R$):",
                            min_value=0.0,
                            max_value=reserva_max,
                            value=reserva_val_inicial,
                            step=10.0,
                            format="%.2f",
                            help="Reserva interna do aplicativo. Não pode ultrapassar o saldo bancário disponível."
                        )
                    with fm_c8:
                        lista_status = ["ativa", "pausada", "concluida", "arquivada"]
                        m_status = missao.get("status", "ativa")
                        idx_stat = lista_status.index(m_status) if m_status in lista_status else 0
                        novo_status_missao = st.selectbox("Estado da Missão:", lista_status, index=idx_stat)

                    btn_salvar_missao = st.form_submit_button("💾 Salvar Parâmetros da Missão", use_container_width=True)
                    if btn_salvar_missao:
                        ok_m, msg_m = planejamento_service.atualizar_missao_parametros(
                            conn,
                            transacao_id=int(missao.get("transacao_id", 33)),
                            valor_alvo=Decimal(str(novo_val_missao)),
                            data_limite=novo_venc_missao.strftime("%Y-%m-%d"),
                            prioridade=nova_prioridade,
                            valor_reserva=Decimal(str(nova_reserva)),
                            turnos_planejados=int(novos_turnos),
                            horas_por_turno=float(novas_horas_turno),
                            status=novo_status_missao,
                            titulo=novo_tit_missao
                        )
                        if ok_m:
                            st.success(msg_m)
                            st.rerun()
                        else:
                            st.error(msg_m)

                # Ações rápidas de estado
                st.write("")
                col_act1, col_act2 = st.columns(2)
                with col_act1:
                    if missao.get("status") != "concluida":
                        if st.button("✅ Marcar Missão como Concluída (Quitada)", key="pm_btn_concluir_ipva", use_container_width=True):
                            planejamento_service.atualizar_status_missao(conn, int(missao.get("transacao_id", 33)), "concluida")
                            st.success("Missão IPVA marcada como CONCLUÍDA! Ela não aparecerá mais como pendência ativa.")
                            st.rerun()
                    else:
                        if st.button("▶️ Reativar Missão IPVA", key="pm_btn_reativar_ipva", use_container_width=True):
                            planejamento_service.atualizar_status_missao(conn, int(missao.get("transacao_id", 33)), "ativa")
                            st.success("Missão IPVA reativada com sucesso!")
                            st.rerun()
                with col_act2:
                    st.caption("ℹ️ *A conclusão da missão arquiva a pendência sem gerar transações financeiras fictícias nem alterar o saldo bancário.*")

    # =========================================================================
    # TAB B: COFRINHOS REAIS DO MERCADO PAGO
    # =========================================================================
    with tab_cofrinhos:
        cofrinhos_pm = planejamento_service.obter_cofrinhos(conn)
        tot_cof_pm = sum(float(c["saldo_confirmado"]) for c in cofrinhos_pm)

        st.markdown(f"#### 🐷 Cofrinhos Reais do Mercado Pago (Total Confirmado: R$ {tot_cof_pm:,.2f})")
        st.caption("Gerencie o dinheiro guardado nos cofrinhos do Mercado Pago. O saldo é informado manualmente sem duplicar com a conta corrente principal.")

        # Grid de cofrinhos com movimentação por transferências internas
        if cofrinhos_pm:
            cols_cpm = st.columns(min(3, len(cofrinhos_pm)))
            for idx_c, cof in enumerate(cofrinhos_pm):
                with cols_cpm[idx_c % len(cols_cpm)]:
                    with st.container(border=True):
                        s_conf = float(cof["saldo_confirmado"])
                        meta_c = float(cof["meta_valor"])
                        dt_att = cof["data_atualizacao"] or "Hoje"
                        inc_c = (cof.get("incluir_saldo_consolidado") == 1)

                        st.markdown(f"**🐷 {cof['nome']}**")
                        st.metric("Saldo do Cofrinho", f"R$ {s_conf:,.2f}", help=f"Meta: R$ {meta_c:,.2f}")
                        pct_cof = min(1.0, s_conf / meta_c) if meta_c > 0 else 0.0
                        st.progress(pct_cof, text=f"Meta: R$ {meta_c:,.2f} ({int(pct_cof*100)}%)")

                        if "IPVA" in cof["nome"].upper():
                            st.caption("🎯 *Fundo IPVA: Alimenta automaticamente a Missão IPVA.*")

                        # Botões de Transferência Interna direta
                        cb1, cb2 = st.columns(2)
                        with cb1:
                            if st.button("➕ Guardar", key=f"btn_g_pm_{cof['id']}", use_container_width=True, type="primary"):
                                modal_transferir_cofrinho(cofrinho_id_pre=cof["id"], tipo_op_pre="guardar")
                        with cb2:
                            if st.button("➖ Resgatar", key=f"btn_r_pm_{cof['id']}", use_container_width=True):
                                modal_transferir_cofrinho(cofrinho_id_pre=cof["id"], tipo_op_pre="resgatar")

                        # Configuração se o cofrinho entra no saldo consolidado livre ou fica apenas nas reservas
                        chk_pm = st.checkbox("Incluir no Saldo Consolidado Livre", value=inc_c, key=f"chk_inc_pm_{cof['id']}",
                                            help="Se desmarcado, fica visível apenas no saldo de reservas sem inflar o dinheiro livre.")
                        if chk_pm != inc_c:
                            saldo_service.configurar_saldo_consolidado_cofrinho(conn, cof["id"], chk_pm)
                            st.rerun()

                        st.caption(f"Movimentado em: {dt_att}")
        else:
            st.info("Nenhum cofrinho cadastrado no Mercado Pago.")

        st.write("")
        c_form1, c_form2 = st.columns(2, gap="medium")

        with c_form1:
            with st.container(border=True):
                st.markdown("##### 📝 Atualizar Saldo de Cofrinho")
                st.caption("Informe o saldo real consultado no aplicativo do Mercado Pago.")
                with st.form("form_atualizar_cofrinho_pm"):
                    cof_opcoes = {c["id"]: c["nome"] for c in cofrinhos_pm} if cofrinhos_pm else {}
                    if cof_opcoes:
                        cof_sel_id = st.selectbox("Selecione o Cofrinho:", list(cof_opcoes.keys()), format_func=lambda x: cof_opcoes[x])
                        novo_saldo_cof = st.number_input("Saldo Real no MP (R$):", min_value=0.0, step=10.0, value=0.0)
                        obs_cof = st.text_input("Observação / Data:", value=f"Conferido em {hoje.strftime('%d/%m/%Y')}")
                        btn_salvar_cof = st.form_submit_button("💾 Salvar Saldo Confirmado", use_container_width=True)
                        if btn_salvar_cof:
                            ok_c, msg_c = planejamento_service.atualizar_saldo_cofrinho(
                                conn,
                                cofrinho_id=cof_sel_id,
                                novo_saldo=Decimal(str(novo_saldo_cof)),
                                observacoes=obs_cof
                            )
                            if ok_c:
                                st.success(msg_c)
                                st.rerun()
                            else:
                                st.error(msg_c)
                    else:
                        st.info("Cadastre um cofrinho primeiro no formulário ao lado.")
                        st.form_submit_button("Aguardando cadastro", disabled=True)

        with c_form2:
            with st.container(border=True):
                st.markdown("##### ➕ Cadastrar Novo Cofrinho")
                st.caption("Adicione um novo cofrinho do Mercado Pago para acompanhamento.")
                with st.form("form_novo_cofrinho_pm"):
                    nome_novo_cof = st.text_input("Nome do Cofrinho (ex: Cofrinho Pneus):")
                    meta_novo_cof = st.number_input("Valor Meta (R$):", min_value=0.0, step=50.0, value=0.0)
                    obj_novo_cof = st.text_input("Objetivo:")
                    btn_criar_cof = st.form_submit_button("➕ Criar Cofrinho", use_container_width=True)
                    if btn_criar_cof:
                        if not nome_novo_cof:
                            st.error("Informe o nome do cofrinho.")
                        else:
                            ok_nc, msg_nc = planejamento_service.criar_ou_editar_cofrinho(
                                conn,
                                nome=nome_novo_cof,
                                meta_valor=Decimal(str(meta_novo_cof)),
                                objetivo=obj_novo_cof
                            )
                            if ok_nc:
                                st.success(msg_nc)
                                st.rerun()
                            else:
                                st.error(msg_nc)

        st.info("""
        🛡️ **Garantias Contábeis de Cofrinhos:**
        - **Diferenciação:** Dinheiro nos cofrinhos reais é informado a partir do app do Mercado Pago. Reservas virtuais são metas internas do sistema.
        - **Anti-Duplicação:** Os saldos dos cofrinhos não alteram nem somam automaticamente à conta principal (R$ 8,83).
        - **Sem Presunção:** Nenhum cofrinho presume saldo positivo antes que você confirme o valor real.
        """)


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

    conta_carlos_meta = next((c for c in contas_pl if c["titular"] == "Carlos"), {})
    limite_carlos = float(conta_carlos_meta.get("limite_total") or 300.0)
    disp_manual_carlos = conta_carlos_meta.get("disponibilidade_atual")

    col_acc1, col_acc2, col_acc3 = st.columns([1.5, 1.5, 1.2])
    with col_acc1:
        txt_disp_card = (
            f"Disponibilidade: <strong style='color:#10b981;'>{formatar_moeda_br(disp_manual_carlos)}</strong>"
            if disp_manual_carlos is not None else
            "Disponibilidade: <em style='color:var(--text-muted);'>Sob consulta no app</em>"
        )
        st.markdown(f"""
        <div style="background-color:var(--bg-subcard); padding:12px 16px; border-radius:12px; border-left:4px solid #2563eb;">
            <div style="font-size:0.85rem; color:var(--text-muted); font-weight:600;">👤 Conta Paga Leve — Carlos</div>
            <div style="font-size:1.25rem; font-weight:800; color:var(--text-primary); margin-top:2px;">
                {formatar_moeda_br(aberto_carlos)} <span style="font-size:0.8rem; font-weight:500; color:var(--text-muted);">(em aberto)</span>
            </div>
            <div style="font-size:0.8rem; color:var(--text-muted); margin-top:4px;">
                Limite Ref.: <strong>{formatar_moeda_br(limite_carlos)}</strong> • {txt_disp_card}
            </div>
            <div style="font-size:0.75rem; color:var(--text-muted); margin-top:4px; font-style:italic;">
                * Limite de referência. Compras acumuladas podem exceder este valor.
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("✏️ Atualizar Disponibilidade", key="btn_disp_carlos_pg", use_container_width=True):
            modal_atualizar_disponibilidade_pagaleve("Carlos")

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