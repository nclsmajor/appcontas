import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

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

st.title("Gerente de Faturas")

# --- CONEXÃO COM O GOOGLE SHEETS ---
# Configura a conexão usando a funcionalidade nativa do Streamlit
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE LÓGICA ---
def get_saldo():
    # Lê a aba 'saldo' ignorando o cache para ter dados em tempo real
    df_saldo = conn.read(worksheet="saldo", ttl=0)
    # Pega o valor da primeira linha (que tem id = 1)
    return float(df_saldo['valor'].iloc[0])

def update_saldo(novo_valor):
    saldo_atual = get_saldo()
    df_saldo = conn.read(worksheet="saldo", ttl=0)
    # Atualiza o valor somando com o que tinha antes
    df_saldo.at[0, 'valor'] = saldo_atual + novo_valor
    # Sobrescreve a aba com o novo valor
    conn.update(worksheet="saldo", data=df_saldo)

def get_contas():
    # Lê todas as contas registradas
    df_contas = conn.read(worksheet="contas", ttl=0)
    # Se a planilha estiver vazia e tiver só a linha de cabeçalho, limpa os nulos
    df_contas = df_contas.dropna(how="all")
    if not df_contas.empty:
        # Ordena do menor para o maior valor
        df_contas = df_contas.sort_values(by="valor", ascending=True).reset_index(drop=True)
    return df_contas

def limpar_bd():
    # Apaga as contas (sobrescreve com um dataframe vazio que só tem o cabeçalho)
    df_vazio = pd.DataFrame(columns=["banco", "motivo", "valor"])
    conn.update(worksheet="contas", data=df_vazio)
    
    # Zera o saldo
    df_saldo_zerado = pd.DataFrame({"id": [1], "valor": [0.0]})
    conn.update(worksheet="saldo", data=df_saldo_zerado)

# --- INTERFACE ---
menu = ["Visualizar Contas", "Adicionar Conta", "Adicionar Saldo", "Limpar Registros"]
escolha = st.sidebar.radio("Navegação", menu)

if escolha == "Adicionar Conta":
    st.header("Nova Conta")
    banco = st.text_input("Banco da Dívida")
    valor = st.number_input("Valor da Dívida (R$)", min_value=0.0, format="%.2f")
    motivo = st.selectbox("Motivo da Dívida", ["crédito", "outro motivo"])
    
    if st.button("Salvar Conta"):
        if banco and valor > 0:
            # Lê as contas atuais
            df_contas = conn.read(worksheet="contas", ttl=0).dropna(how="all")
            # Cria a nova linha
            nova_conta = pd.DataFrame({"banco": [banco], "motivo": [motivo], "valor": [valor]})
            # Junta as antigas com a nova
            df_atualizado = pd.concat([df_contas, nova_conta], ignore_index=True)
            # Salva no Sheets
            conn.update(worksheet="contas", data=df_atualizado)
            
            st.success("Conta registrada com sucesso!")
        else:
            st.warning("Preencha o banco e insira um valor maior que zero.")

elif escolha == "Adicionar Saldo":
    st.header("Adicionar Saldo")
    novo_saldo = st.number_input("Valor em dinheiro (R$)", min_value=0.0, format="%.2f")
    
    if st.button("Somar ao Saldo Disponível"):
        if novo_saldo > 0:
            update_saldo(novo_saldo)
            st.success("Saldo adicionado com sucesso!")
        else:
            st.warning("Insira um valor maior que zero.")

elif escolha == "Visualizar Contas":
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
            if sobra > 0:
                st.success(f"Valor suficiente e sobraram R$ {sobra:.2f}!")
            else:
                st.success("Valor suficiente!")
        elif divida_total == 0:
            st.info("Sem faturas pendentes no momento.")
        else:
            falta = divida_total - saldo_atual
            st.error(f"Ainda faltam R$ {falta:.2f} para quitar tudo.")
            
        st.divider()
        
        if not contas.empty:
            df_exibir = contas.rename(columns={"banco": "Banco", "motivo": "Motivo", "valor": "Valor (R$)"})
            st.dataframe(df_exibir, use_container_width=True, hide_index=True)
            
    except Exception as e:
        st.error("Erro de conexão com a planilha. Aguarde alguns segundos e tente novamente.")

elif escolha == "Limpar Registros":
    st.header("Fim do Mês")
    st.warning("Atenção: Isso zerará todo o seu saldo e apagará todas as contas pendentes.")
    
    if st.button("Confirmar Limpeza", type="primary"):
        limpar_bd()
        st.success("Todos os registros do mês foram apagados!")
            
