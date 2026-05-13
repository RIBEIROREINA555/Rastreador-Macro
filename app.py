import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import time

# ==================================================
# CONFIG
# ==================================================

st.set_page_config(layout="wide")

# ==================================================
# TÍTULO
# ==================================================

st.title("Rastreador Macro - Reinaldo")

# ==================================================
# CONTROLE
# ==================================================

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

    st.write(f"Status: **{status}**")

# ==================================================
# SIDEBAR
# ==================================================

st.sidebar.title("📰 Notícias do Mercado")

noticias = [
    {
        "hora": "09:00",
        "evento": "Payroll EUA",
        "impacto": "⭐⭐⭐"
    },
    {
        "hora": "10:30",
        "evento": "Petróleo",
        "impacto": "⭐⭐"
    },
    {
        "hora": "15:00",
        "evento": "Juros",
        "impacto": "⭐⭐⭐"
    }
]

for n in noticias:

    st.sidebar.write(
        f"{n['hora']} - "
        f"{n['evento']} "
        f"{n['impacto']}"
    )

# ==================================================
# PERÍODO
# ==================================================

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
    index=list(opcoes.keys()).index(
        st.session_state.periodo
    )
)

st.session_state.periodo = periodo

intervalo = opcoes[periodo]

# ==================================================
# CACHE
# ==================================================

@st.cache_data(ttl=60)
def carregar_dados():

    # ==============================================
    # OTIMISMO
    # ==============================================

    ativos_otimismo = {

        # FUTUROS EUA
        "ES=F": 2.5,
        "NQ=F": 2.5,
        "RTY=F": 1.5,

        # COMMODITIES
        "BZ=F": 1.8,

        # ADRS BR
        "VALE": 2.2,
        "PBR": 2.2,
        "ITUB": 1.8,
        "BBD": 1.5,

        # B3
        "VALE3.SA": 2.0,
        "PETR4.SA": 2.0,
        "ITUB4.SA": 1.8,
        "BBDC4.SA": 1.5,
        "BBAS3.SA": 1.4,
        "ABEV3.SA": 1.2,
        "WEGE3.SA": 1.8,
        "SUZB3.SA": 1.5,
        "JBSS3.SA": 1.5,
        "RENT3.SA": 1.4,
        "LREN3.SA": 1.2,
        "MGLU3.SA": 1.0,
        "RADL3.SA": 1.0
    }

    # ==============================================
    # PESSIMISMO
    # ==============================================

    ativos_pessimismo = {

        # VOLATILIDADE
        "^VIX": 2.5,

        # DÓLAR GLOBAL
        "DX-Y.NYB": 2.0,

        # USD/BRL
        "BRL=X": 3.0,

        # BONDS
        "TLT": 1.8,
        "IEF": 1.5,

        # ETFs DEFENSIVOS
        "UUP": 1.5,

        # OURO
        "GC=F": 1.8,

        # RENDA FIXA BR
        "B5P211.SA": 2.0,

        # SMALL CAPS
        "SMAL11.SA": 1.5,

        # JUROS EUA
        "^TNX": 2.0,
        "^IRX": 1.5
    }

    # ==============================================
    # DOWNLOAD OTIMISMO
    # ==============================================

    dados_otimismo = yf.download(
        tickers=list(ativos_otimismo.keys()),
        period="1d",
        interval="1m",
        auto_adjust=True,
        progress=False
    )["Close"]

    # ==============================================
    # DOWNLOAD PESSIMISMO
    # ==============================================

    dados_pessimismo = yf.download(
        tickers=list(ativos_pessimismo.keys()),
        period="5d",
        interval="5m",
        auto_adjust=True,
        progress=False
    )["Close"]

    # ==============================================
    # TIMEZONE
    # ==============================================

    def converter_tz(df):

        if df.index.tz is None:

            df.index = (
                df.index
                .tz_localize("UTC")
                .tz_convert("America/Sao_Paulo")
            )

        else:

            df.index = (
                df.index
                .tz_convert("America/Sao_Paulo")
            )

        return df

    dados_otimismo = converter_tz(
        dados_otimismo
    )

    dados_pessimismo = converter_tz(
        dados_pessimismo
    )

    # ==============================================
    # ÚLTIMAS 12 HORAS
    # ==============================================

    agora = pd.Timestamp.now(
        tz="America/Sao_Paulo"
    )

    limite_12h = (
        agora - pd.Timedelta(hours=12)
    )

    # JUROS NÃO SERÃO FILTRADOS
    juros = ["^TNX", "^IRX"]

    # OTIMISMO
    dados_otimismo = dados_otimismo[
        dados_otimismo.index >= limite_12h
    ]

    # SEPARAR JUROS
    colunas_juros = [

        c for c in dados_pessimismo.columns

        if c in juros
    ]

    colunas_normais = [

        c for c in dados_pessimismo.columns

        if c not in juros
    ]

    dados_juros = (
        dados_pessimismo[colunas_juros]
    )

    dados_normais = (
        dados_pessimismo[colunas_normais]
    )

    # FILTRO 12H
    dados_normais = dados_normais[
        dados_normais.index >= limite_12h
    ]

    # JUNTA NOVAMENTE
    dados_pessimismo = pd.concat(
        [dados_normais, dados_juros],
        axis=1
    )

    return (
        dados_otimismo,
        dados_pessimismo,
        ativos_otimismo,
        ativos_pessimismo
    )

# ==================================================
# CARREGAR
# ==================================================

(
    dados_otimismo,
    dados_pessimismo,
    ativos_otimismo,
    ativos_pessimismo
) = carregar_dados()

# ==================================================
# PROTEÇÃO
# ==================================================

if (
    dados_otimismo.empty
    or
    dados_pessimismo.empty
):

    st.warning(
        "Dados indisponíveis."
    )

    st.stop()

# ==================================================
# LIMPEZA
# ==================================================

dados_otimismo = (
    dados_otimismo.dropna(how="all")
)

dados_pessimismo = (
    dados_pessimismo.dropna(how="all")
)

dados = dados_otimismo.join(
    dados_pessimismo,
    how="outer"
)

dados = dados.ffill()

dados = dados.sort_index()

dados_otimismo = (
    dados[dados_otimismo.columns]
)

dados_pessimismo = (
    dados[dados_pessimismo.columns]
)

# ==================================================
# SHIFT
# ==================================================

shift_map = {
    "1m": 180,
    "5m": 36,
    "15m": 12,
    "30m": 6
}

# ==================================================
# VARIAÇÃO
# ==================================================

ativos_invertidos = [
    "^VIX",
    "DX-Y.NYB",
    "BRL=X",
    "^TNX",
    "^IRX",
    "UUP"
]

def variacao_percentual(
    serie,
    nome_ativo
):

    shift = shift_map.get(intervalo, 1)

    variacao = (
        ((serie / serie.shift(shift)) - 1)
        * 100
    )

    # INVERTER ATIVOS DE MEDO
    if nome_ativo in ativos_invertidos:

        variacao = variacao * -1

    return variacao

# ==================================================
# VARIAÇÕES
# ==================================================

var_otimismo = pd.DataFrame({

    ativo: variacao_percentual(
        dados_otimismo[ativo],
        ativo
    ).fillna(0)

    for ativo in ativos_otimismo
})

var_pessimismo = pd.DataFrame({

    ativo: variacao_percentual(
        dados_pessimismo[ativo],
        ativo
    ).fillna(0)

    for ativo in ativos_pessimismo
})

# ==================================================
# LINHA PONDERADA
# ==================================================

def linha_ponderada(df, pesos):

    ativos_validos = [

        a for a in pesos

        if a in df.columns
    ]

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

# ==================================================
# REMOVER TZ
# ==================================================

linha_otimismo.index = (
    linha_otimismo.index.tz_localize(None)
)

linha_pessimismo.index = (
    linha_pessimismo.index.tz_localize(None)
)

# ==================================================
# GRÁFICO
# ==================================================

fig = go.Figure()

# OTIMISMO
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

# PESSIMISMO
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

# LINHA ZERO
fig.add_hline(
    y=0,
    line_dash="dot",
    line_color="gray"
)

# LAYOUT
fig.update_layout(

    template="plotly_dark",

    hovermode="x unified",

    uirevision=True,

    height=700,

    xaxis=dict(
        rangeslider=dict(
            visible=True
        ),
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

# MOSTRAR
st.plotly_chart(
    fig,
    use_container_width=True,
    config={
        "scrollZoom": True,
        "displaylogo": False
    }
)

# ==================================================
# SINAL
# ==================================================

def gerar_sinal(
    linha_otimismo,
    linha_pessimismo
):

    ultimo_otimismo = (
        linha_otimismo.iloc[-1]
    )

    ultimo_pessimismo = (
        linha_pessimismo.iloc[-1]
    )

    if ultimo_otimismo > ultimo_pessimismo:

        return "🟢 COMPRA"

    elif ultimo_pessimismo > ultimo_otimismo:

        return "🔴 VENDA"

    else:

        return "⚪ NEUTRO"

sinal = gerar_sinal(
    linha_otimismo,
    linha_pessimismo
)

st.subheader(
    f"Sinal Atual: {sinal}"
)

# ==================================================
# INFO
# ==================================================

st.caption(

    f"🕒 Atualizado às: "

    f"{pd.Timestamp.now().strftime('%H:%M:%S')}"
)

# ==================================================
# AUTO REFRESH
# ==================================================

if not st.session_state.pausado:

    time.sleep(60)

    st.rerun()
