import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import time

st.set_page_config(layout="wide")
st.title("Rastreador Macro - Reinaldo")

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
# SESSION STATE (PERÍODO)
# ==============================

if "periodo" not in st.session_state:
    st.session_state.periodo = "1d"

periodo = st.selectbox(
    "Período",
    ["1d", "5d", "15d", "1mo"],
    index=["1d", "5d", "15d", "1mo"].index(st.session_state.periodo)
)

st.session_state.periodo = periodo

# ==============================
# CACHE
# ==============================

@st.cache_data(ttl=60)
def carregar_dados(periodo):

    ativos_otimismo = {
        "ES=F": 2.0,
        "NQ=F": 1.8,
        "BZ=F": 1.5,
        "VALE3.SA": 2.0,
        "PETR4.SA": 2.0,
        "ITUB4.SA": 1.8,
        "BBDC4.SA": 1.5,
        "ABEV3.SA": 1.2,
        "WEGE3.SA": 1.2,
        "B3SA3.SA": 1.2
    }

    ativos_risco = {
        "^VIX": 2.0,
        "TLT": 1.5,
        "DX-Y.NYB": 2.0
    }

    dados_otimismo = yf.download(
        list(ativos_otimismo.keys()),
        period=periodo,
        interval="1m"
    )["Close"]

    dados_risco = yf.download(
        list(ativos_risco.keys()),
        period=periodo,
        interval="1m"
    )["Close"]

   return dados_otimismo, dados_risco, ativos_otimismo, ativos_risco

dados_otimismo, dados_risco, ativos_otimismo, ativos_risco = carregar_dados(periodo)

# proteção contra dados vazios
if dados_otimismo.empty or dados_risco.empty:
    st.warning("Dados indisponíveis no momento. Tente outro período.")
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
# LIMPEZA E ALINHAMENTO SEGURO
# ==============================

dados_otimismo = dados_otimismo.dropna(how="all")
dados_risco = dados_risco.dropna(how="all")

# mantém apenas timestamps válidos
dados_otimismo = dados_otimismo[~dados_otimismo.index.duplicated()]
dados_risco = dados_risco[~dados_risco.index.duplicated()]

# junta sem quebrar
dados = dados_otimismo.join(dados_risco, how="outer").ffill()

# separa novamente
dados_otimismo = dados[dados_otimismo.columns]
dados_risco = dados[dados_risco.columns]

# ==============================
# VARIAÇÃO
# ==============================

def variacao_percentual(serie):
    return ((serie / serie.shift(180)) - 1) * 100

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

def linha_ponderada(df, pesos, span=5):
    ativos_validos = [a for a in pesos if a in df.columns]
    total_peso = sum(pesos[a] for a in ativos_validos)

    linha = sum(df[a] * pesos[a] for a in ativos_validos) / total_peso
    return linha.ewm(span=span).mean()

linha_otimismo = linha_ponderada(var_otimismo, ativos_otimismo)
linha_risco = linha_ponderada(var_risco, ativos_risco)

linha_otimismo.index = linha_otimismo.index.tz_localize(None)
linha_risco.index = linha_risco.index.tz_localize(None)

# ==============================
# CONTROLE DE ZOOM
# ==============================

if "range_x" not in st.session_state:
    st.session_state.range_x = None

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
    uirevision="fix",
    xaxis=dict(
        title="Data/Hora",
        rangeslider=dict(visible=True),
        range=st.session_state.range_x
    ),
    yaxis=dict(
        title="Força (%)",
        fixedrange=False
    )
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

st.subheader(f"Sinal Geral: {gerar_sinal(linha_otimismo, linha_risco)}")

# ==============================
# INFO
# ==============================

st.caption(f"🕒 Última atualização: {pd.Timestamp.now().strftime('%H:%M:%S')}")

# ==============================
# AUTO REFRESH
# ==============================

time.sleep(60)
st.rerun()
