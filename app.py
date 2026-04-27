import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import time

st.set_page_config(layout="wide")

# ==============================
# TÍTULO
# ==============================

st.title("Rastreador Macro - Reinaldo")

# ==============================
# CONTROLE DE ATUALIZAÇÃO
# ==============================

if "pausado" not in st.session_state:
    st.session_state.pausado = False

col1, col2 = st.columns(2)

with col1:
    if st.button("⏸️ Pausar" if not st.session_state.pausado else "▶️ Retomar"):
        st.session_state.pausado = not st.session_state.pausado

with col2:
    status = "🔴 PAUSADO" if st.session_state.pausado else "🟢 AO VIVO"
    st.write(f"Status: **{status}**")

# ==============================
# SIDEBAR - NOTÍCIAS
# ==============================

st.sidebar.title("📰 Notícias do Mercado")

noticias = [
    {"hora": "09:00", "evento": "Payroll EUA", "impacto": "⭐⭐⭐"},
    {"hora": "10:30", "evento": "Estoque de Petróleo", "impacto": "⭐⭐"},
    {"hora": "15:00", "evento": "Taxa de Juros", "impacto": "⭐⭐⭐"},
]

for n in noticias:
    st.sidebar.write(f"{n['hora']} - {n['evento']} {n['impacto']}")

# ==============================
# PERÍODO
# ==============================

opcoes = {
    "1d": "1m",
    "5d": "5m",
    "15d": "15m",
    "1mo": "30m"
}

if "periodo" not in st.session_state:
    st.session_state.periodo = "1d"

periodo = st.selectbox(
    "Período",
    list(opcoes.keys()),
    index=list(opcoes.keys()).index(st.session_state.periodo)
)

st.session_state.periodo = periodo
intervalo = opcoes[periodo]

# ==============================
# CACHE
# ==============================

@st.cache_data(ttl=60)
def carregar_dados(periodo, intervalo):

    ativos_otimismo = {
        "ES=F": 2.0,
        "NQ=F": 1.8,
        "BZ=F": 1.5,
        "VALE3.SA": 2.0,
        "PETR4.SA": 2.0,
        "ITUB4.SA": 1.8,
        "BBDC4.SA": 1.5
    }

    ativos_risco = {
        "^VIX": 2.0,
        "TLT": 1.5,
        "DX-Y.NYB": 2.0
    }

    dados_otimismo = yf.download(
        list(ativos_otimismo.keys()),
        period=periodo,
        interval=intervalo
    )["Close"]

    dados_risco = yf.download(
        list(ativos_risco.keys()),
        period=periodo,
        interval=intervalo
    )["Close"]

    return dados_otimismo, dados_risco, ativos_otimismo, ativos_risco

# ==============================
# CARREGAR DADOS
# ==============================

dados_otimismo, dados_risco, ativos_otimismo, ativos_risco = carregar_dados(periodo, intervalo)

# ==============================
# PROTEÇÃO
# ==============================

if dados_otimismo.empty or dados_risco.empty:
    st.warning("Dados indisponíveis. Tente outro período.")
    st.stop()

# ==============================
# TIMEZONE
# ==============================

def converter_tz(df):
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert("America/Sao_Paulo")
    else:
        df.index = df.index.tz_convert("America/Sao_Paulo")
    return df

dados_otimismo = converter_tz(dados_otimismo)
dados_risco = converter_tz(dados_risco)

# ==============================
# FILTRAR APENAS HOJE
# ==============================

hoje = pd.Timestamp.now(tz="America/Sao_Paulo").date()

dados_otimismo = dados_otimismo[dados_otimismo.index.date == hoje]
dados_risco = dados_risco[dados_risco.index.date == hoje]
# ==============================
# LIMPEZA
# ==============================

dados_otimismo = dados_otimismo.dropna(how="all")
dados_risco = dados_risco.dropna(how="all")

dados = dados_otimismo.join(dados_risco, how="outer").ffill()

dados_otimismo = dados[dados_otimismo.columns]
dados_risco = dados[dados_risco.columns]

# ==============================
# VARIAÇÃO
# ==============================

shift_map = {
    "1m": 180,
    "5m": 36,
    "15m": 12,
    "30m": 6
}

def variacao_percentual(serie):
    return ((serie / serie.shift(shift_map[intervalo])) - 1) * 100

var_otimismo = pd.DataFrame({
    ativo: variacao_percentual(dados_otimismo[ativo]).fillna(0)
    for ativo in ativos_otimismo
})

var_risco = pd.DataFrame({
    ativo: variacao_percentual(dados_risco[ativo]).fillna(0)
    for ativo in ativos_risco
})

# ==============================
# LINHAS
# ==============================

def linha_ponderada(df, pesos):
    ativos_validos = [a for a in pesos if a in df.columns]
    total_peso = sum(pesos[a] for a in ativos_validos)
    return sum(df[a] * pesos[a] for a in ativos_validos) / total_peso

linha_otimismo = linha_ponderada(var_otimismo, ativos_otimismo)
linha_risco = linha_ponderada(var_risco, ativos_risco)

linha_otimismo.index = linha_otimismo.index.tz_localize(None)
linha_risco.index = linha_risco.index.tz_localize(None)

# ==============================
# GRÁFICO
# ==============================

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=linha_otimismo.index,
    y=linha_otimismo,
    mode="lines",
    name="Otimismo",
    line=dict(color="green", width=2)
))

fig.add_trace(go.Scatter(
    x=linha_risco.index,
    y=linha_risco,
    mode="lines",
    name="Risco",
    line=dict(color="red", width=2)
))

fig.update_layout(
    template="plotly_dark",
    hovermode="x",
    uirevision=True,
    xaxis=dict(rangeslider=dict(visible=True)),
    yaxis=dict(title="Força (%)")
)

st.plotly_chart(
    fig,
    use_container_width=True,
    config={"scrollZoom": True}
)

# ==============================
# SINAL
# ==============================

def gerar_sinal(l_ot, l_rg):
    if l_ot.iloc[-1] > l_rg.iloc[-1]:
        return "🟢 COMPRA"
    elif l_rg.iloc[-1] > l_ot.iloc[-1]:
        return "🔴 VENDA"
    else:
        return "⚪ NEUTRO"

st.subheader(f"Sinal: {gerar_sinal(linha_otimismo, linha_risco)}")

# ==============================
# INFO
# ==============================

st.caption(f"🕒 Atualizado às: {pd.Timestamp.now().strftime('%H:%M:%S')}")

# ==============================
# AUTO REFRESH CONTROLADO
# ==============================

if not st.session_state.pausado:
    time.sleep(60)
    st.rerun()
