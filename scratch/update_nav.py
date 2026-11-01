import sys

with open('templates/base.html', 'r', encoding='utf-8') as f:
    content = f.read()

sidebar_old = """          <!-- 9. PATRIMÔNIO & BENS -->
      <div class="sidebar-nav-item relative group">
        <a href="/patrimonio" class="touch-target flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition {% if active_tab == 'patrimonio' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shadow-sm shadow-emerald-500/10 font-bold{% else %}text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="w-6 h-6 flex items-center justify-center text-lg shrink-0">🏛️</span>
          <span class="sidebar-text truncate">Patrimônio & Bens</span>
        </a>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Patrimônio & Bens
        </div>
      </div>"""

sidebar_new = """          <!-- 9. MEU PATRIMÔNIO -->
      <div class="sidebar-nav-item relative group">
        <a href="/patrimonio" class="touch-target flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition {% if active_tab == 'patrimonio' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shadow-sm shadow-emerald-500/10 font-bold{% else %}text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="w-6 h-6 flex items-center justify-center text-lg shrink-0">💎</span>
          <span class="sidebar-text truncate">Meu Patrimônio</span>
        </a>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Meu Patrimônio
        </div>
      </div>

      <!-- 10. MEUS BENS -->
      <div class="sidebar-nav-item relative group">
        <a href="/bens" class="touch-target flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition {% if active_tab == 'bens' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shadow-sm shadow-emerald-500/10 font-bold{% else %}text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="w-6 h-6 flex items-center justify-center text-lg shrink-0">📦</span>
          <span class="sidebar-text truncate">Meus Bens</span>
        </a>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Meus Bens
        </div>
      </div>"""

drawer_old = """        <a href="/patrimonio" onclick="toggleMobileDrawer(false)" class="touch-target flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition {% if active_tab == 'patrimonio' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30{% else %}text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="text-xl">🏛️</span>
          <span>Patrimônio & Bens</span>
        </a>"""

drawer_new = """        <a href="/patrimonio" onclick="toggleMobileDrawer(false)" class="touch-target flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition {% if active_tab == 'patrimonio' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30{% else %}text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="text-xl">💎</span>
          <span>Meu Patrimônio</span>
        </a>
        <a href="/bens" onclick="toggleMobileDrawer(false)" class="touch-target flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition {% if active_tab == 'bens' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30{% else %}text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="text-xl">📦</span>
          <span>Meus Bens</span>
        </a>"""

if sidebar_old not in content:
    print("ERRO: sidebar_old não encontrado!")
    sys.exit(1)

if drawer_old not in content:
    print("ERRO: drawer_old não encontrado!")
    sys.exit(1)

content = content.replace(sidebar_old, sidebar_new, 1)
content = content.replace(drawer_old, drawer_new, 1)

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCESSO: base.html atualizado com entradas separadas para Meu Patrimônio e Meus Bens!")
