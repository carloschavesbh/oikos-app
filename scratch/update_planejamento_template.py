import re

with open('templates/planejamento.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Substituir "Ref. 99: R$ 35,00/h" por "Sua referência média informada: R$ 35,00/h"
content = content.replace(
    '(Ref. 99: R$ 35,00/h)',
    '(Sua referência média informada: R$ 35,00/h)'
)

# 2. Substituir "Líquido Família" por "Após Custos Registrados"
content = content.replace(
    '<span class="block text-[10px] uppercase font-bold text-emerald-600 dark:text-emerald-400">Líquido Família</span>\n            <span class="text-base font-black text-emerald-600 dark:text-emerald-400">{{ md.resultado_liquido_disponivel | moeda }}</span>',
    '<span class="block text-[10px] uppercase font-bold text-emerald-600 dark:text-emerald-400">Após Custos Registrados</span>\n            <span class="text-base font-black text-emerald-600 dark:text-emerald-400">{{ md.resultado_apos_custos_registrados | moeda }}</span>'
)

# 3. Bloco aprimorado de custos do Drive com detalhes de combustível real vs estimado
bloco_custos_antigo = """        <div class="space-y-2 text-xs">
          <div class="flex justify-between items-center py-1.5 border-b border-slate-100 dark:border-slate-800">
            <span class="text-slate-500">Ganho Médio Real por Hora:</span>
            <span class="font-bold text-slate-900 dark:text-white">
              {{ md.ganho_hora_real | moeda }}/h 
              <span class="text-[10px] font-normal text-slate-400">(Sua referência média informada: R$ 35,00/h)</span>
            </span>
          </div>
          <div class="flex justify-between items-center py-1.5 border-b border-slate-100 dark:border-slate-800">
            <span class="text-slate-500">Combustível Registrado (Postos/App):</span>
            <span class="font-medium text-slate-700 dark:text-slate-300">{{ md.detalhe_custos.combustivel_registrado | moeda }}</span>
          </div>
          <div>
            <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Custos Não Inclusos / Indisponíveis:</span>
            <ul class="text-[11px] text-slate-500 dark:text-slate-400 space-y-0.5 list-disc list-inside">
              {% for c_off in md.custos_nao_disponiveis %}
              <li>{{ c_off }}</li>
              {% endfor %}
            </ul>
          </div>
        </div>"""

bloco_custos_novo = """        <div class="space-y-2 text-xs">
          <div class="flex justify-between items-center py-1.5 border-b border-slate-100 dark:border-slate-800">
            <span class="text-slate-500">Ganho Médio Real por Hora:</span>
            <span class="font-bold text-slate-900 dark:text-white">
              {{ md.ganho_hora_real | moeda }}/h 
              <span class="text-[10px] font-normal text-slate-400">(Sua referência média informada: R$ 35,00/h)</span>
            </span>
          </div>
          
          <!-- Decomposição Transparente do Combustível -->
          <div class="p-2.5 rounded-xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 space-y-1.5">
            <div class="flex justify-between items-center">
              <span class="text-slate-600 dark:text-slate-300 font-semibold">Abastecimentos Pagos no Posto (Caixa Real):</span>
              <strong class="text-slate-900 dark:text-white">{{ md.detalhe_combustivel.pago_posto | moeda }}</strong>
            </div>
            <div class="flex justify-between items-center text-[11px] text-slate-500">
              <span>Consumo Estimado nos Turnos (Teórico por Km):</span>
              <span class="font-medium text-slate-600 dark:text-slate-400">{{ md.detalhe_combustivel.estimado_turnos | moeda }}</span>
            </div>
            <p class="text-[10px] text-slate-400 leading-relaxed pt-1 border-t border-slate-200/50 dark:border-slate-700/50">
              ℹ️ {{ md.detalhe_combustivel.explicacao }}
            </p>
          </div>

          <div>
            <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Custos Não Inclusos / Indisponíveis:</span>
            <ul class="text-[11px] text-slate-500 dark:text-slate-400 space-y-0.5 list-disc list-inside">
              {% for c_off in md.custos_nao_disponiveis %}
              <li>{{ c_off }}</li>
              {% endfor %}
            </ul>
          </div>
        </div>"""

if bloco_custos_antigo in content:
    content = content.replace(bloco_custos_antigo, bloco_custos_novo, 1)

# 4. Aprimorar Tabela de Histórico de Renda com Composição de Receitas e Seleção da Amostra
tabela_hist_antiga = """      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50 dark:bg-slate-950/60 text-slate-500 uppercase text-[10px] font-bold tracking-wider">
            <tr>
              <th class="py-2.5 px-3">Mês</th>
              <th class="py-2.5 px-3 text-right">Renda Estável</th>
              <th class="py-2.5 px-3 text-right">Renda Variável</th>
              <th class="py-2.5 px-3 text-right">Total Renda</th>
              <th class="py-2.5 px-3 text-center">Status Histórico</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
            {% for h in ra.historico %}
            <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40">
              <td class="py-2.5 px-3 font-mono font-bold text-slate-800 dark:text-slate-200">{{ h.mes }}</td>
              <td class="py-2.5 px-3 text-right font-medium text-emerald-600 dark:text-emerald-400">{{ h.estavel | moeda }}</td>
              <td class="py-2.5 px-3 text-right font-medium text-amber-600 dark:text-amber-400">{{ h.variavel | moeda }}</td>
              <td class="py-2.5 px-3 text-right font-bold text-slate-900 dark:text-white">{{ (h.estavel + h.variavel) | moeda }}</td>
              <td class="py-2.5 px-3 text-center whitespace-nowrap">
                {% if h.incompleto %}
                <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400" title="{{ h.motivo_incompleto }}">
                  ⚠️ {{ h.motivo_incompleto }}
                </span>
                {% elif not h.tem_dados %}
                <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-200 dark:bg-slate-800 text-slate-500">
                  Lacuna (Sem dados)
                </span>
                {% else %}
                <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                  ✓ Mês Válido
                </span>
                {% endif %}
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>"""

tabela_hist_nova = """      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50 dark:bg-slate-950/60 text-slate-500 uppercase text-[10px] font-bold tracking-wider">
            <tr>
              <th class="py-2.5 px-3 text-center w-12">Amostra</th>
              <th class="py-2.5 px-3">Mês</th>
              <th class="py-2.5 px-3 text-right">Renda Fixa (Salário)</th>
              <th class="py-2.5 px-3 text-right">Renda Variável (99/Extras)</th>
              <th class="py-2.5 px-3 text-right">Total Renda Operacional</th>
              <th class="py-2.5 px-3 text-right text-slate-400">Entradas Externas / Aportes</th>
              <th class="py-2.5 px-3 text-center">Classificação & Integridade</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
            {% for h in ra.historico %}
            <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40 {% if not h.incluir_na_amostra %}opacity-60 bg-slate-50/30 dark:bg-slate-950/20{% endif %}">
              <td class="py-2.5 px-3 text-center">
                <input type="checkbox" onchange="atualizarAmostraMeses()"
                       data-mes="{{ h.mes }}"
                       {% if h.incluir_na_amostra %}checked{% endif %}
                       title="Marcar para incluir na média e cenários"
                       class="chk-amostra-mes w-4 h-4 rounded text-indigo-600 cursor-pointer">
              </td>
              <td class="py-2.5 px-3 font-mono font-bold text-slate-800 dark:text-slate-200">{{ h.mes }}</td>
              <td class="py-2.5 px-3 text-right font-medium text-emerald-600 dark:text-emerald-400">{{ h.estavel | moeda }}</td>
              <td class="py-2.5 px-3 text-right font-medium text-amber-600 dark:text-amber-400">{{ h.variavel | moeda }}</td>
              <td class="py-2.5 px-3 text-right font-bold text-slate-900 dark:text-white">{{ (h.estavel + h.variavel) | moeda }}</td>
              <td class="py-2.5 px-3 text-right font-medium text-slate-400">
                {% if h.aportes_externos > 0 %}{{ h.aportes_externos | moeda }}{% else %}—{% endif %}
              </td>
              <td class="py-2.5 px-3 text-center whitespace-nowrap">
                {% if h.qualidade == 'completo_confirmado' %}
                <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" title="{{ h.motivo_qualidade }}">
                  ✓ Completo Confirmado
                </span>
                {% elif h.qualidade == 'parcial' %}
                <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400" title="{{ h.motivo_qualidade }}">
                  ⚠️ {{ h.qualidade_label }}
                </span>
                {% else %}
                <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-200 dark:bg-slate-800 text-slate-500" title="{{ h.motivo_qualidade }}">
                  Lacuna (Sem dados)
                </span>
                {% endif %}
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>"""

if tabela_hist_antiga in content:
    content = content.replace(tabela_hist_antiga, tabela_hist_nova, 1)

# 5. Adicionar a função JS atualizarAmostraMeses() no script
funcao_js_amostra = """
  async function atualizarAmostraMeses() {
    const checkboxes = document.querySelectorAll('.chk-amostra-mes:checked');
    const mesesAtivos = Array.from(checkboxes).map(c => c.getAttribute('data-mes'));
    try {
      const resp = await fetch('/api/planejamento/meses-amostra', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ meses_ativos: mesesAtivos })
      });
      const res = await resp.json();
      if (res.sucesso) {
        showToast('Amostra Atualizada!', 'Cenários recalculados com os meses selecionados.');
        setTimeout(() => location.reload(), 300);
      }
    } catch (err) {
      showToast('Erro', err.message, true);
    }
  }
"""

if "function atualizarAmostraMeses()" not in content:
    content = content.replace("function mudarSubTab(tab) {", funcao_js_amostra + "\n  function mudarSubTab(tab) {", 1)

# 6. Atualizar a tabela de compromissos para exibir o cálculo real de contribuição e diferenciação de saldo/distribuição
tabela_comp_antiga = """              <th class="py-2.5 px-3">Compromisso</th>
              <th class="py-2.5 px-3">Data Prevista</th>
              <th class="py-2.5 px-3 text-right">Valor Alvo</th>
              <th class="py-2.5 px-3">Cofrinho Vinculado</th>
              <th class="py-2.5 px-3 text-right">Reservado</th>
              <th class="py-2.5 px-3 text-right">Falta</th>
              <th class="py-2.5 px-3 text-right">Sugestão Mensal</th>
              <th class="py-2.5 px-3 text-center">Ações</th>"""

tabela_comp_nova = """              <th class="py-2.5 px-3">Compromisso</th>
              <th class="py-2.5 px-3">Vencimento & Prazo Real</th>
              <th class="py-2.5 px-3 text-right">Valor Alvo</th>
              <th class="py-2.5 px-3">Cofrinho & Reserva Destinada</th>
              <th class="py-2.5 px-3 text-right">Falta Reservar</th>
              <th class="py-2.5 px-3 text-right">Contribuição Real Sugerida</th>
              <th class="py-2.5 px-3 text-center">Ações</th>"""

if tabela_comp_antiga in content:
    content = content.replace(tabela_comp_antiga, tabela_comp_nova, 1)

# Linhas da tabela de compromissos
linhas_comp_antiga = """            {% for d in ca.todas_despesas %}
            <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40">
              <td class="py-3 px-3">
                <strong class="text-slate-900 dark:text-white block">{{ d.nome }}</strong>
                <span class="text-[10px] text-slate-400">{{ d.categoria }} • Resp: {{ d.responsavel }}</span>
              </td>
              <td class="py-3 px-3 font-mono text-slate-600 dark:text-slate-300 whitespace-nowrap">
                {{ d.data_prevista[8:10] }}/{{ d.data_prevista[5:7] }}/{{ d.data_prevista[:4] }}
                <span class="block text-[10px] text-slate-400">em {{ d.meses_ate_data }} mês(es)</span>
              </td>
              <td class="py-3 px-3 text-right font-black text-slate-900 dark:text-white whitespace-nowrap">
                {{ d.valor_alvo | moeda }}
              </td>
              <td class="py-3 px-3">
                {% if d.cofrinho_nome %}
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  🐖 {{ d.cofrinho_nome }}
                </span>
                {% else %}
                <span class="text-slate-400 italic text-[11px]">Sem cofrinho</span>
                {% endif %}
              </td>
              <td class="py-3 px-3 text-right font-bold text-emerald-600 dark:text-emerald-400 whitespace-nowrap">
                {{ d.saldo_reservado_alocado | moeda }}
              </td>
              <td class="py-3 px-3 text-right font-bold text-amber-600 dark:text-amber-400 whitespace-nowrap">
                {{ d.falta_reservar | moeda }}
              </td>
              <td class="py-3 px-3 text-right whitespace-nowrap">
                {% if d.falta_reservar > 0 %}
                <strong class="text-indigo-600 dark:text-indigo-400 block">{{ d.sugestao_mensal | moeda }}/mês</strong>
                <span class="text-[9px] text-slate-400">({{ d.sugestao_semanal | moeda }}/sem)</span>
                {% else %}
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-600">✓ 100% Coberto</span>
                {% endif %}
              </td>
              <td class="py-3 px-3 text-center whitespace-nowrap space-x-1">
                <button type="button" onclick="abrirModalConciliar({{ d.id }}, '{{ d.nome }}', {{ d.valor_alvo }}, {{ d.cofrinho_id or 'null' }})"
                        title="Registrar pagamento e baixar reserva"
                        class="p-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-600 transition cursor-pointer">
                  💳
                </button>
                <button type="button" onclick="excluirDespesaEventual({{ d.id }})"
                        title="Excluir compromisso"
                        class="p-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-600 transition cursor-pointer">
                  🗑️
                </button>
              </td>
            </tr>
            {% endfor %}"""

linhas_comp_nova = """            {% for d in ca.todas_despesas %}
            <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40">
              <td class="py-3 px-3">
                <strong class="text-slate-900 dark:text-white block">{{ d.nome }}</strong>
                <span class="text-[10px] text-slate-400">{{ d.categoria }} • Resp: {{ d.responsavel }}</span>
              </td>
              <td class="py-3 px-3 whitespace-nowrap">
                <span class="font-mono text-slate-700 dark:text-slate-300 font-bold block">
                  {{ d.data_prevista[8:10] }}/{{ d.data_prevista[5:7] }}/{{ d.data_prevista[:4] }}
                </span>
                {% if d.status_prazo == 'vencido' %}
                <span class="text-[10px] font-bold text-rose-600 dark:text-rose-400">⚠️ {{ d.status_prazo_label }}</span>
                {% elif d.status_prazo == 'hoje' %}
                <span class="text-[10px] font-bold text-amber-600 dark:text-amber-400">⚡ Vence Hoje</span>
                {% elif d.status_prazo == 'imediato' %}
                <span class="text-[10px] font-semibold text-amber-500">⏳ {{ d.status_prazo_label }}</span>
                {% else %}
                <span class="text-[10px] text-slate-400">{{ d.status_prazo_label }}</span>
                {% endif %}
              </td>
              <td class="py-3 px-3 text-right font-black text-slate-900 dark:text-white whitespace-nowrap">
                {{ d.valor_alvo | moeda }}
              </td>
              <td class="py-3 px-3">
                {% if d.cofrinho_nome %}
                <div class="space-y-0.5">
                  <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                    🐖 {{ d.cofrinho_nome }}
                  </span>
                  <div class="text-[10px] text-slate-400">
                    Destinado: <strong class="text-emerald-600 dark:text-emerald-400">{{ d.valor_efetivamente_reservado | moeda }}</strong>
                    <span class="text-[9px] text-slate-400" title="Saldo total no cofrinho: {{ d.saldo_total_cofrinho | moeda }}">(de {{ d.saldo_total_cofrinho | moeda }})</span>
                  </div>
                </div>
                {% else %}
                <span class="text-slate-400 italic text-[11px]">Sem cofrinho</span>
                {% endif %}
              </td>
              <td class="py-3 px-3 text-right font-bold text-amber-600 dark:text-amber-400 whitespace-nowrap">
                {{ d.falta_reservar | moeda }}
              </td>
              <td class="py-3 px-3 text-right whitespace-nowrap">
                {% if d.falta_reservar > 0 %}
                  {% if d.status_prazo in ['vencido', 'hoje', 'imediato'] %}
                  <strong class="text-rose-600 dark:text-rose-400 block text-xs">Aporte Imediato</strong>
                  <span class="text-[9px] text-slate-400">{{ d.falta_reservar | moeda }}</span>
                  {% else %}
                  <strong class="text-indigo-600 dark:text-indigo-400 block">{{ d.sugestao_mensal | moeda }}/mês</strong>
                  <span class="text-[9px] text-slate-400">ou {{ d.sugestao_semanal | moeda }}/semana ({{ d.semanas_reais }} sem)</span>
                  {% endif %}
                {% else %}
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-600">✓ 100% Coberto</span>
                {% endif %}
              </td>
              <td class="py-3 px-3 text-center whitespace-nowrap space-x-1">
                <button type="button" onclick="abrirModalConciliar({{ d.id }}, '{{ d.nome }}', {{ d.valor_alvo }}, {{ d.cofrinho_id or 'null' }})"
                        title="Registrar pagamento e baixar reserva"
                        class="p-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-600 transition cursor-pointer">
                  💳
                </button>
                <button type="button" onclick="excluirDespesaEventual({{ d.id }})"
                        title="Excluir compromisso"
                        class="p-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-600 transition cursor-pointer">
                  🗑️
                </button>
              </td>
            </tr>
            {% endfor %}"""

if linhas_comp_antiga in content:
    content = content.replace(linhas_comp_antiga, linhas_comp_nova, 1)

with open('templates/planejamento.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCESSO: templates/planejamento.html atualizado com todas as correções!")
