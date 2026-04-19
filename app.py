import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

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
# ATIVOS
# ==============================

ativos_otimismo = {
    "^GSPC": 2.0,
    "^IXIC": 1.8,
    "VALE3.SA": 1.8,
    "PETR4.SA": 1.8,
    "BZ=F": 1.5
}

ativos_risco = {
    "^VIX": 2.0,
    "TLT": 1.5,
    "DX-Y.NYB": 2.0
}

# ==============================
# PERÍODO
# ==============================

periodo = st.selectbox("Período", ["5d", "15d", "1mo"], index=2)

dados_otimismo = yf.download(list(ativos_otimismo.keys()), period=periodo, interval="5m")["Close"]
dados_risco = yf.download(list(ativos_risco.keys()), period=periodo, interval="5m")["Close"]

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
# ALINHAR DADOS
# ==============================

indice = pd.date_range(
    start=min(dados_otimismo.index.min(), dados_risco.index.min()),
    end=max(dados_otimismo.index.max(), dados_risco.index.max()),
    freq="5min",
    tz="America/Sao_Paulo"
)

dados_otimismo = dados_otimismo.reindex(indice).ffill()
dados_risco = dados_risco.reindex(indice).ffill()

# ==============================
# VARIAÇÃO %
# ==============================

def variacao_percentual(serie):
    return ((serie / serie.shift(36)) - 1) * 100

var_otimismo = pd.DataFrame({
    ativo: variacao_percentual(dados_otimismo[ativo]).fillna(0)
    for ativo in ativos_otimismo
})

var_risco = pd.DataFrame({
    ativo: variacao_percentual(dados_risco[ativo]).fillna(0)
    for ativo in ativos_risco
})

# ==============================
# LINHAS PRINCIPAIS
# ==============================

def linha_ponderada(df, pesos, span=5):
    ativos_validos = [a for a in pesos if a in df.columns]
    total_peso = sum(pesos[a] for a in ativos_validos)

    linha = sum(df[a] * pesos[a] for a in ativos_validos) / total_peso
    return linha.ewm(span=span).mean()

linha_otimismo = linha_ponderada(var_otimismo, ativos_otimismo)
linha_risco = linha_ponderada(var_risco, ativos_risco)

# ==============================
# LIMPEZA INDEX
# ==============================

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
    line=dict(color="green", width=2),
    hoverinfo="x+y"
))

fig.add_trace(go.Scatter(
    x=linha_risco.index,
    y=linha_risco,
    mode="lines",
    name="Risco",
    line=dict(color="red", width=2),
    hoverinfo="x+y"
))

fig.update_layout(
    template="plotly_dark",
    hovermode="x",
    xaxis=dict(
        title="Data/Hora",
        rangeslider=dict(visible=True),
        showspikes=True,
        spikemode="across"
    ),
    yaxis=dict(
        title="Força (%)",
        fixedrange=False
    )
)

# ==============================
# EXIBIÇÃO COM ZOOM
# ==============================

st.plotly_chart(
    fig,
    use_container_width=True,
    config={"scrollZoom": True}
)

# ==============================
# SINAL SIMPLIFICADO
# ==============================

def gerar_sinal(l_ot, l_rg):
    if l_ot.iloc[-1] > l_rg.iloc[-1]:
        return "🟢 COMPRA (Otimismo domina)"
    elif l_rg.iloc[-1] > l_ot.iloc[-1]:
        return "🔴 VENDA (Risco domina)"
    else:
        return "⚪ NEUTRO"

sinal = gerar_sinal(linha_otimismo, linha_risco)

st.subheader(f"Sinal Geral: {sinal}")
