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
