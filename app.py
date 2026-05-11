import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import time

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

        st.session_state.pausado = not st.session_state.pausado

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
    {"hora": "09:00", "evento": "Payroll EUA", "impacto": "⭐⭐⭐"},
    {"hora": "10:30", "evento": "Petróleo", "impacto": "⭐⭐"},
    {"hora": "15:00", "evento": "Juros", "impacto": "⭐⭐⭐"},
]

for n in noticias:

    st.sidebar.write(
        f"{n['hora']} - {n['evento']} {n['impacto']}"
    )

# ==================================================
# PERÍODOS
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
def carregar_dados(periodo, intervalo):

    # ==============================================
    # OTIMISMO
    # ==============================================

    ativos_otimismo = {

        # EUA
        "ES=F": 2.5,       # S&P
        "NQ=F": 2.5,       # Nasdaq
        "RTY=F": 1.5,      # Russell
        "BZ=F": 1.8,       # Petróleo

        # ADRs BR nos EUA
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

        # Volatilidade
        "^VIX": 2.5,

        # Dólar index
        "DX-Y.NYB": 2.5,

        # Bonds EUA
        "TLT": 2.0,

        # Juros EUA
        "^TNX": 2.0,       # 10 anos
        "^IRX": 1.8,       # curto prazo

        # USD/BRL
        "BRL=X": 2.5,

        # ETFs defensivos
        "UUP": 1.5,
        "IEF": 1.5
    }

    # ==============================================
    # DOWNLOAD
    # ==============================================

    dados_otimismo = yf.download(
        tickers=list(ativos_otimismo.keys()),
        period=periodo,
        interval=intervalo,
        auto_adjust=True,
        progress=False
    )["Close"]

    dados_pessimismo = yf.download(
        tickers=list(ativos_pessimismo.keys()),
        period=periodo,
        interval=intervalo,
        auto_adjust=True,
        progress=False
    )["Close"]

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
) = carregar_dados(periodo, intervalo)

# ==================================================
# PROTEÇÃO
# ==================================================

if dados_otimismo.empty or dados_pessimismo.empty:

    st.warning(
        "Dados indisponíveis. Tente novamente."
    )

    st.stop()

# ==================================================
# TIMEZONE
# ==================================================

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

dados_otimismo = converter_tz(dados_otimismo)
dados_pessimismo = converter_tz(dados_pessimismo)

# ==================================================
# LIMPEZA
# ==================================================

dados_otimismo = dados_otimismo.dropna(how="all")
dados_pessimismo = dados_pessimismo.dropna(how="all")

dados = dados_otimismo.join(
    dados_pessimismo,
    how="outer"
)

dados = dados.ffill()

dados = dados.sort_index()

dados_otimismo = dados[dados_otimismo.columns]

dados_pessimismo = dados[dados_pessimismo.columns]

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

def variacao_percentual(serie):

    shift = shift_map.get(intervalo, 1)

    return (
        ((serie / serie.shift(shift)) - 1) * 100
    )

# ==================================================
# VARIAÇÕES
# ==================================================

var_otimismo = pd.DataFrame({

    ativo: variacao_percentual(
        dados_otimismo[ativo]
    ).fillna(0)

    for ativo in ativos_otimismo
})

var_pessimismo = pd.DataFrame({

    ativo: variacao_percentual(
        dados_pessimismo[ativo]
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

def gerar_sinal(l_ot, l_ps):

    ultimo_ot = l_ot.iloc[-1]

    ultimo_ps = l_ps.iloc[-1]

    if ultimo_ot > ultimo_ps:

        return "🟢 COMPRA"

    elif ultimo_ps > ultimo_ot:

        return "🔴 VENDA"

    else:

        return "⚪ NEUTRO"

sinal = gerar_sinal(
    linha_otimismo,
    linha_pessimismo
)

st.subheader(f"Sinal Atual: {sinal}")

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
