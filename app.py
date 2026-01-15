import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import json
import numpy as np
import os

# 1. Configuration de la page
st.set_page_config(page_title="Radar Luca TOTK", layout="wide")

# 2. Chargement et Sauvegarde des données
DATA_FILE = '02_shrines_details.json'

@st.cache_data
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        df = pd.DataFrame(data.get('shrines', []))
        # Si la colonne 'visité' n'existe pas dans le JSON, on l'initialise
        if 'visité' not in df.columns:
            df['visité'] = 0
        return df
    else:
        st.error(f"Fichier {DATA_FILE} non trouvé !")
        return pd.DataFrame()

def save_data(df):
    # On convertit le DataFrame en dictionnaire pour le format JSON d'origine
    shrines_dict = df.to_dict(orient='records')
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump({"shrines": shrines_dict}, f, indent=4, ensure-ascii=False)
    # On vide le cache pour que le prochain chargement prenne les nouvelles valeurs
    st.cache_data.clear()

# Initialisation du DataFrame dans le session_state
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

# On utilise le DF du session_state pour avoir les mises à jour en temps réel
df_top = get_nearest(st.session_state.df, x, y, k, vitesse)

# 5. Interface Principale
st.title("🏹 Radar de Sanctuaires")

col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("Action")
    target = st.selectbox("Sélectionner un sanctuaire :", df_top['name'].tolist())
    
    # Récupération du statut actuel
    current_status = st.session_state.df.loc[st.session_state.df['name'] == target, 'visité'].values[0]
    
    label = "✅ Marquer comme fait" if current_status == 0 else "↩️ Annuler la visite"
    if st.button(label, use_container_width=True, type="primary" if current_status == 0 else "secondary"):
        # Mise à jour dans le session_state
        idx = st.session_state.df[st.session_state.df['name'] == target].index[0]
        st.session_state.df.at[idx, 'visité'] = 1 - current_status
        
        # SAUVEGARDE PHYSIQUE dans le fichier JSON
        save_data(st.session_state.df)
        
        st.success(f"Statut de {target} mis à jour !")
        st.rerun()
    
    st.metric("Progression Globale", f"{int(st.session_state.df['visité'].sum())} / 152")
    st.write("---")
    st.write("📋 **Détails proches :**")
    # On affiche aussi le statut dans le tableau pour plus de clarté
    st.dataframe(df_top[['name', 'distance_m', 'temps', 'visité']], hide_index=True)

with col1:
    # --- CONFIGURATION CARTE ---
    limites = [[-4000, -5000], [4000, 5000]]
    
    m = folium.Map(
        crs='Simple', 
        location=[y, x], 
        zoom_start=0, 
        min_zoom=-3, 
        max_zoom=3
    )
    
    folium.raster_layers.ImageOverlay(
        image="TOTK_Hyrule_Map.png", 
        bounds=limites, 
        opacity=0.8
    ).add_to(m)

    m.fit_bounds(limites)

    # Marqueur Link (Vert)
    folium.Marker(
        [y, x], 
        tooltip="Link est ici", 
        icon=folium.Icon(color='green', icon='user', prefix='fa')
    ).add_to(m)

    # Marqueurs Sanctuaires
    for _, s in df_top.iterrows():
        # On vérifie l'état visité pour la couleur
        est_fait = s['visité'] == 1
        couleur = 'blue' if est_fait else 'orange'  # 'blue' ou 'lightgray' pour les faits
        
        popup_txt = f"<b>{s['name']}</b><br>Statut: {'Fait' if est_fait else 'À faire'}<br>Dist: {s['distance_m']:.0f}m"
        
        folium.Marker(
            [s['y'], s['x']], 
            popup=popup_txt, 
            icon=folium.Icon(color=couleur, icon='info-sign')
        ).add_to(m)

    st_folium(m, width=800, height=600, returned_objects=[])