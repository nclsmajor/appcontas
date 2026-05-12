import streamlit as st
import sqlite3
import pandas as pd

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect("faturas.db", check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS contas 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, valor REAL, banco TEXT, motivo TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS saldo 
                 (id INTEGER PRIMARY KEY, valor REAL)''')
    c.execute("INSERT OR IGNORE INTO saldo (id, valor) VALUES (1, 0.0)")
    conn.commit()
    return conn, c

conn, c = init_db()

# --- FUNÇÕES DE LÓGICA ---
def get_saldo():
    c.execute("SELECT valor FROM saldo WHERE id=1")
    return c.fetchone()[0]

def update_saldo(novo_valor):
    saldo_atual = get_saldo()
    c.execute("UPDATE saldo SET valor=? WHERE id=1", (saldo_atual + novo_valor,))
    conn.commit()

def get_contas():
    # Retorna as contas ordenadas da menor para a maior
    c.execute("SELECT banco, motivo, valor FROM contas ORDER BY valor ASC")
    return c.fetchall()

def limpar_bd():
    c.execute("DELETE FROM contas")
    c.execute("UPDATE saldo SET valor=0 WHERE id=1")
    conn.commit()

# --- INTERFACE ---
st.set_page_config(page_title="Gerenciador de Faturas", page_icon="💳")

# Injeção de CSS para dar espaço nas opções do menu lateral
st.markdown(
    """
    <style>
    div[role="radiogroup"] > label {
        margin-bottom: 15px !important; 
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Gerenciador de Faturas")

# Menu de navegação lateral
menu = ["Visualizar Contas", "Adicionar Conta", "Adicionar Saldo", "Limpar Registros"]
escolha = st.sidebar.radio("Navegação", menu)

if escolha == "Adicionar Conta":
    st.header("Nova Conta")
    banco = st.text_input("Banco da Dívida")
    valor = st.number_input("Valor da Dívida (R$)", min_value=0.0, format="%.2f")
    motivo = st.selectbox("Motivo da Dívida", ["crédito", "outro motivo"])
    
    if st.button("Salvar Conta"):
        if banco and valor > 0:
            c.execute("INSERT INTO contas (valor, banco, motivo) VALUES (?, ?, ?)", (valor, banco, motivo))
            conn.commit()
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
    contas = get_contas()
    saldo_atual = get_saldo()
    divida_total = sum(conta[2] for conta in contas)
    
    # --- CARDS DE VALORES LADO A LADO ---
    col1, col2 = st.columns(2)
    col1.metric("Dívida Total", f"R$ {divida_total:.2f}")
    col2.metric("Saldo Disponível", f"R$ {saldo_atual:.2f}")
    
    # Barra de Progresso Gráfica
    if divida_total > 0:
        progresso = min(saldo_atual / divida_total, 1.0)
        st.progress(progresso)
    else:
        st.progress(1.0 if saldo_atual > 0 else 0.0)
        
    # Lógica de Notificação de Sobra/Falta
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
    
    # Tabela com as contas listadas (da menor para a maior)
    if contas:
        df = pd.DataFrame(contas, columns=["Banco", "Motivo", "Valor (R$)"])
        # Exibe a tabela ocultando o índice numérico padrão do Pandas
        st.dataframe(df, use_container_width=True, hide_index=True)

elif escolha == "Limpar Registros":
    st.header("Fim do Mês")
    st.warning("Atenção: Isso zerará todo o seu saldo e apagará todas as contas pendentes para iniciar um novo ciclo.")
    
    if st.button("Confirmar Limpeza", type="primary"):
        limpar_bd()
        st.success("Todos os registros do mês foram apagados!")
    
