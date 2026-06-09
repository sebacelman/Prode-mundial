import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Prode Mundial 2026", page_icon="⚽", layout="centered")

# --- SECRETS Y CLAVES ---
API_KEY_ODDS = 'a9b7c4446ff19f47b711aea2ac633e5a' 
JSONBIN_BIN_ID = st.secrets["JSONBIN_BIN_ID"]
JSONBIN_KEY = st.secrets["JSONBIN_KEY"]
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

SPORT = 'soccer_fifa_world_cup' 
MARKETS = 'h2h,totals' 
REGIONS = 'eu' 

# --- CONEXIÓN CON JSONBIN (NUBE) ---
def cargar_predicciones_nube():
    headers = {'X-Master-Key': JSONBIN_KEY}
    try:
        response = requests.get(JSONBIN_URL, headers=headers)
        if response.status_code == 200:
            return response.json().get('record', {})
    except:
        pass
    return {}

def guardar_prediccion_nube(id_partido, marcador):
    # 1. Traemos el historial completo de la nube
    estado_actual = cargar_predicciones_nube()
    
    # 2. Actualizamos el diccionario con la nueva predicción
    estado_actual[str(id_partido)] = str(marcador)
    
    # 3. Sobrescribimos la base de datos en la nube
    headers = {
        'Content-Type': 'application/json',
        'X-Master-Key': JSONBIN_KEY
    }
    requests.put(JSONBIN_URL, json=estado_actual, headers=headers)
    
    # 4. Actualizamos la memoria visual de la app
    st.session_state['predicciones'][str(id_partido)] = marcador

# --- TRATAMIENTO DE DATOS DE THE ODDS API ---
@st.cache_data(ttl=3600)
def obtener_partidos_api():
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds'
    params = {'apiKey': API_KEY_ODDS, 'regions': REGIONS, 'markets': MARKETS, 'oddsFormat': 'decimal'}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return []

if 'predicciones' not in st.session_state:
    st.session_state['predicciones'] = cargar_predicciones_nube()

st.title("🏆 Predictor Prode (JSONBin Nube)")
st.write("Datos guardados permanentemente sin tarjetas de crédito.")

if st.button("🔄 Sincronizar Fixture (Próximos 15 días)"):
    st.cache_data.clear()
    st.session_state['predicciones'] = cargar_predicciones_nube()
    st.rerun()

datos_api = obtener_partidos_api()

if datos_api:
    ahora = datetime.now(timezone.utc)
    proximos_15_dias = ahora + timedelta(days=15)
    partidos_encontrados = False

    for partido in datos_api:
        id_partido = str(partido['id'])
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
                
                if st.button(f"🔮 Calcular y guardar", key=f"btn_{id_partido}"):
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
                            
                            marcador_final = f"{marcador_base} {origen_dato}"
                            
                            with st.spinner('Guardando en la nube...'):
                                guardar_prediccion_nube(id_partido, marcador_final)
                            st.rerun()
                        else:
                            st.warning("No se encontraron cuotas base para este encuentro.")
                    else:
                        st.warning("No hay cuotas disponibles aún para este partido.")
                        
    if not partidos_encontrados:
        st.info("No hay partidos en los próximos 15 días.")
else:
    st.error("Error al conectar con la API de cuotas.")
