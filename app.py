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
# PERÍODO E INTERVALO
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

    # --------------------------
    # DOWNLOAD OTIMISMO
    # --------------------------

    dados_otimismo = yf.download(
        tickers=list(ativos_otimismo.keys()),
        period=periodo,
        interval=intervalo,
        auto_adjust=True,
        progress=False
    )["Close"]

    # --------------------------
    # DOWNLOAD RISCO
    # --------------------------

    dados_risco = yf.download(
        tickers=list(ativos_risco.keys()),
        period=periodo,
        interval=intervalo,
        auto_adjust=True,
        progress=False
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
# LIMPEZA E ALINHAMENTO
# ==============================

dados_otimismo = dados_otimismo.dropna(how="all")
dados_risco = dados_risco.dropna(how="all")

# Junta todos os timestamps
dados = dados_otimismo.join(dados_risco, how="outer")

# Preenche buracos
dados = dados.ffill()

# Ordena timestamps
dados = dados.sort_index()

# Separa novamente
dados_otimismo = dados[dados_otimismo.columns]
dados_risco = dados[dados_risco.columns]

# ==============================
# MAPA DE VARIAÇÃO
# ==============================

shift_map = {
    "1m": 180,
    "5m": 36,
    "15m": 12,
    "30m": 6
}

# ==============================
# FUNÇÃO VARIAÇÃO %
# ==============================

def variacao_percentual(serie):

    shift = shift_map.get(intervalo, 1)

    return ((serie / serie.shift(shift)) - 1) * 100

# ==============================
# VARIAÇÕES
# ==============================

var_otimismo = pd.DataFrame({
    ativo: variacao_percentual(dados_otimismo[ativo]).fillna(0)
    for ativo in ativos_otimismo
})

var_risco = pd.DataFrame({
    ativo: variacao_percentual(dados_risco[ativo]).fillna(0)
    for ativo in ativos_risco
})

# ==============================
# LINHA PONDERADA
# ==============================

def linha_ponderada(df, pesos):

    ativos_validos = [a for a in pesos if a in df.columns]

    total_peso = sum(pesos[a] for a in ativos_validos)

    linha = sum(
        df[a] * pesos[a]
        for a in ativos_validos
    ) / total_peso

    return linha

linha_otimismo = linha_ponderada(var_otimismo, ativos_otimismo)
linha_risco = linha_ponderada(var_risco, ativos_risco)

# Remove timezone do gráfico
linha_otimismo.index = linha_otimismo.index.tz_localize(None)
linha_risco.index = linha_risco.index.tz_localize(None)

# ==============================
# GRÁFICO
# ==============================

fig = go.Figure()

# Linha otimista
fig.add_trace(go.Scatter(
    x=linha_otimismo.index,
    y=linha_otimismo,
    mode="lines",
    name="🟢 Otimismo",
    line=dict(color="green", width=2)
))

# Linha risco
fig.add_trace(go.Scatter(
    x=linha_risco.index,
    y=linha_risco,
    mode="lines",
    name="🔴 Risco",
    line=dict(color="red", width=2)
))

# Linha zero
fig.add_hline(
    y=0,
    line_dash="dot",
    line_color="gray"
)

# Layout
fig.update_layout(
    template="plotly_dark",
    hovermode="x unified",
    uirevision=True,
    height=700,

    xaxis=dict(
        rangeslider=dict(visible=True),
        showgrid=False
    ),

    yaxis=dict(
        title="Força (%)",
        showgrid=True
    ),

    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    )
)

# Exibir gráfico
st.plotly_chart(
    fig,
    use_container_width=True,
    config={
        "scrollZoom": True,
        "displaylogo": False
    }
)

# ==============================
# SINAL
# ==============================

def gerar_sinal(l_ot, l_rg):

    ultimo_ot = l_ot.iloc[-1]
    ultimo_rg = l_rg.iloc[-1]

    if ultimo_ot > ultimo_rg:
        return "🟢 COMPRA"

    elif ultimo_rg > ultimo_ot:
        return "🔴 VENDA"

    else:
        return "⚪ NEUTRO"

sinal = gerar_sinal(linha_otimismo, linha_risco)

st.subheader(f"Sinal Atual: {sinal}")

# ==============================
# INFORMAÇÕES
# ==============================

st.caption(
    f"🕒 Atualizado às: "
    f"{pd.Timestamp.now().strftime('%H:%M:%S')}"
)

# ==============================
# AUTO REFRESH
# ==============================

if not st.session_state.pausado:

    time.sleep(60)

    st.rerun()
