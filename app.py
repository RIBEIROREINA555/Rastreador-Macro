import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import time

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="Rastreador Macro - Reinaldo",
    layout="wide"
)

st.title("📊 Rastreador Macro - Reinaldo")

# =========================================================
# STATUS
# =========================================================

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

    status = (
        "🟢 AO VIVO"
        if not st.session_state.pausado
        else "🔴 PAUSADO"
    )

    st.markdown(f"### {status}")

# =========================================================
# CONFIG MERCADO
# =========================================================

PERIODO = "5d"
INTERVALO = "5m"

# =========================================================
# SHIFT
# =========================================================

# 12 candles de 5m = 1 hora

SHIFT = 12

# =========================================================
# FLUXO GLOBAL
# =========================================================

ativos_global = {

    # S&P FUTURO
    "ES=F": 3.5,

    # NASDAQ FUTURO
    "NQ=F": 3.5,

    # SMALL CAPS EUA
    "RTY=F": 1.5,

    # BRASIL ANTECIPADO
    "EWZ": 3.0,

    # PETRÓLEO
    "BZ=F": 2.0,

    # CHINA
    "FXI": 1.5
}

# =========================================================
# FLUXO BRASIL
# =========================================================

ativos_brasil = {

    # PETROBRAS
    "PETR4.SA": 3.0,

    # VALE
    "VALE3.SA": 3.0,

    # ITAÚ
    "ITUB4.SA": 2.0,

    # BRADESCO
    "BBDC4.SA": 1.5,

    # SMALL CAPS
    "SMAL11.SA": 1.5
}

# =========================================================
# PRESSÃO MACRO
# =========================================================

ativos_macro = {

    # DÓLAR
    "USDBRL=X": 4.0,

    # JUROS EUA
    "^TNX": 3.5,

    # DÓLAR GLOBAL
    "DX-Y.NYB": 2.5
}

# =========================================================
# DOWNLOAD
# =========================================================

@st.cache_data(ttl=300)

def carregar_dados():

    tickers = list(

        set(

            list(ativos_global.keys())
            +
            list(ativos_brasil.keys())
            +
            list(ativos_macro.keys())
        )
    )

    dados = yf.download(

        tickers=tickers,

        period=PERIODO,

        interval=INTERVALO,

        auto_adjust=True,

        progress=False,

        group_by="ticker",

        threads=True
    )

    closes = pd.DataFrame()

    for ticker in tickers:

        try:

            serie = dados[ticker]["Close"]

            closes[ticker] = serie

        except:

            pass

    closes = closes.dropna(
        axis=1,
        how="all"
    )

    closes = closes.sort_index()

    closes = closes.ffill()

    return closes

# =========================================================
# CARREGAR
# =========================================================

dados = carregar_dados()

if dados.empty:

    st.error(
        "Erro ao carregar dados."
    )

    st.stop()

# =========================================================
# RETORNO LOG
# =========================================================

def retorno_log(serie):

    retorno = (

        np.log(

            serie / serie.shift(SHIFT)

        ) * 100
    )

    return retorno

# =========================================================
# DATAFRAMES
# =========================================================

df_global = pd.DataFrame()

for ativo in ativos_global:

    if ativo in dados.columns:

        df_global[ativo] = (
            retorno_log(dados[ativo])
        )

df_brasil = pd.DataFrame()

for ativo in ativos_brasil:

    if ativo in dados.columns:

        df_brasil[ativo] = (
            retorno_log(dados[ativo])
        )

df_macro = pd.DataFrame()

for ativo in ativos_macro:

    if ativo in dados.columns:

        df_macro[ativo] = (
            retorno_log(dados[ativo])
        )

# =========================================================
# LIMPEZA
# =========================================================

def limpar(df):

    return (

        df

        .replace(
            [np.inf, -np.inf],
            np.nan
        )

        .fillna(0)
    )

df_global = limpar(df_global)

df_brasil = limpar(df_brasil)

df_macro = limpar(df_macro)

# =========================================================
# LINHA PONDERADA
# =========================================================

def linha_ponderada(
    df,
    pesos
):

    ativos_validos = [

        a for a in pesos

        if a in df.columns
    ]

    total = sum(

        pesos[a]

        for a in ativos_validos
    )

    linha = sum(

        df[a] * pesos[a]

        for a in ativos_validos

    ) / total

    return linha

# =========================================================
# LINHAS
# =========================================================

linha_global = linha_ponderada(
    df_global,
    ativos_global
)

linha_brasil = linha_ponderada(
    df_brasil,
    ativos_brasil
)

linha_macro = linha_ponderada(
    df_macro,
    ativos_macro
)

# =========================================================
# SUAVIZAÇÃO
# =========================================================

linha_global = (
    linha_global
    .rolling(3)
    .mean()
)

linha_brasil = (
    linha_brasil
    .rolling(3)
    .mean()
)

linha_macro = (
    linha_macro
    .rolling(3)
    .mean()
)

# =========================================================
# FORÇA LÍQUIDA
# =========================================================

forca_liquida = (

    linha_global
    +
    linha_brasil

    -

    linha_macro
)

# =========================================================
# REMOVER TZ
# =========================================================

try:

    linha_global.index = (
        linha_global.index
        .tz_localize(None)
    )

    linha_brasil.index = (
        linha_brasil.index
        .tz_localize(None)
    )

    linha_macro.index = (
        linha_macro.index
        .tz_localize(None)
    )

    forca_liquida.index = (
        forca_liquida.index
        .tz_localize(None)
    )

except:

    pass

# =========================================================
# GRÁFICO
# =========================================================

fig = go.Figure()

# =========================================================
# GLOBAL
# =========================================================

fig.add_trace(

    go.Scatter(

        x=linha_global.index,

        y=linha_global,

        mode="lines",

        name="🟢 Fluxo Global",

        line=dict(
            color="lime",
            width=3
        )
    )
)

# =========================================================
# BRASIL
# =========================================================

fig.add_trace(

    go.Scatter(

        x=linha_brasil.index,

        y=linha_brasil,

        mode="lines",

        name="🔵 Fluxo Brasil",

        line=dict(
            color="cyan",
            width=3
        )
    )
)

# =========================================================
# MACRO
# =========================================================

fig.add_trace(

    go.Scatter(

        x=linha_macro.index,

        y=linha_macro,

        mode="lines",

        name="🔴 Pressão Macro",

        line=dict(
            color="red",
            width=2
        )
    )
)

# =========================================================
# FORÇA LÍQUIDA
# =========================================================

fig.add_trace(

    go.Scatter(

        x=forca_liquida.index,

        y=forca_liquida,

        mode="lines",

        name="⚪ Força Líquida",

        opacity=0.5,

        line=dict(
            color="white",
            width=1,
            dash="dot"
        )
    )
)

# =========================================================
# LINHA ZERO
# =========================================================

fig.add_hline(

    y=0,

    line_dash="dot",

    line_color="gray"
)

# =========================================================
# LAYOUT
# =========================================================

fig.update_layout(

    template="plotly_dark",

    height=800,

    hovermode="x unified",

    uirevision=True,

    xaxis=dict(

        rangeslider=dict(
            visible=True
        ),

        showgrid=False
    ),

    yaxis=dict(

        title="Fluxo (%)",

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

# =========================================================
# EXIBIR
# =========================================================

st.plotly_chart(

    fig,

    use_container_width=True,

    config={

        "scrollZoom": True,

        "displaylogo": False
    }
)

# =========================================================
# SINAL
# =========================================================

ultimo = forca_liquida.iloc[-1]

if ultimo > 0.20:

    sinal = "🟢 COMPRA"

elif ultimo < -0.20:

    sinal = "🔴 VENDA"

else:

    sinal = "⚪ NEUTRO"

st.subheader(
    f"Sinal Atual: {sinal}"
)

# =========================================================
# MÉTRICAS
# =========================================================

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "🟢 Global",
    f"{linha_global.iloc[-1]:.2f}"
)

c2.metric(
    "🔵 Brasil",
    f"{linha_brasil.iloc[-1]:.2f}"
)

c3.metric(
    "🔴 Macro",
    f"{linha_macro.iloc[-1]:.2f}"
)

c4.metric(
    "⚪ Líquida",
    f"{forca_liquida.iloc[-1]:.2f}"
)

# =========================================================
# HORÁRIO
# =========================================================

st.caption(

    f"🕒 Atualizado às "

    f"{pd.Timestamp.now().strftime('%H:%M:%S')}"
)

# =========================================================
# AUTO REFRESH
# =========================================================

if not st.session_state.pausado:

    time.sleep(300)

    st.rerun()
