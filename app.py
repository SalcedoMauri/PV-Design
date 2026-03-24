import streamlit as st
import pandas as pd
import numpy_financial as npf
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Estudio Técnico-Económico | GERER L ENERGY", layout="wide")

def calcular_flujo_caja(capex, ahorro_anual, opex_anual, anios, costo_baterias, anio_reemplazo, cok):
    """
    Motor algorítmico (V1.1) para calcular FCF, VPN, TIR y Payback Descontado.
    """
    flujos = []
    flujos_descontados = []
    flujo_acumulado_desc = []
    acumulado = 0
    
    for anio in range(anios + 1):
        # 1. Flujo Nominal
        if anio == 0:
            flujo_neto = -capex
        else:
            flujo_neto = ahorro_anual - opex_anual
            # Reemplazo de banco de baterías (OPEX diferido)
            if anio == anio_reemplazo:
                flujo_neto -= costo_baterias
                
        flujos.append(flujo_neto)
        
        # 2. Flujo Descontado
        flujo_desc = flujo_neto / ((1 + cok) ** anio)
        flujos_descontados.append(flujo_desc)
        
        # 3. Acumulado Descontado
        acumulado += flujo_desc
        flujo_acumulado_desc.append(acumulado)
        
    # Cálculos Financieros
    vpn = npf.npv(cok, flujos)
    try:
        tir = npf.irr(flujos) * 100
    except:
        tir = 0.0
        
    # Calcular Payback Descontado Exacto (Interpolación)
    payback = "No recupera"
    for i in range(1, len(flujo_acumulado_desc)):
        if flujo_acumulado_desc[i] >= 0 and flujo_acumulado_desc[i-1] < 0:
            # Interpolación lineal: Año_Anterior + ABS(Acumulado_Anterior) / Flujo_Descontado_Actual
            fraccion_anio = abs(flujo_acumulado_desc[i-1]) / flujos_descontados[i]
            payback_exacto = (i - 1) + fraccion_anio
            payback = f"{payback_exacto:.1f} años"
            break
            
    df_flujo = pd.DataFrame({
        "Año": range(anios + 1),
        "Flujo Nominal ($)": flujos,
        "Flujo Descontado ($)": flujos_descontados,
        "Retorno Acumulado ($)": flujo_acumulado_desc
    })
    
    return df_flujo, vpn, tir, payback

# --- INTERFAZ DE USUARIO (FRONTEND) ---
st.title("⚡ Motor de Evaluación Financiera: Proyectos Victron")
st.markdown("Generador de Estudios de Pre-Factibilidad Económica")

# --- BARRA LATERAL (INPUTS) ---
st.sidebar.header("Parámetros del Proyecto")
capex = st.sidebar.number_input("Inversión Inicial (CAPEX) USD", value=15000, step=1000)
ahorro_anual = st.sidebar.number_input("Ahorro Anual Proyectado USD", value=3500, step=100)
opex_anual = st.sidebar.number_input("Mantenimiento Anual (OPEX) USD", value=200, step=50)

st.sidebar.markdown("---")
st.sidebar.header("Reemplazo de Equipos")
costo_baterias = st.sidebar.number_input("Costo Reemplazo Baterías USD", value=4000, step=500)
anio_reemplazo = st.sidebar.slider("Año de Reemplazo (Vida útil batería)", min_value=5, max_value=15, value=10)

st.sidebar.markdown("---")
st.sidebar.header("Parámetros Financieros")
cok = st.sidebar.slider("Tasa de Descuento / COK (%)", min_value=2.0, max_value=20.0, value=8.0, step=0.5) / 100
anios = st.sidebar.slider("Horizonte de Evaluación (Años)", min_value=10, max_value=25, value=20)

# --- EJECUCIÓN DEL CÁLCULO ---
df, vpn, tir, payback = calcular_flujo_caja(capex, ahorro_anual, opex_anual, anios, costo_baterias, anio_reemplazo, cok)

# --- VISUALIZACIÓN DE RESULTADOS (MÉTRICAS) ---
col1, col2, col3 = st.columns(3)
col1.metric("Valor Presente Neto (VPN)", f"${vpn:,.2f}", delta="Viable" if vpn > 0 else "No Viable")
col2.metric("Tasa Interna de Retorno (TIR)", f"{tir:.2f}%")
col3.metric("Periodo de Recuperación (Descontado)", payback)

# --- GRÁFICO PROFESIONAL (PLOTLY) ---
st.subheader("Proyección del Flujo de Caja Libre (FCF)")

fig = go.Figure()
# Barras del flujo nominal (para ver el movimiento real de dinero)
fig.add_trace(go.Bar(
    x=df["Año"], 
    y=df["Flujo Nominal ($)"],
    name="Flujo Nominal",
    marker_color=['red' if val < 0 else 'green' for val in df["Flujo Nominal ($)"]]
))
# Línea del flujo acumulado DESCONTADO (para ver el cruce real con el VPN)
fig.add_trace(go.Scatter(
    x=df["Año"], 
    y=df["Retorno Acumulado ($)"],
    name="Retorno Acum. (Descontado)",
    mode='lines+markers',
    line=dict(color='orange', width=3)
))

fig.update_layout(
    xaxis_title="Años de Operación",
    yaxis_title="USD ($)",
    hovermode="x unified",
    template="plotly_white"
)
st.plotly_chart(fig, use_container_width=True)

# --- TABLA DE DATOS ---
with st.expander("Ver Tabla de Amortización Detallada"):
    # Formateo visual para la tabla
    st.dataframe(df.style.format({
        "Flujo Nominal ($)": "${:,.2f}", 
        "Flujo Descontado ($)": "${:,.2f}",
        "Retorno Acumulado ($)": "${:,.2f}"
    }))
