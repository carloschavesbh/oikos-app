import sys

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

card_anual = """
      <!-- CARD RESUMO COMPACTO DE DESPESAS ANUAIS E EVENTUAIS -->
      {% if d.resumo_despesas_anuais %}
      {% set ra = d.resumo_despesas_anuais %}
      <div class="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm space-y-3">
        <div class="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
          <div class="flex items-center gap-2">
            <span class="text-base">📅</span>
            <h2 class="text-xs sm:text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wider">Despesas Anuais & Eventuais</h2>
          </div>
          <a href="/planejamento#calendario-anual" class="text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 font-bold transition">Calendário ➔</a>
        </div>

        <div>
          <div class="flex items-baseline justify-between">
            <span class="text-xs text-slate-500 dark:text-slate-400">Total Previsto (12 Meses)</span>
            <span class="text-lg font-black text-slate-900 dark:text-white">{{ ra.total_previsto | moeda }}</span>
          </div>

          <div class="grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-slate-100 dark:border-slate-800/80 text-[11px]">
            <div>
              <span class="text-slate-400 block truncate">Reservado:</span>
              <strong class="text-emerald-600 dark:text-emerald-400 font-semibold">{{ ra.total_reservado | moeda }} ({{ ra.taxa_cobertura }}%)</strong>
            </div>
            <div>
              <span class="text-slate-400 block truncate">Falta Reservar:</span>
              <strong class="text-amber-600 dark:text-amber-400 font-semibold">{{ ra.total_falta | moeda }}</strong>
            </div>
          </div>

          {% if ra.proximas %}
          <div class="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800/80 space-y-1.5 text-[11px]">
            <span class="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">Próximos Compromissos</span>
            {% for p in ra.proximas %}
            <div class="flex items-center justify-between text-slate-700 dark:text-slate-300">
              <span class="truncate pr-2 font-medium">{{ p.nome }} <span class="text-[10px] text-slate-400">({{ p.data_prevista[8:10] }}/{{ p.data_prevista[5:7] }})</span></span>
              <span class="font-bold shrink-0 text-slate-900 dark:text-white">{{ p.valor_alvo | moeda }}</span>
            </div>
            {% endfor %}
          </div>
          {% endif %}
        </div>
      </div>
      {% endif %}
"""

# Inserir após o fechamento do bloco de patrimônio
ancora = "<!-- CARD RESUMO COMPACTO DE PATRIMÔNIO -->"
idx_ancora = content.find(ancora)
assert idx_ancora != -1, "ancora patrimônio não encontrada em index.html"

# Achar o próximo {% endif %} após ancora
idx_endif = content.find("{% endif %}", idx_ancora)
assert idx_endif != -1, "{% endif %} não encontrado após ancora"

ponto_insercao = idx_endif + len("{% endif %}")
content = content[:ponto_insercao] + "\n" + card_anual + content[ponto_insercao:]

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCESSO: index.html atualizado com card compacto de despesas anuais e eventuais!")
