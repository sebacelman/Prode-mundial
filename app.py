import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Mi Prode en Google Sheets", page_icon="⚽", layout="centered")

API_KEY = 'a9b7c4446ff19f47b711aea2ac633e5a' 
SPORT = 'soccer_fifa_world_cup' 
MARKETS = 'h2h,totals' 
REGIONS = 'eu' 

# --- CONEXIÓN CON GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_predicciones_sheets():
    try:
        df = conn.read(ttl=0)
        if not df.empty and 'id_partido' in df.columns and 'prediccion' in df.columns:
            return dict(zip(df['id_partido'].astype(str), df['prediccion'].astype(str)))
    except Exception as e:
        pass
    return {}

def guardar_prediccion_sheets(id_partido, marcador):
    try:
        df_actual = conn.read(ttl=0)
    except:
        df_actual = pd.DataFrame(columns=['id_partido', 'prediccion'])
    
    if df_actual.empty or 'id_partido' not in df_actual.columns:
        df_actual = pd.DataFrame(columns=['id_partido', 'prediccion'])

    df_actual['id_partido'] = df_actual['id_partido'].astype(str)

    if id_partido in df_actual['id_partido'].values:
        df_actual.loc[df_actual['id_partido'] == id_partido, 'prediccion'] = marcador
    else:
        nueva_fila = pd.DataFrame([{'id_partido': str(id_partido), 'prediccion': str(marcador)}])
        df_actual = pd.concat([df_actual, nueva_fila], ignore_index=True)
    
    conn.update(data=df_actual)
    st.session_state['predicciones'][id_partido] = marcador

# --- TRATAMIENTO DE DATOS DE THE ODDS API ---
@st.cache_data(ttl=3600)
def obtener_partidos_api():
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds'
    params = {'apiKey': API_KEY, 'regions': REGIONS, 'markets': MARKETS, 'oddsFormat': 'decimal'}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return []

if 'predicciones' not in st.session_state:
    st.session_state['predicciones'] = cargar_predicciones_sheets()

st.title("🏆 Prode Mundial 2026 (Nube)")
st.write("Datos sincronizados directamente en tu Google Sheet.")

if st.button("🔄 Sincronizar Fixture (Próximos 15 días)"):
    st.cache_data.clear()
    st.session_state['predicciones'] = cargar_predicciones_sheets()
    st.rerun()

datos_api = obtener_partidos_api()

if datos_api:
    ahora = datetime.now(timezone.utc)
    proximos_15_dias = ahora + timedelta(days=15)
    partidos_encontrados = False

    for partido in datos_api:
        id_partido = str(partido['id'])
        # Ya tiene corregido el error de la "o" faltante
        fecha_partido = datetime.strptime(partido['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        
        if ahora <= fecha_partido <= proximos_15_dias:
            partidos_encontrados = True
            equipo_local = partido['home_team']
            equipo_visitante = partido['away_team']
            fecha_formateada = fecha_partido.strftime("%d/%m %H:%M")
            
            with st.container(border=True):
                st.markdown(f"**📅 {fecha_formateada}**")
                st.subheader(f"{equipo_local} vs {equipo_visitante}")
                
                prediccion_actual = st.session_state['predicciones'].get(id_partido, "Sin predecir")
                
                if prediccion_actual != "Sin predecir":
                    st.success(f"📝 Pronóstico guardado: **{prediccion_actual}**")
                else:
                    st.info("📝 Estado: Sin predecir")
                
                if st.button(f"🔮 Calcular y guardar en Sheets", key=f"btn_{id_partido}"):
                    if partido['bookmakers']:
                        h2h = None
                        totals = None
                        
                        for bookmaker in partido['bookmakers']:
                            mercados = bookmaker['markets']
                            h2h_temp = next((m['outcomes'] for m in mercados if m['key'] == 'h2h'), None)
                            totals_temp = next((m['outcomes'] for m in mercados if m['key'] == 'totals'), None)
                            
                            if h2h_temp and totals_temp:
                                h2h = h2h_temp
                                totals = totals_temp
                                break 
                        
                        if not h2h:
                            for bookmaker in partido['bookmakers']:
                                mercados = bookmaker['markets']
                                h2h_temp = next((m['outcomes'] for m in mercados if m['key'] == 'h2h'), None)
                                if h2h_temp:
                                    h2h = h2h_temp
                                    break
                        
                        if h2h:
                            ganador_cuota = min(h2h, key=lambda x: x['price'])['name']
                            
                            # --- NUEVA LÓGICA DE TRANSPARENCIA ---
                            if totals:
                                es_under = 'Under' in min(totals, key=lambda x: x['price'])['name']
                                origen_dato = "🎯 (Apuestas)"
                            else:
                                es_under = True 
                                origen_dato = "🛡️ (Respaldo)"
                            
                            if ganador_cuota == equipo_local:
                                marcador_base = "1-0" if es_under else "2-1"
                            elif ganador_cuota == equipo_visitante:
                                marcador_base = "0-1" if es_under else "1-2"
                            else:
                                marcador_base = "1-1" if es_under else "2-2"
                            
                            # Juntamos el resultado numérico con la etiqueta de cómo se calculó
                            marcador_final = f"{marcador_base} {origen_dato}"
                            
                            with st.spinner('Guardando en Google Sheets...'):
                                guardar_prediccion_sheets(id_partido, marcador_final)
                            st.rerun()
                        else:
                            st.warning("No se encontraron cuotas base (Ganador/Empate) para este encuentro en ninguna casa de apuestas.")
                    else:
                        st.warning("No hay cuotas disponibles aún para este partido.")
                        
    if not partidos_encontrados:
        st.info("No hay partidos en los próximos 15 días.")
else:
    st.error("Error al conectar con la API de cuotas.")
