import streamlit as st
import requests
from datetime import datetime, timedelta, timezone

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Mi Prode Mundial 2026", page_icon="⚽", layout="centered")

# --- PARÁMETROS FIJOS (CALIBRADOS) ---
API_KEY_ODDS = 'a9b7c4446ff19f47b711aea2ac633e5a' 
JSONBIN_BIN_ID = st.secrets["JSONBIN_BIN_ID"]
JSONBIN_KEY = st.secrets["JSONBIN_KEY"]
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
UMBRAL_PARIDAD = 0.45  # Valor fijo basado en el percentil 21% de Qatar 2022

SPORT = 'soccer_fifa_world_cup' 
MARKETS = 'h2h,totals' 
REGIONS = 'eu' 

# --- CONEXIÓN NUBE ---
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
    estado_actual = cargar_predicciones_nube()
    estado_actual[str(id_partido)] = str(marcador)
    headers = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_KEY}
    requests.put(JSONBIN_URL, json=estado_actual, headers=headers)
    st.session_state['predicciones'][str(id_partido)] = marcador

# --- MOTOR HEURÍSTICO ---
def calcular_marcador_inteligente(ganador, cuota_ganador, equipo_local, equipo_visitante, tendencia_goles_str):
    if not tendencia_goles_str:
        es_under = True
        linea_numerica = 2.5
    else:
        partes = tendencia_goles_str.split()
        es_under = "Under" in partes[0]
        linea_numerica = float(partes[1]) if len(partes) > 1 else 2.5

    es_goleada = cuota_ganador < 1.55

    if ganador not in [equipo_local, equipo_visitante]:
        if es_under: return "0-0" if linea_numerica < 2.0 else "1-1"
        else: return "2-2" if linea_numerica < 4.0 else "3-3"

    if es_under:
        if linea_numerica <= 1.5: goles_ganador, goles_perdedor = 1, 0
        elif linea_numerica <= 2.5: goles_ganador, goles_perdedor = 2, 0
        elif linea_numerica <= 3.5: goles_ganador, goles_perdedor = (3, 0) if es_goleada else (2, 1)
        else: goles_ganador, goles_perdedor = (4, 0) if es_goleada else (3, 1)
    else:
        if linea_numerica <= 1.5: goles_ganador, goles_perdedor = (3, 0) if es_goleada else (2, 0)
        elif linea_numerica <= 2.5: goles_ganador, goles_perdedor = (3, 0) if es_goleada else (2, 1)
        elif linea_numerica <= 3.5: goles_ganador, goles_perdedor = (4, 0) if es_goleada else (3, 1)
        else: goles_ganador, goles_perdedor = (5, 0) if es_goleada else (3, 2)

    return f"{goles_ganador}-{goles_perdedor}" if ganador == equipo_local else f"{goles_perdedor}-{goles_ganador}"

# --- APP ---
@st.cache_data(ttl=3600)
def obtener_partidos_api():
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds'
    params = {'apiKey': API_KEY_ODDS, 'regions': REGIONS, 'markets': MARKETS, 'oddsFormat': 'decimal'}
    response = requests.get(url, params=params)
    return response.json() if response.status_code == 200 else []

if 'predicciones' not in st.session_state:
    st.session_state['predicciones'] = cargar_predicciones_nube()

st.title("🏆 Mi Prode Cuantitativo")
st.write(f"Umbral de paridad (fijo): {UMBRAL_PARIDAD}")

if st.button("🔄 Sincronizar"):
    st.cache_data.clear()
    st.session_state['predicciones'] = cargar_predicciones_nube()
    st.rerun()

datos_api = obtener_partidos_api()

for partido in datos_api:
    fecha_partido = datetime.strptime(partido['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) <= fecha_partido <= (datetime.now(timezone.utc) + timedelta(days=15)):
        with st.container(border=True):
            st.subheader(f"{partido['home_team']} vs {partido['away_team']}")
            if st.button("🔮 Calcular", key=f"btn_{partido['id']}"):
                # Lógica simplificada de extracción
                h2h = next((m['outcomes'] for m in partido['bookmakers'][0]['markets'] if m['key'] == 'h2h'), None)
                totals = next((m['outcomes'] for m in partido['bookmakers'][0]['markets'] if m['key'] == 'totals'), None)
                
                cuota_local = next((x['price'] for x in h2h if x['name'] == partido['home_team']), 99.0)
                cuota_visitante = next((x['price'] for x in h2h if x['name'] == partido['away_team']), 99.0)
                
                # APLICACIÓN DEL UMBRAL FIJO
                if abs(cuota_local - cuota_visitante) <= UMBRAL_PARIDAD and min(cuota_local, cuota_visitante) > 2.00:
                    ganador_nombre, es_empate = "Empate Técnico", True
                else:
                    ganador_nombre, es_empate = min(h2h, key=lambda x: x['price'])['name'], False
                
                marcador = calcular_marcador_inteligente(ganador_nombre, min(h2h, key=lambda x: x['price'])['price'], partido['home_team'], partido['away_team'], totals[0]['name'] if totals else None)
                marcador_final = f"{'⚖️ ' if es_empate else ''}{marcador}"
                
                guardar_prediccion_nube(partido['id'], marcador_final)
                st.rerun()
            st.info(f"Pronóstico: {st.session_state['predicciones'].get(partido['id'], 'Sin predecir')}")
