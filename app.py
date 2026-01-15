import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import numpy as np
import json

# 1. Configuration de la page
st.set_page_config(page_title="Radar Luca TOTK", layout="wide")

# 2. Connexion à Google Sheets
# On laisse Streamlit gérer les secrets automatiquement via [connections.gsheets]
url = "https://docs.google.com/spreadsheets/d/1Kw65ATn2m9YkDZunhRVwWqUHKDgIg2B3d6eGusNckDo/edit#gid=0"
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600)
def load_data():
    return conn.read(spreadsheet=url, worksheet="shrines")

# --- CHARGEMENT / INITIALISATION ---
if 'df' not in st.session_state:
    try:
        df_cloud = load_data()
        if df_cloud is None or df_cloud.empty:
            with open('02_shrines_details.json', 'r', encoding='utf-8') as f:
                local_data = json.load(f)
            df_init = pd.DataFrame(local_data.get('shrines', []))
            if 'visité' not in df_init.columns:
                df_init['visité'] = 0
            conn.update(spreadsheet=url, worksheet="shrines", data=df_init)
            st.session_state.df = df_init
        else:
            df_cloud['visité'] = pd.to_numeric(df_cloud['visité'], errors='coerce').fillna(0).astype(int)
            st.session_state.df = df_cloud
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        st.stop()

# 3. Barre latérale
st.sidebar.title("🎮 Guide de Luca")
link_x = st.sidebar.number_input("Position X", value=-254.0)
link_y = st.sidebar.number_input("Position Y", value=107.0)
k = st.sidebar.slider("Sanctuaires proches", 1, 20, 10)
vitesse = st.sidebar.number_input("Vitesse (km/h)", value=8.5)

# 4. Calcul des distances
def get_nearest(df, px, py, k, speed):
    temp = df.copy()
    temp['distance_m'] = np.sqrt((temp['x'] - px)**2 + (temp['y'] - py)**2)
    res = temp.sort_values('distance_m').head(k).copy()
    speed_mps = speed / 3.6
    res['temps'] = res['distance_m'].apply(lambda d: f"{int((d/speed_mps)//60)}m {int((d/speed_mps)%60)}s")
    return res

df_top = get_nearest(st.session_state.df, link_x, link_y, k, vitesse)

# 5. Interface
st.title("🏹 Radar de Sanctuaires")
col1, col2 = st.columns([2, 1])

with col2:
    target = st.selectbox("Sélectionner un sanctuaire :", df_top['name'].tolist())
    status = st.session_state.df.loc[st.session_state.df['name'] == target, 'visité'].values[0]
    
    label = "✅ Marquer comme fait" if status == 0 else "↩️ Annuler"
    if st.button(label, use_container_width=True):
        idx = st.session_state.df[st.session_state.df['name'] == target].index[0]
        st.session_state.df.at[idx, 'visité'] = 1 - status
        conn.update(spreadsheet=url, worksheet="shrines", data=st.session_state.df)
        st.cache_data.clear()
        st.rerun()
    
    st.metric("Progression", f"{int(st.session_state.df['visité'].sum())} / 152")
    st.dataframe(df_top[['name', 'distance_m', 'visité']], hide_index=True)

with col1:
    # Carte centrée sur Link avec Zoom -3 à +3
    m = folium.Map(crs='Simple', location=[link_y, link_x], zoom_start=0, min_zoom=-3, max_zoom=3)
    folium.raster_layers.ImageOverlay(image="TOTK_Hyrule_Map.png", bounds=[[-4000, -5000], [4000, 5000]], opacity=0.8).add_to(m)
    folium.Marker([link_y, link_x], icon=folium.Icon(color='green', icon='user', prefix='fa')).add_to(m)
    
    for _, s in df_top.iterrows():
        folium.Marker([s['y'], s['x']], popup=s['name'], 
                      icon=folium.Icon(color='lightgray' if s['visité'] == 1 else 'orange')).add_to(m)
    
    st_folium(m, width=1000, height=800, returned_objects=[])