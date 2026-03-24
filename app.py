import streamlit as st
import pandas as pd
import numpy_financial as npf
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Estudio Técnico-Económico | Victron Energy", layout="wide")

# --- BASE DE DATOS VICTRON (Actualiza estos precios con tu lista oficial) ---
CATALOGO_INVERSORES = {
    "MultiPlus-II 48/5000/70-50": 1850.00,
    "MultiPlus-II 48/8000/110-100": 2600.00,
    "Quattro 48/10000/140-100/100": 3800.00,
    "Quattro 48/15000/200-100/100": 4900.00,
    "Sistema Trifásico (3x Quattro 10kVA)": 11400.00
}

# Costos paramétricos referenciales
COSTO_POR_KWP_PANELES = 350.0 # USD por kWp de paneles solares
COSTO_POR_KWH_BATERIA = 400.0 # USD por kWh de batería de litio (Ej. Pylontech/Victron)
MARGEN_BOS = 1.20 # 20% adicional por cables, protecciones, estructura y mano de obra

def calcular_flujo_caja(capex, ahorro_anual, opex_anual, anios, costo_baterias, anio_reemplazo, cok):
    flujos, flujos_descontados, flujo_acumulado_desc = [], [], []
    acumulado = 0
    
    for anio in range(anios + 1):
        if anio == 0:
            flujo_neto = -capex
        else:
            flujo_neto = ahorro_anual - opex_anual
            if anio == anio_reemplazo:
                flujo_neto -= costo_baterias
                
        flujos.append(flujo_neto)
        flujo_desc = flujo_neto / ((1 + cok) ** anio)
        flujos_descontados.append(flujo_desc)
        acumulado += flujo_desc
        flujo_acumulado_desc.append(acumulado)
        
    vpn = npf.npv(cok, flujos)
    try:
        tir = npf.irr(flujos) * 100
    except:
        tir = 0.0
        
    payback = "No recupera"
    for i in range(1, len(flujo_acumulado_desc)):
        if flujo_acumulado_desc[i] >= 0 and flujo_acumulado_desc[i-1] < 0:
            fraccion_anio = abs(flujo_acumulado_desc[i-1]) / flujos_descontados[i]
            payback = f"{(i - 1) + fraccion_anio:.1f} años"
            break
            
    df_flujo = pd.DataFrame({
        "Año": range(anios + 1),
        "Flujo Nominal ($)": flujos,
        "Flujo Descontado ($)": flujos_descontados,
        "Retorno Acumulado ($)": flujo_acumulado_desc
    })
    return df_flujo, vpn, tir, payback

# --- FRONTEND E INTERFAZ ---
st.title("⚡ Diseño Fotovoltaico & Pre-Factibilidad")
st.markdown("**Powered by Victron Energy** | *Ingeniería por Mauricio Salcedo*")

# --- SIDEBAR: DIMENSIONAMIENTO TÉCNICO ---
st.sidebar.header("1. Selección de Equipos (CAPEX)")

inversor_seleccionado = st.sidebar.selectbox("Inversor/Cargador Victron", list(CATALOGO_INVERSORES.keys()))
costo_inversor = CATALOGO_INVERSORES[inversor_seleccionado]

potencia_solar = st.sidebar.number_input("Arreglo Solar (kWp)", min_value=0.0, value=5.0, step=1.0)
costo_paneles = potencia_solar * COSTO_POR_KWP_PANELES

capacidad_bateria = st.sidebar.number_input("Banco de Baterías (kWh)", min_value=0.0, value=10.0, step=2.5)
costo_banco_baterias = capacidad_bateria * COSTO_POR_KWH_BATERIA

# Cálculo del CAPEX Total
capex_equipos = costo_inversor + costo_paneles + costo_banco_baterias
capex_total = capex_equipos * MARGEN_BOS

st.sidebar.markdown(f"**CAPEX Estimado:** `${capex_total:,.2f}` USD")

st.sidebar.markdown("---")
st.sidebar.header("2. Operación y Mantenimiento")
ahorro_anual = st.sidebar.number_input("Ahorro Anual Proyectado USD", value=3000, step=100)
opex_anual = st.sidebar.number_input("Mantenimiento Anual USD", value=200, step=50)
anio_reemplazo = st.sidebar.slider("Año de reemplazo de baterías", 5, 15, 10)

st.sidebar.markdown("---")
st.sidebar.header("3. Parámetros Financieros")
cok = st.sidebar.slider("Tasa de Descuento (COK %)", 2.0, 20.0, 8.0, 0.5) / 100
anios = st.sidebar.slider("Horizonte (Años)", 10, 25, 20)

# --- EJECUCIÓN ---
df, vpn, tir, payback = calcular_flujo_caja(capex_total, ahorro_anual, opex_anual, anios, costo_banco_baterias, anio_reemplazo, cok)

# --- VISUALIZACIÓN ---
st.subheader("Indicadores de Inversión")
col1, col2, col3, col4 = st.columns(4)
col1.metric("CAPEX Total", f"${capex_total:,.0f}")
col2.metric("VPN (Valor Presente Neto)", f"${vpn:,.0f}", delta="Viable" if vpn > 0 else "Riesgo")
col3.metric("TIR", f"{tir:.1f}%")
col4.metric("Payback", payback)

fig = go.Figure()
fig.add_trace(go.Bar(x=df["Año"], y=df["Flujo Nominal ($)"], name="Flujo Nominal", marker_color=['#E63946' if val < 0 else '#2A9D8F' for val in df["Flujo Nominal ($)"]]))
fig.add_trace(go.Scatter(x=df["Año"], y=df["Retorno Acumulado ($)"], name="Retorno Acum. (Descontado)", mode='lines+markers', line=dict(color='#F4A261', width=3)))
fig.update_layout(xaxis_title="Años de Operación", yaxis_title="USD ($)", hovermode="x unified", template="plotly_white")
st.plotly_chart(fig, use_container_width=True)
