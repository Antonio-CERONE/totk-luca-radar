import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import json
import numpy as np

# 1. Configuration de la page
st.set_page_config(page_title="Radar Luca TOTK", layout="wide")

# 2. Chargement des données
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

# 3. Barre latérale : Saisie des coordonnées
st.sidebar.title("🎮 Guide de Luca")
x = st.sidebar.number_input("Position X", value=-254.0)
y = st.sidebar.number_input("Position Y", value=107.0)
k = st.sidebar.slider("Sanctuaires proches", 1, 20, 10)
vitesse = st.sidebar.number_input("Vitesse (km/h)", value=8.5)

# 4. Calcul des plus proches
def get_nearest(df, px, py, k, speed):
    temp = df.copy()
    # Distance euclidienne
    temp['distance_m'] = np.sqrt((temp['x'] - px)**2 + (temp['y'] - py)**2)
    res = temp.sort_values('distance_m').head(k).copy()
    # Calcul du temps
    speed_mps = speed / 3.6
    res['temps'] = res['distance_m'].apply(lambda d: f"{int((d/speed_mps)//60)}m {int((d/speed_mps)%60)}s")
    return res

df_top = get_nearest(st.session_state.df, x, y, k, vitesse)

# 5. Interface Principale
st.title("🏹 Radar de Sanctuaires")

col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("Action")
    target = st.selectbox("Sélectionner un sanctuaire :", df_top['name'].tolist())
    
    # Récupération du statut
    current_status = st.session_state.df.loc[st.session_state.df['name'] == target, 'visité'].values[0]
    
    label = "✅ Marquer comme fait" if current_status == 0 else "↩️ Annuler la visite"
    if st.button(label, use_container_width=True, type="primary" if current_status == 0 else "secondary"):
        idx = st.session_state.df[st.session_state.df['name'] == target].index[0]
        st.session_state.df.at[idx, 'visité'] = 1 - current_status
        st.rerun()
    
    st.metric("Progression Globale", f"{int(st.session_state.df['visité'].sum())} / 152")
    st.write("---")
    st.write("📋 **Détails proches :**")
    st.dataframe(df_top[['name', 'distance_m', 'temps']], hide_index=True)

with col1:
    # --- CONFIGURATION CARTE ---
    limites = [[-4000, -5000], [4000, 5000]]
    
    # Création de l'objet Map
    m = folium.Map(
        crs='Simple', 
        location=[y, x], 
        zoom_start=-1, 
        min_zoom=-3, 
        max_zoom=2
    )
    
    # Image de fond
    folium.raster_layers.ImageOverlay(
        image="TOTK_Hyrule_Map.png", 
        bounds=limites, 
        opacity=0.8
    ).add_to(m)

    # Ajustement automatique au démarrage
    m.fit_bounds(limites)

    # Marqueur Link (Vert)
    folium.Marker(
        [y, x], 
        tooltip="Link est ici", 
        icon=folium.Icon(color='green', icon='user', prefix='fa')
    ).add_to(m)

    # Marqueurs Sanctuaires
    for _, s in df_top.iterrows():
        est_fait = s['visité'] == 1
        couleur = 'lightgray' if est_fait else 'orange'
        popup_txt = f"<b>{s['name']}</b><br>Dist: {s['distance_m']:.0f}m<br>Temps: {s['temps']}"
        
        folium.Marker(
            [s['y'], s['x']], 
            popup=popup_txt, 
            icon=folium.Icon(color=couleur)
        ).add_to(m)

    # Affichage final
    st_folium(m, width=800, height=600, returned_objects=[])