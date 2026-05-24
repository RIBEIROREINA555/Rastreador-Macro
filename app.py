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
# CONTROLE
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
# OTIMISMO (WIN)
# =========================================================

ativos_otimismo = {

    # S&P FUTURO
    "ES=F": 3.5,

    # NASDAQ FUTURO
    "NQ=F": 3.5,

    # SMALL CAPS EUA
    "RTY=F": 1.5,

    # ETF BRASIL
    "EWZ": 3.0,

    # PETRÓLEO
    "BZ=F": 2.0,

    # CHINA
    "FXI": 1.5
}

# =========================================================
# PESSIMISMO (WDO)
# =========================================================

ativos_pessimismo = {

    # DÓLAR BR
    "USDBRL=X": 4.0,

    # DÓLAR GLOBAL
    "DX-Y.NYB": 3.0,

    # JUROS EUA
    "^TNX": 3.5
}

# =========================================================
# PRESSÃO MACRO
# =========================================================

ativos_macro = {

    # JUROS LONGOS EUA
    "^TNX": 4.0,

    # DÓLAR GLOBAL
    "DX-Y.NYB": 3.5,

    # DÓLAR BR
    "USDBRL=X": 2.5
}

# =========================================================
# DOWNLOAD
# =========================================================

@st.cache_data(ttl=300)

def carregar_dados():

    tickers = list(

        set(

            list(ativos_otimismo.keys())
            +
            list(ativos_pessimismo.keys())
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

            closes[ticker] = (
                dados[ticker]["Close"]
            )

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

df_otimismo = pd.DataFrame()

for ativo in ativos_otimismo:

    if ativo in dados.columns:

        df_otimismo[ativo] = (
            retorno_log(dados[ativo])
        )

df_pessimismo = pd.DataFrame()

for ativo in ativos_pessimismo:

    if ativo in dados.columns:

        df_pessimismo[ativo] = (
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

df_otimismo = limpar(df_otimismo)

df_pessimismo = limpar(df_pessimismo)

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

linha_otimismo = linha_ponderada(
    df_otimismo,
    ativos_otimismo
)

linha_pessimismo = linha_ponderada(
    df_pessimismo,
    ativos_pessimismo
)

linha_macro = linha_ponderada(
    df_macro,
    ativos_macro
)

# =========================================================
# SUAVIZAÇÃO
# =========================================================

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

# PRESSÃO MACRO MAIS SUAVE

linha_macro = (

    linha_macro

    .rolling(6)

    .mean()
)

# =========================================================
# REMOVER TZ
# =========================================================

try:

    linha_otimismo.index = (
        linha_otimismo.index
        .tz_localize(None)
    )

    linha_pessimismo.index = (
        linha_pessimismo.index
        .tz_localize(None)
    )

    linha_macro.index = (
        linha_macro.index
        .tz_localize(None)
    )

except:

    pass

# =========================================================
# GRÁFICO
# =========================================================

fig = go.Figure()

# =========================================================
# OTIMISMO
# =========================================================

fig.add_trace(

    go.Scatter(

        x=linha_otimismo.index,

        y=linha_otimismo,

        mode="lines",

        name="🟢 Otimismo (WIN)",

        line=dict(
            color="lime",
            width=3
        )
    )
)

# =========================================================
# PESSIMISMO
# =========================================================

fig.add_trace(

    go.Scatter(

        x=linha_pessimismo.index,

        y=linha_pessimismo,

        mode="lines",

        name="🔴 Pessimismo (WDO)",

        line=dict(
            color="red",
            width=3
        )
    )
)

# =========================================================
# PRESSÃO MACRO
# =========================================================

fig.add_trace(

    go.Scatter(

        x=linha_macro.index,

        y=linha_macro,

        mode="lines",

        name="🟠 Pressão Macro",

        line=dict(
            color="orange",
            width=2,
            dash="dot"
        ),

        opacity=0.8
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

ultimo_otimismo = (
    linha_otimismo.iloc[-1]
)

ultimo_pessimismo = (
    linha_pessimismo.iloc[-1]
)

ultimo_macro = (
    linha_macro.iloc[-1]
)

# =========================================================
# LEITURA
# =========================================================

if (

    ultimo_otimismo > ultimo_pessimismo
    and
    ultimo_macro < 0

):

    leitura = "🟢 Ambiente favorável para WIN"

elif (

    ultimo_pessimismo > ultimo_otimismo
    and
    ultimo_macro > 0

):

    leitura = "🔴 Ambiente favorável para WDO"

else:

    leitura = "⚪ Ambiente misto"

st.subheader(leitura)

# =========================================================
# MÉTRICAS
# =========================================================

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

    "🟠 Pressão Macro",

    f"{linha_macro.iloc[-1]:.2f}"
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
