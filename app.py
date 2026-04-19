import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("Rastreador Macro - Reinaldo")

# ==============================
# 1️⃣ ATIVOS PRINCIPAIS
# ==============================

# 🟢 OTIMISMO (índice)
ativos_otimismo = {
    "^GSPC": 2.0,
    "^IXIC": 1.8,
    "VALE3.SA": 1.8,
    "PETR4.SA": 1.8,
    "BZ=F": 1.5
}

# 🔴 RISCO (dólar / proteção)
ativos_risco = {
    "^VIX": 2.0,
    "TLT": 1.5,
    "DX-Y.NYB": 2.0
}

# ==============================
# 2️⃣ BAIXAR DADOS (AGORA 30 DIAS)
# ==============================

dados_otimismo = yf.download(list(ativos_otimismo.keys()), period="30d", interval="5m")["Close"]
dados_risco = yf.download(list(ativos_risco.keys()), period="30d", interval="5m")["Close"]

# ==============================
# 3️⃣ CONVERTER HORÁRIO BRASIL
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
# 4️⃣ ALINHAR DADOS
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
# 5️⃣ VARIAÇÃO % (3 HORAS)
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
# 6️⃣ LINHAS PRINCIPAIS
# ==============================

def linha_ponderada(df, pesos, span=5):
    ativos_validos = [a for a in pesos if a in df.columns]
    total_peso = sum(pesos[a] for a in ativos_validos)

    linha = sum(df[a] * pesos[a] for a in ativos_validos) / total_peso
    return linha.ewm(span=span).mean()

linha_otimismo = linha_ponderada(var_otimismo, ativos_otimismo)
linha_risco = linha_ponderada(var_risco, ativos_risco)

# ==============================
# 7️⃣ RASTREAMENTO
# ==============================

def calcular_rastreamento(df):
    rastreio = pd.DataFrame()

    for ativo in df.columns:
        serie = df[ativo]

        ema9 = serie.ewm(span=9).mean()
        ema21 = serie.ewm(span=21).mean()

        rastreio[ativo] = (ema9 - ema21) * 2

    return rastreio.mean(axis=1)

linha_rastreamento = calcular_rastreamento(var_risco)

# ==============================
# 8️⃣ AJUSTE VISUAL (SEM CORTAR HISTÓRICO)
# ==============================

linha_otimismo.index = linha_otimismo.index.tz_localize(None)
linha_risco.index = linha_risco.index.tz_localize(None)
linha_rastreamento.index = linha_rastreamento.index.tz_localize(None)

# ==============================
# 🔥 CONTROLE DE VISUALIZAÇÃO
# ==============================

st.sidebar.title("Configuração de Visualização")

dias_visiveis = st.sidebar.slider("Dias para visualizar", 1, 30, 5)

filtro = linha_otimismo.index > (linha_otimismo.index.max() - pd.Timedelta(days=dias_visiveis))

linha_otimismo_plot = linha_otimismo[filtro]
linha_risco_plot = linha_risco[filtro]
linha_rastreamento_plot = linha_rastreamento[filtro]

# ==============================
# 9️⃣ GRÁFICO
# ==============================

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=linha_otimismo_plot.index,
    y=linha_otimismo_plot,
    mode="lines",
    name="Otimismo (WIN)",
    line=dict(color="green", width=2)
))

fig.add_trace(go.Scatter(
    x=linha_risco_plot.index,
    y=linha_risco_plot,
    mode="lines",
    name="Risco (WDO)",
    line=dict(color="red", width=2)
))

fig.add_trace(go.Scatter(
    x=linha_rastreamento_plot.index,
    y=linha_rastreamento_plot,
    mode="lines",
    name="Rastreamento",
    line=dict(color="blue", width=2)
))

fig.update_layout(
    template="plotly_dark",
    xaxis=dict(
        title="Data/Hora (Brasília)",
        tickformat="%d/%m %H:%M",
        showspikes=True,
        spikemode="across"
    ),
    yaxis=dict(
        title="Força (%)",
        side="right",
        showspikes=True,
        spikemode="across"
    ),
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)

# ==============================
# 🔟 SINAL
# ==============================

def gerar_sinal(l_ot, l_rg, l_rt):
    if l_rt.iloc[-1] > 0 and l_ot.iloc[-1] > 0:
        return "🟢 COMPRA FORTE"
    elif l_rt.iloc[-1] < 0 and l_rg.iloc[-1] > 0:
        return "🔴 VENDA FORTE"
    else:
        return "⚪ NEUTRO"

sinal = gerar_sinal(linha_otimismo, linha_risco, linha_rastreamento)

st.subheader(f"Sinal Geral: {sinal}")