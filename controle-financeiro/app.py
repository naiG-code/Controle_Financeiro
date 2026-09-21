"""Controle Financeiro Pessoal - Etapa 1: registrar transação, ver saldo, listar transações."""
from datetime import date

import pandas as pd
import streamlit as st

import database as db

st.set_page_config(page_title="Controle Financeiro", page_icon="💰", layout="centered")

NOMES_MESES = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def formatar_mes(mes):
    if mes == "Todos":
        return "Todos"
    ano, mes_num = mes.split("-")
    return f"{NOMES_MESES[int(mes_num)]}/{ano}"


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
st.subheader("📌 Gastos fixos")

with st.expander("Cadastrar novo gasto fixo"):
    with st.form("form_gasto_fixo", clear_on_submit=True):
        categorias_despesa_novo = db.listar_categorias(conn, tipo="despesa")
        descricao_fixo = st.text_input("Descrição", key="descricao_novo_gasto_fixo")
        col1, col2 = st.columns(2)
        with col1:
            valor_fixo = st.number_input(
                "Valor (R$)", min_value=0.0, step=1.0, format="%.2f", key="valor_novo_gasto_fixo"
            )
            categoria_fixo_nome = st.selectbox(
                "Categoria",
                [c["nome"] for c in categorias_despesa_novo],
                key="categoria_novo_gasto_fixo",
            )
        with col2:
            dia_fixo = st.number_input(
                "Dia do vencimento", min_value=1, max_value=31, step=1, value=5,
                key="dia_novo_gasto_fixo",
            )
            parcelas_fixo = st.number_input(
                "Quantidade de parcelas (0 = sem prazo, repete todo mês)",
                min_value=0, step=1, value=0,
                key="parcelas_novo_gasto_fixo",
            )

        if st.form_submit_button("Adicionar gasto fixo"):
            if not descricao_fixo.strip():
                st.error("Preencha a descrição.")
            elif valor_fixo <= 0:
                st.error("O valor deve ser maior que zero.")
            else:
                categoria_fixo = next(
                    c for c in categorias_despesa_novo if c["nome"] == categoria_fixo_nome
                )
                db.adicionar_gasto_fixo(
                    conn,
                    descricao=descricao_fixo.strip(),
                    valor_centavos=db.reais_para_centavos(valor_fixo),
                    categoria_id=categoria_fixo["id"],
                    dia_vencimento=int(dia_fixo),
                    total_parcelas=int(parcelas_fixo) if parcelas_fixo > 0 else None,
                )
                st.success("Gasto fixo cadastrado!")
                st.rerun()


@st.dialog("Editar gasto fixo")
def editar_gasto_fixo_dialog(gasto):
    categorias_despesa_edicao = db.listar_categorias(conn, tipo="despesa")
    nomes_categorias_despesa = [c["nome"] for c in categorias_despesa_edicao]
    with st.form("form_editar_gasto_fixo"):
        nova_descricao_fixo = st.text_input("Descrição", value=gasto["descricao"])
        col1, col2 = st.columns(2)
        with col1:
            novo_valor_fixo = st.number_input(
                "Valor (R$)", min_value=0.0, step=1.0, format="%.2f",
                value=db.centavos_para_reais(gasto["valor_centavos"]),
            )
            indice_categoria_fixo = (
                nomes_categorias_despesa.index(gasto["categoria"])
                if gasto["categoria"] in nomes_categorias_despesa
                else 0
            )
            nova_categoria_fixo_nome = st.selectbox(
                "Categoria", nomes_categorias_despesa, index=indice_categoria_fixo
            )
        with col2:
            novo_dia_fixo = st.number_input(
                "Dia do vencimento", min_value=1, max_value=31, step=1,
                value=gasto["dia_vencimento"],
            )
            novas_parcelas_fixo = st.number_input(
                "Quantidade de parcelas (0 = sem prazo, repete todo mês)",
                min_value=0, step=1,
                value=gasto["total_parcelas"] or 0,
            )
            if gasto["total_parcelas"] is not None:
                st.caption(f"Já lançadas: {gasto['parcelas_lancadas']} de {gasto['total_parcelas']}")

        col_salvar, col_cancelar = st.columns(2)
        salvar_fixo = col_salvar.form_submit_button("Salvar", type="primary")
        cancelar_fixo = col_cancelar.form_submit_button("Cancelar")

        if salvar_fixo:
            if not nova_descricao_fixo.strip():
                st.error("Preencha a descrição.")
            elif novo_valor_fixo <= 0:
                st.error("O valor deve ser maior que zero.")
            else:
                nova_categoria_fixo = next(
                    c for c in categorias_despesa_edicao if c["nome"] == nova_categoria_fixo_nome
                )
                db.atualizar_gasto_fixo(
                    conn,
                    gasto["id"],
                    descricao=nova_descricao_fixo.strip(),
                    valor_centavos=db.reais_para_centavos(novo_valor_fixo),
                    categoria_id=nova_categoria_fixo["id"],
                    dia_vencimento=int(novo_dia_fixo),
                    total_parcelas=int(novas_parcelas_fixo) if novas_parcelas_fixo > 0 else None,
                )
                st.rerun()
        if cancelar_fixo:
            st.rerun()


gastos_fixos = db.listar_gastos_fixos(conn)
if not gastos_fixos:
    st.info("Nenhum gasto fixo cadastrado ainda.")
else:
    for g in gastos_fixos:
        col1, col2, col3, col4 = st.columns([5, 2, 1, 1])
        with col1:
            detalhe = f"{g['categoria']} · todo dia {g['dia_vencimento']}"
            if g["total_parcelas"] is not None:
                detalhe += f" · {g['parcelas_lancadas']}/{g['total_parcelas']} parcelas"
            st.write(f"{g['descricao']}  \n:gray[{detalhe}]")
        with col2:
            st.write(db.formatar_moeda(g["valor_centavos"]))
        with col3:
            if st.button("✏️", key=f"editar_fixo_{g['id']}", help="Editar gasto fixo"):
                editar_gasto_fixo_dialog(g)
        with col4:
            if st.button("🗑️", key=f"excluir_fixo_{g['id']}", help="Excluir gasto fixo"):
                st.session_state["confirmar_exclusao_fixo_id"] = g["id"]

        if st.session_state.get("confirmar_exclusao_fixo_id") == g["id"]:
            st.warning(
                f'Excluir o gasto fixo "{g["descricao"]}"? '
                "As transações já lançadas a partir dele não são apagadas."
            )
            col_sim, col_nao = st.columns(2)
            if col_sim.button("Sim, excluir", key=f"confirmar_fixo_{g['id']}", type="primary"):
                db.excluir_gasto_fixo(conn, g["id"])
                del st.session_state["confirmar_exclusao_fixo_id"]
                st.rerun()
            if col_nao.button("Cancelar", key=f"cancelar_fixo_{g['id']}"):
                del st.session_state["confirmar_exclusao_fixo_id"]
                st.rerun()

    mes_atual = date.today().strftime("%Y-%m")
    pendentes = db.gastos_fixos_pendentes(conn, mes_atual)
    if pendentes:
        total_pendente = sum(g["valor_centavos"] for g in pendentes)
        if st.button(
            f"Lançar {len(pendentes)} gasto(s) fixo(s) de {formatar_mes(mes_atual)} "
            f"({db.formatar_moeda(total_pendente)})",
            type="primary",
        ):
            db.lancar_gastos_fixos_do_mes(conn, mes_atual)
            st.success("Gastos fixos lançados!")
            st.rerun()
    else:
        st.caption(f"Todos os gastos fixos de {formatar_mes(mes_atual)} já foram lançados.")

st.divider()
st.subheader("Nova transação")

tipo = st.radio(
    "Tipo",
    ["despesa", "receita"],
    horizontal=True,
    format_func=lambda t: "Despesa" if t == "despesa" else "Receita",
    key="tipo_nova_transacao",
)

with st.form("form_transacao", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        data_transacao = st.date_input("Data", value=date.today())
        categorias = db.listar_categorias(conn, tipo=tipo)
        nomes_categorias = [c["nome"] for c in categorias]
        categoria_nome = st.selectbox("Categoria", nomes_categorias)
    with col2:
        valor = st.number_input("Valor (R$)", min_value=0.0, step=1.0, format="%.2f")

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
    novo_tipo = st.radio(
        "Tipo",
        ["despesa", "receita"],
        index=0 if transacao["tipo"] == "despesa" else 1,
        horizontal=True,
        format_func=lambda t: "Despesa" if t == "despesa" else "Receita",
        key=f"tipo_editar_transacao_{transacao['id']}",
    )
    with st.form("form_editar_transacao"):
        col1, col2 = st.columns(2)
        with col1:
            nova_data = st.date_input("Data", value=date.fromisoformat(transacao["data"]))
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
        with col2:
            novo_valor = st.number_input(
                "Valor (R$)",
                min_value=0.0,
                step=1.0,
                format="%.2f",
                value=db.centavos_para_reais(transacao["valor_centavos"]),
            )

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

opcoes_categoria = {"Todas": None}
for c in db.listar_categorias(conn):
    rotulo = f"{c['nome']} ({'Despesa' if c['tipo'] == 'despesa' else 'Receita'})"
    opcoes_categoria[rotulo] = c["id"]

col_filtro1, col_filtro2 = st.columns(2)
with col_filtro1:
    categoria_filtro_rotulo = st.selectbox("Filtrar por categoria", list(opcoes_categoria.keys()))
with col_filtro2:
    meses_disponiveis = ["Todos"] + db.listar_meses_disponiveis(conn)
    mes_filtro = st.selectbox("Filtrar por mês", meses_disponiveis, format_func=formatar_mes)

categoria_filtro_id = opcoes_categoria[categoria_filtro_rotulo]
mes_filtro_valor = None if mes_filtro == "Todos" else mes_filtro
filtro_ativo = categoria_filtro_id is not None or mes_filtro_valor is not None

transacoes = db.listar_transacoes(conn, categoria_id=categoria_filtro_id, mes=mes_filtro_valor)
if not transacoes:
    if filtro_ativo:
        st.info("Nenhuma transação encontrada para esse filtro.")
    else:
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

st.divider()
titulo_resumo = "Resumo"
if mes_filtro_valor:
    titulo_resumo += f" — {formatar_mes(mes_filtro_valor)}"
st.subheader(titulo_resumo)

totais = db.calcular_totais(conn, mes=mes_filtro_valor)
col_receitas, col_despesas, col_saldo = st.columns(3)
col_receitas.metric("Receitas", db.formatar_moeda(totais["receitas"]))
col_despesas.metric("Despesas", db.formatar_moeda(totais["despesas"]))
col_saldo.metric("Saldo do período", db.formatar_moeda(totais["saldo"]))

st.divider()
titulo_grafico = "Gastos por categoria"
if mes_filtro_valor:
    titulo_grafico += f" — {formatar_mes(mes_filtro_valor)}"
st.subheader(titulo_grafico)

gastos_por_categoria = db.calcular_soma_por_categoria(conn, tipo="despesa", mes=mes_filtro_valor)
if not gastos_por_categoria:
    st.info("Nenhuma despesa registrada" + (" nesse mês." if mes_filtro_valor else " ainda."))
else:
    dados_grafico = pd.DataFrame(
        {"Total (R$)": [db.centavos_para_reais(v) for v in gastos_por_categoria.values()]},
        index=list(gastos_por_categoria.keys()),
    )
    st.bar_chart(dados_grafico)
