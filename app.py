import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Predicciones Prode Mundial", page_icon="⚽", layout="centered")

API_KEY = 'a9b7c4446ff19f47b711aea2ac633e5a' 
SPORT = 'soccer_fifa_world_cup' # Apuntando directo al Mundial
MARKETS = 'correct_score'
REGIONS = 'eu' 

@st.cache_data(ttl=3600) # El caché es vital para cuidar tus 500 créditos
def obtener_predicciones():
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds'
    params = {
        'apiKey': API_KEY,
        'regions': REGIONS,
        'markets': MARKETS,
        'oddsFormat': 'decimal'
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        st.error(f"🚨 Error de conexión. Código: {response.status_code}")
        st.json(response.json())
        return None
    
    data = response.json()
    
    if not data:
        st.warning(f"⚠️ No hay partidos disponibles para la liga seleccionada con el mercado '{MARKETS}'.")
        return pd.DataFrame()
        
    partidos_procesados = []
    
    # Definimos la ventana de tiempo: Desde ahora hasta exactamente 7 días en el futuro
    ahora = datetime.now(timezone.utc)
    proxima_semana = ahora + timedelta(days=7)

    for partido in data:
        # Convertimos la fecha del partido (ISO 8601) a un objeto datetime de Python
        fecha_str = partido['commence_time']
        fecha_partido = datetime.strptime(fecha_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        
        # Filtro temporal: Solo procesamos si el partido ocurre en los próximos 7 días
        if ahora <= fecha_partido <= proxima_semana:
            equipo_local = partido['home_team']
            equipo_visitante = partido['away_team']
            
            if partido['bookmakers']:
                apuestas = partido['bookmakers'][0]['markets'][0]['outcomes']
                resultado_mas_probable = min(apuestas, key=lambda x: x['price'])
                
                partidos_procesados.append({
                    "Fecha": fecha_partido.strftime("%d/%m/%Y %H:%M"),
                    "Partido": f"{equipo_local} vs {equipo_visitante}",
                    "Predicción (Goles)": resultado_mas_probable['name'],
                    "Cuota": resultado_mas_probable['price']
                })
            
    if not partidos_procesados:
        st.info("No hay partidos programados para los próximos 7 días que tengan cuotas de resultado exacto publicadas.")
        return pd.DataFrame()
            
    return pd.DataFrame(partidos_procesados)

# --- INTERFAZ DE LA APP ---
st.title("🏆 Predictor Mundial 2026")
st.write("Predicciones de Resultados Exactos para los próximos 7 días.")

if st.button("Actualizar Predicciones"):
    with st.spinner('Consultando cuotas del mercado...'):
        df = obtener_predicciones()
        
        if df is not None and not df.empty:
            st.success("¡Datos actualizados!")
            st.dataframe(df, use_container_width=True, hide_index=True)
