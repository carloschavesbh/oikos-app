# Script completo para refatorar templates/base.html com Sidebar recolhível e Mobile Drawer
with open("templates/base.html", "r", encoding="utf-8") as f:
    conteudo = f.read()

# 1. CSS para Sidebar e Drawer
novo_css = """    /* --- SIDEBAR RESPONSIVA & RECOLHÍVEL (DESKTOP) --- */
    @media (min-width: 768px) {
      #app-sidebar {
        width: 16rem;
        transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      }
      #main-wrapper {
        padding-left: 16rem;
        transition: padding-left 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      }
      html.sidebar-collapsed #app-sidebar {
        width: 5rem;
      }
      html.sidebar-collapsed #main-wrapper {
        padding-left: 5rem;
      }
      html.sidebar-collapsed .sidebar-text {
        display: none !important;
      }
      html.sidebar-collapsed .sidebar-expanded-only {
        display: none !important;
      }
      html.sidebar-collapsed .sidebar-collapsed-only {
        display: flex !important;
      }
      html:not(.sidebar-collapsed) .sidebar-collapsed-only {
        display: none !important;
      }
      /* Tooltip flutuante ativo no modo recolhido para mouse hover e foco de teclado */
      html.sidebar-collapsed .sidebar-nav-item:hover .sidebar-tooltip,
      html.sidebar-collapsed .sidebar-nav-item:focus-within .sidebar-tooltip {
        opacity: 1 !important;
        visibility: visible !important;
        transform: translateX(0) !important;
      }
      html:not(.sidebar-collapsed) .sidebar-tooltip {
        display: none !important;
      }
    }
    .sidebar-tooltip {
      opacity: 0;
      visibility: hidden;
      transform: translateX(-6px);
      transition: opacity 0.15s ease, transform 0.15s ease, visibility 0.15s;
    }
    @media (max-width: 767px) {
      #app-sidebar {
        display: none !important;
      }
      #main-wrapper {
        padding-left: 0 !important;
      }
    }"""

# Inserir CSS
if "/* --- SIDEBAR RESPONSIVA & RECOLHÍVEL (DESKTOP) --- */" not in conteudo:
    conteudo = conteudo.replace("</style>", novo_css + "\n  </style>")

# 2. Substituir a estrutura do Body (de <body> até o final do conteúdo principal)
# Vamos localizar de `<header class="border-b` até `</main>`
padrao_header_main = re.compile(
    r'<!-- HEADER & NAVBAR GLOBAL -->.*?<!-- CONTEÚDO PRINCIPAL INJETADO -->\s*<main class="flex-grow max-w-6xl w-full mx-auto px-3 sm:px-6 py-4">\s*{% block content %}{% endblock %}\s*</main>',
    re.DOTALL
)

novo_layout_sidebar = """  <!-- ===================================================================== -->
  <!-- [ SIDEBAR RECOLHÍVEL OFICIAL OIKOS (DESKTOP md: >= 768px) ]            -->
  <!-- ===================================================================== -->
  <aside id="app-sidebar" aria-label="Navegação Principal"
         class="fixed top-0 bottom-0 left-0 z-40 bg-white/95 dark:bg-slate-900/95 border-r border-slate-200 dark:border-slate-800/80 backdrop-blur-md flex flex-col justify-between select-none shadow-sm">
    
    <!-- TOPO DA SIDEBAR: LOGO + TOGGLE RECOLHER -->
    <div class="p-3 border-b border-slate-200/80 dark:border-slate-800/80 flex items-center justify-between min-h-[64px]">
      
      <!-- LOGO EXPANDIDO (Horizontal completo + Badge) -->
      <a href="/" class="sidebar-expanded-only flex items-center gap-2 hover:opacity-95 transition truncate" title="Oikos • Início">
        <img src="/static/logo-header.png" alt="Oikos" class="h-8 w-auto object-contain rounded-lg bg-white px-1.5 py-0.5 shadow-sm border border-slate-200/60 dark:border-slate-700/60">
        <span class="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
          {{ OIKOS_EDICAO_NOME | default("Pessoal") }}
        </span>
      </a>

      <!-- LOGO RECOLHIDO (Ícone limpo centralizado) -->
      <a href="/" class="sidebar-collapsed-only mx-auto items-center justify-center hover:opacity-95 transition" title="Oikos • Início">
        <img src="/static/app-icon.png" alt="Oikos" class="h-9 w-9 object-contain rounded-xl bg-white p-1 shadow-sm border border-slate-200/60 dark:border-slate-700/60">
      </a>

      <!-- BOTÃO MINIMIZAR / EXPANDIR (Visível no topo modo expandido) -->
      <button type="button" onclick="toggleSidebar()" aria-label="Recolher ou expandir menu lateral"
              class="sidebar-expanded-only p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              title="Recolher menu lateral">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7"></path>
        </svg>
      </button>
    </div>

    <!-- NAVEGAÇÃO: LISTA DE ITENS -->
    <nav class="flex-1 py-3 px-2 space-y-1 overflow-y-auto custom-scroll" aria-label="Links do Sistema">
      
      <!-- 1. VISÃO GERAL -->
      <div class="sidebar-nav-item relative group">
        <a href="/" class="touch-target flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition {% if active_tab == 'visao_geral' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shadow-sm shadow-emerald-500/10 font-bold{% else %}text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="w-6 h-6 flex items-center justify-center text-lg shrink-0">🏠</span>
          <span class="sidebar-text truncate">Visão Geral</span>
        </a>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Visão Geral
        </div>
      </div>

      <!-- 2. PLANEJAMENTO -->
      <div class="sidebar-nav-item relative group">
        <a href="/planejamento" class="touch-target flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition {% if active_tab == 'planejamento' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shadow-sm shadow-emerald-500/10 font-bold{% else %}text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="w-6 h-6 flex items-center justify-center text-lg shrink-0">🎯</span>
          <span class="sidebar-text truncate">Planejamento</span>
        </a>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Planejamento
        </div>
      </div>

      <!-- 3. LANÇAMENTOS -->
      <div class="sidebar-nav-item relative group">
        <a href="/lancamentos" class="touch-target flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition {% if active_tab == 'lancamentos' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shadow-sm shadow-emerald-500/10 font-bold{% else %}text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="w-6 h-6 flex items-center justify-center text-lg shrink-0">📋</span>
          <span class="sidebar-text truncate">Lançamentos</span>
        </a>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Lançamentos
        </div>
      </div>

      <!-- 4. CONTAS & COFRINHOS -->
      <div class="sidebar-nav-item relative group">
        <a href="/contas" class="touch-target flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition {% if active_tab == 'contas' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shadow-sm shadow-emerald-500/10 font-bold{% else %}text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="w-6 h-6 flex items-center justify-center text-lg shrink-0">🏦</span>
          <span class="sidebar-text truncate">Contas & Cofrinhos</span>
        </a>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Contas & Cofrinhos
        </div>
      </div>

      <!-- 5. CARTÕES -->
      <div class="sidebar-nav-item relative group">
        <a href="/cartoes" class="touch-target flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition {% if active_tab == 'cartoes' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shadow-sm shadow-emerald-500/10 font-bold{% else %}text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="w-6 h-6 flex items-center justify-center text-lg shrink-0">💳</span>
          <span class="sidebar-text truncate">Cartões</span>
        </a>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Cartões
        </div>
      </div>

      <!-- 6. PAGA LEVE -->
      <div class="sidebar-nav-item relative group">
        <a href="/pagaleve" class="touch-target flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition {% if active_tab == 'pagaleve' %}bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 shadow-sm shadow-amber-500/10 font-bold{% else %}text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="w-6 h-6 flex items-center justify-center shrink-0">
            <img src="/imagem/unnamed.png" class="w-5 h-5 rounded-md object-contain" alt="Paga Leve">
          </span>
          <span class="sidebar-text truncate">Paga Leve</span>
        </a>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Paga Leve
        </div>
      </div>

      <!-- 7. OIKOS DRIVE -->
      <div class="sidebar-nav-item relative group">
        <a href="/motorista" class="touch-target flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition {% if active_tab in ['motorista', 'drive'] %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shadow-sm shadow-emerald-500/10 font-bold{% else %}text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="w-6 h-6 flex items-center justify-center text-lg shrink-0">🚗</span>
          <span class="sidebar-text truncate">Oikos Drive</span>
        </a>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Oikos Drive
        </div>
      </div>

      <!-- 8. MISSÕES & METAS -->
      <div class="sidebar-nav-item relative group">
        <a href="/missoes" class="touch-target flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition {% if active_tab == 'missoes' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shadow-sm shadow-emerald-500/10 font-bold{% else %}text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="w-6 h-6 flex items-center justify-center text-lg shrink-0">🎯</span>
          <span class="sidebar-text truncate">Missões & Metas</span>
        </a>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Missões & Metas
        </div>
      </div>

    </nav>

    <!-- RODAPÉ DA SIDEBAR: TEMA + TOGGLE DE EXPANSÃO -->
    <div class="p-2.5 border-t border-slate-200/80 dark:border-slate-800/80 space-y-1">
      
      <!-- BOTÃO ALTERNAR TEMA -->
      <div class="sidebar-nav-item relative group">
        <button id="sidebar-theme-toggle" onclick="toggleTheme()" type="button"
                class="w-full touch-target flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition cursor-pointer">
          <span id="sidebar-theme-icon" class="w-6 h-6 flex items-center justify-center text-base shrink-0">🌙</span>
          <span id="sidebar-theme-text" class="sidebar-text truncate">Modo Noturno</span>
        </button>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Alternar Tema Claro / Noturno
        </div>
      </div>

      <!-- BOTÃO RECOLHER / EXPANDIR SIDEBAR -->
      <div class="sidebar-nav-item relative group">
        <button id="sidebar-toggle-btn" onclick="toggleSidebar()" type="button"
                class="w-full touch-target flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition cursor-pointer">
          <span class="w-6 h-6 flex items-center justify-center text-sm shrink-0">
            <svg id="sidebar-toggle-icon" class="w-4 h-4 transform transition-transform duration-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7"></path>
            </svg>
          </span>
          <span id="sidebar-toggle-text" class="sidebar-text truncate">Recolher Menu</span>
        </button>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Recolher / Expandir Menu
        </div>
      </div>

    </div>
  </aside>

  <!-- ===================================================================== -->
  <!-- [ TOPBAR COMPACTA PARA MOBILE (< 768px) ]                              -->
  <!-- ===================================================================== -->
  <header class="md:hidden border-b border-slate-200 dark:border-slate-800/80 bg-white/95 dark:bg-slate-900/90 backdrop-blur-md sticky top-0 z-30 transition-colors">
    <div class="px-3.5 py-2.5 flex items-center justify-between">
      
      <!-- LADO ESQUERDO: HAMBÚRGUER + LOGO MOBILE -->
      <div class="flex items-center gap-2.5">
        <button type="button" onclick="toggleMobileDrawer(true)" aria-label="Abrir menu de navegação"
                class="touch-target p-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800/80 dark:hover:bg-slate-700 active:scale-95 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700/60 shadow-sm transition flex items-center justify-center cursor-pointer">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
          </svg>
        </button>

        <a href="/" class="flex items-center gap-1.5" title="Oikos • Início">
          <img src="/static/app-icon.png" alt="Oikos" class="h-7 w-7 object-contain rounded-lg bg-white p-0.5 shadow-sm border border-slate-200/60 dark:border-slate-700/60">
          <span class="font-black text-slate-900 dark:text-white text-base tracking-tight">Oikos</span>
          <span class="px-1.5 py-0.2 rounded text-[9px] font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25">
            {{ OIKOS_EDICAO_NOME | default("Pessoal") }}
          </span>
        </a>
      </div>

      <!-- LADO DIREITO: TEMA & ATUALIZAR -->
      <div class="flex items-center gap-1.5">
        <button id="mobile-theme-toggle" onclick="toggleTheme()" type="button" title="Alternar Modo Claro / Noturno"
                class="touch-target p-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800/80 dark:hover:bg-slate-700 active:scale-95 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700/60 shadow-sm transition flex items-center justify-center cursor-pointer">
          <span id="mobile-theme-icon" class="text-sm">🌙</span>
        </button>
        <button onclick="location.reload()" title="Atualizar dados"
                class="touch-target p-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800/80 dark:hover:bg-slate-700 active:scale-95 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700/60 shadow-sm transition flex items-center justify-center cursor-pointer">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
          </svg>
        </button>
      </div>

    </div>
  </header>

  <!-- ===================================================================== -->
  <!-- [ MOBILE DRAWER (MENU LATERAL DESLIZANTE PARA CELULAR) ]               -->
  <!-- ===================================================================== -->
  <div id="mobile-drawer" class="fixed inset-0 z-50 hidden transition-opacity duration-300">
    <!-- Backdrop escuro -->
    <div id="mobile-drawer-backdrop" onclick="toggleMobileDrawer(false)" class="absolute inset-0 bg-black/70 backdrop-blur-sm opacity-0 transition-opacity duration-300"></div>

    <!-- Painel deslizante lateral -->
    <div id="mobile-drawer-panel" class="absolute top-0 bottom-0 left-0 w-72 max-w-[85vw] bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col justify-between transform -translate-x-full transition-transform duration-300 ease-in-out z-10">
      
      <!-- Topo do Drawer -->
      <div class="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <img src="/static/app-icon.png" alt="Oikos" class="h-8 w-8 object-contain rounded-xl bg-white p-1 shadow-sm border border-slate-200/60 dark:border-slate-700/60">
          <div>
            <span class="font-black text-slate-900 dark:text-white text-base tracking-tight leading-none block">Oikos</span>
            <span class="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold uppercase tracking-wider">Edição {{ OIKOS_EDICAO_NOME | default("Pessoal") }}</span>
          </div>
        </div>
        <button type="button" onclick="toggleMobileDrawer(false)" class="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition">
          ✕
        </button>
      </div>

      <!-- Navegação Completa no Mobile -->
      <nav class="flex-1 p-3 space-y-1.5 overflow-y-auto custom-scroll">
        <a href="/" onclick="toggleMobileDrawer(false)" class="touch-target flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition {% if active_tab == 'visao_geral' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30{% else %}text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="text-xl">🏠</span>
          <span>Visão Geral</span>
        </a>
        <a href="/planejamento" onclick="toggleMobileDrawer(false)" class="touch-target flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition {% if active_tab == 'planejamento' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30{% else %}text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="text-xl">🎯</span>
          <span>Planejamento</span>
        </a>
        <a href="/lancamentos" onclick="toggleMobileDrawer(false)" class="touch-target flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition {% if active_tab == 'lancamentos' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30{% else %}text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="text-xl">📋</span>
          <span>Lançamentos</span>
        </a>
        <a href="/contas" onclick="toggleMobileDrawer(false)" class="touch-target flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition {% if active_tab == 'contas' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30{% else %}text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="text-xl">🏦</span>
          <span>Contas & Cofrinhos</span>
        </a>
        <a href="/cartoes" onclick="toggleMobileDrawer(false)" class="touch-target flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition {% if active_tab == 'cartoes' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30{% else %}text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="text-xl">💳</span>
          <span>Cartões</span>
        </a>
        <a href="/pagaleve" onclick="toggleMobileDrawer(false)" class="touch-target flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition {% if active_tab == 'pagaleve' %}bg-amber-500/15 text-amber-600 dark:text-amber-400 font-bold border border-amber-500/30{% else %}text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <img src="/imagem/unnamed.png" class="w-6 h-6 rounded-md object-contain" alt="Paga Leve">
          <span>Paga Leve</span>
        </a>
        <a href="/motorista" onclick="toggleMobileDrawer(false)" class="touch-target flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition {% if active_tab in ['motorista', 'drive'] %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30{% else %}text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="text-xl">🚗</span>
          <span>Oikos Drive</span>
        </a>
        <a href="/missoes" onclick="toggleMobileDrawer(false)" class="touch-target flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition {% if active_tab == 'missoes' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30{% else %}text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="text-xl">🎯</span>
          <span>Missões & Metas</span>
        </a>
      </nav>

      <!-- Rodapé do Drawer -->
      <div class="p-4 border-t border-slate-200 dark:border-slate-800 space-y-2">
        <button type="button" onclick="toggleTheme()" class="w-full touch-target flex items-center justify-between px-3 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/80 text-xs font-semibold text-slate-700 dark:text-slate-200">
          <span class="flex items-center gap-2">
            <span id="drawer-theme-icon">🌙</span>
            <span id="drawer-theme-text">Modo Noturno</span>
          </span>
          <span class="text-[10px] text-slate-400 uppercase font-bold">Alternar</span>
        </button>
      </div>

    </div>
  </div>

  <!-- ===================================================================== -->
  <!-- [ CONTAINER PRINCIPAL COM OFFSET DINÂMICO PARA SIDEBAR ]               -->
  <!-- ===================================================================== -->
  <div id="main-wrapper" class="min-h-screen flex flex-col justify-between w-full">
    
    <!-- CONTEÚDO PRINCIPAL INJETADO -->
    <main class="flex-grow max-w-6xl w-full mx-auto px-3 sm:px-6 py-4 md:py-6">
      {% block content %}{% endblock %}
    </main>

  </div>"""

if padrao_header_main.search(conteudo):
    conteudo = padrao_header_main.sub(novo_layout_sidebar, conteudo)
    print("Layout da Sidebar e Header substituido com sucesso.")
else:
    print("Aviso: padrao_header_main nao encontrado exatamente. Vamos tentar substituição pontual.")

