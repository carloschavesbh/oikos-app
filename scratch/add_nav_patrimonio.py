# Script para adicionar Patrimonio & Bens na barra lateral e drawer de templates/base.html
with open('templates/base.html', 'r', encoding='utf-8') as f:
    text = f.read()

sidebar_item = """      <!-- 9. PATRIMÔNIO & BENS -->
      <div class="sidebar-nav-item relative group">
        <a href="/patrimonio" class="touch-target flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition {% if active_tab == 'patrimonio' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shadow-sm shadow-emerald-500/10 font-bold{% else %}text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="w-6 h-6 flex items-center justify-center text-lg shrink-0">🏛️</span>
          <span class="sidebar-text truncate">Patrimônio & Bens</span>
        </a>
        <div class="sidebar-tooltip absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-bold shadow-xl border border-slate-700 whitespace-nowrap z-50 pointer-events-none">
          Patrimônio & Bens
        </div>
      </div>
"""

drawer_item = """        <a href="/patrimonio" onclick="toggleMobileDrawer(false)" class="touch-target flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition {% if active_tab == 'patrimonio' %}bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30{% else %}text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60{% endif %}">
          <span class="text-xl">🏛️</span>
          <span>Patrimônio & Bens</span>
        </a>
"""

if 'href="/patrimonio"' not in text:
    # Inserir antes de </nav> na sidebar
    nav_sidebar_end = text.find('</nav>')
    if nav_sidebar_end != -1:
        text = text[:nav_sidebar_end] + sidebar_item + "\n    " + text[nav_sidebar_end:]
        print("Patrimônio adicionado na sidebar!")

    # Inserir no mobile drawer antes de </nav> do drawer
    nav_drawer_end = text.find('</nav>', nav_sidebar_end + len(sidebar_item) + 20)
    if nav_drawer_end != -1:
        text = text[:nav_drawer_end] + drawer_item + "      " + text[nav_drawer_end:]
        print("Patrimônio adicionado no drawer!")

    with open('templates/base.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print("templates/base.html atualizado!")
else:
    print("Item já cadastrado.")

