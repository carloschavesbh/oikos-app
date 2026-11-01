import sys

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = """      <!-- CARD RESUMO COMPACTO DE PATRIMÔNIO -->
      {% if d.resumo_patrimonio %}
      {% set rp = d.resumo_patrimonio %}
      <div class="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm">
        <div class="flex items-center justify-between pb-2.5 border-b border-slate-100 dark:border-slate-800">
          <div class="flex items-center gap-2">
            <span class="text-base">🏛️</span>
            <h2 class="text-xs sm:text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wider">Patrimônio Líquido</h2>
          </div>
          <a href="/patrimonio" class="text-xs text-emerald-600 dark:text-emerald-400 hover:text-emerald-500 font-bold">Ver bens ➔</a>
        </div>

        <div class="mt-3">
          <div class="flex items-baseline justify-between">
            <span class="text-xs text-slate-500 dark:text-slate-400">Total Consolidado</span>
            <span class="text-xl font-black text-emerald-600 dark:text-emerald-400">{{ rp.patrimonio_liquido | moeda }}</span>
          </div>

          <div class="grid grid-cols-2 gap-2 mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800/80 text-[11px]">
            <div>
              <span class="text-slate-400 block">Ativos Físicos:</span>
              <strong class="text-slate-800 dark:text-slate-200">{{ rp.total_bens | moeda }}</strong>
            </div>
            <div>
              <span class="text-slate-400 block">Saldo em Caixa:</span>
              <strong class="text-emerald-600 dark:text-emerald-400">{{ rp.saldo_caixa | moeda }}</strong>
            </div>
          </div>
        </div>
      </div>
      {% endif %}"""

new_block = """      <!-- CARD RESUMO COMPACTO DE PATRIMÔNIO -->
      {% if d.resumo_patrimonio %}
      {% set rp = d.resumo_patrimonio %}
      <div class="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm space-y-3">
        <div class="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
          <div class="flex items-center gap-2">
            <span class="text-base">💎</span>
            <h2 class="text-xs sm:text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wider">Patrimônio Líquido</h2>
          </div>
          <div class="flex items-center gap-2 text-xs">
            <a href="/bens" class="text-slate-500 hover:text-emerald-500 dark:text-slate-400 transition" title="Ver Meus Bens">📦 Bens ({{ rp.qtd_bens }})</a>
            <span class="text-slate-300 dark:text-slate-700">|</span>
            <a href="/patrimonio" class="text-emerald-600 dark:text-emerald-400 hover:text-emerald-500 font-bold transition">Balanço ➔</a>
          </div>
        </div>

        <div>
          <div class="flex items-baseline justify-between">
            <span class="text-xs text-slate-500 dark:text-slate-400">Total Consolidado (Ativos - Passivos)</span>
            <span class="text-xl font-black {% if rp.patrimonio_liquido >= 0 %}text-emerald-600 dark:text-emerald-400{% else %}text-rose-600 dark:text-rose-400{% endif %}">
              {{ rp.patrimonio_liquido | moeda }}
            </span>
          </div>

          <div class="grid grid-cols-3 gap-2 mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800/80 text-[11px]">
            <div>
              <span class="text-slate-400 block truncate">📦 Bens:</span>
              <strong class="text-slate-800 dark:text-slate-200 font-semibold">{{ rp.total_bens | moeda }}</strong>
            </div>
            <div>
              <span class="text-slate-400 block truncate">🏦 Caixa:</span>
              <strong class="text-emerald-600 dark:text-emerald-400 font-semibold">{{ rp.saldo_caixa | moeda }}</strong>
            </div>
            <div>
              <span class="text-slate-400 block truncate" title="Parcelas nominais conhecidas de cartões e compras">💳 Obrigações:</span>
              <strong class="text-rose-600 dark:text-rose-400 font-semibold">-{{ rp.total_passivos | moeda }}</strong>
            </div>
          </div>
        </div>
      </div>
      {% endif %}"""

if old_block not in content:
    print("ERRO: old_block não encontrado em index.html!")
    sys.exit(1)

content = content.replace(old_block, new_block, 1)

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCESSO: index.html atualizado com card de resumo patrimonial linkando para /patrimonio e /bens!")
