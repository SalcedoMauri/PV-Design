import streamlit as st
import pandas as pd
import numpy_financial as npf
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Estudio Técnico-Económico | GERER L ENERGY", layout="wide")

# --- CARGA DE BASE DE DATOS (CATÁLOGO VICTRON) ---
@st.cache_data
def cargar_catalogo():
    try:
        # Lee el archivo CSV. Asegúrate de que el nombre coincida exactamente en GitHub.
        df = pd.read_csv("precios_victron.csv")
        # Limpieza de seguridad: convierte la columna '$' a número puro (quita comas si las hay)
        df['$'] = df['$'].astype(str).str.replace(',', '').astype(float)
        return df
    except FileNotFoundError:
        # Mensaje de error amigable por si el nombre del archivo no coincide
        return pd.DataFrame({"Código": ["Error"], "Equipo": ["Falta archivo precios_victron.csv"], "$": [0.0]})

df_catalogo = cargar_catalogo()

def calcular_flujo_caja(capex, ahorro_anual, opex_anual, anios, costo_baterias, anio_reemplazo, cok):
    """Motor algorítmico (V1.1) para calcular FCF, VPN, TIR y Payback Descontado."""
    flujos = []
    flujos_descontados = []
    flujo_acumulado_desc = []
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
st.sidebar.header("1. Selección de Equipos Victron")

# Menú desplegable alimentado por tu CSV
lista_equipos = df_catalogo['Equipo'].tolist()
equipo_seleccionado = st.sidebar.selectbox("Inversor/Equipo Principal:", lista_equipos)

# Búsqueda automática del precio
if equipo_seleccionado != "Falta archivo precios_victron.csv":
    precio_unitario = df_catalogo.loc[df_catalogo['Equipo'] == equipo_seleccionado, '$'].values[0]
else:
    precio_unitario = 0.0

cantidad = st.sidebar.number_input("Cantidad (Ej. 3 para Trifásico):", min_value=1, value=1, step=1)
costo_equipos_victron = precio_unitario * cantidad

# Mostrar subtotal al usuario
st.sidebar.markdown(f"**Subtotal Victron:** ${costo_equipos_victron:,.2f} USD")

st.sidebar.markdown("---")
st.sidebar.header("2. Balance of System (BOS)")
st.sidebar.caption("Costo de Paneles, Baterías, Tableros, Cables y Mano de Obra")
otros_costos = st.sidebar.number_input("Costo Restante (USD):", value=10000.0, step=500.0)

# El CAPEX ahora se calcula solo
capex_total = costo_equipos_victron + otros_costos
st.sidebar.markdown(f"### CAPEX Total: ${capex_total:,.2f} USD")

st.sidebar.markdown("---")
st.sidebar.header("3. Parámetros Operativos")
ahorro_anual = st.sidebar.number_input("Ahorro Anual Proyectado USD", value=3500.0, step=100.0)
opex_anual = st.sidebar.number_input("Mantenimiento Anual (OPEX) USD", value=200.0, step=50.0)

st.sidebar.markdown("---")
st.sidebar.header("4. Reemplazo de Baterías")
costo_baterias = st.sidebar.number_input("Costo Reemplazo Baterías USD", value=4000.0, step=500.0)
anio_reemplazo = st.sidebar.slider("Año de Reemplazo (Vida útil)", min_value=5, max_value=15, value=10)

st.sidebar.markdown("---")
st.sidebar.header("5. Parámetros Financieros")
cok = st.sidebar.slider("Tasa de Descuento / COK (%)", min_value=2.0, max_value=20.0, value=8.0, step=0.5) / 100
anios = st.sidebar.slider("Horizonte de Evaluación (Años)", min_value=10, max_value=25, value=20)

# --- EJECUCIÓN DEL CÁLCULO ---
# Le pasamos el CAPEX TOTAL calculado algorítmicamente
df, vpn, tir, payback = calcular_flujo_caja(capex_total, ahorro_anual, opex_anual, anios, costo_baterias, anio_reemplazo, cok)

# --- VISUALIZACIÓN DE RESULTADOS (MÉTRICAS) ---
col1, col2, col3 = st.columns(3)
col1.metric("Valor Presente Neto (VPN)", f"${vpn:,.2f}", delta="Viable" if vpn > 0 else "No Viable")
col2.metric("Tasa Interna de Retorno (TIR)", f"{tir:.2f}%")
col3.metric("Periodo de Recuperación (Descontado)", payback)

# --- GRÁFICO PROFESIONAL (PLOTLY) ---
st.subheader("Proyección del Flujo de Caja Libre (FCF)")

fig = go.Figure()
fig.add_trace(go.Bar(
    x=df["Año"], 
    y=df["Flujo Nominal ($)"],
    name="Flujo Nominal",
    marker_color=['red' if val < 0 else 'green' for val in df["Flujo Nominal ($)"]]
))
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
    st.dataframe(df.style.format({
        "Flujo Nominal ($)": "${:,.2f}", 
        "Flujo Descontado ($)": "${:,.2f}",
        "Retorno Acumulado ($)": "${:,.2f}"
    }))
