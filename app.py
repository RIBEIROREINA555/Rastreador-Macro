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
        "🔴 PAUSADO"
        if st.session_state.pausado
        else "🟢 AO VIVO"
    )

    st.markdown(f"### {status}")

# =========================================================
# PERÍODO
# =========================================================

opcoes = {
    "1d": "1m",
    "5d": "5m",
    "15d": "15m",
    "1mo": "30m"
}

if "periodo" not in st.session_state:
    st.session_state.periodo = "5d"

periodo = st.selectbox(
    "Período",
    list(opcoes.keys()),
    index=list(opcoes.keys()).index(
        st.session_state.periodo
    )
)

st.session_state.periodo = periodo

intervalo = opcoes[periodo]

# =========================================================
# SHIFT
# =========================================================

shift_map = {
    "1m": 180,
    "5m": 36,
    "15m": 12,
    "30m": 6
}

shift = shift_map.get(intervalo, 1)

# =========================================================
# ATIVOS
# =========================================================

# =========================================================
# OTIMISMO
# =========================================================

ativos_otimismo = {

    # FUTUROS EUA
    "ES=F": 3.0,
    "NQ=F": 3.0,
    "RTY=F": 1.5,

    # BRASIL
    "EWZ": 2.5,
    "VALE": 2.0,
    "PBR": 2.0,
    "ITUB": 1.8,

    # B3
    "VALE3.SA": 2.0,
    "PETR4.SA": 2.0,
    "ITUB4.SA": 1.8,
    "BBDC4.SA": 1.5,
    "BBAS3.SA": 1.5,
    "WEGE3.SA": 1.5,
    "SMAL11.SA": 1.3,

    # SEMICONDUTORES
    "SOXX": 2.0,

    # BANCOS EUA
    "XLF": 1.5,

    # HIGH YIELD
    "HYG": 1.5
}

# =========================================================
# PESSIMISMO
# =========================================================

ativos_pessimismo = {

    # VOLATILIDADE
    "^VIX": 3.0,

    # DÓLAR GLOBAL
    "DX-Y.NYB": 3.0,

    # DÓLAR BR
    "USDBRL=X": 3.5,

    # JUROS EUA
    "^TNX": 3.0,
    "^TYX": 2.5,

    # OURO
    "GC=F": 1.5,

    # DÓLAR ETF
    "UUP": 1.5
}

# =========================================================
# DOWNLOAD
# =========================================================

@st.cache_data(ttl=60)

def carregar_dados():

    tickers = list(
        set(
            list(ativos_otimismo.keys())
            +
            list(ativos_pessimismo.keys())
        )
    )

    try:

        dados = yf.download(

            tickers=tickers,

            period=periodo,

            interval=intervalo,

            auto_adjust=True,

            progress=False,

            group_by="ticker",

            threads=True
        )

    except Exception as e:

        st.error(f"Erro no download: {e}")

        return None

    # =====================================================
    # EXTRAIR CLOSE
    # =====================================================

    closes = pd.DataFrame()

    for ticker in tickers:

        try:

            closes[ticker] = dados[ticker]["Close"]

        except:

            pass

    if closes.empty:

        return None

    # =====================================================
    # TIMEZONE
    # =====================================================

    try:

        if closes.index.tz is None:

            closes.index = (
                closes.index
                .tz_localize("UTC")
                .tz_convert("America/Sao_Paulo")
            )

        else:

            closes.index = (
                closes.index
                .tz_convert("America/Sao_Paulo")
            )

    except:

        pass

    # =====================================================
    # ÚLTIMAS 12 HORAS
    # =====================================================

    agora = pd.Timestamp.now(
        tz="America/Sao_Paulo"
    )

    limite_12h = (
        agora - pd.Timedelta(hours=12)
    )

    juros = [
        "^TNX",
        "^TYX"
    ]

    colunas_juros = [
        c for c in closes.columns
        if c in juros
    ]

    colunas_normais = [
        c for c in closes.columns
        if c not in juros
    ]

    dados_normais = (
        closes[colunas_normais]
    )

    dados_juros = (
        closes[colunas_juros]
    )

    dados_normais = dados_normais[
        dados_normais.index >= limite_12h
    ]

    closes = pd.concat(
        [dados_normais, dados_juros],
        axis=1
    )

    closes = closes.sort_index()

    closes = closes.ffill()

    return closes

# =========================================================
# CARREGAR
# =========================================================

dados = carregar_dados()

if dados is None or dados.empty:

    st.error(
        "Não foi possível carregar os dados."
    )

    st.stop()

# =========================================================
# VARIAÇÃO
# =========================================================

ativos_invertidos = [

    "^VIX",
    "DX-Y.NYB",
    "USDBRL=X",
    "^TNX",
    "^TYX",
    "UUP"
]

def variacao_percentual(
    serie,
    nome
):

    variacao = (
        np.log(
            serie / serie.shift(shift)
        ) * 100
    )

    if nome in ativos_invertidos:

        variacao = variacao * -1

    return variacao.fillna(0)

# =========================================================
# DATAFRAMES
# =========================================================

var_otimismo = pd.DataFrame({

    ativo: variacao_percentual(
        dados[ativo],
        ativo
    )

    for ativo in ativos_otimismo

    if ativo in dados.columns
})

var_pessimismo = pd.DataFrame({

    ativo: variacao_percentual(
        dados[ativo],
        ativo
    )

    for ativo in ativos_pessimismo

    if ativo in dados.columns
})

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

    if len(ativos_validos) == 0:

        return pd.Series(dtype=float)

    total_peso = sum(

        pesos[a]

        for a in ativos_validos
    )

    linha = sum(

        df[a] * pesos[a]

        for a in ativos_validos

    ) / total_peso

    return linha

linha_otimismo = linha_ponderada(
    var_otimismo,
    ativos_otimismo
)

linha_pessimismo = linha_ponderada(
    var_pessimismo,
    ativos_pessimismo
)

# =========================================================
# SUAVIZAÇÃO
# =========================================================

linha_otimismo = (
    linha_otimismo
    .rolling(5)
    .mean()
)

linha_pessimismo = (
    linha_pessimismo
    .rolling(5)
    .mean()
)

# =========================================================
# FORÇA LÍQUIDA
# =========================================================

forca_liquida = (
    linha_otimismo
    -
    linha_pessimismo
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
# OTIMISMO
# =========================================================

fig.add_trace(

    go.Scatter(

        x=linha_otimismo.index,

        y=linha_otimismo,

        mode="lines",

        name="🟢 Otimismo",

        line=dict(
            color="green",
            width=2
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

        name="🔴 Pessimismo",

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

        line=dict(
            color="white",
            width=3
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

    height=750,

    hovermode="x unified",

    uirevision=True,

    xaxis=dict(

        rangeslider=dict(
            visible=True
        ),

        showgrid=False
    ),

    yaxis=dict(

        title="Força Macro (%)",

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

def gerar_sinal():

    ultimo = forca_liquida.iloc[-1]

    if ultimo > 0.15:

        return "🟢 COMPRA"

    elif ultimo < -0.15:

        return "🔴 VENDA"

    else:

        return "⚪ NEUTRO"

sinal = gerar_sinal()

# =========================================================
# STATUS
# =========================================================

st.subheader(
    f"Sinal Atual: {sinal}"
)

# =========================================================
# MÉTRICAS
# =========================================================

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(

        "🟢 Otimismo",

        f"{linha_otimismo.iloc[-1]:.2f}"
    )

with col2:

    st.metric(

        "🔴 Pessimismo",

        f"{linha_pessimismo.iloc[-1]:.2f}"
    )

with col3:

    st.metric(

        "⚪ Força Líquida",

        f"{forca_liquida.iloc[-1]:.2f}"
    )

# =========================================================
# ATUALIZAÇÃO
# =========================================================

st.caption(

    f"🕒 Atualizado às "

    f"{pd.Timestamp.now().strftime('%H:%M:%S')}"
)

# =========================================================
# AUTO REFRESH
# =========================================================

if not st.session_state.pausado:

    time.sleep(60)

    st.rerun()
