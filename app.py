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

st.title("Gerente de Faturas")

# --- CONEXÃO COM O GOOGLE SHEETS ---
# Configura a conexão usando a funcionalidade nativa do Streamlit
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE LÓGICA ---
def get_saldo():
    # Lê a aba 'saldo' ignorando o cache para ter dados em tempo real
    df_saldo = conn.read(worksheet="saldo", ttl=0)
    return float(df_saldo['valor'].iloc[0])

def update_saldo(novo_valor):
    saldo_atual = get_saldo()
    df_saldo = conn.read(worksheet="saldo", ttl=0)
    df_saldo.at[0, 'valor'] = saldo_atual + novo_valor
    conn.update(worksheet="saldo", data=df_saldo)

def get_contas():
    # Lê todas as contas registradas
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
menu = ["Visualizar Contas", "Adicionar Conta", "Adicionar Saldo", "Excluir Conta"]
escolha = st.sidebar.radio("Navegação", menu)

if escolha == "Adicionar Conta":
    st.header("Nova Conta")
    
    tipo_conta = st.radio(
        "Tipo de Conta", 
        ["temporária", "fixa"], 
        help="Fixas: Precisa pagar todo mês (ex: academia, spotify). Temporárias: Somem à medida que for pagando (ex: faturas do cartão)."
    )
    
    cobrador = st.text_input("Quem está cobrando? (Ex: Banco, Supermercado, Academia)")
    valor = st.number_input("Valor da Dívida (R$)", min_value=0.0, format="%.2f")
    
    # --- NOVO CAMPO DE DATA DE VENCIMENTO ---
    data_vencimento = st.date_input("Data de Vencimento", value=date.today(), format="DD/MM/YYYY")
    
    opcao_motivo = st.selectbox("Motivo da Dívida", ["crédito", "outro"])
    
    if opcao_motivo == "outro":
        motivo_digitado = st.text_input("Qual o outro motivo?")
        motivo = motivo_digitado.lower()
    else:
        motivo = opcao_motivo.lower()
    
    if st.button("Salvar Conta"):
        if cobrador and valor > 0 and motivo:
            df_contas = conn.read(worksheet="contas", ttl=0).dropna(how="all")
            
            # Formata a data para salvar como texto (ex: 15/05/2026)
            data_formatada = data_vencimento.strftime("%d/%m/%Y")
            
            # Nova estrutura de colunas atualizada com a data
            nova_conta = pd.DataFrame({
                "cobrador": [cobrador], 
                "motivo": [motivo], 
                "valor": [valor],
                "tipo": [tipo_conta],
                "data_vencimento": [data_formatada]
            })
            df_atualizado = pd.concat([df_contas, nova_conta], ignore_index=True)
            conn.update(worksheet="contas", data=df_atualizado)
            
            st.success("Conta registrada com sucesso!")
        else:
            st.warning("Preencha todos os campos e insira um valor maior que zero.")

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
            # Exibe a coluna de data na tabela de forma elegante
            df_exibir = contas.rename(columns={
                "cobrador": "Cobrador", 
                "motivo": "Motivo", 
                "valor": "Valor (R$)", 
                "tipo": "Tipo",
                "data_vencimento": "Vencimento"
            })
            st.dataframe(df_exibir, use_container_width=True, hide_index=True)
            
    except Exception as e:
        st.error("Erro de conexão com a planilha. Aguarde alguns segundos e tente novamente.")

elif escolha == "Excluir Conta":
    st.header("Excluir Conta")
    st.info("Selecione uma conta para removê-la manualmente (ideal para contas fixas que você cancelou).")
    
    try:
        contas = get_contas()
        if not contas.empty:
            opcoes = []
            for i, row in contas.iterrows():
                # Tenta puxar a data, se não houver (para contas cadastradas antes dessa atualização), deixa em branco
                data_venc = row.get('data_vencimento', 'Sem data')
                if pd.isna(data_venc):
                    data_venc = 'Sem data'
                    
                opcoes.append(f"{row['cobrador']} - R$ {row['valor']} ({row['tipo']}) - Venc: {data_venc}")
            
            conta_selecionada = st.selectbox("Selecione a conta:", range(len(opcoes)), format_func=lambda x: opcoes[x])
            
            if st.button("Excluir", type="primary"):
                excluir_conta(conta_selecionada)
                st.success("Conta excluída com sucesso!")
                st.rerun()
        else:
            st.warning("Não há contas cadastradas.")
    except Exception as e:
        st.error("Erro ao carregar as contas.")
