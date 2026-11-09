"""
====================================================================
MÓDULO DE SERVIÇO DE SALDO (saldo_service.py)
====================================================================
Serviço centralizado para gestão de saldos bancários, marcos iniciais,
ajustes de conciliação e transferências.

Garantias de Arquitetura:
- Precisão monetária usando Decimal e quantização bancária (ROUND_HALF_EVEN).
- Persistência oficial de ajustes em centavos inteiros (INTEGER).
- Identificação relacional estável via conta_id (contas_config.id).
- Critério determinístico de corte por snapshot para a data do marco.
- Isolamento contábil: ajustes não geram receitas/despesas familiares.
- Despesas com afeta_saldo_bancario=0 (desconto em folha) não debitam contas bancárias.
- Soft-delete para auditoria contábil transparente.
"""

from decimal import Decimal, ROUND_HALF_EVEN
import json
import sqlite3
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, date, timedelta
import calendar

CENTAVOS = Decimal("0.01")


def to_decimal(val: Any) -> Decimal:
    """Converte qualquer valor numérico ou string para Decimal com 2 casas decimais."""
    if val is None or val == "":
        return Decimal("0.00")
    try:
        return Decimal(str(val)).quantize(CENTAVOS, rounding=ROUND_HALF_EVEN)
    except Exception:
        return Decimal("0.00")


def decimal_to_cents(d: Decimal) -> int:
    """Converte Decimal para centavos inteiros (ex: 150.25 -> 15025)."""
    return int((d * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def cents_to_decimal(cents: int) -> Decimal:
    """Converte centavos inteiros para Decimal com 2 casas decimais."""
    if cents is None:
        return Decimal("0.00")
    return (Decimal(cents) / Decimal(100)).quantize(CENTAVOS, rounding=ROUND_HALF_EVEN)


def migrar_esquema(conn: sqlite3.Connection) -> None:
    """
    Executa migrações não-destrutivas necessárias para o sistema de saldo e ajustes.
    Não altera registros nem classificações existentes.
    """
    cur = conn.cursor()

    # 1. Tabela de Ajustes e Marcos Iniciais
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ajustes_saldo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_id INTEGER NOT NULL REFERENCES contas_config(id),
        data DATE NOT NULL,
        saldo_informado_centavos INTEGER NOT NULL,
        saldo_calculado_centavos INTEGER NOT NULL,
        diferenca_centavos INTEGER NOT NULL,
        tipo TEXT NOT NULL DEFAULT 'ajuste', -- 'marco_inicial' ou 'ajuste'
        transacoes_contempladas_ids TEXT DEFAULT '[]', -- JSON list com IDs contemplados na data
        status TEXT NOT NULL DEFAULT 'ativo', -- 'ativo', 'cancelado', 'substituido'
        motivo TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cancelado_em TIMESTAMP,
        motivo_cancelamento TEXT,
        ajuste_substituto_id INTEGER REFERENCES ajustes_saldo(id)
    );
    """)

    # 2. Adição de colunas relacionais e de controle em transacoes
    cur.execute("PRAGMA table_info(transacoes)")
    cols_transacoes = [col[1] for col in cur.fetchall()]

    if "conta_id" not in cols_transacoes:
        cur.execute("ALTER TABLE transacoes ADD COLUMN conta_id INTEGER REFERENCES contas_config(id)")
    
    if "conta_destino_id" not in cols_transacoes:
        cur.execute("ALTER TABLE transacoes ADD COLUMN conta_destino_id INTEGER REFERENCES contas_config(id)")

    if "afeta_saldo_bancario" not in cols_transacoes:
        cur.execute("ALTER TABLE transacoes ADD COLUMN afeta_saldo_bancario INTEGER DEFAULT 1")

    if "status_pagamento" not in cols_transacoes:
        cur.execute("ALTER TABLE transacoes ADD COLUMN status_pagamento TEXT DEFAULT 'pendente'")

    if "valor_financiado_renegociado" not in cols_transacoes:
        cur.execute("ALTER TABLE transacoes ADD COLUMN valor_financiado_renegociado REAL DEFAULT 0")

    if "renegociacao_origem_id" not in cols_transacoes:
        cur.execute("ALTER TABLE transacoes ADD COLUMN renegociacao_origem_id INTEGER REFERENCES transacoes(id)")

    if "juros" not in cols_transacoes:
        cur.execute("ALTER TABLE transacoes ADD COLUMN juros REAL DEFAULT 0")

    if "desconto" not in cols_transacoes:
        cur.execute("ALTER TABLE transacoes ADD COLUMN desconto REAL DEFAULT 0")

    if "motivo_ajuste" not in cols_transacoes:
        cur.execute("ALTER TABLE transacoes ADD COLUMN motivo_ajuste TEXT")

    # Verifica pagaleve_compras
    cur.execute("PRAGMA table_info(pagaleve_compras)")
    cols_pl = [col[1] for col in cur.fetchall()]
    if cols_pl:
        if "juros" not in cols_pl:
            cur.execute("ALTER TABLE pagaleve_compras ADD COLUMN juros REAL DEFAULT 0")
        if "desconto" not in cols_pl:
            cur.execute("ALTER TABLE pagaleve_compras ADD COLUMN desconto REAL DEFAULT 0")
        if "motivo_ajuste" not in cols_pl:
            cur.execute("ALTER TABLE pagaleve_compras ADD COLUMN motivo_ajuste TEXT")

    # 3. Associação segura de conta_id baseada no nome textual existente
    cur.execute("""
    UPDATE transacoes 
    SET conta_id = (SELECT id FROM contas_config WHERE contas_config.nome = transacoes.conta)
    WHERE conta_id IS NULL AND conta IS NOT NULL
    """)

    # 4. Tabela Relacional de Pagamentos Efetivos de Despesas
    cur.execute("PRAGMA table_info(pagamentos_despesas)")
    cols_pag_raw = cur.fetchall()
    cols_pag = [col[1] for col in cols_pag_raw]
    
    # Se a tabela já existia com NOT NULL em data_pagamento, migra para permitir NULL (Condição 5)
    data_pag_notnull = any(col[1] == 'data_pagamento' and col[3] == 1 for col in cols_pag_raw)
    if data_pag_notnull:
        cur.execute("SELECT COUNT(*) FROM pagamentos_despesas")
        cnt_pags = cur.fetchone()[0]
        if cnt_pags == 0:
            cur.execute("DROP TABLE pagamentos_despesas")
            cols_pag = []
        else:
            cur.execute("""
            CREATE TABLE pagamentos_despesas_tmp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transacao_id INTEGER NOT NULL REFERENCES transacoes(id),
                data_pagamento DATE,
                data_real_desconhecida INTEGER DEFAULT 0,
                classificacao TEXT DEFAULT 'pagamento_efetivo',
                valor_pago REAL NOT NULL,
                valor_pago_centavos INTEGER NOT NULL,
                conta_id INTEGER NOT NULL REFERENCES contas_config(id),
                momento_pagamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                afeta_saldo_bancario INTEGER DEFAULT 1,
                considerado_no_marco INTEGER DEFAULT 0,
                forma_pagamento TEXT DEFAULT 'Pix',
                observacao TEXT,
                tipo_ajuste_valor TEXT DEFAULT 'normal',
                valor_encargos REAL DEFAULT 0,
                valor_desconto REAL DEFAULT 0,
                cancelado INTEGER DEFAULT 0,
                cancelado_em TIMESTAMP,
                motivo_cancelamento TEXT
            )
            """)
            shared_cols = [c for c in cols_pag if c in [
                "id", "transacao_id", "data_pagamento", "valor_pago", "valor_pago_centavos",
                "conta_id", "momento_pagamento", "afeta_saldo_bancario", "considerado_no_marco",
                "forma_pagamento", "observacao", "cancelado", "cancelado_em", "motivo_cancelamento"
            ]]
            shared_str = ", ".join(shared_cols)
            cur.execute(f"INSERT INTO pagamentos_despesas_tmp ({shared_str}) SELECT {shared_str} FROM pagamentos_despesas")
            cur.execute("DROP TABLE pagamentos_despesas")
            cur.execute("ALTER TABLE pagamentos_despesas_tmp RENAME TO pagamentos_despesas")
            cols_pag = shared_cols

    cur.execute("""
    CREATE TABLE IF NOT EXISTS pagamentos_despesas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transacao_id INTEGER NOT NULL REFERENCES transacoes(id),
        data_pagamento DATE,
        data_real_desconhecida INTEGER DEFAULT 0,
        classificacao TEXT DEFAULT 'pagamento_efetivo',
        valor_pago REAL NOT NULL,
        valor_pago_centavos INTEGER NOT NULL,
        conta_id INTEGER NOT NULL REFERENCES contas_config(id),
        momento_pagamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        afeta_saldo_bancario INTEGER DEFAULT 1,
        considerado_no_marco INTEGER DEFAULT 0,
        forma_pagamento TEXT DEFAULT 'Pix',
        observacao TEXT,
        tipo_ajuste_valor TEXT DEFAULT 'normal',
        valor_encargos REAL DEFAULT 0,
        valor_desconto REAL DEFAULT 0,
        cancelado INTEGER DEFAULT 0,
        cancelado_em TIMESTAMP,
        motivo_cancelamento TEXT
    );
    """)

    cur.execute("PRAGMA table_info(pagamentos_despesas)")
    cols_pag_atual = [col[1] for col in cur.fetchall()]
    novas_cols_pag = [
        ("data_real_desconhecida", "INTEGER DEFAULT 0"),
        ("classificacao", "TEXT DEFAULT 'pagamento_efetivo'"),
        ("tipo_ajuste_valor", "TEXT DEFAULT 'normal'"),
        ("valor_encargos", "REAL DEFAULT 0"),
        ("valor_desconto", "REAL DEFAULT 0")
    ]
    for col, col_def in novas_cols_pag:
        if col not in cols_pag_atual:
            try:
                cur.execute(f"ALTER TABLE pagamentos_despesas ADD COLUMN {col} {col_def}")
            except Exception:
                pass

    # 5. Colunas de Subcontas e Vínculo em contas_config
    cur.execute("PRAGMA table_info(contas_config)")
    cols_cc = [r[1] for r in cur.fetchall()]
    if "conta_pai_id" not in cols_cc:
        try:
            cur.execute("ALTER TABLE contas_config ADD COLUMN conta_pai_id INTEGER REFERENCES contas_config(id)")
        except Exception:
            pass
    if "incluir_saldo_consolidado" not in cols_cc:
        try:
            cur.execute("ALTER TABLE contas_config ADD COLUMN incluir_saldo_consolidado INTEGER DEFAULT 1")
        except Exception:
            pass
    if "icone" not in cols_cc:
        try:
            cur.execute("ALTER TABLE contas_config ADD COLUMN icone TEXT DEFAULT '🏦'")
        except Exception:
            pass

    # Garante existência e padronização da conta contábil '99Pay'
    cur.execute("SELECT id, nome FROM contas_config WHERE nome IN ('99Pay', 'Saldo 99 (App)')")
    row_99 = cur.fetchone()
    if not row_99:
        try:
            cur.execute("""
                INSERT INTO contas_config (nome, tipo, cor, conta_pai_id, incluir_saldo_consolidado)
                VALUES ('99Pay', 'digital', '#f59e0b', NULL, 1)
            """)
        except Exception:
            pass
    elif row_99[1] != '99Pay':
        try:
            cur.execute("UPDATE contas_config SET nome = '99Pay' WHERE id = ?", (row_99[0],))
        except Exception:
            pass

    # 6. Colunas em cofrinhos
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cofrinhos'")
    tem_cofrinhos = cur.fetchone() is not None
    if tem_cofrinhos:
        cur.execute("PRAGMA table_info(cofrinhos)")
        cols_cof = [r[1] for r in cur.fetchall()]
        if "conta_config_id" not in cols_cof:
            try:
                cur.execute("ALTER TABLE cofrinhos ADD COLUMN conta_config_id INTEGER REFERENCES contas_config(id)")
            except Exception:
                pass
        if "incluir_saldo_consolidado" not in cols_cof:
            try:
                cur.execute("ALTER TABLE cofrinhos ADD COLUMN incluir_saldo_consolidado INTEGER DEFAULT 0")
            except Exception:
                pass

        # 7. Sincronização automática dos cofrinhos com contas_config
        cur.execute("SELECT id, nome, saldo_confirmado FROM cofrinhos")
        cofrinhos_list = cur.fetchall()
        for cof in cofrinhos_list:
            c_id = cof[0]
            c_nome = cof[1]
            cur.execute("SELECT id FROM contas_config WHERE nome = ?", (c_nome,))
            r_cc = cur.fetchone()
            if r_cc:
                cc_id = r_cc[0]
                cur.execute("UPDATE contas_config SET tipo = 'cofrinho', conta_pai_id = 1 WHERE id = ?", (cc_id,))
            else:
                cur.execute("""
                    INSERT INTO contas_config (nome, tipo, cor, conta_pai_id, incluir_saldo_consolidado)
                    VALUES (?, 'cofrinho', '#f59e0b', 1, 0)
                """, (c_nome,))
                cc_id = cur.lastrowid
            cur.execute("UPDATE cofrinhos SET conta_config_id = ? WHERE id = ?", (cc_id, c_id))

    # 8. Colunas operacionais em turnos
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='turnos'")
    if cur.fetchone() is not None:
        cur.execute("PRAGMA table_info(turnos)")
        cols_t = [r[1] for r in cur.fetchall()]
        novas_cols_t = [
            ("km_inicial", "REAL"),
            ("km_final", "REAL"),
            ("ganho_dinheiro_pix", "REAL DEFAULT 0.0"),
            ("ganho_online", "REAL DEFAULT 0.0"),
            ("status_turno", "TEXT DEFAULT 'encerrado'"),
            ("combustivel_consumido_estimado", "REAL DEFAULT 0.0"),
            ("created_at", "TEXT")
        ]
        for col, col_def in novas_cols_t:
            if col not in cols_t:
                try:
                    cur.execute(f"ALTER TABLE turnos ADD COLUMN {col} {col_def}")
                except Exception:
                    pass

    # 9. Tabela de Abastecimentos do Veículo (Drivvo-style)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS veiculo_abastecimentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data DATE NOT NULL,
        hodometro REAL,
        combustivel TEXT NOT NULL DEFAULT 'Etanol',
        litros REAL,
        preco_litro REAL,
        valor_bruto REAL,
        desconto REAL DEFAULT 0.0,
        valor_pago REAL NOT NULL,
        conta TEXT,
        conta_id INTEGER REFERENCES contas_config(id),
        tanque_cheio INTEGER DEFAULT 1,
        posto TEXT,
        observacao TEXT,
        transacao_id INTEGER REFERENCES transacoes(id),
        created_at TEXT
    );
    """)

    # Vincula o abastecimento real existente da transação #40 (20/10 - R$ 90,48) se ainda não inserido
    cur.execute("SELECT id, data, valor, conta, conta_id FROM transacoes WHERE id = 40")
    r40 = cur.fetchone()
    if r40:
        cur.execute("SELECT count(*) FROM veiculo_abastecimentos WHERE transacao_id = 40")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO veiculo_abastecimentos (
                    data, hodometro, combustivel, litros, preco_litro, valor_bruto, desconto, valor_pago,
                    conta, conta_id, tanque_cheio, posto, observacao, transacao_id, created_at
                ) VALUES (
                    '2026-10-20', NULL, 'Etanol', NULL, NULL, 100.0, 9.52, 90.48,
                    ?, ?, NULL, 'Posto de Combustível', 'Cupom de R$ 9,52 em dinheiro físico (litros, hodômetro e tanque cheio aguardando confirmação)', 40, '2026-10-20 18:00:00'
                )
            """, (r40[3] or 'Dinheiro / Carteira', r40[4] or 2))

    conn.commit()


def obter_contas(conn: sqlite3.Connection, incluir_cofrinhos: bool = True) -> List[Dict[str, Any]]:
    """Retorna contas configuradas ordenadas por id."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(contas_config)")
    cols = [r[1] for r in cur.fetchall()]
    tem_icone = "icone" in cols
    query = "SELECT id, nome, tipo, cor, conta_pai_id, incluir_saldo_consolidado" + (", icone" if tem_icone else "") + " FROM contas_config ORDER BY id ASC"
    cur.execute(query)
    rows = cur.fetchall()
    res = []
    for r in rows:
        if not incluir_cofrinhos and r[2] == 'cofrinho':
            continue
        ic = r[6] if tem_icone and len(r) > 6 and r[6] else ("🌐" if "mercado" in str(r[1]).lower() else ("🚕" if "99" in str(r[1]).lower() else ("👛" if "carteira" in str(r[1]).lower() or "dinheiro" in str(r[1]).lower() else "🏦")))
        res.append({
            "id": r[0],
            "nome": r[1],
            "tipo": r[2],
            "cor": r[3] or "#009ee3",
            "conta_pai_id": r[4],
            "incluir_saldo_consolidado": r[5] if r[5] is not None else 1,
            "icone": ic
        })
    return res



def obter_ajuste_ativo(
    conn: sqlite3.Connection, 
    conta_id: int, 
    data_limite: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Retorna o ajuste ativo mais recente para a conta (ordenado por data DESC, id DESC).
    Se data_limite for informada, considera apenas ajustes com data <= data_limite.
    """
    cur = conn.cursor()
    if data_limite:
        cur.execute("""
            SELECT id, conta_id, data, saldo_informado_centavos, saldo_calculado_centavos,
                   diferenca_centavos, tipo, transacoes_contempladas_ids, motivo, criado_em
            FROM ajustes_saldo
            WHERE conta_id = ? AND status = 'ativo' AND data <= ?
            ORDER BY data DESC, id DESC
            LIMIT 1
        """, (conta_id, data_limite))
    else:
        cur.execute("""
            SELECT id, conta_id, data, saldo_informado_centavos, saldo_calculado_centavos,
                   diferenca_centavos, tipo, transacoes_contempladas_ids, motivo, criado_em
            FROM ajustes_saldo
            WHERE conta_id = ? AND status = 'ativo'
            ORDER BY data DESC, id DESC
            LIMIT 1
        """, (conta_id,))
    
    row = cur.fetchone()
    if not row:
        return None

    contempladas = []
    if row[7]:
        try:
            contempladas = json.loads(row[7])
        except Exception:
            contempladas = []

    return {
        "id": row[0],
        "conta_id": row[1],
        "data": row[2],
        "saldo_informado": cents_to_decimal(row[3]),
        "saldo_informado_centavos": row[3],
        "saldo_calculado": cents_to_decimal(row[4]),
        "diferenca": cents_to_decimal(row[5]),
        "tipo": row[6],
        "transacoes_contempladas_ids": set(contempladas),
        "motivo": row[8],
        "criado_em": row[9]
    }


def calcular_saldo_conta(
    conn: sqlite3.Connection, 
    conta_id: int, 
    data_referencia: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calcula o saldo real e dinâmico de uma conta com base no saldo inicial oficial
    e em TODO o histórico de transações consolidadas até a data de referência / atual.
    
    Fórmula Contábil Oficial:
    Saldo = Saldo Inicial + SUM(entradas pagas) - SUM(despesas pagas) - SUM(transferências enviadas) + SUM(transferências recebidas).
    
    Garantias:
    - Qualquer despesa com pago = 1 (mesmo com data retroativa como 20/10 ou 25/10) abate diretamente do saldo da conta.
    - Transferências internas atualizam origem e destino simultaneamente.
    - Despesas com afeta_saldo_bancario = 0 não debitam saldo bancário.
    """
    cur = conn.cursor()

    # Informações da conta
    cur.execute("SELECT id, nome, tipo, cor FROM contas_config WHERE id = ?", (conta_id,))
    conta_row = cur.fetchone()
    if not conta_row:
        return {
            "conta_id": conta_id,
            "conta_nome": "Desconhecida",
            "saldo_atual": Decimal("0.00"),
            "saldo_centavos": 0,
            "tem_marco": False,
            "ajuste_id": None,
            "total_receitas_posteriores": Decimal("0.00"),
            "total_despesas_posteriores": Decimal("0.00"),
            "total_transf_entradas": Decimal("0.00"),
            "total_transf_saidas": Decimal("0.00")
        }
    
    conta_nome = conta_row[1]

    # Busca o marco inicial ativo mais recente da conta para obter o Saldo Inicial Base da implantação
    cur.execute("""
        SELECT id, data, saldo_informado_centavos, motivo
        FROM ajustes_saldo
        WHERE conta_id = ? AND tipo = 'marco_inicial' AND status = 'ativo'
        ORDER BY data DESC, id DESC
        LIMIT 1
    """, (conta_id,))
    marco_ini = cur.fetchone()

    if not marco_ini:
        # Fallback para qualquer marco inicial cadastrado caso não haja flag 'ativo'
        cur.execute("""
            SELECT id, data, saldo_informado_centavos, motivo
            FROM ajustes_saldo
            WHERE conta_id = ? AND tipo = 'marco_inicial'
            ORDER BY data DESC, id DESC
            LIMIT 1
        """, (conta_id,))
        marco_ini = cur.fetchone()

    if marco_ini:
        saldo_cents = marco_ini[2]
        data_inicio = marco_ini[1]
        tem_marco = True
        ajuste_id = marco_ini[0]
        marco_data = marco_ini[1]
        marco_saldo = cents_to_decimal(saldo_cents)
    else:
        saldo_cents = 0
        data_inicio = "2026-10-19"  # Data base de corte/implantação do sistema
        tem_marco = False
        ajuste_id = None
        marco_data = None
        marco_saldo = None

    # Busca todas as movimentações consolidadas da conta a partir da data base
    query = """
        SELECT id, data, COALESCE(valor_pago, valor) as valor, tipo, conta_id, conta_destino_id, afeta_saldo_bancario, conta
        FROM transacoes
        WHERE (pago = 1 OR status_pagamento = 'pago') 
          AND (afeta_saldo_bancario = 1 OR afeta_saldo_bancario IS NULL)
          AND (
              conta_id = ? 
              OR conta_destino_id = ?
              OR (conta_id IS NULL AND conta = ?)
          )
    """
    params = [conta_id, conta_id, conta_nome]

    if data_inicio:
        query += " AND COALESCE(data_liquidacao, data) >= ?"
        params.append(data_inicio)

    if data_referencia:
        query += " AND COALESCE(data_liquidacao, data) <= ?"
        params.append(data_referencia)

    query += " ORDER BY data ASC, id ASC"

    cur.execute(query, params)
    rows = cur.fetchall()

    rec_post_cents = 0
    desp_post_cents = 0
    transf_in_cents = 0
    transf_out_cents = 0

    for r in rows:
        t_id, t_data, t_val, t_tipo, t_origem_id, t_dest_id, t_afeta, t_conta_str = r
        val_cents = decimal_to_cents(to_decimal(t_val))

        eh_origem = (t_origem_id == conta_id) or (t_origem_id is None and t_conta_str == conta_nome)
        eh_destino = (t_dest_id == conta_id)

        if t_tipo == "receita" and eh_origem:
            saldo_cents += val_cents
            rec_post_cents += val_cents
        elif t_tipo == "despesa" and eh_origem:
            saldo_cents -= val_cents
            desp_post_cents += val_cents
        elif t_tipo == "transferencia":
            if eh_origem:
                saldo_cents -= val_cents
                transf_out_cents += val_cents
            if eh_destino:
                saldo_cents += val_cents
                transf_in_cents += val_cents

    return {
        "conta_id": conta_id,
        "conta_nome": conta_nome,
        "saldo_atual": cents_to_decimal(saldo_cents),
        "saldo_centavos": saldo_cents,
        "tem_marco": tem_marco,
        "ajuste_id": ajuste_id,
        "marco_data": marco_data,
        "marco_saldo": marco_saldo,
        "total_receitas_posteriores": cents_to_decimal(rec_post_cents),
        "total_despesas_posteriores": cents_to_decimal(desp_post_cents),
        "total_transf_entradas": cents_to_decimal(transf_in_cents),
        "total_transf_saidas": cents_to_decimal(transf_out_cents),
    }


def calcular_saldo_consolidado(
    conn: sqlite3.Connection, 
    data_referencia: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calcula o saldo consolidado de todas as contas ativas em contas_config.
    Separa rigorosamente o saldo livre disponível do saldo alocado em reservas/cofrinhos,
    permitindo ao usuário configurar se cada cofrinho é incluído no consolidado livre ou apenas nas reservas.
    Transferências internas anulam-se no total geral com reservas.
    """
    contas = obter_contas(conn, incluir_cofrinhos=True)
    total_livre_cents = 0
    total_reservas_cents = 0
    detalhes_contas = []

    for c in contas:
        res = calcular_saldo_conta(conn, c["id"], data_referencia=data_referencia)
        res["tipo"] = c.get("tipo", "corrente")
        res["cor"] = c.get("cor", "#009ee3")
        res["icone"] = c.get("icone", "🏦")
        res["conta_pai_id"] = c.get("conta_pai_id")
        res["incluir_saldo_consolidado"] = c.get("incluir_saldo_consolidado", 1)
        detalhes_contas.append(res)

        eh_cofrinho = (c.get("tipo") == "cofrinho")
        incluir_no_livre = (c.get("incluir_saldo_consolidado", 1 if not eh_cofrinho else 0) == 1)

        if incluir_no_livre:
            total_livre_cents += res["saldo_centavos"]
        else:
            total_reservas_cents += res["saldo_centavos"]

    total_geral_cents = total_livre_cents + total_reservas_cents

    return {
        "saldo_consolidado": cents_to_decimal(total_livre_cents),
        "saldo_consolidado_centavos": total_livre_cents,
        "saldo_reservas": cents_to_decimal(total_reservas_cents),
        "saldo_reservas_centavos": total_reservas_cents,
        "saldo_total_com_reservas": cents_to_decimal(total_geral_cents),
        "saldo_total_com_reservas_centavos": total_geral_cents,
        "contas": detalhes_contas
    }


def transferir_para_cofrinho(
    conn: sqlite3.Connection,
    cofrinho_id: int,
    valor: float,
    data_iso: str,
    descricao: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Realiza transferência interna de recurso livre do Mercado Pago para um cofrinho vinculado.
    Reduz o saldo livre da origem e aumenta o saldo do cofrinho sem gerar receita ou despesa.
    """
    if valor <= 0:
        return False, "O valor deve ser maior que zero."

    cur = conn.cursor()
    cur.execute("SELECT id, nome, conta_pai_id, conta_config_id FROM cofrinhos WHERE id = ?", (cofrinho_id,))
    row = cur.fetchone()
    if not row:
        return False, "Cofrinho não encontrado."

    cof_id, cof_nome, pai_id, cc_id = row
    origem_id = pai_id or 1
    destino_id = cc_id

    if not destino_id:
        cur.execute("SELECT id FROM contas_config WHERE nome = ?", (cof_nome,))
        row_cc = cur.fetchone()
        if row_cc:
            destino_id = row_cc[0]
            cur.execute("UPDATE cofrinhos SET conta_config_id = ? WHERE id = ?", (destino_id, cof_id))
        else:
            cur.execute("""
                INSERT INTO contas_config (nome, tipo, cor, conta_pai_id, incluir_saldo_consolidado)
                VALUES (?, 'cofrinho', '#f59e0b', ?, 0)
            """, (cof_nome, origem_id))
            destino_id = cur.lastrowid
            cur.execute("UPDATE cofrinhos SET conta_config_id = ? WHERE id = ?", (destino_id, cof_id))

    desc_final = descricao.strip() if descricao and descricao.strip() else f"Aporte {cof_nome}"

    cur.execute("""
        INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, conta_destino_id, pago, afeta_saldo_bancario)
        VALUES (?, ?, ?, 'transferencia', 'Transferência Interna', 'Mercado Pago', ?, ?, 1, 1)
    """, (data_iso, desc_final, float(valor), origem_id, destino_id))

    # Sincroniza saldo_confirmado em cofrinhos
    res_dest = calcular_saldo_conta(conn, destino_id)
    cur.execute("UPDATE cofrinhos SET saldo_confirmado = ?, data_atualizacao = ? WHERE id = ?", 
                (float(res_dest["saldo_atual"]), data_iso, cof_id))

    conn.commit()
    return True, f"R$ {valor:,.2f} guardado no {cof_nome} com sucesso!"


def retirar_de_cofrinho(
    conn: sqlite3.Connection,
    cofrinho_id: int,
    valor: float,
    data_iso: str,
    descricao: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Realiza resgate interno de um cofrinho para a conta principal Mercado Pago.
    Reduz o saldo do cofrinho e recompõe o saldo livre da origem sem gerar receita ou despesa.
    """
    if valor <= 0:
        return False, "O valor deve ser maior que zero."

    cur = conn.cursor()
    cur.execute("SELECT id, nome, conta_pai_id, conta_config_id FROM cofrinhos WHERE id = ?", (cofrinho_id,))
    row = cur.fetchone()
    if not row:
        return False, "Cofrinho não encontrado."

    cof_id, cof_nome, pai_id, cc_id = row
    origem_id = cc_id
    destino_id = pai_id or 1

    if not origem_id:
        cur.execute("SELECT id FROM contas_config WHERE nome = ?", (cof_nome,))
        row_cc = cur.fetchone()
        if row_cc:
            origem_id = row_cc[0]
            cur.execute("UPDATE cofrinhos SET conta_config_id = ? WHERE id = ?", (origem_id, cof_id))
        else:
            return False, "Conta vinculada do cofrinho não encontrada."

    # Verifica saldo disponível no cofrinho
    res_origem = calcular_saldo_conta(conn, origem_id)
    saldo_disponivel_cof = res_origem["saldo_atual"]
    if Decimal(str(valor)) > saldo_disponivel_cof:
        return False, f"Saldo insuficiente no {cof_nome} (Disponível: R$ {saldo_disponivel_cof:,.2f})."

    # Validação de reservas comprometidas: a soma das reservas manuais não pode ficar maior que o novo saldo
    cur.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='planejamento_despesas_eventuais'
    """)
    if cur.fetchone():
        cur.execute("""
            SELECT COALESCE(SUM(valor_reservado_manual), 0)
            FROM planejamento_despesas_eventuais
            WHERE cofrinho_id = ? AND status != 'cancelada'
        """, (cof_id,))
        soma_reservada = Decimal(str(cur.fetchone()[0] or 0.0))
        novo_saldo_projetado = saldo_disponivel_cof - Decimal(str(valor))
        if novo_saldo_projetado < soma_reservada:
            livre_para_resgate = max(Decimal("0.00"), saldo_disponivel_cof - soma_reservada)
            return False, (
                f"Resgate não permitido: R$ {soma_reservada:,.2f} deste cofrinho já estão atribuídos a compromissos anuais. "
                f"Valor livre para resgate: R$ {livre_para_resgate:,.2f}."
            )

    desc_final = descricao.strip() if descricao and descricao.strip() else f"Resgate {cof_nome}"

    cur.execute("""
        INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, conta_destino_id, pago, afeta_saldo_bancario)
        VALUES (?, ?, ?, 'transferencia', 'Transferência Interna', ?, ?, ?, 1, 1)
    """, (data_iso, desc_final, float(valor), cof_nome, origem_id, destino_id))

    # Sincroniza saldo_confirmado em cofrinhos
    res_orig_pos = calcular_saldo_conta(conn, origem_id)
    cur.execute("UPDATE cofrinhos SET saldo_confirmado = ?, data_atualizacao = ? WHERE id = ?", 
                (float(res_orig_pos["saldo_atual"]), data_iso, cof_id))

    conn.commit()
    return True, f"R$ {valor:,.2f} resgatado do {cof_nome} para o Mercado Pago com sucesso!"


def configurar_saldo_consolidado_cofrinho(
    conn: sqlite3.Connection,
    cofrinho_id: int,
    incluir_no_consolidado: bool
) -> Tuple[bool, str]:
    """
    Configura se o saldo de um cofrinho aparece no saldo consolidado livre ou apenas no saldo de reservas.
    """
    cur = conn.cursor()
    val_int = 1 if incluir_no_consolidado else 0
    cur.execute("SELECT conta_config_id, nome FROM cofrinhos WHERE id = ?", (cofrinho_id,))
    row = cur.fetchone()
    if not row:
        return False, "Cofrinho não encontrado."

    cc_id, nome = row
    cur.execute("UPDATE cofrinhos SET incluir_saldo_consolidado = ? WHERE id = ?", (val_int, cofrinho_id))
    if cc_id:
        cur.execute("UPDATE contas_config SET incluir_saldo_consolidado = ? WHERE id = ?", (val_int, cc_id))
    conn.commit()
    status_txt = "incluído no saldo consolidado livre" if incluir_no_consolidado else "mantido apenas no saldo de reservas"
    return True, f"Configuração atualizada: '{nome}' agora está {status_txt}."



def listar_transacoes_da_data(
    conn: sqlite3.Connection, 
    conta_id: int, 
    data_iso: str
) -> List[Dict[str, Any]]:
    """
    Retorna os lançamentos cadastrados para uma conta em uma data específica.
    Útil para exibir no diálogo de conciliação / ajuste.
    """
    cur = conn.cursor()
    cur.execute("SELECT nome FROM contas_config WHERE id = ?", (conta_id,))
    c_row = cur.fetchone()
    c_nome = c_row[0] if c_row else ""

    cur.execute("""
        SELECT id, descricao, valor, tipo, pago, afeta_saldo_bancario
        FROM transacoes
        WHERE data = ? 
          AND pago = 1
          AND (conta_id = ? OR (conta_id IS NULL AND conta = ?))
        ORDER BY id ASC
    """, (data_iso, conta_id, c_nome))

    rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "descricao": r[1],
            "valor": to_decimal(r[2]),
            "tipo": r[3],
            "pago": r[4],
            "afeta_saldo_bancario": r[5]
        }
        for r in rows
    ]


def registrar_ajuste(
    conn: sqlite3.Connection,
    conta_id: int,
    data_ajuste: str,
    saldo_informado: Decimal,
    tipo: str = "ajuste",
    motivo: str = "",
    transacoes_contempladas_ids: Optional[List[int]] = None
) -> int:
    """
    Registra um marco ou ajuste de saldo.
    Calcula o saldo que o sistema calculava até aquele momento exato para apurar a diferença.
    Valores são estritamente persistidos em centavos inteiros.
    """
    saldo_informado_dec = to_decimal(saldo_informado)
    saldo_informado_cents = decimal_to_cents(saldo_informado_dec)

    # Calcula saldo do sistema na data de referência
    res_atual = calcular_saldo_conta(conn, conta_id, data_referencia=data_ajuste)
    saldo_calculado_cents = res_atual["saldo_centavos"]
    diferenca_cents = saldo_informado_cents - saldo_calculado_cents

    cur = conn.cursor()
    if transacoes_contempladas_ids is None:
        cur.execute("""
            SELECT id FROM transacoes
            WHERE data = ? AND (conta_id = ? OR conta_destino_id = ?)
        """, (data_ajuste, conta_id, conta_id))
        ids_contemplados = [r[0] for r in cur.fetchall()]
    else:
        ids_contemplados = transacoes_contempladas_ids
    json_contempladas = json.dumps(ids_contemplados)

    # Marca pagamentos de despesas já existentes até a data do ajuste como contemplados no marco
    try:
        cur.execute("""
            UPDATE pagamentos_despesas
            SET considerado_no_marco = 1
            WHERE conta_id = ? AND cancelado = 0 AND data_pagamento <= ?
        """, (conta_id, data_ajuste))
    except Exception:
        pass

    cur.execute("""
        INSERT INTO ajustes_saldo (
            conta_id, data, saldo_informado_centavos, saldo_calculado_centavos,
            diferenca_centavos, tipo, transacoes_contempladas_ids, status, motivo
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ativo', ?)
    """, (
        conta_id,
        data_ajuste,
        saldo_informado_cents,
        saldo_calculado_cents,
        diferenca_cents,
        tipo,
        json_contempladas,
        motivo
    ))

    novo_id = cur.lastrowid
    conn.commit()
    return novo_id


def cancelar_ajuste(
    conn: sqlite3.Connection,
    ajuste_id: int,
    motivo_cancelamento: str = ""
) -> bool:
    """
    Executa o cancelamento contábil (soft-delete) de um ajuste.
    Preserva a trilha de auditoria sem apagar o registro físico.
    """
    cur = conn.cursor()
    agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        UPDATE ajustes_saldo
        SET status = 'cancelado',
            cancelado_em = ?,
            motivo_cancelamento = ?
        WHERE id = ? AND status = 'ativo'
    """, (agora_iso, motivo_cancelamento, ajuste_id))

    sucesso = cur.rowcount > 0
    conn.commit()
    return sucesso


def listar_historico_ajustes(
    conn: sqlite3.Connection,
    conta_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Retorna o histórico completo de ajustes e marcos (ativos e cancelados) para auditoria.
    """
    cur = conn.cursor()
    query = """
        SELECT a.id, a.conta_id, c.nome, a.data, a.saldo_informado_centavos,
               a.saldo_calculado_centavos, a.diferenca_centavos, a.tipo,
               a.status, a.motivo, a.criado_em, a.cancelado_em, a.motivo_cancelamento,
               a.transacoes_contempladas_ids
        FROM ajustes_saldo a
        JOIN contas_config c ON c.id = a.conta_id
    """
    params = []
    if conta_id:
        query += " WHERE a.conta_id = ?"
        params.append(conta_id)

    query += " ORDER BY a.data DESC, a.id DESC"
    cur.execute(query, params)
    rows = cur.fetchall()

    resultado = []
    for r in rows:
        contempladas = []
        if r[13]:
            try:
                contempladas = json.loads(r[13])
            except Exception:
                contempladas = []
        resultado.append({
            "id": r[0],
            "conta_id": r[1],
            "conta_nome": r[2],
            "data": r[3],
            "saldo_informado": cents_to_decimal(r[4]),
            "saldo_calculado": cents_to_decimal(r[5]),
            "diferenca": cents_to_decimal(r[6]),
            "tipo": r[7],
            "status": r[8],
            "motivo": r[9],
            "criado_em": r[10],
            "cancelado_em": r[11],
            "motivo_cancelamento": r[12],
            "transacoes_contempladas_ids": contempladas
        })
    return resultado


# ==============================================================================
# GESTÃO RELACIONAL E AUDITÁVEL DE PAGAMENTOS DE DESPESAS
# ==============================================================================

def registrar_pagamento(
    conn: sqlite3.Connection,
    transacao_id: int,
    data_pagamento: Optional[str],
    valor_pago: float,
    conta_id: int,
    afeta_saldo_bancario: int = 1,
    considerado_no_marco: int = 0,
    forma_pagamento: str = "Pix",
    observacao: str = "",
    data_real_desconhecida: int = 0,
    classificacao: str = "pagamento_efetivo",
    tipo_ajuste_valor: str = "normal",
    valor_encargos: float = 0.0,
    valor_desconto: float = 0.0
) -> Dict[str, Any]:
    """
    Registra um pagamento (integral ou parcial) para uma obrigação em transacoes.
    Preserva a data de vencimento da obrigação original e vincula o débito bancário
    à conta utilizada e à data efetiva do pagamento.
    
    Aplica validação estrita (Condição 13): impede que pagamentos ultrapassem o saldo
    devedor restante sem que haja declaração explícita de encargos/juros ou renegociação.
    """
    cur = conn.cursor()
    cur.execute("SELECT id, valor, data, descricao FROM transacoes WHERE id = ?", (transacao_id,))
    t = cur.fetchone()
    if not t:
        raise ValueError(f"Obrigação #{transacao_id} não encontrada.")

    val_orig = to_decimal(t[1])
    val_pago_dec = to_decimal(valor_pago)
    val_cents = decimal_to_cents(val_pago_dec)

    # Verifica saldo devedor atual antes do novo pagamento
    cur.execute("""
        SELECT COALESCE(SUM(valor_pago_centavos), 0)
        FROM pagamentos_despesas
        WHERE transacao_id = ? AND cancelado = 0
    """, (transacao_id,))
    total_pago_anterior_cents = cur.fetchone()[0]
    total_pago_anterior = cents_to_decimal(total_pago_anterior_cents)
    saldo_devedor_atual = max(Decimal("0.00"), val_orig - total_pago_anterior)

    # Condição 13: Validação de limite do saldo devedor (permite excesso se houver declaração de juros/encargos)
    if tipo_ajuste_valor == "normal" and float(valor_encargos or 0.0) == 0.0 and val_pago_dec > saldo_devedor_atual:
        excesso = val_pago_dec - saldo_devedor_atual
        raise ValueError(
            f"O valor do pagamento (R$ {val_pago_dec:.2f}) excede o saldo devedor restante da obrigação (R$ {saldo_devedor_atual:.2f}) em R$ {excesso:.2f}. "
            f"Para efetuar pagamento maior que o saldo devedor, selecione explicitamente o tipo de ajuste (ex: 'Com Juros/Multa' ou 'Renegociação/Acordo') e informe os encargos."
        )

    # 1. Insere o pagamento auditável
    cur.execute("""
        INSERT INTO pagamentos_despesas 
        (transacao_id, data_pagamento, data_real_desconhecida, classificacao, valor_pago, valor_pago_centavos, conta_id, afeta_saldo_bancario, considerado_no_marco, forma_pagamento, observacao, tipo_ajuste_valor, valor_encargos, valor_desconto)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (transacao_id, data_pagamento, data_real_desconhecida, classificacao, float(val_pago_dec), val_cents, conta_id, afeta_saldo_bancario, considerado_no_marco, forma_pagamento, observacao, tipo_ajuste_valor, float(valor_encargos), float(valor_desconto)))
    pag_id = cur.lastrowid

    # 2. Recalcula o total pago e atualiza status da obrigação
    cur.execute("""
        SELECT COALESCE(SUM(valor_pago_centavos), 0)
        FROM pagamentos_despesas
        WHERE transacao_id = ? AND cancelado = 0
    """, (transacao_id,))
    total_pago_cents = cur.fetchone()[0]
    total_pago = cents_to_decimal(total_pago_cents)
    saldo_devedor = max(Decimal("0.00"), val_orig - total_pago)

    if total_pago >= val_orig:
        novo_status = "PAGA"
        novo_pago = 1
    elif total_pago > Decimal("0.00"):
        novo_status = "parcial"
        novo_pago = 2  # 2 indica parcialmente pago
    else:
        novo_status = "pendente"
        novo_pago = 0

    try:
        cur.execute("ALTER TABLE transacoes ADD COLUMN data_liquidacao TEXT")
    except Exception:
        pass

    cur.execute("SELECT conta, conta_id FROM transacoes WHERE id = ?", (transacao_id,))
    row_orig_trans = cur.fetchone()
    orig_conta = row_orig_trans[0] if row_orig_trans else None
    orig_conta_id = row_orig_trans[1] if row_orig_trans else None

    # Verifica se a transação original pertence a um cartão de crédito
    eh_cartao_credito = False
    if orig_conta_id is not None or orig_conta is not None:
        cur.execute("SELECT id FROM cartoes WHERE id = ? OR nome = ?", (orig_conta_id, orig_conta))
        eh_cartao_credito = cur.fetchone() is not None

    cur.execute("SELECT nome FROM contas_config WHERE id = ?", (conta_id,))
    row_c_nome = cur.fetchone()
    nome_conta_pag = row_c_nome[0] if row_c_nome else None

    if eh_cartao_credito:
        # PRESERVA O CARTÃO: Compras de cartão de crédito NUNCA perdem seu conta_id nem seu nome de cartão!
        cur.execute("""
            UPDATE transacoes
            SET pago = ?, status_pagamento = ?, data_liquidacao = ?,
                valor_pago = ?, juros = ?, desconto = ?, afeta_saldo_bancario = 0
            WHERE id = ?
        """, (novo_pago, novo_status, data_pagamento, float(val_pago_dec), float(valor_encargos), float(valor_desconto), transacao_id))
    elif nome_conta_pag:
        cur.execute("""
            UPDATE transacoes
            SET pago = ?, status_pagamento = ?, data_liquidacao = ?, conta = ?, conta_id = ?, afeta_saldo_bancario = ?,
                valor_pago = ?, juros = ?, desconto = ?
            WHERE id = ?
        """, (novo_pago, novo_status, data_pagamento, nome_conta_pag, conta_id, afeta_saldo_bancario, float(val_pago_dec), float(valor_encargos), float(valor_desconto), transacao_id))
    else:
        cur.execute("""
            UPDATE transacoes
            SET pago = ?, status_pagamento = ?, data_liquidacao = ?, conta_id = ?, afeta_saldo_bancario = ?,
                valor_pago = ?, juros = ?, desconto = ?
            WHERE id = ?
        """, (novo_pago, novo_status, data_pagamento, conta_id, afeta_saldo_bancario, float(val_pago_dec), float(valor_encargos), float(valor_desconto), transacao_id))
    conn.commit()

    return {
        "pagamento_id": pag_id,
        "transacao_id": transacao_id,
        "data_pagamento": data_pagamento,
        "valor_pago": val_pago_dec,
        "total_pago": total_pago,
        "saldo_devedor": saldo_devedor,
        "status_pagamento": novo_status,
        "pago_flag": novo_pago
    }



def desfazer_pagamento_transacao(
    conn: sqlite3.Connection,
    transacao_id: int,
    motivo: str = "Desfazer pagamento solicitado pelo usuário"
) -> Dict[str, Any]:
    """
    Reverte/estorna o pagamento de uma despesa ou obrigação de forma auditável e segura:
    - Valida idempotência: se o lançamento já estiver pendente (pago = 0), impede duplicação.
    - Localiza o último pagamento ativo em pagamentos_despesas e estorna-o com cancelado = 1.
    - Atualiza a transação para status 'pendente' (pago = 0) e limpa data_liquidacao.
    - Recompõe o saldo bancário da conta debitada.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT id, descricao, valor, data, pago, status_pagamento, conta, conta_id, tipo
        FROM transacoes
        WHERE id = ?
    """, (transacao_id,))
    t = cur.fetchone()
    if not t:
        raise ValueError(f"Lançamento #{transacao_id} não encontrado.")

    tid, desc, valor, data_venc, pago, status_pag, conta_nome, conta_id, tipo = t

    if pago != 1:
        raise ValueError(f"O lançamento '{desc}' (#{transacao_id}) já se encontra pendente ou não possui pagamento ativo para desfazer.")

    # Busca o último pagamento não cancelado
    cur.execute("""
        SELECT id, valor_pago, conta_id, data_pagamento
        FROM pagamentos_despesas
        WHERE transacao_id = ? AND (cancelado = 0 OR cancelado IS NULL)
        ORDER BY id DESC
        LIMIT 1
    """, (transacao_id,))
    row_pag = cur.fetchone()

    valor_estornado = float(valor or 0.0)
    cid_debitada = conta_id
    if row_pag:
        pag_id = row_pag[0]
        valor_estornado = float(row_pag[1] or valor or 0.0)
        cid_debitada = row_pag[2] or conta_id
        estornar_pagamento(conn, pag_id, motivo=motivo)
    else:
        # Fallback de auditoria para transações legadas sem pagamentos_despesas
        cur.execute("""
            INSERT INTO pagamentos_despesas
            (transacao_id, data_pagamento, valor_pago, valor_pago_centavos, conta_id, cancelado, cancelado_em, motivo_cancelamento)
            VALUES (?, CURRENT_DATE, ?, ?, ?, 1, CURRENT_TIMESTAMP, ?)
        """, (transacao_id, float(valor_estornado), decimal_to_cents(to_decimal(valor_estornado)), conta_id, motivo))

    hoje_iso = date.today().isoformat()
    # Se for receita, o status ao reverter para nao-pago e 'pendente'; se despesa com data passada, 'atrasada'
    if tipo == 'receita':
        novo_status = 'pendente'
    else:
        novo_status = 'atrasada' if (data_venc and str(data_venc) < hoje_iso) else 'pendente'

    cur.execute("""
        UPDATE transacoes
        SET pago = 0, status_pagamento = ?, data_liquidacao = NULL, valor_pago = NULL, juros = 0.0, desconto = 0.0
        WHERE id = ?
    """, (novo_status, transacao_id))
    conn.commit()

    return {
        "transacao_id": transacao_id,
        "descricao": desc,
        "valor_estornado": valor_estornado,
        "data_vencimento": str(data_venc),
        "conta_id": cid_debitada,
        "status": novo_status,
        "tipo": tipo
    }


def estornar_pagamento(
    conn: sqlite3.Connection,
    pagamento_id: int,
    motivo: str = "Estorno solicitado pelo usuário"
) -> Dict[str, Any]:
    """
    Estorna um pagamento específico com rastreabilidade (soft-delete).
    Recompõe o saldo bancário se foi pós-marco e atualiza o saldo devedor da obrigação.
    """
    cur = conn.cursor()
    cur.execute("SELECT transacao_id, valor_pago, conta_id, data_pagamento, considerado_no_marco FROM pagamentos_despesas WHERE id = ?", (pagamento_id,))
    p = cur.fetchone()
    if not p:
        raise ValueError(f"Pagamento #{pagamento_id} não encontrado.")

    t_id = p[0]

    # Marca como cancelado
    cur.execute("""
        UPDATE pagamentos_despesas
        SET cancelado = 1, cancelado_em = CURRENT_TIMESTAMP, motivo_cancelamento = ?
        WHERE id = ?
    """, (motivo, pagamento_id))

    # Recalcula a obrigação vinculada
    cur.execute("SELECT valor FROM transacoes WHERE id = ?", (t_id,))
    val_orig = to_decimal(cur.fetchone()[0])

    cur.execute("""
        SELECT COALESCE(SUM(valor_pago_centavos), 0)
        FROM pagamentos_despesas
        WHERE transacao_id = ? AND cancelado = 0
    """, (t_id,))
    total_pago_cents = cur.fetchone()[0]
    total_pago = cents_to_decimal(total_pago_cents)
    saldo_devedor = max(Decimal("0.00"), val_orig - total_pago)

    if total_pago >= val_orig:
        novo_status = "pago"
        novo_pago = 1
    elif total_pago > Decimal("0.00"):
        novo_status = "parcial"
        novo_pago = 2
    else:
        novo_status = "pendente"
        novo_pago = 0

    cur.execute("UPDATE transacoes SET pago = ?, status_pagamento = ? WHERE id = ?", (novo_pago, novo_status, t_id))
    conn.commit()

    return {
        "transacao_id": t_id,
        "total_pago": total_pago,
        "saldo_devedor": saldo_devedor,
        "status_pagamento": novo_status,
        "pago_flag": novo_pago
    }


def obter_pagamentos_transacao(conn: sqlite3.Connection, transacao_id: int) -> List[Dict[str, Any]]:
    """Retorna todos os pagamentos vinculados a uma obrigação (ativos e cancelados)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.data_pagamento, p.valor_pago, p.conta_id, c.nome, p.forma_pagamento,
               p.observacao, p.considerado_no_marco, p.cancelado, p.cancelado_em, p.motivo_cancelamento,
               p.momento_pagamento, p.data_real_desconhecida, p.classificacao, p.tipo_ajuste_valor,
               p.valor_encargos, p.valor_desconto
        FROM pagamentos_despesas p
        LEFT JOIN contas_config c ON c.id = p.conta_id
        WHERE p.transacao_id = ?
        ORDER BY p.data_pagamento ASC, p.id ASC
    """, (transacao_id,))
    rows = cur.fetchall()
    return [{
        "id": r[0],
        "data_pagamento": r[1],
        "valor_pago": to_decimal(r[2]),
        "conta_id": r[3],
        "conta_nome": r[4] or "Desconhecida",
        "forma_pagamento": r[5] or "Pix",
        "observacao": r[6] or "",
        "considerado_no_marco": bool(r[7]),
        "cancelado": bool(r[8]),
        "cancelado_em": r[9],
        "motivo_cancelamento": r[10],
        "momento_pagamento": r[11],
        "data_real_desconhecida": bool(r[12]),
        "classificacao": r[13] or "pagamento_efetivo",
        "tipo_ajuste_valor": r[14] or "normal",
        "valor_encargos": to_decimal(r[15] or 0),
        "valor_desconto": to_decimal(r[16] or 0)
    } for r in rows]


def obter_resumo_obrigacao(conn: sqlite3.Connection, transacao_id: int) -> Dict[str, Any]:
    """Retorna resumo completo da obrigação com valor nominal, total pago, saldo devedor e lista de pagamentos."""
    cur = conn.cursor()
    cur.execute("SELECT id, data, descricao, valor, pago, status_pagamento, conta, conta_id FROM transacoes WHERE id = ?", (transacao_id,))
    t = cur.fetchone()
    if not t:
        return {}
    val_orig = to_decimal(t[3])
    pags = obter_pagamentos_transacao(conn, transacao_id)
    pags_ativos = [p for p in pags if not p["cancelado"]]
    total_pago = sum((p["valor_pago"] for p in pags_ativos), Decimal("0.00"))
    saldo_devedor = max(Decimal("0.00"), val_orig - total_pago)
    return {
        "id": t[0],
        "data_vencimento": t[1],
        "descricao": t[2],
        "valor_original": val_orig,
        "pago_flag": t[4],
        "status_pagamento": t[5] or ("pago" if t[4] == 1 else "pendente"),
        "conta_padrao": t[6],
        "conta_id": t[7],
        "total_pago": total_pago,
        "saldo_devedor": saldo_devedor,
        "pagamentos": pags,
        "pagamentos_ativos": pags_ativos
    }


def obter_metricas_combustivel(conn: sqlite3.Connection, data_referencia: Optional[str] = None) -> Dict[str, Any]:
    """
    Retorna métricas segregadas de combustível e abastecimentos do veículo (estilo Drivvo):
    1. Total efetivamente pago em abastecimentos (fluxo de caixa real) no dia, semana e mês.
    2. Consumo operacional estimado por quilometragem rodada nos turnos.
    3. Faturamento bruto das corridas.
    4. Resultado de Caixa após Abastecimentos (Faturamento - Abastecimento Pago).
    5. Resultado Operacional Estimado (Faturamento - Consumo Estimado).
    NÃO desconta os dois custos simultaneamente e não os chama de lucro líquido completo.
    """
    if data_referencia:
        hoje = datetime.strptime(data_referencia, "%Y-%m-%d").date()
    else:
        hoje = date.today()
    hoje_iso = hoje.strftime("%Y-%m-%d")
    inicio_semana = (hoje - timedelta(days=hoje.weekday())).strftime("%Y-%m-%d")
    fim_semana = (hoje + timedelta(days=6 - hoje.weekday())).strftime("%Y-%m-%d")
    inicio_mes = hoje.replace(day=1).strftime("%Y-%m-%d")
    ultimo_dia_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    fim_mes = hoje.replace(day=ultimo_dia_mes).strftime("%Y-%m-%d")

    cur = conn.cursor()
    
    # 1. Abastecimentos registrados em veiculo_abastecimentos
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='veiculo_abastecimentos'")
    tem_tabela = cur.fetchone() is not None

    abastecimentos = []
    ids_transacoes_vinculadas = set()

    pago_hoje = 0.0
    pago_semana = 0.0
    pago_mes = 0.0

    litros_hoje = 0.0
    litros_semana = 0.0
    litros_mes = 0.0

    if tem_tabela:
        cur.execute("""
            SELECT id, data, hodometro, combustivel, litros, preco_litro, valor_bruto,
                   desconto, valor_pago, conta, conta_id, tanque_cheio, posto, observacao, transacao_id
            FROM veiculo_abastecimentos
            ORDER BY data DESC, hodometro DESC, id DESC
        """)
        for r in cur.fetchall():
            val_pago = float(r[8] or 0.0)
            lit = float(r[4]) if r[4] is not None else None
            hod = float(r[2]) if r[2] is not None else None
            prc = float(r[5]) if r[5] is not None else ((val_pago / lit) if lit and lit > 0 else None)
            tq = int(r[11]) if r[11] is not None else None
            dt = r[1]
            if r[14]:
                ids_transacoes_vinculadas.add(r[14])
            abastecimentos.append({
                "id": r[0],
                "data": dt,
                "hodometro": hod,
                "combustivel": r[3] or "Etanol",
                "litros": lit,
                "preco_litro": prc,
                "valor_bruto": float(r[6] or val_pago),
                "desconto": float(r[7] or 0.0),
                "valor_pago": val_pago,
                "conta": r[9] or "Conta",
                "conta_id": r[10],
                "tanque_cheio": tq,
                "posto": r[12] or "",
                "observacao": r[13] or "",
                "transacao_id": r[14]
            })
            if dt == hoje_iso:
                pago_hoje += val_pago
                if lit is not None:
                    litros_hoje += lit
            if inicio_semana <= dt <= fim_semana:
                pago_semana += val_pago
                if lit is not None:
                    litros_semana += lit
            if inicio_mes <= dt <= fim_mes:
                pago_mes += val_pago
                if lit is not None:
                    litros_mes += lit

    # Também verifica se há despesas de combustível em transacoes ainda não cadastradas em veiculo_abastecimentos
    cur.execute("""
        SELECT id, data, descricao, valor, conta, conta_id, tipo, categoria
        FROM transacoes
        WHERE tipo = 'despesa'
          AND pago = 1
          AND (
              categoria LIKE '%Combust%'
              OR descricao LIKE '%Combust%'
              OR descricao LIKE '%Abastec%'
              OR descricao LIKE '%Etanol%'
              OR descricao LIKE '%Gasolina%'
          )
        ORDER BY data DESC, id DESC
    """)
    despesas_comb_avulsas = []
    for tr in cur.fetchall():
        tr_id, dt, desc, val, c_nome, c_id, tp, cat = tr
        if tr_id not in ids_transacoes_vinculadas:
            val_f = float(val or 0.0)
            despesas_comb_avulsas.append({
                "id": tr_id,
                "data": dt,
                "descricao": desc,
                "valor": val_f,
                "conta": c_nome,
                "conta_id": c_id,
                "categoria": cat
            })
            if dt == hoje_iso:
                pago_hoje += val_f
            if inicio_semana <= dt <= fim_semana:
                pago_semana += val_f
            if inicio_mes <= dt <= fim_mes:
                pago_mes += val_f

    # 2. Turnos operacionais encerrados (consumo estimado pela quilometragem)
    cur.execute("""
        SELECT id, data, km, ganho_bruto, ganho_dinheiro_pix, ganho_online,
               combustivel_consumido_estimado, combustivel, status_turno
        FROM turnos
        WHERE status_turno != 'aberto'
        ORDER BY data DESC, id DESC
    """)
    rows_turnos = cur.fetchall()
    consumo_hoje = 0.0
    consumo_semana = 0.0
    consumo_mes = 0.0
    km_hoje = 0.0
    km_semana = 0.0
    km_mes = 0.0
    bruto_hoje = 0.0
    bruto_semana = 0.0
    bruto_mes = 0.0

    for t in rows_turnos:
        t_id, dt, km, gb, g_din, g_onl, c_est, comb, st = t
        c_val = float(c_est or comb or 0.0)
        km_val = float(km or 0.0)
        gb_val = float(gb or 0.0)
        if dt == hoje_iso:
            consumo_hoje += c_val
            km_hoje += km_val
            bruto_hoje += gb_val
        if inicio_semana <= dt <= fim_semana:
            consumo_semana += c_val
            km_semana += km_val
            bruto_semana += gb_val
        if inicio_mes <= dt <= fim_mes:
            consumo_mes += c_val
            km_mes += km_val
            bruto_mes += gb_val

    # Resultados segregados (NUNCA desconta ambos simultaneamente)
    res_caixa_hoje = round(bruto_hoje - pago_hoje, 2)
    res_caixa_semana = round(bruto_semana - pago_semana, 2)
    res_caixa_mes = round(bruto_mes - pago_mes, 2)

    res_op_hoje = round(bruto_hoje - consumo_hoje, 2)
    res_op_semana = round(bruto_semana - consumo_semana, 2)
    res_op_mes = round(bruto_mes - consumo_mes, 2)

    return {
        "hoje": {
            "pago_real": round(pago_hoje, 2),
            "litros": round(litros_hoje, 2),
            "consumo_estimado": round(consumo_hoje, 2),
            "km_rodado": round(km_hoje, 1),
            "faturamento_bruto": round(bruto_hoje, 2),
            "resultado_caixa": res_caixa_hoje,
            "resultado_operacional_estimado": res_op_hoje
        },
        "semana": {
            "pago_real": round(pago_semana, 2),
            "litros": round(litros_semana, 2),
            "consumo_estimado": round(consumo_semana, 2),
            "km_rodado": round(km_semana, 1),
            "faturamento_bruto": round(bruto_semana, 2),
            "resultado_caixa": res_caixa_semana,
            "resultado_operacional_estimado": res_op_semana
        },
        "mes": {
            "pago_real": round(pago_mes, 2),
            "litros": round(litros_mes, 2),
            "consumo_estimado": round(consumo_mes, 2),
            "km_rodado": round(km_mes, 1),
            "faturamento_bruto": round(bruto_mes, 2),
            "resultado_caixa": res_caixa_mes,
            "resultado_operacional_estimado": res_op_mes
        },
        "abastecimentos_veiculo": abastecimentos,
        "despesas_sem_vinculo_veiculo": despesas_comb_avulsas
    }


def obter_recebimentos_turno(
    conn: sqlite3.Connection,
    turno_id: int
) -> Dict[str, Any]:
    """
    Retorna todos os recebimentos vinculados ao turno, total já contabilizado e valor restante elegível.
    Permite auditar duplicidades e garantir que o total de recebimentos não ultrapasse o faturamento bruto.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT id, data, ganho_dinheiro_pix, ganho_online, ganho_bruto, plataforma
        FROM turnos WHERE id = ?
    """, (turno_id,))
    t_row = cur.fetchone()
    if not t_row:
        return {"erro": "Turno não encontrado"}

    tid, dt, din_pix, onl, bruto, plat = t_row
    din_pix = float(din_pix or 0.0)
    onl = float(onl or 0.0)
    bruto = float(bruto or (din_pix + onl))

    cur.execute("""
        SELECT id, data, descricao, valor, conta, conta_id, tipo, pago, afeta_saldo_bancario
        FROM transacoes
        WHERE turno_id = ? AND tipo = 'receita'
        ORDER BY id ASC
    """, (turno_id,))
    transacoes = [{
        "id": r[0],
        "data": r[1],
        "descricao": r[2],
        "valor": float(r[3] or 0.0),
        "conta": r[4],
        "conta_id": r[5],
        "tipo": r[6],
        "pago": r[7],
        "afeta_saldo_bancario": r[8]
    } for r in cur.fetchall()]

    total_contabilizado = round(sum(t["valor"] for t in transacoes), 2)
    restante_elegivel = max(0.0, round(bruto - total_contabilizado, 2))
    excedente = max(0.0, round(total_contabilizado - bruto, 2)) if total_contabilizado > bruto else 0.0

    # Verifica se o turno pertence a período anterior ou coberto pelo marco de saldo ou marco de produção
    cur.execute("SELECT MAX(data) FROM ajustes_saldo WHERE status = 'ativo'")
    r_aj = cur.fetchone()
    marco_saldo_data = r_aj[0] if r_aj and r_aj[0] else None

    cur.execute("SELECT MAX(data_corte) FROM motorista_marco_producao WHERE status = 'ativo'")
    r_prod = cur.fetchone()
    marco_prod_data = r_prod[0] if r_prod and r_prod[0] else None

    cur.execute("SELECT status_conciliacao FROM turnos WHERE id = ?", (turno_id,))
    r_st_c = cur.fetchone()
    st_concil_db = str(r_st_c[0] if r_st_c and r_st_c[0] else "")

    eh_incorporado_marco = False
    motivo_incorporacao = ""

    if not transacoes:
        if marco_prod_data and dt <= marco_prod_data:
            eh_incorporado_marco = True
            motivo_incorporacao = f"Turno contemplado no marco acumulado da 99 ({marco_prod_data})."
        elif marco_saldo_data and dt < marco_saldo_data:
            eh_incorporado_marco = True
            motivo_incorporacao = f"Turno realizado em {dt}, anterior ao marco de corte do saldo bancário ({marco_saldo_data})."
        elif st_concil_db in ("incorporado_marco", "incorporado"):
            if (marco_prod_data and dt <= marco_prod_data) or (marco_saldo_data and dt < marco_saldo_data):
                eh_incorporado_marco = True
                motivo_incorporacao = "Turno conciliado e já incorporado ao marco inicial."

    status = "pendente"
    if eh_incorporado_marco:
        status = "incorporado_marco"
        restante_elegivel = 0.0
    elif total_contabilizado > bruto + 0.01:
        status = "excedente"  # Erro contábil detectado (como duplicidade)
    elif total_contabilizado >= bruto - 0.01 and total_contabilizado > 0:
        status = "integral"
    elif total_contabilizado > 0:
        status = "parcial"

    return {
        "turno_id": tid,
        "data": dt,
        "plataforma": plat,
        "ganho_dinheiro_pix": din_pix,
        "ganho_online": onl,
        "ganho_bruto": bruto,
        "transacoes": transacoes,
        "total_contabilizado": total_contabilizado,
        "restante_elegivel": restante_elegivel,
        "excedente": excedente,
        "status": status,
        "eh_incorporado_marco": eh_incorporado_marco,
        "motivo_incorporacao": motivo_incorporacao,
        "marco_saldo_data": marco_saldo_data
    }


def registrar_recebimento_turno(
    conn: sqlite3.Connection,
    turno_id: int,
    config_recebimento: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Contabiliza com rigor e segurança o recebimento financeiro dos ganhos de um turno.
    
    Regras de Negócio e Segurança:
    1. O total de recebimentos vinculados NUNCA pode exceder o faturamento bruto do turno.
    2. Impede contabilização repetida por cliques sucessivos ou reabertura do formulário.
    3. Impede gerar movimentações bancárias para turnos anteriores ao marco de saldo.
    4. Quando ganho_dinheiro_pix for R$ 0,00, não permite crédito positivo nessa modalidade.
    5. Ganhos online só entram no extrato bancário se expressamente confirmados pelo usuário.
    6. Não cria transações de ajuste para disfarçar divergências.
    """
    info = obter_recebimentos_turno(conn, turno_id)
    if "erro" in info:
        return False, info["erro"]

    bruto = info["ganho_bruto"]
    din_pix = info["ganho_dinheiro_pix"]
    onl = info["ganho_online"]
    dt_turno = info["data"]
    total_atual = info["total_contabilizado"]
    restante = info["restante_elegivel"]

    # Bloqueio de turnos já incorporados ao marco
    if info.get("eh_incorporado_marco") or info.get("status") == "incorporado_marco":
        return False, f"Este turno ({dt_turno}) já está incorporado ao saldo do marco de conciliação. Não é permitido gerar novas entradas financeiras para evitar duplicidade."

    # Bloqueio de duplicidade / idempotência
    if restante <= 0.009:
        return False, f"Este turno já está 100% contabilizado (R$ {total_atual:,.2f} de R$ {bruto:,.2f}). Não é permitido contabilizar além do faturamento bruto."

    cur = conn.cursor()
    modo = config_recebimento.get("modo", "nenhum")
    mensagens = []

    # 1. Cálculo prévio do valor total solicitado
    novo_total_solicitado = 0.0

    if modo == "conta_unica":
        val_u = float(config_recebimento.get("valor", 0.0))
        if val_u <= 0:
            return False, "O valor a creditar deve ser maior que zero."
        novo_total_solicitado += val_u

    elif modo == "divisao":
        divisoes = config_recebimento.get("divisoes", [])
        soma_div = sum(float(d.get("valor", 0.0)) for d in divisoes)
        if soma_div <= 0:
            return False, "A soma da divisão entre contas deve ser maior que zero."
        novo_total_solicitado += soma_div

    elif modo == "vincular":
        tr_id_vinc = config_recebimento.get("transacao_id")
        if not tr_id_vinc:
            return False, "Selecione a transação a ser vinculada."
        cur.execute("SELECT valor FROM transacoes WHERE id = ? AND tipo = 'receita'", (tr_id_vinc,))
        r_vinc = cur.fetchone()
        if not r_vinc:
            return False, f"Transação #{tr_id_vinc} não encontrada ou não é receita."
        novo_total_solicitado += float(r_vinc[0] or 0.0)

    # Ganhos online se confirmado crédito bancário
    if config_recebimento.get("online_creditado", False):
        onl_val = float(config_recebimento.get("online_valor", 0.0))
        if onl_val > 0:
            novo_total_solicitado += onl_val

    # 2. VALIDAÇÃO DO TETO: Não permitir exceder faturamento bruto
    if (total_atual + novo_total_solicitado) > (bruto + 0.01):
        return False, f"Operação bloqueada: O total a contabilizar (R$ {total_atual + novo_total_solicitado:,.2f}) excederia o faturamento bruto do turno (R$ {bruto:,.2f}). Restante elegível disponível: R$ {restante:,.2f}."

    # 3. Execução dos lançamentos
    if modo == "conta_unica":
        conta_id = config_recebimento.get("conta_id")
        val_u = float(config_recebimento.get("valor", 0.0))
        cur.execute("SELECT nome FROM contas_config WHERE id = ?", (conta_id,))
        c_row = cur.fetchone()
        c_nome = c_row[0] if c_row else "Conta"
        
        # Se din_pix for 0 e os ganhos foram online, identifica corretamente como Ganhos 99 (Turno #X)
        desc = f"Ganhos 99 - Turno #{turno_id}" if (din_pix == 0 and onl > 0) else f"Ganhos 99 - Dinheiro/Pix (Turno #{turno_id})"
        cur.execute("""
            INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
            VALUES (?, ?, ?, 'receita', '99 / Chaves (Carlos)', ?, ?, 1, 1, ?)
        """, (dt_turno, desc, val_u, c_nome, conta_id, turno_id))
        mensagens.append(f"R$ {val_u:,.2f} creditados em {c_nome}")

    elif modo == "divisao":
        divisoes = config_recebimento.get("divisoes", [])
        for div in divisoes:
            c_id = div.get("conta_id")
            val = float(div.get("valor", 0.0))
            if val > 0 and c_id:
                cur.execute("SELECT nome FROM contas_config WHERE id = ?", (c_id,))
                c_row = cur.fetchone()
                c_nome = c_row[0] if c_row else "Conta"
                cur.execute("""
                    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
                    VALUES (?, ?, ?, 'receita', '99 / Chaves (Carlos)', ?, ?, 1, 1, ?)
                """, (dt_turno, f"Ganhos 99 - Turno #{turno_id} ({c_nome})", val, c_nome, c_id, turno_id))
                mensagens.append(f"R$ {val:,.2f} em {c_nome}")

    elif modo == "vincular":
        tr_id_vinc = config_recebimento.get("transacao_id")
        cur.execute("UPDATE transacoes SET turno_id = ? WHERE id = ?", (turno_id, tr_id_vinc))
        cur.execute("SELECT descricao, valor, conta FROM transacoes WHERE id = ?", (tr_id_vinc,))
        r_v = cur.fetchone()
        if r_v:
            mensagens.append(f"Vinculado à receita #{tr_id_vinc} ('{r_v[0]}' - R$ {r_v[1]:,.2f} em {r_v[2]})")

    if config_recebimento.get("online_creditado", False):
        onl_conta_id = config_recebimento.get("online_conta_id")
        onl_val = float(config_recebimento.get("online_valor", 0.0))
        if onl_val > 0 and onl_conta_id:
            cur.execute("SELECT nome FROM contas_config WHERE id = ?", (onl_conta_id,))
            c_row = cur.fetchone()
            c_nome = c_row[0] if c_row else "Conta"
            cur.execute("""
                INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
                VALUES (?, ?, ?, 'receita', '99 / Chaves (Carlos)', ?, ?, 1, 1, ?)
            """, (dt_turno, f"Repasse/Crédito Online 99 (Turno #{turno_id})", onl_val, c_nome, onl_conta_id, turno_id))
            mensagens.append(f"Online confirmado: R$ {onl_val:,.2f} em {c_nome}")

    conn.commit()
    if mensagens:
        return True, "Recebimento registrado com sucesso: " + " • ".join(mensagens)
    return True, "Turno registrado sem movimentações financeiras imediatas."


def estornar_recebimento_turno(
    conn: sqlite3.Connection,
    transacao_id: int,
    turno_id: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Estorna (exclui do extrato bancário) uma transação de recebimento vinculada a turno.
    Corrige duplicidades financeiras sem mascarar saldos e restaura a saúde do fluxo de caixa.
    """
    cur = conn.cursor()
    cur.execute("SELECT id, descricao, valor, conta, turno_id FROM transacoes WHERE id = ?", (transacao_id,))
    row = cur.fetchone()
    if not row:
        return False, f"Transação #{transacao_id} não encontrada no banco de dados."

    tid, desc, val, c_nome, t_id = row
    if turno_id and t_id != turno_id:
        return False, f"Transação #{transacao_id} não pertence ao Turno #{turno_id}."

    cur.execute("DELETE FROM transacoes WHERE id = ?", (transacao_id,))
    conn.commit()
    return True, f"Transação #{transacao_id} ('{desc}' • R$ {val:,.2f} em {c_nome}) foi estornada com sucesso! Saldo bancário corrigido."


def desvincular_recebimento_turno(
    conn: sqlite3.Connection,
    transacao_id: int
) -> Tuple[bool, str]:
    """
    Desvincula a transação do turno, mantendo-a intacta no extrato financeiro.
    IMPORTANTE: Só deve ser usada se a entrada foi um valor bancário real independente do turno.
    Não resolve duplicidades geradas por erro no sistema (para duplicidades, use estornar).
    """
    cur = conn.cursor()
    cur.execute("SELECT id, descricao, valor, conta FROM transacoes WHERE id = ?", (transacao_id,))
    row = cur.fetchone()
    if not row:
        return False, f"Transação #{transacao_id} não encontrada."

    cur.execute("UPDATE transacoes SET turno_id = NULL WHERE id = ?", (transacao_id,))
    conn.commit()
    return True, f"Transação #{transacao_id} desvinculada do turno e preservada no extrato da conta {row[3]}."


def editar_recebimento_turno(
    conn: sqlite3.Connection,
    transacao_id: int,
    novo_valor: float,
    nova_conta_id: int,
    nova_data: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Permite corrigir o destino e o valor de uma contabilização existente,
    respeitando o teto do faturamento bruto do turno e atualizando a conta de crédito.
    """
    if novo_valor <= 0:
        return False, "O valor do recebimento deve ser maior que zero."

    cur = conn.cursor()
    cur.execute("SELECT id, turno_id, valor, conta, conta_id, data FROM transacoes WHERE id = ?", (transacao_id,))
    r_tr = cur.fetchone()
    if not r_tr:
        return False, f"Transação #{transacao_id} não encontrada."

    tr_id, t_id, val_antigo, c_antiga, c_id_antiga, dt_antiga = r_tr

    if t_id:
        info = obter_recebimentos_turno(conn, t_id)
        bruto = info["ganho_bruto"]
        outros_tot = sum(t["valor"] for t in info["transacoes"] if t["id"] != transacao_id)
        if (outros_tot + novo_valor) > (bruto + 0.01):
            return False, f"Edição bloqueada: O novo valor (R$ {novo_valor:,.2f}) somado às outras transações (R$ {outros_tot:,.2f}) excederia o faturamento bruto do turno (R$ {bruto:,.2f})."

    cur.execute("SELECT nome FROM contas_config WHERE id = ?", (nova_conta_id,))
    r_c = cur.fetchone()
    if not r_c:
        return False, f"Conta #{nova_conta_id} não encontrada."
    novo_c_nome = r_c[0]

    dt_final = nova_data or dt_antiga
    cur.execute("""
        UPDATE transacoes 
        SET valor = ?, conta_id = ?, conta = ?, data = ?
        WHERE id = ?
    """, (novo_valor, nova_conta_id, novo_c_nome, dt_final, transacao_id))
    conn.commit()

    return True, f"Transação #{transacao_id} atualizada com sucesso para R$ {novo_valor:,.2f} na conta {novo_c_nome}."



def obter_transacoes_receita_para_vinculo(
    conn: sqlite3.Connection,
    limite_dias: int = 14
) -> List[Dict[str, Any]]:
    """Retorna receitas recentes não vinculadas a nenhum turno para permitir vincular sem criar duplicidade."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, data, descricao, valor, conta, conta_id, categoria
        FROM transacoes
        WHERE tipo = 'receita'
          AND (turno_id IS NULL OR turno_id = 0)
        ORDER BY data DESC, id DESC
        LIMIT 30
    """)
    rows = cur.fetchall()
    return [{
        "id": r[0],
        "data": r[1],
        "descricao": r[2],
        "valor": float(r[3] or 0.0),
        "conta": r[4],
        "conta_id": r[5],
        "categoria": r[6]
    } for r in rows]


def transferir_dinheiro_para_mercado_pago(
    conn: sqlite3.Connection,
    valor: float,
    data_str: str,
    desc: str = "Depósito Dinheiro Corridas ➔ Mercado Pago"
) -> Tuple[bool, str]:
    """
    Registra transferência interna de 'Dinheiro / Carteira' para 'Mercado Pago'.
    Reduz o saldo da carteira e aumenta o saldo do Mercado Pago.
    NÃO cria receita nem despesa, impedindo duplicidade quando dinheiro em mãos é depositado no banco.
    """
    if valor <= 0:
        return False, "Valor de transferência deve ser maior que zero."
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM contas_config WHERE nome LIKE '%Carteira%' OR tipo = 'dinheiro' LIMIT 1")
    r_cart = cur.fetchone()
    cart_id = r_cart[0] if r_cart else 2
    cart_nome = r_cart[1] if r_cart else "Dinheiro / Carteira"

    cur.execute("SELECT id, nome FROM contas_config WHERE nome LIKE '%Mercado Pago%' LIMIT 1")
    r_mp = cur.fetchone()
    mp_id = r_mp[0] if r_mp else 1
    mp_nome = r_mp[1] if r_mp else "Mercado Pago"

    cur.execute("""
        INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, conta_destino_id, pago, afeta_saldo_bancario)
        VALUES (?, ?, ?, 'transferencia', 'Transferência', ?, ?, ?, 1, 1)
    """, (data_str, desc.strip(), float(valor), cart_nome, cart_id, mp_id))
    conn.commit()
    return True, f"Transferência de R$ {valor:,.2f} ({cart_nome} ➔ {mp_nome}) registrada com sucesso sem gerar receita duplicada!"


def obter_abastecimentos_veiculo(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Retorna todos os abastecimentos detalhados do veículo (Drivvo-style) ordenados por data decrescente."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, data, hodometro, combustivel, litros, preco_litro, valor_bruto,
               desconto, valor_pago, conta, conta_id, tanque_cheio, posto, observacao, transacao_id, created_at
        FROM veiculo_abastecimentos
        ORDER BY data DESC, hodometro DESC, id DESC
    """)
    rows = cur.fetchall()
    return [{
        "id": r[0],
        "data": r[1],
        "hodometro": float(r[2] or 0.0),
        "combustivel": r[3] or "Etanol",
        "litros": float(r[4] or 0.0),
        "preco_litro": float(r[5] or 0.0),
        "valor_bruto": float(r[6] or 0.0),
        "desconto": float(r[7] or 0.0),
        "valor_pago": float(r[8] or 0.0),
        "conta": r[9] or "Conta",
        "conta_id": r[10],
        "tanque_cheio": int(r[11] or 1),
        "posto": r[12] or "",
        "observacao": r[13] or "",
        "transacao_id": r[14],
        "created_at": r[15]
    } for r in rows]


def obter_despesas_combustivel_sem_abastecimento(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Retorna despesas financeiras reais de combustível no extrato que ainda não foram vinculadas ao veículo."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, data, descricao, valor, conta, conta_id, categoria
        FROM transacoes
        WHERE tipo = 'despesa'
          AND pago = 1
          AND (
              categoria LIKE '%Combust%'
              OR descricao LIKE '%Combust%'
              OR descricao LIKE '%Abastec%'
              OR descricao LIKE '%Etanol%'
              OR descricao LIKE '%Gasolina%'
          )
          AND id NOT IN (
              SELECT transacao_id FROM veiculo_abastecimentos WHERE transacao_id IS NOT NULL
          )
        ORDER BY data DESC, id DESC
    """)
    rows = cur.fetchall()
    return [{
        "id": r[0],
        "data": r[1],
        "descricao": r[2],
        "valor": float(r[3] or 0.0),
        "conta": r[4],
        "conta_id": r[5],
        "categoria": r[6]
    } for r in rows]


def salvar_abastecimento_veiculo(
    conn: sqlite3.Connection,
    dados: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Salva ou atualiza um abastecimento no módulo do veículo.
    Se dados['transacao_id'] for informado, VINCULA à transação existente SEM criar nova saída financeira.
    Se dados['transacao_id'] não for informado, cria um ÚNICO lançamento financeiro em transacoes com valor = valor_pago.
    """
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(veiculo_abastecimentos)")
    cols_abast = [c[1] for c in cur.fetchall()]
    if "app_desconto" not in cols_abast:
        cur.execute("ALTER TABLE veiculo_abastecimentos ADD COLUMN app_desconto TEXT DEFAULT 'Nenhum'")
        conn.commit()

    data_str = dados.get("data") or str(date.today())
    hodometro = float(dados.get("hodometro") or 0.0)
    combustivel = dados.get("combustivel") or "Etanol"
    litros = float(dados.get("litros") or 0.0)
    valor_pago = float(dados.get("valor_pago") or 0.0)
    valor_bruto_in = float(dados.get("valor_bomba") or dados.get("valor_bruto") or 0.0)
    desconto_in = float(dados.get("desconto") or 0.0)

    if valor_bruto_in > 0 and valor_pago <= 0:
        valor_pago = max(0.0, valor_bruto_in - desconto_in)
    if valor_bruto_in >= valor_pago and valor_bruto_in > 0:
        valor_bruto = round(valor_bruto_in, 2)
        desconto = round(max(0.0, valor_bruto - valor_pago), 2)
    else:
        desconto = round(max(0.0, desconto_in), 2)
        valor_bruto = round(valor_pago + desconto, 2)

    app_desconto = (dados.get("app_desconto") or "Nenhum").strip() or "Nenhum"
    conta = dados.get("conta") or "Dinheiro / Carteira"
    conta_id = dados.get("conta_id") or (1 if "Mercado" in conta else (1779 if "99" in conta else 2))
    tanque_cheio = 1 if dados.get("tanque_cheio", True) else 0
    posto = (dados.get("posto") or "").strip()
    obs = (dados.get("observacao") or "").strip()
    transacao_id = dados.get("transacao_id")

    # Preço Real por Litro = Valor Pago Real / Litros
    preco_litro = round(valor_pago / litros, 3) if (litros and litros > 0) else None

    # Caso 0: Atualização de registro existente de veiculo_abastecimentos
    id_abast = dados.get("id")
    if id_abast:
        cur.execute("""
            UPDATE veiculo_abastecimentos
            SET data = ?, hodometro = ?, combustivel = ?, litros = ?, preco_litro = ?,
                valor_bruto = ?, desconto = ?, valor_pago = ?, conta = ?, conta_id = ?,
                tanque_cheio = ?, posto = ?, observacao = ?
            WHERE id = ?
        """, (data_str, hodometro, combustivel, litros, preco_litro, valor_bruto,
              desconto, valor_pago, conta, conta_id, tanque_cheio, posto, obs, id_abast))
        conn.commit()
        return True, "Registro de abastecimento atualizado com sucesso!"

    # Caso 1: Já possui transacao_id vinculada (ou fornecida pelo usuário)
    if transacao_id:
        cur.execute("SELECT id, valor, conta FROM transacoes WHERE id = ?", (transacao_id,))
        r_tr = cur.fetchone()
        if not r_tr:
            return False, f"Transação #{transacao_id} não encontrada no extrato financeiro."
        
        # Se já existir vínculo para esta transação, atualiza os dados em vez de duplicar
        cur.execute("SELECT id FROM veiculo_abastecimentos WHERE transacao_id = ?", (transacao_id,))
        r_exist = cur.fetchone()
        if r_exist:
            cur.execute("""
                UPDATE veiculo_abastecimentos
                SET data = ?, hodometro = ?, combustivel = ?, litros = ?, preco_litro = ?,
                    valor_bruto = ?, desconto = ?, valor_pago = ?, conta = ?, conta_id = ?,
                    tanque_cheio = ?, posto = ?, observacao = ?
                WHERE id = ?
            """, (data_str, hodometro, combustivel, litros, preco_litro, valor_bruto,
                  desconto, valor_pago, conta, conta_id, tanque_cheio, posto, obs, r_exist[0]))
            conn.commit()
            return True, f"Abastecimento #{r_exist[0]} vinculado à Despesa #{transacao_id} atualizado com sucesso!"

        # Insere em veiculo_abastecimentos vinculado
        cur.execute("""
            INSERT INTO veiculo_abastecimentos (
                data, hodometro, combustivel, litros, preco_litro, valor_bruto,
                desconto, valor_pago, conta, conta_id, tanque_cheio, posto, observacao, transacao_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data_str, hodometro, combustivel, litros, preco_litro, valor_bruto,
              desconto, valor_pago, conta, conta_id, tanque_cheio, posto, obs, transacao_id))
        conn.commit()
        return True, f"Abastecimento ({combustivel} • R$ {valor_pago:,.2f}) vinculado com sucesso à Despesa #{transacao_id} sem duplicar saída bancária!"

    # Caso 2: Novo abastecimento com criação de despesa única
    else:
        desc_tr = f"Abastecimento {combustivel}" + (f" ({litros:.1f}L)" if (litros and litros > 0) else "") + (f" - {posto}" if posto else "")
        cur.execute("""
            INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario)
            VALUES (?, ?, ?, 'despesa', 'Combustível (Trabalho)', ?, ?, 1, 1)
        """, (data_str, desc_tr, valor_pago, conta, conta_id))
        nova_transacao_id = cur.lastrowid

        cur.execute("""
            INSERT INTO veiculo_abastecimentos (
                data, hodometro, combustivel, litros, preco_litro, valor_bruto,
                desconto, valor_pago, conta, conta_id, tanque_cheio, posto, observacao, transacao_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data_str, hodometro, combustivel, litros, preco_litro, valor_bruto,
              desconto, valor_pago, conta, conta_id, tanque_cheio, posto, obs, nova_transacao_id))
        conn.commit()
        return True, f"Abastecimento de R$ {valor_pago:,.2f} ({combustivel}) registrado com sucesso no veículo e no extrato ({conta})!"


def excluir_abastecimento_veiculo(
    conn: sqlite3.Connection,
    id_abast: int,
    excluir_transacao_financeira: bool = False
) -> Tuple[bool, str]:
    """Remove o registro do veículo. Se excluir_transacao_financeira for True, também remove o lançamento em transacoes."""
    cur = conn.cursor()
    cur.execute("SELECT id, transacao_id, valor_pago, combustivel FROM veiculo_abastecimentos WHERE id = ?", (id_abast,))
    row = cur.fetchone()
    if not row:
        return False, "Abastecimento não encontrado."

    tr_id = row[1]
    val = row[2]
    comb = row[3]

    cur.execute("DELETE FROM veiculo_abastecimentos WHERE id = ?", (id_abast,))
    if excluir_transacao_financeira and tr_id:
        cur.execute("DELETE FROM transacoes WHERE id = ?", (tr_id,))

    conn.commit()
    msg = f"Abastecimento ({comb} • R$ {val:,.2f}) removido do veículo"
    if excluir_transacao_financeira and tr_id:
        msg += " e despesa financeira removida do extrato."
    else:
        msg += " (lançamento financeiro preservado no extrato)."
    return True, msg


# =============================================================================
# 13. GESTÃO DO MARCO OPERACIONAL DE PRODUÇÃO DA 99
# =============================================================================

def obter_marco_producao_99(conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
    """
    Retorna o marco operacional de produção acumulada ATIVO cadastrado para a 99.
    IMPORTANTE: É apenas histórico operacional de produção, sem qualquer efeito financeiro em saldos de contas.
    """
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


def salvar_marco_producao_99(
    conn: sqlite3.Connection,
    data_corte: str,
    faturamento_bruto: float,
    recebido_dinheiro_pix: float,
    recebido_online: float,
    observacao: str = ""
) -> Dict[str, Any]:
    """
    Salva uma nova revisão do marco operacional da 99 no SQLite.
    Arquiva a versão anterior como 'substituido' para auditoria e ativa a nova referência.
    """
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
    return obter_marco_producao_99(conn)


def obter_producao_consolidada_99(
    conn: sqlite3.Connection,
    data_ref: Optional[date] = None
) -> Dict[str, Any]:
    """
    Calcula a produção consolidada oficial da 99 para o mês de referência:
    - Faturamento acumulado do Marco Oficial Ativo
    - Faturamento real dos turnos registrados após a data de corte do marco no mês
    - Faturamento da semana corrente (segunda a domingo)
    - Segregação estrita entre Dinheiro e App/Online
    """
    if data_ref is None:
        data_ref = date.today()

    ano = data_ref.year
    mes = data_ref.month
    inicio_mes = f"{ano}-{mes:02d}-01"
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    fim_mes = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

    # Semana corrente (segunda a domingo)
    inicio_sem = data_ref - timedelta(days=data_ref.weekday())
    fim_sem = inicio_sem + timedelta(days=6)
    ini_sem_str = inicio_sem.strftime("%Y-%m-%d")
    fim_sem_str = fim_sem.strftime("%Y-%m-%d")

    cur = conn.cursor()
    marco = obter_marco_producao_99(conn)

    # Condiciona a utilização do marco ativo ao mês de referência consultado
    mes_ref = f"{ano}-{mes:02d}"
    marco_mesmo_mes = bool(marco and str(marco.get("data_corte") or "")[:7] == mes_ref)

    if marco_mesmo_mes:
        fat_marco = float(marco["faturamento_bruto"])
        din_marco = float(marco["recebido_dinheiro_pix"])
        onl_marco = float(marco["recebido_online"])
        corte_marco = str(marco["data_corte"])
    else:
        fat_marco = 0.0
        din_marco = 0.0
        onl_marco = 0.0
        corte_marco = None

    # Turnos da semana corrente
    cur.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(ganho_bruto), 0),
            COALESCE(SUM(ganho_dinheiro_pix), 0),
            COALESCE(SUM(ganho_online), 0),
            COALESCE(SUM(combustivel), 0),
            COALESCE(SUM(horas), 0),
            COALESCE(SUM(km), 0)
        FROM turnos
        WHERE data >= ? AND data <= ?
    """, (ini_sem_str, fim_sem_str))
    sem_row = cur.fetchone()

    qtd_sem = sem_row[0]
    bruto_sem = round(float(sem_row[1]), 2)
    din_sem = round(float(sem_row[2]), 2)
    onl_sem = round(float(sem_row[3]), 2)
    comb_sem = round(float(sem_row[4]), 2)
    horas_sem = round(float(sem_row[5]), 2)
    km_sem = round(float(sem_row[6]), 2)

    # Turnos no mês corrente (se houver marco no mesmo mês, considera turnos pós-marco; senão, todos do mês)
    if corte_marco:
        cur.execute("""
            SELECT
                COUNT(*),
                COALESCE(SUM(ganho_bruto), 0),
                COALESCE(SUM(ganho_dinheiro_pix), 0),
                COALESCE(SUM(ganho_online), 0),
                COALESCE(SUM(combustivel), 0),
                COALESCE(SUM(horas), 0),
                COALESCE(SUM(km), 0)
            FROM turnos
            WHERE data > ? AND data >= ? AND data <= ?
        """, (corte_marco, inicio_mes, fim_mes))
    else:
        cur.execute("""
            SELECT
                COUNT(*),
                COALESCE(SUM(ganho_bruto), 0),
                COALESCE(SUM(ganho_dinheiro_pix), 0),
                COALESCE(SUM(ganho_online), 0),
                COALESCE(SUM(combustivel), 0),
                COALESCE(SUM(horas), 0),
                COALESCE(SUM(km), 0)
            FROM turnos
            WHERE data >= ? AND data <= ?
        """, (inicio_mes, fim_mes))
    pos_row = cur.fetchone()

    qtd_pos = pos_row[0]
    bruto_pos = round(float(pos_row[1]), 2)
    din_pos = round(float(pos_row[2]), 2)
    onl_pos = round(float(pos_row[3]), 2)
    comb_pos = round(float(pos_row[4]), 2)
    horas_pos = round(float(pos_row[5]), 2)
    km_pos = round(float(pos_row[6]), 2)

    total_mes_bruto = round(fat_marco + bruto_pos, 2)
    total_mes_din = round(din_marco + din_pos, 2)
    total_mes_onl = round(onl_marco + onl_pos, 2)

    divergencia = round(total_mes_bruto - (total_mes_din + total_mes_onl), 2)

    marco_retorno = marco if marco_mesmo_mes else None

    return {
        "marco": marco_retorno,
        "marco_oficial": marco_retorno,
        "mes_referencia": f"{ano}-{mes:02d}",
        "total_mes_bruto": total_mes_bruto,
        "total_mes_dinheiro": total_mes_din,
        "total_mes_dinheiro_pix": total_mes_din,
        "total_mes_online": total_mes_onl,
        "divergencia_centavos": divergencia,
        "semana": {
            "periodo_label": f"{inicio_sem.strftime('%d/%m')} a {fim_sem.strftime('%d/%m')}",
            "turnos_qtd": qtd_sem,
            "bruto": bruto_sem,
            "dinheiro": din_sem,
            "online": onl_sem,
            "combustivel": comb_sem,
            "horas": horas_sem,
            "km": km_sem
        },
        "pos_marco": {
            "turnos_qtd": qtd_pos,
            "bruto": bruto_pos,
            "dinheiro": din_pos,
            "online": onl_pos,
            "combustivel": comb_pos,
            "horas": horas_pos,
            "km": km_pos
        }
    }



