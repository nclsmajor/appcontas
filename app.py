import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import date

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerenciador de Faturas", page_icon="💳")

# Injeção de CSS
st.markdown(
    """
    <style>
    div[role="radiogroup"] > label { margin-bottom: 15px !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# --- INICIALIZAÇÃO DO ESTADO DE LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# --- FUNÇÕES DE LOGIN ---
def login():
    with st.sidebar.expander("🔐 Login ADM"):
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            # Busca credenciais nos Secrets do Streamlit
            if usuario == st.secrets["credentials"]["usuario"] and senha == st.secrets["credentials"]["senha"]:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos")

def logout():
    st.session_state.autenticado = False
    st.rerun()

# --- CONEXÃO COM O GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE LÓGICA ---
def get_saldo():
    df_saldo = conn.read(worksheet="saldo", ttl=0)
    return float(df_saldo['valor'].iloc[0])

def update_saldo(novo_valor):
    saldo_atual = get_saldo()
    df_saldo = conn.read(worksheet="saldo", ttl=0)
    df_saldo.at[0, 'valor'] = saldo_atual + novo_valor
    conn.update(worksheet="saldo", data=df_saldo)

def get_contas():
    df_contas = conn.read(worksheet="contas", ttl=0)
    df_contas = df_contas.dropna(how="all")
    if not df_contas.empty:
        df_contas = df_contas.sort_values(by="valor", ascending=True).reset_index(drop=True)
    return df_contas

def excluir_conta(index):
    df_contas = get_contas()
    df_contas = df_contas.drop(index)
    conn.update(worksheet="contas", data=df_contas)

# --- INTERFACE ---
st.title("Gerente de Faturas")

# Definição do Menu baseado no Login
if st.session_state.autenticado:
    menu = ["Visualizar Contas", "Adicionar Conta", "Adicionar Saldo", "Excluir Conta"]
    st.sidebar.success("Logado como ADM")
    if st.sidebar.button("Sair"):
        logout()
else:
    menu = ["Visualizar Contas"]
    login() # Mostra o formulário de login na lateral para visitantes

escolha = st.sidebar.radio("Navegação", menu)

# --- TELAS ---

if escolha == "Visualizar Contas":
    st.header("Resumo do Mês")
    try:
        contas = get_contas()
        saldo_atual = get_saldo()
        
        if not contas.empty:
            divida_total = contas['valor'].sum()
        else:
            divida_total = 0.0
        
        col1, col2 = st.columns(2)
        col1.metric("Dívida Total", f"R$ {divida_total:.2f}")
        col2.metric("Saldo Disponível", f"R$ {saldo_atual:.2f}")
        
        if divida_total > 0:
            progresso = min(saldo_atual / divida_total, 1.0)
            st.progress(progresso)
        else:
            st.progress(1.0 if saldo_atual > 0 else 0.0)
            
        if saldo_atual >= divida_total and divida_total > 0:
            sobra = saldo_atual - divida_total
            st.success(f"Valor suficiente! Sobra: R$ {sobra:.2f}")
        elif divida_total == 0:
            st.info("Sem faturas pendentes.")
        else:
            falta = divida_total - saldo_atual
            st.error(f"Faltam R$ {falta:.2f} para quitar tudo.")
            
        st.divider()
        if not contas.empty:
            df_exibir = contas.rename(columns={
                "cobrador": "Cobrador", "motivo": "Motivo", 
                "valor": "Valor (R$)", "tipo": "Tipo", "data_vencimento": "Vencimento"
            })
            st.dataframe(df_exibir, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error("Erro ao conectar com a planilha.")

# As telas abaixo só aparecem para o ADM, pois o menu é restrito
elif escolha == "Adicionar Conta":
    st.header("Nova Conta")
    tipo_conta = st.radio("Tipo", ["temporária", "fixa"])
    cobrador = st.text_input("Cobrador")
    valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
    data_vencimento = st.date_input("Data de Vencimento", value=date.today(), format="DD/MM/YYYY")
    opcao_motivo = st.selectbox("Motivo", ["crédito", "outro"])
    
    motivo = st.text_input("Especifique o motivo").lower() if opcao_motivo == "outro" else opcao_motivo.lower()

    if st.button("Salvar"):
        if cobrador and valor > 0:
            df_contas = conn.read(worksheet="contas", ttl=0).dropna(how="all")
            data_formatada = data_vencimento.strftime("%d/%m/%Y")
            nova_conta = pd.DataFrame({
                "cobrador": [cobrador], "motivo": [motivo], "valor": [valor],
                "tipo": [tipo_conta], "data_vencimento": [data_formatada]
            })
            conn.update(worksheet="contas", data=pd.concat([df_contas, nova_conta], ignore_index=True))
            st.success("Conta registrada!")
        else:
            st.warning("Preencha os campos obrigatórios.")

elif escolha == "Adicionar Saldo":
    st.header("Adicionar Saldo")
    novo_saldo = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
    if st.button("Somar Saldo"):
        if novo_saldo > 0:
            update_saldo(novo_saldo)
            st.success("Saldo atualizado!")

elif escolha == "Excluir Conta":
    st.header("Excluir Conta")
    try:
        contas = get_contas()
        if not contas.empty:
            opcoes = [f"{r['cobrador']} - R$ {r['valor']} - {r['data_vencimento']}" for i, r in contas.iterrows()]
            selecao = st.selectbox("Selecione para excluir:", range(len(opcoes)), format_func=lambda x: opcoes[x])
            if st.button("Confirmar Exclusão", type="primary"):
                excluir_conta(selecao)
                st.success("Excluída!")
                st.rerun()
    except:
        st.error("Erro ao carregar lista.")
