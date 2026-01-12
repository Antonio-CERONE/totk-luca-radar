import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import json
import numpy as np

# Configuration de l'interface Luca
st.set_page_config(page_title="Radar Luca TOTK", layout="wide")

@st.cache_data
def load_data():
    with open('02_shrines_details.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    df = pd.DataFrame(data.get('shrines', []))
    if 'visité' not in df.columns:
        df['visité'] = 0
    return df

if 'df' not in st.session_state:
    st.session_state.df = load_data()

# Barre latérale pour Luca
st.sidebar.header("📍 Position de Link")
x_pos = st.sidebar.number_input("Coordonnée X", value=-565.0)
y_pos = st.sidebar.number_input("Coordonnée Y", value=-3524.0)
k_shrines = st.sidebar.slider("Sanctuaires à afficher", 1, 20, 10)
vitesse = st.sidebar.number_input("Vitesse (km/h)", value=8.5)

# Calcul des distances et temps
def get_nearest(df, px, py, k, speed):
    temp = df.copy()
    temp['distance_m'] = np.sqrt((temp['x'] - px)**2 + (temp['y'] - py)**2)
    res = temp.sort_values('distance_m').head(k).copy()
    speed_mps = speed / 3.6
    res['temps'] = res['distance_m'].apply(lambda d: f"{int((d/speed_mps)//60)}min {int((d/speed_mps)%60)}s")
    return res

df_top = get_nearest(st.session_state.df, x_pos, y_pos, k_shrines, vitesse)

st.title("🏹 Radar Sheikah de Luca")

col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("Validation")
    target = st.selectbox("Sélectionner un sanctuaire :", df_top['name'].tolist())
    
    status_val = st.session_state.df.loc[st.session_state.df['name'] == target, 'visité'].values[0]
    is_done = (status_val == 1)
    
    if st.button("Marquer comme visité" if not is_done else "Annuler la visite", 
                 type="primary" if not is_done else "secondary", use_container_width=True):
        idx = st.session_state.df[st.session_state.df['name'] == target].index[0]
        st.session_state.df.at[idx, 'visité'] = 1 - status_val
        st.rerun()

    st.write(f"📊 **Progression : {int(st.session_state.df['visité'].sum())} / 152**")

with col1:
    # Carte Folium
    m = folium.Map(crs='Simple', location=[y_pos, x_pos], zoom_start=0)
    folium.raster_layers.ImageOverlay(
        image="TOTK_Hyrule_Map.png", 
        bounds=[[-4000, -5000], [4000, 5000]], 
        opacity=0.8
    ).add_to(m)
    
    # Link
    folium.Marker([y_pos, x_pos], icon=folium.Icon(color='green', icon='user', prefix='fa')).add_to(m)

    # Sanctuaires
    for _, s in df_top.iterrows():
        fait = (s['visité'] == 1)
        color = 'lightgray' if fait else 'orange'
        popup_html = f"<b>{s['name']}</b><br>Statut: {'✅ Fait' if fait else '⏳ À faire'}<br>Dist: {s['distance_m']:.0f}m<br>Temps: {s['temps']}"
        folium.Marker([s['y'], s['x']], popup=popup_html, icon=folium.Icon(color=color)).add_to(m)
    
    st_folium(m, width=700, height=500, returned_objects=[])

st.subheader("📋 Liste détaillée")
st.dataframe(df_top[['name', 'region', 'distance_m', 'temps', 'visité']], use_container_width=True)