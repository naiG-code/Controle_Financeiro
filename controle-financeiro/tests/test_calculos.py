"""Testes dos cálculos financeiros (saldo e somas por categoria)."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database as db


def nova_conexao():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.inicializar_banco(conn)
    return conn


def test_saldo_atual_sem_transacoes_e_zero():
    conn = nova_conexao()
    assert db.calcular_saldo_atual(conn) == 0


def test_saldo_atual_considera_saldo_inicial():
    conn = nova_conexao()
    db.set_saldo_inicial_centavos(conn, 10000)  # R$ 100,00
    assert db.calcular_saldo_atual(conn) == 10000


def test_saldo_atual_soma_receita_e_subtrai_despesa():
    conn = nova_conexao()
    categoria_receita = db.listar_categorias(conn, tipo="receita")[0]
    categoria_despesa = db.listar_categorias(conn, tipo="despesa")[0]

    db.adicionar_transacao(
        conn, "2026-01-01", "Salário", 300000, "receita", categoria_receita["id"]
    )
    db.adicionar_transacao(
        conn, "2026-01-02", "Mercado", 15000, "despesa", categoria_despesa["id"]
    )

    assert db.calcular_saldo_atual(conn) == 300000 - 15000


def test_soma_por_categoria():
    conn = nova_conexao()
    alimentacao = next(
        c for c in db.listar_categorias(conn, tipo="despesa") if c["nome"] == "Alimentação"
    )
    transporte = next(
        c for c in db.listar_categorias(conn, tipo="despesa") if c["nome"] == "Transporte"
    )

    db.adicionar_transacao(conn, "2026-01-01", "Mercado", 5000, "despesa", alimentacao["id"])
    db.adicionar_transacao(conn, "2026-01-02", "Restaurante", 3000, "despesa", alimentacao["id"])
    db.adicionar_transacao(conn, "2026-01-03", "Ônibus", 1000, "despesa", transporte["id"])

    resultado = db.calcular_soma_por_categoria(conn, tipo="despesa")

    assert resultado["Alimentação"] == 8000
    assert resultado["Transporte"] == 1000


def test_valores_quebrados_nao_perdem_precisao():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]

    for _ in range(10):
        db.adicionar_transacao(
            conn,
            "2026-01-01",
            "Cafezinho",
            db.reais_para_centavos(0.10),
            "despesa",
            categoria["id"],
        )

    saldo = db.calcular_saldo_atual(conn)
    assert saldo == -100  # 10 x R$0,10 = R$1,00 exatos, sem sobra de ponto flutuante


def test_formatar_moeda():
    assert db.formatar_moeda(123456) == "R$ 1.234,56"
    assert db.formatar_moeda(100) == "R$ 1,00"
    assert db.formatar_moeda(0) == "R$ 0,00"


def test_atualizar_transacao_altera_campos_e_saldo():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_transacao(conn, "2026-01-01", "Mercado", 5000, "despesa", categoria["id"])
    transacao_id = db.listar_transacoes(conn)[0]["id"]
    outra_categoria = db.listar_categorias(conn, tipo="despesa")[1]

    db.atualizar_transacao(
        conn,
        transacao_id,
        data="2026-01-02",
        descricao="Mercado (corrigido)",
        valor_centavos=7000,
        tipo="despesa",
        categoria_id=outra_categoria["id"],
    )

    transacao = db.obter_transacao(conn, transacao_id)
    assert transacao["descricao"] == "Mercado (corrigido)"
    assert transacao["valor_centavos"] == 7000
    assert transacao["categoria_id"] == outra_categoria["id"]
    assert db.calcular_saldo_atual(conn) == -7000


def test_excluir_transacao_remove_e_atualiza_saldo():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_transacao(conn, "2026-01-01", "Mercado", 5000, "despesa", categoria["id"])
    transacao_id = db.listar_transacoes(conn)[0]["id"]

    db.excluir_transacao(conn, transacao_id)

    assert db.obter_transacao(conn, transacao_id) is None
    assert db.listar_transacoes(conn) == []
    assert db.calcular_saldo_atual(conn) == 0


def test_listar_transacoes_filtra_por_categoria():
    conn = nova_conexao()
    alimentacao = next(
        c for c in db.listar_categorias(conn, tipo="despesa") if c["nome"] == "Alimentação"
    )
    transporte = next(
        c for c in db.listar_categorias(conn, tipo="despesa") if c["nome"] == "Transporte"
    )

    db.adicionar_transacao(conn, "2026-01-01", "Mercado", 5000, "despesa", alimentacao["id"])
    db.adicionar_transacao(conn, "2026-01-02", "Ônibus", 1000, "despesa", transporte["id"])

    resultado = db.listar_transacoes(conn, categoria_id=alimentacao["id"])

    assert len(resultado) == 1
    assert resultado[0]["descricao"] == "Mercado"


def test_listar_transacoes_filtra_por_mes():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_transacao(conn, "2026-01-15", "Janeiro", 1000, "despesa", categoria["id"])
    db.adicionar_transacao(conn, "2026-02-10", "Fevereiro", 2000, "despesa", categoria["id"])

    resultado = db.listar_transacoes(conn, mes="2026-02")

    assert len(resultado) == 1
    assert resultado[0]["descricao"] == "Fevereiro"


def test_calcular_totais_soma_receitas_e_despesas():
    conn = nova_conexao()
    categoria_receita = db.listar_categorias(conn, tipo="receita")[0]
    categoria_despesa = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_transacao(
        conn, "2026-01-05", "Salário", 300000, "receita", categoria_receita["id"]
    )
    db.adicionar_transacao(
        conn, "2026-01-10", "Mercado", 15000, "despesa", categoria_despesa["id"]
    )

    totais = db.calcular_totais(conn)

    assert totais == {"receitas": 300000, "despesas": 15000, "saldo": 285000}


def test_calcular_totais_filtra_por_mes():
    conn = nova_conexao()
    categoria_receita = db.listar_categorias(conn, tipo="receita")[0]
    categoria_despesa = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_transacao(
        conn, "2026-01-05", "Salário", 300000, "receita", categoria_receita["id"]
    )
    db.adicionar_transacao(
        conn, "2026-02-10", "Mercado", 15000, "despesa", categoria_despesa["id"]
    )

    totais = db.calcular_totais(conn, mes="2026-01")

    assert totais == {"receitas": 300000, "despesas": 0, "saldo": 300000}


def test_calcular_totais_sem_transacoes_e_zero():
    conn = nova_conexao()
    assert db.calcular_totais(conn) == {"receitas": 0, "despesas": 0, "saldo": 0}


def test_soma_por_categoria_filtra_por_mes():
    conn = nova_conexao()
    alimentacao = next(
        c for c in db.listar_categorias(conn, tipo="despesa") if c["nome"] == "Alimentação"
    )

    db.adicionar_transacao(conn, "2026-01-05", "Mercado", 5000, "despesa", alimentacao["id"])
    db.adicionar_transacao(conn, "2026-02-05", "Mercado", 3000, "despesa", alimentacao["id"])

    resultado = db.calcular_soma_por_categoria(conn, tipo="despesa", mes="2026-01")

    assert resultado["Alimentação"] == 5000


def test_listar_meses_disponiveis_ordena_do_mais_recente():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_transacao(conn, "2026-01-15", "Janeiro", 1000, "despesa", categoria["id"])
    db.adicionar_transacao(conn, "2026-03-10", "Março", 2000, "despesa", categoria["id"])
    db.adicionar_transacao(conn, "2026-02-05", "Fevereiro", 3000, "despesa", categoria["id"])

    assert db.listar_meses_disponiveis(conn) == ["2026-03", "2026-02", "2026-01"]


def test_adicionar_gasto_fixo_e_listar():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_gasto_fixo(conn, "Aluguel", 120000, categoria["id"], dia_vencimento=5)

    gastos = db.listar_gastos_fixos(conn)
    assert len(gastos) == 1
    assert gastos[0]["descricao"] == "Aluguel"
    assert gastos[0]["dia_vencimento"] == 5


def test_atualizar_gasto_fixo_altera_valor():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_gasto_fixo(conn, "Aluguel", 120000, categoria["id"], dia_vencimento=5)
    gasto_id = db.listar_gastos_fixos(conn)[0]["id"]

    db.atualizar_gasto_fixo(conn, gasto_id, "Aluguel", 135000, categoria["id"], dia_vencimento=10)

    gasto = db.obter_gasto_fixo(conn, gasto_id)
    assert gasto["valor_centavos"] == 135000
    assert gasto["dia_vencimento"] == 10


def test_lancar_gastos_fixos_do_mes_cria_transacoes():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_gasto_fixo(conn, "Aluguel", 120000, categoria["id"], dia_vencimento=5)
    db.adicionar_gasto_fixo(conn, "Internet", 10000, categoria["id"], dia_vencimento=15)

    quantidade = db.lancar_gastos_fixos_do_mes(conn, "2026-03")

    assert quantidade == 2
    transacoes = db.listar_transacoes(conn, mes="2026-03")
    datas = sorted(t["data"] for t in transacoes)
    assert datas == ["2026-03-05", "2026-03-15"]


def test_lancar_gastos_fixos_do_mes_nao_duplica():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_gasto_fixo(conn, "Aluguel", 120000, categoria["id"], dia_vencimento=5)

    db.lancar_gastos_fixos_do_mes(conn, "2026-03")
    quantidade_segunda_vez = db.lancar_gastos_fixos_do_mes(conn, "2026-03")

    assert quantidade_segunda_vez == 0
    assert len(db.listar_transacoes(conn, mes="2026-03")) == 1


def test_lancar_gastos_fixos_respeita_ultimo_dia_do_mes():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_gasto_fixo(conn, "Assinatura", 5000, categoria["id"], dia_vencimento=31)

    db.lancar_gastos_fixos_do_mes(conn, "2026-02")  # fevereiro não tem dia 31

    transacoes = db.listar_transacoes(conn, mes="2026-02")
    assert transacoes[0]["data"] == "2026-02-28"


def test_excluir_gasto_fixo_mantem_transacoes_historicas():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_gasto_fixo(conn, "Aluguel", 120000, categoria["id"], dia_vencimento=5)
    gasto_id = db.listar_gastos_fixos(conn)[0]["id"]
    db.lancar_gastos_fixos_do_mes(conn, "2026-03")

    db.excluir_gasto_fixo(conn, gasto_id)

    assert db.listar_gastos_fixos(conn) == []
    transacoes = db.listar_transacoes(conn, mes="2026-03")
    assert len(transacoes) == 1
    assert transacoes[0]["descricao"] == "Aluguel"


def test_gasto_fixo_parcelado_mostra_progresso():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_gasto_fixo(
        conn, "Geladeira", 30000, categoria["id"], dia_vencimento=10, total_parcelas=3
    )

    db.lancar_gastos_fixos_do_mes(conn, "2026-01")

    gasto = db.listar_gastos_fixos(conn)[0]
    assert gasto["total_parcelas"] == 3
    assert gasto["parcelas_lancadas"] == 1


def test_gasto_fixo_parcelado_desativa_apos_ultima_parcela():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_gasto_fixo(
        conn, "Geladeira", 30000, categoria["id"], dia_vencimento=10, total_parcelas=2
    )

    db.lancar_gastos_fixos_do_mes(conn, "2026-01")
    assert len(db.listar_gastos_fixos(conn)) == 1  # ainda ativo, falta 1 parcela

    db.lancar_gastos_fixos_do_mes(conn, "2026-02")
    assert db.listar_gastos_fixos(conn) == []  # desativado, cumpriu as 2 parcelas
    assert len(db.listar_gastos_fixos(conn, apenas_ativos=False)) == 1
    assert len(db.listar_transacoes(conn)) == 2


def test_gasto_fixo_sem_total_parcelas_nao_desativa():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_gasto_fixo(conn, "Internet", 10000, categoria["id"], dia_vencimento=15)

    for mes in ("2026-01", "2026-02", "2026-03"):
        db.lancar_gastos_fixos_do_mes(conn, mes)

    assert len(db.listar_gastos_fixos(conn)) == 1


def test_editar_total_parcelas_reativa_gasto_fixo_concluido():
    conn = nova_conexao()
    categoria = db.listar_categorias(conn, tipo="despesa")[0]
    db.adicionar_gasto_fixo(
        conn, "Geladeira", 30000, categoria["id"], dia_vencimento=10, total_parcelas=1
    )
    gasto_id = db.listar_gastos_fixos(conn)[0]["id"]
    db.lancar_gastos_fixos_do_mes(conn, "2026-01")
    assert db.listar_gastos_fixos(conn) == []  # já concluiu a única parcela

    db.atualizar_gasto_fixo(
        conn, gasto_id, "Geladeira", 30000, categoria["id"], dia_vencimento=10, total_parcelas=3
    )

    gastos_ativos = db.listar_gastos_fixos(conn)
    assert len(gastos_ativos) == 1
    assert gastos_ativos[0]["parcelas_lancadas"] == 1
    assert gastos_ativos[0]["total_parcelas"] == 3
