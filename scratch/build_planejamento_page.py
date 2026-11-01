import re

with open('templates/planejamento.html', 'r', encoding='utf-8') as f:
    orig = f.read()

# Identificar o ponto após o cabeçalho de mês
# O cabeçalho termina com </div> seguido de <!-- SEÇÃO 1: INDICADOR DE SAÚDE FINANCEIRA
ancora_cabecalho = '<!-- SEÇÃO 1: INDICADOR DE SAÚDE FINANCEIRA'
assert ancora_cabecalho in orig, "ancora_cabecalho não encontrada"

idx_cab = orig.find(ancora_cabecalho)

# Navegador de Abas
barra_subtabs = """
  <!-- SUB-NAVEGAÇÃO: 3 PILARES DO PLANEJAMENTO INTELIGENTE -->
  <div class="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2 overflow-x-auto">
    <button type="button" onclick="mudarSubTab('orcamento')" id="btn-tab-orcamento"
            class="tab-btn px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold flex items-center gap-2 transition cursor-pointer bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shadow-xs">
      <span>🎯</span> <span>Orçamento & Saúde</span>
    </button>
    <button type="button" onclick="mudarSubTab('renda')" id="btn-tab-renda"
            class="tab-btn px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold flex items-center gap-2 transition cursor-pointer text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60">
      <span>📈</span> <span>Renda Familiar & Cenários</span>
      <span class="px-1.5 py-0.2 rounded-full text-[10px] font-black bg-indigo-500/20 text-indigo-600 dark:text-indigo-400">Novo</span>
    </button>
    <button type="button" onclick="mudarSubTab('calendario')" id="btn-tab-calendario"
            class="tab-btn px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold flex items-center gap-2 transition cursor-pointer text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60">
      <span>📅</span> <span>Calendário Anual (12 Meses)</span>
      <span class="px-1.5 py-0.2 rounded-full text-[10px] font-black bg-amber-500/20 text-amber-600 dark:text-amber-400">12m</span>
    </button>
  </div>

  <!-- CONTAINER TAB 1: ORÇAMENTO & SAÚDE FINANCEIRA -->
  <div id="tab-conteudo-orcamento" class="space-y-5">
"""

# Conteúdo das novas Tabs: Renda & Calendário
novo_conteudo_tabs = """
  </div>
  <!-- FIM CONTAINER TAB 1 -->

  <!-- ===================================================================== -->
  <!-- CONTAINER TAB 2: RENDA FAMILIAR & CENÁRIOS DE SENSIBILIDADE           -->
  <!-- ===================================================================== -->
  <div id="tab-conteudo-renda" class="space-y-5 hidden">
    
    {% if renda_analise and comp_cenarios %}
    {% set ra = renda_analise %}
    {% set cc = comp_cenarios %}
    {% set cen = ra.cenarios %}

    <!-- CARDS DE DESTAQUE: RENDA FAMILIAR & CENÁRIOS -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
      
      <!-- CARD 1: RENDA TOTAL HABITUAL -->
      <div class="bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs relative overflow-hidden">
        <div class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 font-semibold mb-1">
          <span>Renda Habitual Estimada</span>
          <span class="px-2 py-0.5 rounded text-[10px] font-extrabold bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">Projetada</span>
        </div>
        <div class="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
          {{ cc.cenarios.habitual.renda_total | moeda }}
        </div>
        <div class="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800/80 text-[11px] text-slate-500 dark:text-slate-400 flex justify-between">
          <span>Estável: <strong>{{ cen.estavel.valor_final | moeda }}</strong></span>
          <span>Variável: <strong>{{ cen.habitual.valor_final | moeda }}</strong></span>
        </div>
      </div>

      <!-- CARD 2: RENDA ESTÁVEL (SALÁRIO) -->
      <div class="bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
        <div class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 font-semibold mb-1">
          <span>Renda Estável (Fixa)</span>
          <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">Contratual</span>
        </div>
        <div class="text-2xl font-black text-emerald-600 dark:text-emerald-400 tracking-tight">
          {{ cen.estavel.valor_final | moeda }}
        </div>
        <div class="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800/80 text-[11px] text-slate-500 dark:text-slate-400">
          Base: Média de {{ ra.estatisticas_estavel.qtd_meses_validos }} meses (Salário Fernanda)
        </div>
      </div>

      <!-- CARD 3: RENDA VARIÁVEL HABITUAL -->
      <div class="bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
        <div class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 font-semibold mb-1">
          <span>Renda Variável (Drive)</span>
          <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400">Operacional</span>
        </div>
        <div class="text-2xl font-black text-amber-600 dark:text-amber-400 tracking-tight">
          {{ cen.habitual.valor_final | moeda }}
        </div>
        <div class="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800/80 text-[11px] text-slate-500 dark:text-slate-400">
          Mín: {{ ra.estatisticas_variavel.minimo_observado | moeda }} | Máx: {{ ra.estatisticas_variavel.maximo_observado | moeda }}
        </div>
      </div>

      <!-- CARD 4: RESULTADO NO CENÁRIO HABITUAL -->
      <div class="bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
        <div class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 font-semibold mb-1">
          <span>Saldo Previsto (Habitual)</span>
          <span class="px-2 py-0.5 rounded text-[10px] font-bold {% if cc.cenarios.habitual.sobra_ou_falta >= 0 %}bg-emerald-500/10 text-emerald-600{% else %}bg-rose-500/10 text-rose-600{% endif %}">
            {{ cc.cenarios.habitual.status | upper }}
          </span>
        </div>
        <div class="text-2xl font-black {% if cc.cenarios.habitual.sobra_ou_falta >= 0 %}text-emerald-600 dark:text-emerald-400{% else %}text-rose-600 dark:text-rose-400{% endif %} tracking-tight">
          {{ cc.cenarios.habitual.sobra_ou_falta | moeda }}
        </div>
        <div class="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800/80 text-[11px] text-slate-500 dark:text-slate-400">
          Despesas Totais: {{ cc.despesas_totais | moeda }}
        </div>
      </div>

    </div>

    <!-- SEÇÃO: 3 CENÁRIOS DE SENSIBILIDADE COM AJUSTE MANUAL -->
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xs space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-3">
        <div>
          <h2 class="text-sm sm:text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <span>⚖️</span> <span>Cenários de Sensibilidade da Renda Familiar</span>
          </h2>
          <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Compare o impacto de diferentes níveis de faturamento do Drive nas contas do mês.
          </p>
        </div>
        <button type="button" onclick="abrirModalCenarios()"
                class="touch-target inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-indigo-500/15 hover:bg-indigo-500/25 active:scale-95 text-indigo-600 dark:text-indigo-400 border border-indigo-500/30 text-xs font-bold transition cursor-pointer self-start sm:self-auto">
          <span>✏️</span> <span>Ajustar Cenários</span>
        </button>
      </div>

      <!-- GRADE DOS 3 CENÁRIOS -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        
        <!-- CENÁRIO 1: CONSERVADOR -->
        <div class="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950/40 space-y-3 relative">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
              <span>🛡️</span> <span>Conservador</span>
            </span>
            {% if cen.conservador.is_manual %}
            <span class="px-2 py-0.5 rounded text-[9px] font-black bg-indigo-500/15 text-indigo-600 dark:text-indigo-400">Manual</span>
            {% else %}
            <span class="px-2 py-0.5 rounded text-[9px] font-medium bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400">Histórico</span>
            {% endif %}
          </div>
          <div>
            <span class="text-xs text-slate-400 block">Renda Total:</span>
            <span class="text-xl font-black text-slate-900 dark:text-white">{{ cc.cenarios.conservador.renda_total | moeda }}</span>
            <span class="text-[11px] text-slate-400 block">(Fixa {{ cen.estavel.valor_final | moeda }} + Drive {{ cen.conservador.valor_final | moeda }})</span>
          </div>
          <div class="pt-2 border-t border-slate-200/60 dark:border-slate-800/60 space-y-1.5 text-xs">
            <div class="flex justify-between">
              <span class="text-slate-500">Resultado Previsto:</span>
              <strong class="{% if cc.cenarios.conservador.sobra_ou_falta >= 0 %}text-emerald-600{% else %}text-rose-600{% endif %}">
                {{ cc.cenarios.conservador.sobra_ou_falta | moeda }}
              </strong>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">Cobertura da Estrutura:</span>
              <strong class="{% if cc.cenarios.conservador.cobre_estrutura %}text-emerald-600{% else %}text-amber-600{% endif %}">
                {{ cc.cenarios.conservador.cobertura_estrutura_pct }}%
              </strong>
            </div>
          </div>
          <p class="text-[10px] text-slate-400 italic leading-relaxed pt-1 border-t border-slate-200/40 dark:border-slate-800/40">
            {{ cen.conservador.descricao }}
          </p>
        </div>

        <!-- CENÁRIO 2: HABITUAL -->
        <div class="p-4 rounded-xl border-2 border-indigo-500/40 bg-indigo-50/10 dark:bg-indigo-950/20 space-y-3 relative shadow-xs">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 flex items-center gap-1.5">
              <span>⭐</span> <span>Habitual</span>
            </span>
            {% if cen.habitual.is_manual %}
            <span class="px-2 py-0.5 rounded text-[9px] font-black bg-indigo-500/15 text-indigo-600 dark:text-indigo-400">Manual</span>
            {% else %}
            <span class="px-2 py-0.5 rounded text-[9px] font-medium bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400">Histórico</span>
            {% endif %}
          </div>
          <div>
            <span class="text-xs text-slate-400 block">Renda Total:</span>
            <span class="text-xl font-black text-slate-900 dark:text-white">{{ cc.cenarios.habitual.renda_total | moeda }}</span>
            <span class="text-[11px] text-slate-400 block">(Fixa {{ cen.estavel.valor_final | moeda }} + Drive {{ cen.habitual.valor_final | moeda }})</span>
          </div>
          <div class="pt-2 border-t border-slate-200/60 dark:border-slate-800/60 space-y-1.5 text-xs">
            <div class="flex justify-between">
              <span class="text-slate-500">Resultado Previsto:</span>
              <strong class="{% if cc.cenarios.habitual.sobra_ou_falta >= 0 %}text-emerald-600{% else %}text-rose-600{% endif %}">
                {{ cc.cenarios.habitual.sobra_ou_falta | moeda }}
              </strong>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">Cobertura da Estrutura:</span>
              <strong class="{% if cc.cenarios.habitual.cobre_estrutura %}text-emerald-600{% else %}text-amber-600{% endif %}">
                {{ cc.cenarios.habitual.cobertura_estrutura_pct }}%
              </strong>
            </div>
          </div>
          <p class="text-[10px] text-slate-400 italic leading-relaxed pt-1 border-t border-slate-200/40 dark:border-slate-800/40">
            {{ cen.habitual.descricao }}
          </p>
        </div>

        <!-- CENÁRIO 3: FAVORÁVEL -->
        <div class="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950/40 space-y-3 relative">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
              <span>🚀</span> <span>Favorável</span>
            </span>
            {% if cen.favorável.is_manual %}
            <span class="px-2 py-0.5 rounded text-[9px] font-black bg-indigo-500/15 text-indigo-600 dark:text-indigo-400">Manual</span>
            {% else %}
            <span class="px-2 py-0.5 rounded text-[9px] font-medium bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400">Histórico</span>
            {% endif %}
          </div>
          <div>
            <span class="text-xs text-slate-400 block">Renda Total:</span>
            <span class="text-xl font-black text-slate-900 dark:text-white">{{ cc.cenarios.favorável.renda_total | moeda }}</span>
            <span class="text-[11px] text-slate-400 block">(Fixa {{ cen.estavel.valor_final | moeda }} + Drive {{ cen.favorável.valor_final | moeda }})</span>
          </div>
          <div class="pt-2 border-t border-slate-200/60 dark:border-slate-800/60 space-y-1.5 text-xs">
            <div class="flex justify-between">
              <span class="text-slate-500">Resultado Previsto:</span>
              <strong class="{% if cc.cenarios.favorável.sobra_ou_falta >= 0 %}text-emerald-600{% else %}text-rose-600{% endif %}">
                {{ cc.cenarios.favorável.sobra_ou_falta | moeda }}
              </strong>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">Cobertura da Estrutura:</span>
              <strong class="{% if cc.cenarios.favorável.cobre_estrutura %}text-emerald-600{% else %}text-amber-600{% endif %}">
                {{ cc.cenarios.favorável.cobertura_estrutura_pct }}%
              </strong>
            </div>
          </div>
          <p class="text-[10px] text-slate-400 italic leading-relaxed pt-1 border-t border-slate-200/40 dark:border-slate-800/40">
            {{ cen.favorável.descricao }}
          </p>
        </div>

      </div>

      <!-- NOTA DE RESPONSABILIDADE & METODOLOGIA -->
      <div class="bg-amber-500/5 border border-amber-500/20 rounded-xl p-3 text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2.5">
        <span class="text-base shrink-0">⚠️</span>
        <div class="space-y-0.5">
          <strong>Atenção Metodológica:</strong>
          <span>{{ ra.aviso_metodologico }}</span>
        </div>
      </div>

    </div>

    <!-- DUAS COLUNAS: INTEGRAÇÃO DRIVE VS NATUREZA DAS DESPESAS -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      
      <!-- LADO ESQUERDO: MARGEM OPERACIONAL DO DRIVE -->
      {% if margem_drive %}
      {% set md = margem_drive %}
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xs space-y-4">
        <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
          <div class="flex items-center gap-2">
            <span class="text-xl">🚕</span>
            <h3 class="font-bold text-sm text-slate-900 dark:text-white">Margem Operacional do Oikos Drive</h3>
          </div>
          <span class="text-xs text-slate-500">{{ md.qtd_turnos }} turnos ({{ md.horas_totais | horas_br }})</span>
        </div>

        <div class="grid grid-cols-3 gap-2 text-center">
          <div class="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/40">
            <span class="block text-[10px] uppercase font-bold text-slate-400">Faturamento Bruto</span>
            <span class="text-base font-black text-slate-900 dark:text-white">{{ md.faturamento_bruto | moeda }}</span>
          </div>
          <div class="p-2.5 rounded-xl bg-rose-50/50 dark:bg-rose-950/20">
            <span class="block text-[10px] uppercase font-bold text-rose-500">Custos Registrados</span>
            <span class="text-base font-black text-rose-600 dark:text-rose-400">-{{ md.custos_registrados | moeda }}</span>
          </div>
          <div class="p-2.5 rounded-xl bg-emerald-50/50 dark:bg-emerald-950/20">
            <span class="block text-[10px] uppercase font-bold text-emerald-600 dark:text-emerald-400">Líquido Família</span>
            <span class="text-base font-black text-emerald-600 dark:text-emerald-400">{{ md.resultado_liquido_disponivel | moeda }}</span>
          </div>
        </div>

        <div class="space-y-2 text-xs">
          <div class="flex justify-between items-center py-1.5 border-b border-slate-100 dark:border-slate-800">
            <span class="text-slate-500">Ganho Médio Real por Hora:</span>
            <span class="font-bold text-slate-900 dark:text-white">
              {{ md.ganho_hora_real | moeda }}/h 
              <span class="text-[10px] font-normal text-slate-400">(Ref. 99: R$ 35,00/h)</span>
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
        </div>

        <div class="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 text-[11px] text-slate-500 leading-relaxed border border-slate-100 dark:border-slate-800">
          <strong>Garantia Anti-Duplicidade:</strong> {{ md.aviso_anti_duplicidade }}
        </div>
      </div>
      {% endif %}

      <!-- LADO DIREITO: CLASSIFICAÇÃO DE DESPESAS POR NATUREZA -->
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xs space-y-4">
        <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
          <div class="flex items-center gap-2">
            <span class="text-xl">🏛️</span>
            <h3 class="font-bold text-sm text-slate-900 dark:text-white">Despesas por Natureza Orçamentária</h3>
          </div>
          <span class="text-xs text-slate-400">Atributo Separado</span>
        </div>

        <!-- 3 BARRAS DE NATUREZA -->
        <div class="space-y-3">
          {% for nat_id, nat_info in cc.por_natureza.items() %}
          <div class="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/30 space-y-1.5">
            <div class="flex justify-between items-center text-xs">
              <span class="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                <span>{{ nat_info.icone }}</span> <span>{{ nat_info.nome }}</span>
              </span>
              <span class="font-black text-slate-900 dark:text-white">{{ nat_info.total | moeda }} ({{ nat_info.pct_total }}%)</span>
            </div>
            <div class="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
              <div class="h-full rounded-full {% if nat_id == 'estrutura_familiar' %}bg-indigo-500{% elif nat_id == 'qualidade_vida' %}bg-emerald-500{% else %}bg-amber-500{% endif %}"
                   style="width: {{ nat_info.pct_total }}%;"></div>
            </div>
          </div>
          {% endfor %}
        </div>

        <!-- RECLASSIFICAÇÃO RÁPIDA DE CATEGORIAS -->
        <details class="text-xs group">
          <summary class="cursor-pointer font-bold text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 flex items-center justify-between py-1">
            <span>⚙️ Gerenciar Classificação das Categorias</span>
            <span class="group-open:rotate-180 transition">▼</span>
          </summary>
          <div class="mt-3 space-y-2 max-h-56 overflow-y-auto pr-1 divide-y divide-slate-100 dark:divide-slate-800">
            {% for c in orcamento_categorias %}
            <div class="flex items-center justify-between py-1.5 gap-2">
              <span class="font-medium text-slate-700 dark:text-slate-300 truncate">{{ c.categoria }}</span>
              <select onchange="salvarNaturezaCategoria('{{ c.categoria }}', this.value)"
                      class="text-[11px] py-1 px-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 focus:ring-1 focus:ring-indigo-500">
                <option value="estrutura_familiar" {% if c.categoria in ['Alimentação', 'HABITAÇÃO', 'Moradia/Contas', 'Energia', 'Combustível (Trabalho)', 'Manutenção Veículo', 'SAÚDE', 'Medicamentos', 'Educação', 'Impostos Veículo', 'Pagamento de fatura'] %}selected{% endif %}>🏠 Estrutura</option>
                <option value="qualidade_vida" {% if c.categoria in ['Pessoal', 'Barbearia', 'Academia / Wellhub', 'Streaming', 'Lazer', 'Eletrodomésticos'] %}selected{% endif %}>🌱 Qualidade</option>
                <option value="objetivos_investimentos" {% if c.categoria in ['Acordo BV', 'Outras Dívidas', 'Empréstimos', 'Investimentos'] %}selected{% endif %}>🎯 Objetivos</option>
              </select>
            </div>
            {% endfor %}
          </div>
        </details>
      </div>

    </div>

    <!-- HISTÓRICO DE MESES ANALISADOS (COM BADGES DE LACUNAS E MESES INCOMPLETOS) -->
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xs space-y-3">
      <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
        <div>
          <h3 class="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
            <span>📊</span> <span>Histórico Mensal de Renda ({{ ra.meses_analise }} meses analisados)</span>
          </h3>
          <p class="text-xs text-slate-500 mt-0.5">Identificação transparente de meses incompletos e lacunas de informação.</p>
        </div>
        <span class="text-xs font-semibold text-slate-500">{{ ra.estatisticas_variavel.qtd_meses_validos }} meses válidos</span>
      </div>

      <div class="overflow-x-auto">
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
      </div>
    </div>

    {% endif %}

  </div>
  <!-- FIM CONTAINER TAB 2 -->

  <!-- ===================================================================== -->
  <!-- CONTAINER TAB 3: CALENDÁRIO ANUAL & DESPESAS EVENTUAIS (12 MESES)     -->
  <!-- ===================================================================== -->
  <div id="tab-conteudo-calendario" class="space-y-5 hidden">
    
    {% if calendario_anual %}
    {% set ca = calendario_anual %}

    <!-- CARDS DE DESTAQUE DO CALENDÁRIO ANUAL -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
      
      <div class="bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
        <div class="flex items-center justify-between text-xs text-slate-500 font-semibold mb-1">
          <span>Total Previsto (12 Meses)</span>
          <span class="px-2 py-0.5 rounded text-[10px] font-extrabold bg-indigo-500/10 text-indigo-600">Alvo</span>
        </div>
        <div class="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
          {{ ca.total_geral_previsto | moeda }}
        </div>
        <div class="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-400">
          IPVA, Seguros, Matrículas e Eventuais
        </div>
      </div>

      <div class="bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
        <div class="flex items-center justify-between text-xs text-slate-500 font-semibold mb-1">
          <span>Já Reservado em Cofrinhos</span>
          <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-600">Alocado</span>
        </div>
        <div class="text-2xl font-black text-emerald-600 dark:text-emerald-400 tracking-tight">
          {{ ca.total_geral_reservado | moeda }}
        </div>
        <div class="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-400">
          Taxa de Cobertura: <strong>{{ ca.taxa_cobertura_global }}%</strong>
        </div>
      </div>

      <div class="bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
        <div class="flex items-center justify-between text-xs text-slate-500 font-semibold mb-1">
          <span>Falta Reservar</span>
          <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-600">Meta</span>
        </div>
        <div class="text-2xl font-black text-amber-600 dark:text-amber-400 tracking-tight">
          {{ ca.total_geral_falta | moeda }}
        </div>
        <div class="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-400">
          Para liquidação integral no prazo
        </div>
      </div>

      <div class="bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs flex flex-col justify-between">
        <div class="flex items-center justify-between text-xs text-slate-500 font-semibold mb-1">
          <span>Novo Compromisso</span>
          <span class="text-base">📅</span>
        </div>
        <button type="button" onclick="abrirModalNovaDespesaEventual()"
                class="touch-target w-full py-2.5 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-bold text-xs transition shadow-sm cursor-pointer flex items-center justify-center gap-2">
          <span>+</span> <span>Novo Compromisso</span>
        </button>
      </div>

    </div>

    <!-- LINHA DO TEMPO DOS 12 MESES -->
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xs space-y-3">
      <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <span class="text-xl">🗓️</span>
          <h3 class="font-bold text-sm text-slate-900 dark:text-white">Linha do Tempo dos Próximos 12 Meses</h3>
        </div>
        <span class="text-xs text-slate-400">Visão consolidada</span>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
        {% for m12 in ca.meses %}
        <div class="p-3 rounded-xl border {% if m12.despesas | length > 0 %}border-indigo-500/30 bg-indigo-50/10 dark:bg-indigo-950/20{% else %}border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/30{% endif %} flex flex-col justify-between">
          <div>
            <span class="text-[10px] uppercase font-bold text-slate-400 block">{{ m12.label }}</span>
            <span class="text-sm font-black text-slate-900 dark:text-white mt-1 block">
              {% if m12.total_previsto > 0 %}{{ m12.total_previsto | moeda }}{% else %}<span class="text-slate-300 dark:text-slate-700 font-normal">—</span>{% endif %}
            </span>
          </div>
          {% if m12.despesas | length > 0 %}
          <div class="mt-2 pt-1.5 border-t border-slate-200/50 dark:border-slate-800/50 flex items-center justify-between text-[10px]">
            <span class="text-indigo-600 dark:text-indigo-400 font-bold">{{ m12.despesas | length }} item(s)</span>
            <span class="text-emerald-600 font-semibold">{{ m12.total_reservado | moeda }}</span>
          </div>
          {% endif %}
        </div>
        {% endfor %}
      </div>
    </div>

    <!-- TABELA / CARDS DE COMPROMISSOS CADASTRADOS -->
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xs space-y-3">
      <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
        <div>
          <h3 class="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
            <span>📋</span> <span>Compromissos Anuais, Sazonais e Eventuais</span>
          </h3>
          <p class="text-xs text-slate-500 mt-0.5">Gestão de IPVA, seguros, matrículas e celebrações com suporte a cofrinhos.</p>
        </div>
      </div>

      {% if ca.todas_despesas %}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50 dark:bg-slate-950/60 text-slate-500 uppercase text-[10px] font-bold tracking-wider">
            <tr>
              <th class="py-2.5 px-3">Compromisso</th>
              <th class="py-2.5 px-3">Data Prevista</th>
              <th class="py-2.5 px-3 text-right">Valor Alvo</th>
              <th class="py-2.5 px-3">Cofrinho Vinculado</th>
              <th class="py-2.5 px-3 text-right">Reservado</th>
              <th class="py-2.5 px-3 text-right">Falta</th>
              <th class="py-2.5 px-3 text-right">Sugestão Mensal</th>
              <th class="py-2.5 px-3 text-center">Ações</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
            {% for d in ca.todas_despesas %}
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
            {% endfor %}
          </tbody>
        </table>
      </div>
      {% else %}
      <div class="py-8 text-center text-xs text-slate-400 bg-slate-50 dark:bg-slate-950/40 rounded-xl border border-dashed border-slate-200 dark:border-slate-800 space-y-2">
        <span class="text-3xl block">📅</span>
        <p>Nenhuma despesa anual ou eventual cadastrada ainda.</p>
        <button type="button" onclick="abrirModalNovaDespesaEventual()"
                class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-600 text-white font-bold text-xs hover:bg-indigo-700 transition cursor-pointer">
          <span>+</span> <span>Cadastrar Primeira Despesa</span>
        </button>
      </div>
      {% endif %}

    </div>

    {% endif %}

  </div>
  <!-- FIM CONTAINER TAB 3 -->
"""

# Fechamento do bloco e inserção
content = orig[:idx_cab] + barra_subtabs + orig[idx_cab:]

# Encontrar o fechamento de lancamentos_ajustes para fechar a Tab 1 e inserir Tab 2 e 3
ancora_fim_orcamento = '<!-- MODAL: AJUSTAR LIMITE ORÇADO DA CATEGORIA -->'
assert ancora_fim_orcamento in content, "ancora_fim_orcamento não encontrada"

idx_fim_orc = content.find(ancora_fim_orcamento)
content = content[:idx_fim_orc] + novo_conteudo_tabs + "\n\n" + content[idx_fim_orc:]

# Agora adicionar os novos modais e scripts antes de {% endblock %}
novos_modais_e_scripts = """
<!-- MODAL: AJUSTAR CENÁRIOS DE RENDA -->
<div id="modal-cenarios" class="hidden fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs animate-fade-in">
  <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-5 shadow-2xl space-y-4">
    <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
      <div class="flex items-center gap-2">
        <span class="text-xl">⚖️</span>
        <h3 class="font-bold text-sm text-slate-900 dark:text-white">Ajustar Cenários de Renda</h3>
      </div>
      <button type="button" onclick="fecharModalCenarios()" class="text-slate-400 hover:text-slate-600 text-base font-bold">✕</button>
    </div>

    <form id="form-cenarios" onsubmit="salvarCenarios(event)" class="space-y-3 text-xs">
      <div>
        <label class="block font-bold text-slate-700 dark:text-slate-300 mb-1">Renda Estável / Fixa (R$)</label>
        <input type="number" step="0.01" id="input-estavel-manual" placeholder="Ex: 3437.38"
               value="{{ renda_analise.cenarios.estavel.valor_final if renda_analise else '' }}"
               class="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white font-bold">
      </div>
      <div>
        <label class="block font-bold text-slate-700 dark:text-slate-300 mb-1">Cenário Conservador do Drive (R$)</label>
        <input type="number" step="0.01" id="input-cons-manual" placeholder="Ex: 159.92"
               value="{{ renda_analise.cenarios.conservador.valor_final if renda_analise else '' }}"
               class="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white font-bold">
      </div>
      <div>
        <label class="block font-bold text-slate-700 dark:text-slate-300 mb-1">Cenário Habitual do Drive (R$)</label>
        <input type="number" step="0.01" id="input-hab-manual" placeholder="Ex: 1877.84"
               value="{{ renda_analise.cenarios.habitual.valor_final if renda_analise else '' }}"
               class="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white font-bold">
      </div>
      <div>
        <label class="block font-bold text-slate-700 dark:text-slate-300 mb-1">Cenário Favorável do Drive (R$)</label>
        <input type="number" step="0.01" id="input-fav-manual" placeholder="Ex: 3947.04"
               value="{{ renda_analise.cenarios.favorável.valor_final if renda_analise else '' }}"
               class="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white font-bold">
      </div>

      <div class="pt-2 flex items-center justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
        <button type="button" onclick="fecharModalCenarios()" class="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold">Salvar Cenários</button>
      </div>
    </form>
  </div>
</div>

<!-- MODAL: NOVA DESPESA EVENTUAL / ANUAL -->
<div id="modal-despesa-eventual" class="hidden fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs animate-fade-in">
  <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-5 shadow-2xl space-y-4">
    <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
      <div class="flex items-center gap-2">
        <span class="text-xl">📅</span>
        <h3 class="font-bold text-sm text-slate-900 dark:text-white">Novo Compromisso Anual / Eventual</h3>
      </div>
      <button type="button" onclick="fecharModalNovaDespesaEventual()" class="text-slate-400 hover:text-slate-600 text-base font-bold">✕</button>
    </div>

    <form id="form-despesa-eventual" onsubmit="salvarNovaDespesaEventual(event)" class="space-y-3 text-xs">
      <div>
        <label class="block font-bold text-slate-700 dark:text-slate-300 mb-1">Nome do Compromisso *</label>
        <input type="text" id="dev-nome" required placeholder="Ex: IPVA HB20 2027, Seguro Auto, Matrícula"
               class="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white font-semibold">
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="block font-bold text-slate-700 dark:text-slate-300 mb-1">Categoria</label>
          <select id="dev-categoria" class="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white">
            <option value="Impostos Veículo">Impostos Veículo</option>
            <option value="Manutenção Veículo">Manutenção Veículo</option>
            <option value="Educação">Educação</option>
            <option value="Habitação">Habitação</option>
            <option value="Lazer">Lazer / Celebrações</option>
            <option value="Outros">Outros</option>
          </select>
        </div>
        <div>
          <label class="block font-bold text-slate-700 dark:text-slate-300 mb-1">Responsável</label>
          <select id="dev-responsavel" class="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white">
            <option value="Família">Família</option>
            <option value="Carlos">Carlos</option>
            <option value="Fernanda">Fernanda</option>
          </select>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="block font-bold text-slate-700 dark:text-slate-300 mb-1">Data Prevista *</label>
          <input type="date" id="dev-data" required
                 class="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white">
        </div>
        <div>
          <label class="block font-bold text-slate-700 dark:text-slate-300 mb-1">Valor Estimado (R$) *</label>
          <input type="number" step="0.01" id="dev-valor" required placeholder="0.00"
                 class="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white font-bold">
        </div>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="block font-bold text-slate-700 dark:text-slate-300 mb-1">Vincular Cofrinho</label>
          <select id="dev-cofrinho" class="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white">
            <option value="">Nenhum cofrinho</option>
            {% if calendario_anual %}
            {% for cof in calendario_anual.cofrinhos_disponiveis %}
            <option value="{{ cof.id }}">🐖 {{ cof.nome }} (Saldo: {{ cof.saldo_confirmado | moeda }})</option>
            {% endfor %}
            {% endif %}
          </select>
        </div>
        <div>
          <label class="block font-bold text-slate-700 dark:text-slate-300 mb-1">Recorrência</label>
          <select id="dev-recorrencia" class="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white">
            <option value="anual">Anual</option>
            <option value="semestral">Semestral</option>
            <option value="pontual">Pontual</option>
          </select>
        </div>
      </div>

      <div class="pt-2 flex items-center justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
        <button type="button" onclick="fecharModalNovaDespesaEventual()" class="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold">Criar Compromisso</button>
      </div>
    </form>
  </div>
</div>

<!-- MODAL: CONCILIAR PAGAMENTO E BAIXAR RESERVA -->
<div id="modal-conciliar" class="hidden fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs animate-fade-in">
  <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-sm w-full p-5 shadow-2xl space-y-4">
    <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
      <div class="flex items-center gap-2">
        <span class="text-xl">💳</span>
        <h3 class="font-bold text-sm text-slate-900 dark:text-white">Conciliar Pagamento</h3>
      </div>
      <button type="button" onclick="fecharModalConciliar()" class="text-slate-400 hover:text-slate-600 text-base font-bold">✕</button>
    </div>

    <form id="form-conciliar" onsubmit="salvarConciliacao(event)" class="space-y-3 text-xs">
      <input type="hidden" id="conc-id">
      <div>
        <span class="text-slate-400 block">Compromisso:</span>
        <strong id="conc-nome" class="text-slate-900 dark:text-white text-sm"></strong>
      </div>
      <div>
        <label class="block font-bold text-slate-700 dark:text-slate-300 mb-1">Valor Efetivamente Pago (R$)</label>
        <input type="number" step="0.01" id="conc-valor" required
               class="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white font-bold">
      </div>
      <div>
        <label class="block font-bold text-slate-700 dark:text-slate-300 mb-1">Data do Pagamento</label>
        <input type="date" id="conc-data" required
               class="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white">
      </div>
      <div class="pt-2">
        <label class="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" id="conc-baixar-cofrinho" checked class="w-4 h-4 rounded text-emerald-600">
          <span class="text-slate-700 dark:text-slate-300">Baixar reserva do cofrinho vinculado (sem duplicar despesa)</span>
        </label>
      </div>

      <div class="pt-2 flex items-center justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
        <button type="button" onclick="fecharModalConciliar()" class="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold">Confirmar Pagamento</button>
      </div>
    </form>
  </div>
</div>

<script>
  function mudarSubTab(tab) {
    const tabs = ['orcamento', 'renda', 'calendario'];
    tabs.forEach(t => {
      const elConteudo = document.getElementById(`tab-conteudo-${t}`);
      const elBtn = document.getElementById(`btn-tab-${t}`);
      if (t === tab) {
        elConteudo.classList.remove('hidden');
        elBtn.className = "tab-btn px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold flex items-center gap-2 transition cursor-pointer bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shadow-xs";
      } else {
        elConteudo.classList.add('hidden');
        elBtn.className = "tab-btn px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold flex items-center gap-2 transition cursor-pointer text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60";
      }
    });
    if (history.replaceState) {
      history.replaceState(null, null, `#tab-${tab}`);
    }
  }

  // Ativa tab se vier na URL hash
  window.addEventListener('DOMContentLoaded', () => {
    const hash = window.location.hash;
    if (hash === '#tab-renda' || hash === '#renda') {
      mudarSubTab('renda');
    } else if (hash === '#tab-calendario' || hash === '#calendario-anual' || hash === '#calendario') {
      mudarSubTab('calendario');
    }
  });

  // Modal Cenários
  function abrirModalCenarios() {
    document.getElementById('modal-cenarios').classList.remove('hidden');
  }
  function fecharModalCenarios() {
    document.getElementById('modal-cenarios').classList.add('hidden');
  }

  async function salvarCenarios(e) {
    e.preventDefault();
    const payload = {
      ano: {{ ano }},
      mes: {{ mes }},
      estavel_manual: document.getElementById('input-estavel-manual').value || null,
      conservador_manual: document.getElementById('input-cons-manual').value || null,
      habitual_manual: document.getElementById('input-hab-manual').value || null,
      favoravel_manual: document.getElementById('input-fav-manual').value || null
    };
    try {
      const resp = await fetch('/api/planejamento/cenarios', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const res = await resp.json();
      if (res.sucesso) {
        showToast('Sucesso!', 'Cenários de renda atualizados.');
        fecharModalCenarios();
        setTimeout(() => location.reload(), 300);
      } else {
        showToast('Erro', res.erro || 'Falha ao salvar cenários.', true);
      }
    } catch (err) {
      showToast('Erro', err.message, true);
    }
  }

  // Salvar Natureza Orçamentária
  async function salvarNaturezaCategoria(cat, nat) {
    try {
      const resp = await fetch('/api/planejamento/natureza-despesa', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ categoria: cat, natureza: nat })
      });
      const res = await resp.json();
      if (res.sucesso) {
        showToast('Atualizado!', `Categoria ${cat} agora é ${nat}.`);
        setTimeout(() => location.reload(), 300);
      }
    } catch (err) {
      showToast('Erro', err.message, true);
    }
  }

  // Modal Nova Despesa Eventual
  function abrirModalNovaDespesaEventual() {
    const hojeIso = new Date().toISOString().split('T')[0];
    document.getElementById('dev-data').value = hojeIso;
    document.getElementById('modal-despesa-eventual').classList.remove('hidden');
  }
  function fecharModalNovaDespesaEventual() {
    document.getElementById('modal-despesa-eventual').classList.add('hidden');
  }

  async function salvarNovaDespesaEventual(e) {
    e.preventDefault();
    const payload = {
      nome: document.getElementById('dev-nome').value,
      categoria: document.getElementById('dev-categoria').value,
      responsavel: document.getElementById('dev-responsavel').value,
      data_prevista: document.getElementById('dev-data').value,
      valor_estimado: parseFloat(document.getElementById('dev-valor').value) || 0,
      cofrinho_id: document.getElementById('dev-cofrinho').value || null,
      recorrencia: document.getElementById('dev-recorrencia').value
    };
    try {
      const resp = await fetch('/api/planejamento/despesas-eventuais', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const res = await resp.json();
      if (res.sucesso) {
        showToast('Criado!', 'Compromisso anual adicionado.');
        fecharModalNovaDespesaEventual();
        setTimeout(() => location.reload(), 300);
      } else {
        showToast('Erro', res.erro || 'Falha ao criar.', true);
      }
    } catch (err) {
      showToast('Erro', err.message, true);
    }
  }

  // Modal Conciliar Pagamento
  function abrirModalConciliar(id, nome, valor, cofrinhoId) {
    document.getElementById('conc-id').value = id;
    document.getElementById('conc-nome').innerText = nome;
    document.getElementById('conc-valor').value = valor;
    document.getElementById('conc-data').value = new Date().toISOString().split('T')[0];
    document.getElementById('modal-conciliar').classList.remove('hidden');
  }
  function fecharModalConciliar() {
    document.getElementById('modal-conciliar').classList.add('hidden');
  }

  async function salvarConciliacao(e) {
    e.preventDefault();
    const id = document.getElementById('conc-id').value;
    const payload = {
      valor_pago: parseFloat(document.getElementById('conc-valor').value) || 0,
      data_pagamento: document.getElementById('conc-data').value,
      baixar_reserva_cofrinho: document.getElementById('conc-baixar-cofrinho').checked
    };
    try {
      const resp = await fetch(`/api/planejamento/despesas-eventuais/${id}/conciliar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const res = await resp.json();
      if (res.sucesso) {
        showToast('Conciliado!', 'Pagamento registrado com sucesso.');
        fecharModalConciliar();
        setTimeout(() => location.reload(), 300);
      } else {
        showToast('Erro', res.erro || 'Falha ao conciliar.', true);
      }
    } catch (err) {
      showToast('Erro', err.message, true);
    }
  }

  async function excluirDespesaEventual(id) {
    if (!confirm('Deseja realmente remover este compromisso?')) return;
    try {
      const resp = await fetch(`/api/planejamento/despesas-eventuais/${id}/excluir`, { method: 'POST' });
      const res = await resp.json();
      if (res.sucesso) {
        showToast('Removido!', 'Compromisso excluído.');
        setTimeout(() => location.reload(), 300);
      }
    } catch (err) {
      showToast('Erro', err.message, true);
    }
  }
</script>
"""

idx_endblock = content.rfind('{% endblock %}')
assert idx_endblock != -1, "{% endblock %} não encontrado"

content = content[:idx_endblock] + novos_modais_e_scripts + "\n" + content[idx_endblock:]

with open('templates/planejamento.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCESSO: templates/planejamento.html remodelado com sub-tabs e novas seções de Renda e Calendário!")
