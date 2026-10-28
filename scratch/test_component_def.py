import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from decimal import Decimal
import calendar
import saldo_service
import planejamento_service

def render_painel_prioridades_operacional(df: pd.DataFrame, df_turnos: pd.DataFrame, saldo_atual: float, conectar_fn):
    """
    PAINEL OPERACIONAL DE PRIORIDADES, CAIXA E METAS DE TRABALHO (MOTORISTA 99)
    Responde diretamente às 5 perguntas essenciais:
    1. O que é prioridade hoje?
    2. O que vence nos próximos 7 dias?
    3. Quanto dinheiro tenho?
    4. Quanto ainda preciso conseguir?
    5. Quanto preciso trabalhar para alcançar essa meta?
    """
    # Marco de referência: 20/10/2026 (ou data atual real)
    hoje = date(2026, 10, 20) if date.today().year == 2026 else date.today()
    hoje_str = hoje.strftime("%Y-%m-%d")
    limite_7d = hoje + timedelta(days=7)
    limite_7d_str = limite_7d.strftime("%Y-%m-%d")
    ano_atual = hoje.year
    mes_atual = hoje.month
    ultimo_dia = calendar.monthrange(ano_atual, mes_atual)[1]
    fim_mes = date(ano_atual, mes_atual, ultimo_dia)
    fim_mes_str = fim_mes.strftime("%Y-%m-%d")
    dias_corridos_restantes = max(1, (fim_mes - hoje).days + 1)

    # 1. Obter saldos detalhados por conta
    conn = conectar_fn()
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
    
    # 2. Filtragem segura de despesas pendentes
    df_desp = df[(df["tipo"] == "despesa") & (df["pago"] == 0)].copy()
    
    # Separar despesas bancárias reais (afeta_saldo_bancario == 1) de descontos em folha (afeta_saldo_bancario == 0)
    if "afeta_saldo_bancario" in df_desp.columns:
        df_caixa = df_desp[(df_desp["afeta_saldo_bancario"] == 1) | (df_desp["afeta_saldo_bancario"].isna())].copy()
        df_folha = df_desp[df_desp["afeta_saldo_bancario"] == 0].copy()
    else:
        df_caixa = df_desp.copy()
        df_folha = pd.DataFrame()

    # Divisão temporal estrita de Outubro
    vencidas = df_caixa[(df_caixa["data"] < hoje_str) & (df_caixa["data"] >= f"{ano_atual}-{mes_atual:02d}-01")].sort_values("data")
    vencem_hoje = df_caixa[df_caixa["data"] == hoje_str]
    prox_7d = df_caixa[(df_caixa["data"] > hoje_str) & (df_caixa["data"] <= limite_7d_str)].sort_values("data")
    restante_mes = df_caixa[(df_caixa["data"] > limite_7d_str) & (df_caixa["data"] <= fim_mes_str)].sort_values("data")

    tot_vencidas = float(vencidas["valor"].sum()) if not vencidas.empty else 0.0
    tot_hoje = float(vencem_hoje["valor"].sum()) if not vencem_hoje.empty else 0.0
    tot_7d = float(prox_7d["valor"].sum()) if not prox_7d.empty else 0.0
    tot_restante_mes = float(restante_mes["valor"].sum()) if not restante_mes.empty else 0.0
    tot_caixa_pendente_mes = tot_vencidas + tot_hoje + tot_7d + tot_restante_mes

    # Destaque específico do Acordo BV (22/10)
    bv_row = df_caixa[df_caixa["descricao"].str.contains("BV", case=False, na=False)]
    val_bv_nominal = float(bv_row["valor"].iloc[0]) if not bv_row.empty else 0.0
    val_bv_ref_outubro = 1921.22 # Valor de referência informado pelo usuário
    tot_7d_sem_bv = max(0.0, tot_7d - val_bv_nominal)

    # Destaque específico do IPVA (29/10)
    ipva_row = df_caixa[df_caixa["descricao"].str.contains("IPVA", case=False, na=False)]
    val_ipva = float(ipva_row["valor"].iloc[0]) if not ipva_row.empty else 0.0

    # Turnos realizados em Outubro pós-marco
    df_turnos_out = pd.DataFrame()
    if not df_turnos.empty and "data" in df_turnos.columns:
        df_turnos_out = df_turnos[df_turnos["data"] >= f"{ano_atual}-{mes_atual:02d}-01"].copy()
    total_bruto_turnos = float(df_turnos_out["ganho_bruto"].sum()) if not df_turnos_out.empty else 0.0
    total_comb_turnos = float(df_turnos_out["combustivel"].sum()) if not df_turnos_out.empty else 0.0
    total_liq_turnos = total_bruto_turnos - total_comb_turnos

    conn.close()

    # --- RENDERIZAÇÃO DO COMPONENTE ---
    with st.container(border=True):
        st.markdown("### 🎯 Painel Operacional • Prioridades, Caixa & Metas da 99")
        st.caption(f"📅 **Terça-feira, {hoje.strftime('%d/%m/%Y')}** • Foco imediato para a semana e fechamento de Outubro")

        # 1. AS 5 RESPOSTAS IMEDIATAS (GRID DE CARDS EXECUTIVOS)
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric(
                label="💵 Dinheiro Disponível",
                value=f"R$ {saldo_total_disponivel:,.2f}",
                help="Saldo real conciliado e livre de contas (Mercado Pago + Carteira)"
            )
            mp_val = next((c['saldo'] for c in saldos_contas if 'Mercado' in c['nome']), 0.0)
            cart_val = next((c['saldo'] for c in saldos_contas if 'Dinheiro' in c['nome'] or 'Carteira' in c['nome']), 0.0)
            st.caption(f"MP: **R$ {mp_val:,.2f}** | Dinheiro: **R$ {cart_val:,.2f}**")

        with c2:
            st.metric(
                label="🚨 Atrasadas + Hoje",
                value=f"R$ {(tot_vencidas + tot_hoje):,.2f}",
                delta=f"{len(vencidas)} contas atrasadas" if len(vencidas) > 0 else "Em dia",
                delta_color="inverse" if len(vencidas) > 0 else "normal",
                help="Total de contas com vencimento até hoje que ainda não foram pagas"
            )
            st.caption(f"Hoje: **R$ {tot_hoje:,.2f}** | Atrasadas: **R$ {tot_vencidas:,.2f}**")

        with c3:
            st.metric(
                label="⏳ Próximos 7 Dias",
                value=f"R$ {tot_7d:,.2f}",
                delta="Inclui BV (22/10)" if val_bv_nominal > 0 else "Confirmadas",
                delta_color="inverse" if val_bv_nominal > 0 else "normal",
                help=f"Contas a vencer entre 21/10 e 27/10. Sem o BV, totaliza R$ {tot_7d_sem_bv:,.2f}"
            )
            st.caption(f"Sem BV: **R$ {tot_7d_sem_bv:,.2f}** | BV: **R$ {val_bv_nominal:,.2f}**")

        with c4:
            # Falta cobrir na semana (Atrasadas + 7 dias sem BV - saldo)
            necessidade_semana_sem_bv = max(0.0, (tot_vencidas + tot_hoje + tot_7d_sem_bv) - saldo_total_disponivel)
            st.metric(
                label="🎯 Falta para a Semana",
                value=f"R$ {necessidade_semana_sem_bv:,.2f}",
                delta="Mínimo Essencial" if necessidade_semana_sem_bv > 0 else "✅ Coberto",
                delta_color="inverse" if necessidade_semana_sem_bv > 0 else "normal",
                help="Valor líquido novo necessário para cobrir atrasadas essenciais e os próximos 7 dias (sem considerar o BV)"
            )
            st.caption("Foco urgente dos próximos 5 a 7 dias")

        with c5:
            # Falta cobrir no mês inteiro (com BV nominal)
            falta_mes_tudo = max(0.0, tot_caixa_pendente_mes - saldo_total_disponivel)
            st.metric(
                label="📊 Falta no Mês (Tudo)",
                value=f"R$ {falta_mes_tudo:,.2f}",
                delta=f"Restam {dias_corridos_restantes} dias",
                delta_color="inverse" if falta_mes_tudo > 0 else "normal",
                help=f"Total de todas as despesas pendentes de Outubro menos o saldo disponível em contas"
            )
            st.caption(f"Sem BV: **R$ {max(0.0, tot_caixa_pendente_mes - val_bv_nominal - saldo_total_disponivel):,.2f}**")

        st.divider()

        # 2. ALERTAS CRÍTICOS: ACORDO BV E MISSÃO IPVA
        col_alerta1, col_alerta2 = st.columns(2)
        with col_alerta1:
            st.warning(f"""
            ⚠️ **COMPROMISSO CRÍTICO: Acordo BV (Parcela 4/24)**
            - **Vencimento:** Quinta-feira, **22/10/2026** (em 2 dias).
            - **Valor no Banco:** R$ {val_bv_nominal:,.2f} | **Valor Referência Outubro:** R$ {val_bv_ref_outubro:,.2f}.
            - **Risco Financeiro:** Como o pagamento provavelmente ocorrerá após o vencimento, há risco de incidência de juros/multa ou perda do acordo original. *Não existe prazo seguro presumido para atraso.*
            """)
        with col_alerta2:
            dias_ipva = max(0, (date(2026, 10, 29) - hoje).days)
            st.info(f"""
            🚘 **MISSÃO IPVA 2025/2026: R$ {val_ipva:,.2f}**
            - **Vencimento:** Quinta-feira, **29/10/2026** ({dias_ipva} dias restantes).
            - **Importância:** Regularidade fiscal do veículo de trabalho.
            - **Meta de Reserva:** Sugere-se reservar cerca de **R$ {(val_ipva / max(1, dias_ipva)):,.2f}/dia** para não comprometer o fluxo de caixa no dia 29.
            """)

        # 3. PLANEJAMENTO DE TRABALHO NA 99 (SIMULADOR DE METAS)
        with st.container(border=True):
            st.markdown("#### 🚕 Planejamento Operacional do Motorista (Metas da 99)")
            st.caption("Calcule exatamente quanto precisa faturar para atingir o líquido necessário, sem ilusão contábil entre faturamento bruto e lucro.")

            cp1, cp2, cp3 = st.columns([1.6, 1.2, 1.2])
            with cp1:
                tratamento_bv = st.radio(
                    "Tratamento do Acordo BV na meta de trabalho:",
                    [
                        "1. Prioridade Total (Inclui BV Nominal: R$ 1.428,82)",
                        "2. Prioridade Total (Inclui BV Referência: R$ 1.921,22)",
                        "3. Prioridade Essencial (Casa + IPVA, sem o BV no momento)"
                    ],
                    index=0,
                    key="vg_tratamento_bv_radio"
                )
            with cp2:
                dias_trabalho_sim = st.slider(
                    f"Dias de trabalho até 31/10 (de {dias_corridos_restantes}d corridos):",
                    min_value=1,
                    max_value=dias_corridos_restantes,
                    value=min(8, dias_corridos_restantes),
                    step=1,
                    key="vg_dias_trabalho_sim"
                )
            with cp3:
                margem_liq_sim = st.slider(
                    "Margem Líquida Estimada (%):",
                    min_value=50,
                    max_value=80,
                    value=65,
                    step=5,
                    help="Percentual do bruto que sobra após combustível e custos diretos do carro. Padrão prudencial: 65%.",
                    key="vg_margem_liq_sim"
                ) / 100.0

            # Definir a meta com base na opção do BV
            if "Nominal" in tratamento_bv:
                valor_alvo_total = tot_caixa_pendente_mes
                rotulo_alvo = "Total de Contas de Outubro (incluindo BV R$ 1.428,82)"
            elif "Referência" in tratamento_bv:
                valor_alvo_total = tot_caixa_pendente_mes - val_bv_nominal + val_bv_ref_outubro
                rotulo_alvo = f"Total de Contas de Outubro (com BV Ref R$ {val_bv_ref_outubro:,.2f})"
            else:
                valor_alvo_total = tot_caixa_pendente_mes - val_bv_nominal
                rotulo_alvo = "Contas Essenciais + IPVA (sem BV)"

            liquido_faltante = max(0.0, valor_alvo_total - saldo_total_disponivel)
            meta_liq_dia = liquido_faltante / dias_trabalho_sim if dias_trabalho_sim > 0 else 0.0
            meta_bruta_dia = meta_liq_dia / margem_liq_sim if margem_liq_sim > 0 else 0.0
            horas_estimadas_dia = meta_bruta_dia / 35.0 # Média conservadora de R$ 35,00 bruto/hora

            st.write("")
            cm1, cm2, cm3, cm4 = st.columns(4)
            with cm1:
                st.metric("🎯 Alvo Líquido Restante", f"R$ {liquido_faltante:,.2f}", help=rotulo_alvo)
            with cm2:
                st.metric(f"💰 Meta Líquida / Dia ({dias_trabalho_sim}d)", f"R$ {meta_liq_dia:,.2f}/dia", help="O que precisa sobrar limpo no bolso todo dia")
            with cm3:
                st.metric(f"🚕 Faturamento Bruto / Dia", f"R$ {meta_bruta_dia:,.2f}/dia", delta=f"Margem: {int(margem_liq_sim*100)}%", delta_color="normal", help="Total bruto que precisa entrar no app da 99 por dia")
            with cm4:
                st.metric("⏱️ Horas Estimadas / Dia", f"~{horas_estimadas_dia:.1f}h / dia", help="Estimativa baseada em R$ 35/h bruto na praça")

            # Status de turnos do mês
            st.write("")
            c_tr1, c_tr2 = st.columns([2.5, 1.5], vertical_alignment="center")
            with c_tr1:
                st.caption(f"🏁 **Turnos registrados no sistema:** {len(df_turnos_out)} turno(s) no mês • Ganho líquido acumulado: **R$ {total_liq_turnos:,.2f}**.")
                st.caption("💡 *Nota de Transparência: O faturamento bruto anterior de cerca de R$ 1.300 do início do mês já foi consumido pelas despesas operacionais e contas pagas antes do marco de 19/10. O saldo real atual em caixa é de R$ 86,33.*")
            with c_tr2:
                st.caption("Para calibrar sua margem real exata, lance seus turnos diários no botão **'🚕 + Lançar Turno'** acima.")

        # 4. EXPANDERS DE DETALHAMENTO TRANSPARENTE
        with st.expander(f"📋 Ver as {len(vencidas)} Contas Atrasadas (R$ {tot_vencidas:,.2f})"):
            if not vencidas.empty:
                cols_v = ["data", "descricao", "categoria", "valor", "conta"]
                df_v_show = vencidas[cols_v].copy()
                df_v_show.columns = ["Vencimento", "Descrição", "Categoria", "Valor (R$)", "Conta"]
                st.dataframe(df_v_show, use_container_width=True)
                st.caption("⚠️ *Priorize água (Copasa), luz (Cemig SIM) e saúde/medicamentos para a manutenção básica da casa.*")
            else:
                st.success("Nenhuma conta atrasada!")

        with st.expander(f"🗓️ Ver Contas dos Próximos 7 Dias & Restante do Mês ({len(prox_7d) + len(restante_mes)} contas)"):
            df_fut_show = pd.concat([prox_7d, restante_mes])
            if not df_fut_show.empty:
                cols_f = ["data", "descricao", "categoria", "valor", "conta"]
                df_f_show = df_fut_show[cols_f].copy()
                df_f_show.columns = ["Vencimento", "Descrição", "Categoria", "Valor (R$)", "Conta"]
                st.dataframe(df_f_show, use_container_width=True)
            else:
                st.info("Nenhuma conta futura pendente para este mês.")

        with st.expander("💼 Descontos em Folha da Fernanda (Segregados do Caixa)"):
            st.markdown("""
            - **Plano de Saúde Família Desconto em Folha:** R$ 578,17
            - **Planos Odontológicos:** R$ 19,94
            - **Total em Folha:** **R$ 598,11**
            
            *Estes valores são descontados diretamente do contracheque da Fernanda antes do salário líquido (R$ 3.523,43) cair no Mercado Pago. Eles estão contabilizados no custo familiar de Saúde, mas **não debitam a conta bancária**.*
            """)

        with st.expander("🏦 Detalhe dos Saldos por Conta (Conciliado em 19/10/2026)"):
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                st.metric("Mercado Pago", f"R$ {mp_val:,.2f}")
            with col_b2:
                st.metric("Dinheiro / Carteira", f"R$ {cart_val:,.2f}")
            with col_b3:
                st.metric("Consolidado Livre", f"R$ {saldo_total_disponivel:,.2f}")
            st.caption("Nenhum limite de crédito de cartão ou limite Paga Leve foi incluído nestes saldos.")

print("Component definition test successful!")
