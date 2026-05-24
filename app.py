import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import time

# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    layout="wide",
    page_title="Rastreador Macro"
)

st.title("📊 Rastreador Macro - Reinaldo")

# =====================================================
# PAUSA
# =====================================================

if "pausado" not in st.session_state:
    st.session_state.pausado = False

col1, col2 = st.columns(2)

with col1:

    if st.button(
        "⏸️ Pausar"
        if not st.session_state.pausado
        else "▶️ Retomar"
    ):

        st.session_state.pausado = (
            not st.session_state.pausado
        )

with col2:

    st.write(

        "🟢 AO VIVO"

        if not st.session_state.pausado

        else

        "🔴 PAUSADO"
    )

# =====================================================
# PERÍODO
# =====================================================

opcoes = {
    "1d": "1m",
    "5d": "5m"
}

periodo = st.selectbox(
    "Período",
    list(opcoes.keys()),
    index=1
)

intervalo = opcoes[periodo]

# =====================================================
# SHIFT
# =====================================================

shift_map = {
    "1m": 60,
    "5m": 12
}

shift = shift_map[intervalo]

# =====================================================
# ATIVOS
# =====================================================

ativos_otimismo = {

    "ES=F": 3.0,
    "NQ=F": 3.0,
    "RTY=F": 1.5,

    "EWZ": 3.0,

    "VALE": 2.0,
    "PBR": 2.0,
    "ITUB": 1.5,

    "VALE3.SA": 2.0,
    "PETR4.SA": 2.0,
    "ITUB4.SA": 1.5
}

ativos_pessimismo = {

    "USDBRL=X": 4.0,

    "^TNX": 2.5
}

# =====================================================
# DOWNLOAD
# =====================================================

@st.cache_data(ttl=60)

def baixar():

    tickers = list(

        set(
            list(ativos_otimismo.keys())
            +
            list(ativos_pessimismo.keys())
        )
    )

    dados = yf.download(

        tickers=tickers,

        period=periodo,

        interval=intervalo,

        auto_adjust=True,

        progress=False,

        group_by="ticker",

        threads=True
    )

    closes = pd.DataFrame()

    for t in tickers:

        try:

            closes[t] = dados[t]["Close"]

        except:

            pass

    closes = closes.dropna(
        axis=1,
        how="all"
    )

    closes = closes.ffill()

    return closes

dados = baixar()

# =====================================================
# PROTEÇÃO
# =====================================================

if dados.empty:

    st.error("Sem dados.")

    st.stop()

# =====================================================
# VARIAÇÃO LOG
# =====================================================

def retorno(serie):

    return (
        np.log(
            serie / serie.shift(shift)
        ) * 100
    )

# =====================================================
# DATAFRAMES
# =====================================================

var_otimismo = pd.DataFrame()

for ativo in ativos_otimismo:

    if ativo in dados.columns:

        var_otimismo[ativo] = (
            retorno(dados[ativo])
        )

var_pessimismo = pd.DataFrame()

for ativo in ativos_pessimismo:

    if ativo in dados.columns:

        var_pessimismo[ativo] = (
            retorno(dados[ativo])
        )

# =====================================================
# LIMPEZA
# =====================================================

var_otimismo = (
    var_otimismo
    .replace([np.inf, -np.inf], np.nan)
    .fillna(0)
)

var_pessimismo = (
    var_pessimismo
    .replace([np.inf, -np.inf], np.nan)
    .fillna(0)
)

# =====================================================
# LINHA PONDERADA
# =====================================================

def linha(df, pesos):

    ativos_validos = [

        a for a in pesos

        if a in df.columns
    ]

    total = sum(

        pesos[a]

        for a in ativos_validos
    )

    return sum(

        df[a] * pesos[a]

        for a in ativos_validos

    ) / total

linha_otimismo = linha(
    var_otimismo,
    ativos_otimismo
)

linha_pessimismo = linha(
    var_pessimismo,
    ativos_pessimismo
)

# =====================================================
# SUAVIZAÇÃO
# =====================================================

linha_otimismo = (
    linha_otimismo
    .rolling(3)
    .mean()
)

linha_pessimismo = (
    linha_pessimismo
    .rolling(3)
    .mean()
)

# =====================================================
# FORÇA LÍQUIDA
# =====================================================

forca = (
    linha_otimismo
    -
    linha_pessimismo
)

# =====================================================
# GRÁFICO
# =====================================================

fig = go.Figure()

fig.add_trace(

    go.Scatter(

        x=linha_otimismo.index,

        y=linha_otimismo,

        mode="lines",

        name="🟢 Otimismo",

        line=dict(
            color="lime",
            width=2
        )
    )
)

fig.add_trace(

    go.Scatter(

        x=linha_pessimismo.index,

        y=linha_pessimismo,

        mode="lines",

        name="🔴 Pessimismo",

        line=dict(
            color="red",
            width=2
        )
    )
)

fig.add_trace(

    go.Scatter(

        x=forca.index,

        y=forca,

        mode="lines",

        name="⚪ Força Líquida",

        line=dict(
            color="white",
            width=3
        )
    )
)

fig.add_hline(
    y=0,
    line_dash="dot"
)

fig.update_layout(

    template="plotly_dark",

    height=700,

    hovermode="x unified",

    xaxis=dict(
        rangeslider=dict(
            visible=True
        )
    )
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# =====================================================
# SINAL
# =====================================================

ultimo = forca.iloc[-1]

if ultimo > 0.10:

    sinal = "🟢 COMPRA"

elif ultimo < -0.10:

    sinal = "🔴 VENDA"

else:

    sinal = "⚪ NEUTRO"

st.subheader(
    f"Sinal Atual: {sinal}"
)

# =====================================================
# MÉTRICAS
# =====================================================

c1, c2, c3 = st.columns(3)

c1.metric(
    "🟢 Otimismo",
    f"{linha_otimismo.iloc[-1]:.2f}"
)

c2.metric(
    "🔴 Pessimismo",
    f"{linha_pessimismo.iloc[-1]:.2f}"
)

c3.metric(
    "⚪ Força Líquida",
    f"{forca.iloc[-1]:.2f}"
)

# =====================================================
# HORÁRIO
# =====================================================

st.caption(

    f"🕒 Atualizado às "

    f"{pd.Timestamp.now().strftime('%H:%M:%S')}"
)

# =====================================================
# AUTO REFRESH
# =====================================================

if not st.session_state.pausado:

    time.sleep(60)

    st.rerun()
