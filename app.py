import streamlit as st
import pandas as pd
import numpy_financial as npf
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Estudio Técnico-Económico | GERER L ENERGY", layout="wide")

# --- BASE DE DATOS AMBIENTAL (PERÚ) ---
# Diccionario interno de radiación solar (HSP promedio anual)
hsp_peru = {
    "Arequipa (Arequipa)": 6.0,
    "Moquegua (Moquegua)": 6.2,
    "Piura (Piura)": 5.8,
    "Tacna (Tacna)": 5.6,
    "Cusco (Cusco)": 5.5,
    "Chiclayo (Lambayeque)": 5.4,
    "Trujillo (La Libertad)": 5.2,
    "Huancayo (Junín)": 5.1,
    "Iquitos (Loreto)": 4.8,
    "Lima (Lima)": 4.0
}

# --- CARGA DE CATÁLOGO COMERCIAL ---
@st.cache_data
def cargar_catalogo():
    try:
        df = pd.read_csv("precios_victron.csv", encoding='latin1', sep=None, engine='python')
        df['$'] = df['$'].astype(str).str.replace(',', '').astype(float)
        return df
    except Exception as e:
        return pd.DataFrame({"Código": ["Error"], "Equipo": [f"Error base de datos: {e}"], "$": [0.0]})

df_catalogo = cargar_catalogo()

# --- FUNCIONES DE INGENIERÍA NORMATIVA Y GEOMÉTRICA ---
def sizing_inversor(demanda_kw, fp=0.95):
    return (demanda_kw / fp) * 1.25 # NEC: 125%

def sizing_bateria(energia_nocturna_kwh, dias_autonomia=1, dod=0.80, eff_inv=0.95):
    return (energia_nocturna_kwh * dias_autonomia) / (dod * eff_inv) # IEEE

def sizing_paneles_energia(consumo_diario_kwh, hsp, pr=0.75):
    return consumo_diario_kwh / (hsp * pr) # IEC 61724

def sizing_geometrico(area_m2, potencia_panel_w=550, area_panel_m2=2.2, factor_ocupacion=0.8):
    # Calcula cuántos paneles caben y la potencia máxima posible en ese techo
    paneles_max = int((area_m2 * factor_ocupacion) / area_panel_m2)
    kwp_max = (paneles_max * potencia_panel_w) / 1000.0
    return paneles_max, kwp_max

def calcular_flujo_caja(capex, ahorro_anual, opex_anual, anios, costo_baterias, anio_reemplazo, cok):
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

# --- FRONTEND ---
st.title("⚡ Motor de Ingeniería y Finanzas: Sistemas Victron")
st.markdown("Basado en normativas (NEC, IEEE, IEC) y parámetros geoespaciales.")

# --- BLOQUE 1: INGENIERÍA Y SIZING ---
with st.expander("1. Parámetros del Cliente y Dimensionamiento Teórico", expanded=True):
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        st.write("**Datos Eléctricos**")
        demanda_max = st.number_input("Demanda Máxima Simultánea (kW)", value=10.0, step=1.0)
        consumo_dia = st.number_input("Consumo Total Diario (kWh)", value=40.0, step=5.0)
        consumo_noche = st.number_input("Consumo Nocturno (kWh)", value=15.0, step=1.0)
        
    with col_b:
        st.write("**Ubicación y Espacio**")
        ubicacion = st.selectbox("Ciudad de Instalación", list(hsp_peru.keys()))
        hsp_local = hsp_peru[ubicacion]
        st.info(f"☀️ Radiación (HSP): **{hsp_local} horas**")
        area_techo = st.number_input("Área Útil de Techo (m²)", value=80.0, step=10.0)
        
    with col_c:
        st.write("**Dictamen Normativo (Mínimo Requerido)**")
        req_inversor = sizing_inversor(demanda_max)
        req_bat = sizing_bateria(consumo_noche)
        req_pv_energia = sizing_paneles_energia(consumo_dia, hsp_local)
        
        # Lógica geométrica
        paneles_max_techo, kwp_max_techo = sizing_geometrico(area_techo)
        
        st.success(f"⚡ **Inversor (NEC):** {req_inversor:.2f} kVA min.")
        st.success(f"🔋 **Batería (IEEE):** {req_bat:.2f} kWh netos.")
        
        # Alerta si el techo es muy pequeño para lo que el cliente pide
        if req_pv_energia > kwp_max_techo:
            st.error(f"☀️ **Paneles:** Requiere {req_pv_energia:.2f} kWp, pero en el techo solo caben {kwp_max_techo:.2f} kWp ({paneles_max_techo} paneles). ¡Falta espacio!")
        else:
            st.success(f"☀️ **Paneles (IEC):** Requiere {req_pv_energia:.2f} kWp. El techo soporta hasta {kwp_max_techo:.2f} kWp. OK.")

st.markdown("---")

# --- BLOQUE 2: BARRA LATERAL COMERCIAL ---
st.sidebar.header("2. Selección Comercial (BOM)")
st.sidebar.caption("Cruce el dictamen con los equipos reales.")

lista_equipos = df_catalogo['Equipo'].tolist()
equipo_seleccionado = st.sidebar.selectbox("Inversor/Equipo Principal:", lista_equipos)

if equipo_seleccionado != "Error":
    precio_unitario = df_catalogo.loc[df_catalogo['Equipo'] == equipo_seleccionado, '$'].values[0]
else:
    precio_unitario = 0.0

cantidad = st.sidebar.number_input("Cantidad de Inversores:", min_value=1, value=1, step=1)
costo_equipos_victron = precio_unitario * cantidad
st.sidebar.markdown(f"**Subtotal Victron:** ${costo_equipos_victron:,.2f} USD")

st.sidebar.markdown("---")
st.sidebar.header("3. Resto del BOS")
otros_costos = st.sidebar.number_input("Paneles, Baterías, Cables (USD):", value=15000.0, step=1000.0)

capex_total = costo_equipos_victron + otros_costos
st.sidebar.markdown(f"### CAPEX Total: ${capex_total:,.2f} USD")

st.sidebar.markdown("---")
st.sidebar.header("4. Finanzas")
ahorro_anual = st.sidebar.number_input("Ahorro Anual Proyectado USD", value=4500.0, step=100.0)
opex_anual = st.sidebar.number_input("OPEX Anual USD", value=300.0, step=50.0)
costo_baterias = st.sidebar.number_input("Costo Reemplazo Baterías USD", value=6000.0, step=500.0)
anio_reemplazo = st.sidebar.slider("Año Reemplazo Batería", min_value=5, max_value=15, value=10)
cok = st.sidebar.slider("COK (%)", min_value=2.0, max_value=20.0, value=8.0, step=0.5) / 100
anios = st.sidebar.slider("Años Evaluación", min_value=10, max_value=25, value=20)

# --- EJECUCIÓN DEL CÁLCULO FINANCIERO ---
df, vpn, tir, payback = calcular_flujo_caja(capex_total, ahorro_anual, opex_anual, anios, costo_baterias, anio_reemplazo, cok)

# --- RESULTADOS FINANCIEROS ---
col1, col2, col3 = st.columns(3)
col1.metric("Valor Presente Neto (VPN)", f"${vpn:,.2f}", delta="Viable" if vpn > 0 else "No Viable")
col2.metric("Tasa Interna de Retorno (TIR)", f"{tir:.2f}%")
col3.metric("Periodo de Recuperación (Desc.)", payback)

st.subheader("Proyección Financiera a Largo Plazo")
fig = go.Figure()
fig.add_trace(go.Bar(x=df["Año"], y=df["Flujo Nominal ($)"], name="Flujo Nominal", marker_color=['red' if val < 0 else 'green' for val in df["Flujo Nominal ($)"]]))
fig.add_trace(go.Scatter(x=df["Año"], y=df["Retorno Acumulado ($)"], name="Retorno Acum. (Descontado)", mode='lines+markers', line=dict(color='orange', width=3)))
fig.update_layout(xaxis_title="Años de Operación", yaxis_title="USD ($)", hovermode="x unified", template="plotly_white")
st.plotly_chart(fig, use_container_width=True)
