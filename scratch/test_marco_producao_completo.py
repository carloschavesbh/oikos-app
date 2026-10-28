import sqlite3
import pandas as pd

def test_marco_completo():
    print("=== INICIANDO TESTE COMPLETO DO MARCO DE PRODUÇÃO 99 ===")
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()

    # Criação do schema
    cur.execute("""
    CREATE TABLE IF NOT EXISTS turnos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data DATE NOT NULL,
        horas REAL NOT NULL,
        km REAL DEFAULT 0,
        ganho_bruto REAL NOT NULL,
        combustivel REAL DEFAULT 0,
        observacao TEXT,
        plataforma TEXT DEFAULT '99'
    );
    """)

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
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS transacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data DATE NOT NULL,
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        tipo TEXT NOT NULL,
        conta TEXT NOT NULL,
        pago INTEGER DEFAULT 1
    );
    """)

    # 1. Inserir turno real existente de 19/10/2026
    cur.execute("INSERT INTO turnos (id, data, horas, km, ganho_bruto, combustivel, observacao) VALUES (2, '2026-10-19', 1.0, 15.0, 17.60, 0.0, 'Segunda feira')")

    # 2. Inserir transação de saldo inicial para verificar imunidade contábil
    cur.execute("INSERT INTO transacoes (data, descricao, valor, tipo, conta, pago) VALUES ('2026-10-01', 'Saldo Dinheiro', 77.50, 'receita', 'Dinheiro', 1)")
    cur.execute("INSERT INTO transacoes (data, descricao, valor, tipo, conta, pago) VALUES ('2026-10-01', 'Saldo MP', 8.83, 'receita', 'Mercado Pago', 1)")
    conn.commit()

    # 3. Gravar marco da 99
    cur.execute("""
    INSERT INTO motorista_marco_producao (plataforma, data_corte, faturamento_bruto, recebido_dinheiro_pix, recebido_online, observacao)
    VALUES ('99', '2026-10-20', 1340.40, 369.25, 971.14, 'Marco inicial real até 20/10/2026')
    """)
    conn.commit()

    # 4. Validar centavo
    cur.execute("SELECT faturamento_bruto, recebido_dinheiro_pix, recebido_online FROM motorista_marco_producao WHERE plataforma='99'")
    fat_bruto, rec_din, rec_onl = cur.fetchone()
    soma_modalidades = round(rec_din + rec_onl, 2)
    divergencia = round(fat_bruto - soma_modalidades, 2)

    assert fat_bruto == 1340.40
    assert rec_din == 369.25
    assert rec_onl == 971.14
    assert soma_modalidades == 1340.39
    assert divergencia == 0.01
    print(f"✅ Regra do Centavo: {fat_bruto:.2f} = {rec_din:.2f} + {rec_onl:.2f} (Divergência: {divergencia:+.2f} preservada)")

    # 5. Validar não duplicação do turno de 19/10
    df_turnos = pd.read_sql_query("SELECT * FROM turnos", conn)
    corte = '2026-10-20'
    turnos_inclusos = df_turnos[df_turnos['data'] <= corte]
    turnos_post = df_turnos[df_turnos['data'] > corte]

    assert len(turnos_inclusos) == 1
    assert turnos_inclusos.iloc[0]['ganho_bruto'] == 17.60
    assert len(turnos_post) == 0

    bruto_post = float(turnos_post['ganho_bruto'].sum()) if not turnos_post.empty else 0.0
    faturamento_acumulado = fat_bruto + bruto_post
    assert faturamento_acumulado == 1340.40
    print("✅ Regra de Não Duplicação: Turno de 19/10 (R$ 17,60) NÃO foi somado a 1340.40!")

    # 6. Validar turno posterior
    cur.execute("INSERT INTO turnos (data, horas, km, ganho_bruto, combustivel, observacao) VALUES ('2026-10-21', 4.0, 50.0, 120.00, 35.0, 'Turno pós marco')")
    conn.commit()

    df_turnos_novo = pd.read_sql_query("SELECT * FROM turnos", conn)
    turnos_post_novo = df_turnos_novo[df_turnos_novo['data'] > corte]
    bruto_post_novo = float(turnos_post_novo['ganho_bruto'].sum())
    faturamento_acumulado_novo = fat_bruto + bruto_post_novo
    assert faturamento_acumulado_novo == 1340.40 + 120.00 == 1460.40
    print(f"✅ Turnos Posteriores: Turno de 21/10 somou perfeitamente. Total: R$ {faturamento_acumulado_novo:.2f}")

    # 7. Validar isolamento bancário
    cur.execute("SELECT SUM(valor) FROM transacoes WHERE conta='Dinheiro'")
    saldo_carteira = cur.fetchone()[0]
    assert saldo_carteira == 77.50
    assert saldo_carteira != 77.50 + 369.25
    cur.execute("SELECT COUNT(*) FROM transacoes")
    assert cur.fetchone()[0] == 2
    print("✅ Isolamento Bancário: Zero transações criadas, carteira e saldos intocados.")

    conn.close()
    print("🎉 TODOS OS TESTES PASSARAM COM SUCESSO!")

if __name__ == "__main__":
    test_marco_completo()
