"""Controle Financeiro Pessoal - Etapa 1: registrar transação, ver saldo, listar transações."""
from datetime import date

import streamlit as st

import database as db

st.set_page_config(page_title="Controle Financeiro", page_icon="💰", layout="centered")


@st.cache_resource
def get_conn():
    conn = db.conectar()
    db.inicializar_banco(conn)
    return conn


conn = get_conn()

st.title("💰 Controle Financeiro Pessoal")

saldo_inicial = db.get_saldo_inicial_centavos(conn)
ha_transacoes = len(db.listar_transacoes(conn)) > 0

if saldo_inicial == 0 and not ha_transacoes:
    with st.expander("⚙️ Definir saldo inicial (primeira vez)", expanded=True):
        st.write(
            "Informe quanto dinheiro você já tinha antes de começar a usar o app "
            "(pode deixar 0 se quiser começar do zero)."
        )
        valor_inicial = st.number_input(
            "Saldo inicial (R$)", min_value=0.0, step=10.0, format="%.2f"
        )
        if st.button("Salvar saldo inicial"):
            db.set_saldo_inicial_centavos(conn, db.reais_para_centavos(valor_inicial))
            st.success("Saldo inicial salvo!")
            st.rerun()

saldo_atual = db.calcular_saldo_atual(conn)
st.metric("Saldo atual", db.formatar_moeda(saldo_atual))

st.divider()
st.subheader("Nova transação")

with st.form("form_transacao", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        data_transacao = st.date_input("Data", value=date.today())
        tipo = st.radio(
            "Tipo",
            ["despesa", "receita"],
            horizontal=True,
            format_func=lambda t: "Despesa" if t == "despesa" else "Receita",
        )
    with col2:
        valor = st.number_input("Valor (R$)", min_value=0.0, step=1.0, format="%.2f")
        categorias = db.listar_categorias(conn, tipo=tipo)
        nomes_categorias = [c["nome"] for c in categorias]
        categoria_nome = st.selectbox("Categoria", nomes_categorias)

    descricao = st.text_input("Descrição")

    enviado = st.form_submit_button("Registrar transação")
    if enviado:
        if not descricao.strip():
            st.error("Preencha a descrição.")
        elif valor <= 0:
            st.error("O valor deve ser maior que zero.")
        else:
            categoria = next(c for c in categorias if c["nome"] == categoria_nome)
            db.adicionar_transacao(
                conn,
                data=data_transacao.isoformat(),
                descricao=descricao.strip(),
                valor_centavos=db.reais_para_centavos(valor),
                tipo=tipo,
                categoria_id=categoria["id"],
            )
            st.success("Transação registrada!")
            st.rerun()

@st.dialog("Editar transação")
def editar_transacao_dialog(transacao):
    with st.form("form_editar_transacao"):
        col1, col2 = st.columns(2)
        with col1:
            nova_data = st.date_input("Data", value=date.fromisoformat(transacao["data"]))
            novo_tipo = st.radio(
                "Tipo",
                ["despesa", "receita"],
                index=0 if transacao["tipo"] == "despesa" else 1,
                horizontal=True,
                format_func=lambda t: "Despesa" if t == "despesa" else "Receita",
            )
        with col2:
            novo_valor = st.number_input(
                "Valor (R$)",
                min_value=0.0,
                step=1.0,
                format="%.2f",
                value=db.centavos_para_reais(transacao["valor_centavos"]),
            )
            categorias_tipo = db.listar_categorias(conn, tipo=novo_tipo)
            nomes_tipo = [c["nome"] for c in categorias_tipo]
            categoria_atual = db.obter_transacao(conn, transacao["id"])["categoria_id"]
            nomes_atuais_por_id = {c["id"]: c["nome"] for c in categorias_tipo}
            indice_categoria = (
                nomes_tipo.index(nomes_atuais_por_id[categoria_atual])
                if categoria_atual in nomes_atuais_por_id
                else 0
            )
            nova_categoria_nome = st.selectbox("Categoria", nomes_tipo, index=indice_categoria)

        nova_descricao = st.text_input("Descrição", value=transacao["descricao"])

        col_salvar, col_cancelar = st.columns(2)
        salvar = col_salvar.form_submit_button("Salvar", type="primary")
        cancelar = col_cancelar.form_submit_button("Cancelar")

        if salvar:
            if not nova_descricao.strip():
                st.error("Preencha a descrição.")
            elif novo_valor <= 0:
                st.error("O valor deve ser maior que zero.")
            else:
                nova_categoria = next(c for c in categorias_tipo if c["nome"] == nova_categoria_nome)
                db.atualizar_transacao(
                    conn,
                    transacao["id"],
                    data=nova_data.isoformat(),
                    descricao=nova_descricao.strip(),
                    valor_centavos=db.reais_para_centavos(novo_valor),
                    tipo=novo_tipo,
                    categoria_id=nova_categoria["id"],
                )
                st.rerun()
        if cancelar:
            st.rerun()


st.divider()
st.subheader("Transações")

transacoes = db.listar_transacoes(conn)
if not transacoes:
    st.info("Nenhuma transação registrada ainda.")
else:
    for t in transacoes:
        sinal = "+" if t["tipo"] == "receita" else "-"
        cor = "green" if t["tipo"] == "receita" else "red"
        col1, col2, col3, col4, col5 = st.columns([2, 5, 2, 1, 1])
        with col1:
            st.write(t["data"])
        with col2:
            st.write(f"{t['descricao']}  \n:gray[{t['categoria']}]")
        with col3:
            st.markdown(f":{cor}[{sinal} {db.formatar_moeda(t['valor_centavos'])}]")
        with col4:
            if st.button("✏️", key=f"editar_{t['id']}", help="Editar transação"):
                editar_transacao_dialog(t)
        with col5:
            if st.button("🗑️", key=f"excluir_{t['id']}", help="Excluir transação"):
                st.session_state["confirmar_exclusao_id"] = t["id"]

        if st.session_state.get("confirmar_exclusao_id") == t["id"]:
            st.warning(f'Excluir a transação "{t["descricao"]}"? Essa ação não pode ser desfeita.')
            col_sim, col_nao = st.columns(2)
            if col_sim.button("Sim, excluir", key=f"confirmar_{t['id']}", type="primary"):
                db.excluir_transacao(conn, t["id"])
                del st.session_state["confirmar_exclusao_id"]
                st.rerun()
            if col_nao.button("Cancelar", key=f"cancelar_{t['id']}"):
                del st.session_state["confirmar_exclusao_id"]
                st.rerun()
