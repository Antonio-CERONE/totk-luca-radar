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
        # On extrait la liste des sanctuaires
        shrines_list = data.get('shrines', [])
        df = pd.DataFrame(shrines_list)
        
        # Initialisation de la colonne 'visité' si elle n'existe pas
        if 'visité' not in df.columns:
            df['visité'] = 0
        return df
    else:
        st.error(f"Fichier {DATA_FILE} non trouvé !")
        return pd.DataFrame()

def save_data(df):
    # Conversion du DataFrame en dictionnaire pour respecter le format JSON
    shrines_dict = df.to_dict(orient='records')
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        # Correction : ensure_ascii avec un underscore _
        json.dump({"shrines": shrines_dict}, f, indent=4, ensure_ascii=False)
    # On vide le cache Streamlit pour forcer la relecture au prochain tour
    st.cache_data.clear()

# Initialisation du DataFrame dans le session_state pour l'interactivité
if 'df' not in st.session_state:
    st.session_state.df = load_data()

# 3. Barre latérale : Paramètres de Link
st.sidebar.title("🎮 Bienvenue à toi Luca")
x = st.sidebar.number_input("Position X", value=-254.0)
y = st.sidebar.number_input("Position Y", value=107.0)
k = st.sidebar.slider("Sanctuaires proches", 1, 20, 10)
vitesse = st.sidebar.number_input("Vitesse (km/h)", value=8.5)

# 4. Fonction de calcul des sanctuaires les plus proches
def get_nearest(df, px, py, k, speed):
    temp = df.copy()
    # Calcul de la distance euclidienne
    temp['distance_m'] = np.sqrt((temp['x'] - px)**2 + (temp['y'] - py)**2)
    res = temp.sort_values('distance_m').head(k).copy()
    
    # Calcul du temps de trajet estimé
    speed_mps = speed / 3.6
    res['temps'] = res['distance_m'].apply(
        lambda d: f"{int((d/speed_mps)//60)}m {int((d/speed_mps)%60)}s"
    )
    return res

# On calcule les données à afficher basées sur l'état actuel de la session
df_top = get_nearest(st.session_state.df, x, y, k, vitesse)

# 5. Interface Principale
st.title("🏹 Radar de Sanctuaires")

col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("Action")
    target = st.selectbox("Sélectionner un sanctuaire :", df_top['name'].tolist())
    
    # Récupération du statut actuel pour le bouton
    current_status = st.session_state.df.loc[st.session_state.df['name'] == target, 'visité'].values[0]
    
    label = "✅ Marquer comme fait" if current_status == 0 else "↩️ Annuler la visite"
    
    if st.button(label, use_container_width=True, type="primary" if current_status == 0 else "secondary"):
        # 1. Mise à jour dans l'état de la session
        idx = st.session_state.df[st.session_state.df['name'] == target].index[0]
        st.session_state.df.at[idx, 'visité'] = 1 - current_status
        
        # 2. Sauvegarde dans le fichier JSON (persistance)
        save_data(st.session_state.df)
        
        # 3. Rafraîchissement de l'application
        st.rerun()
    
    # Statistiques de progression
    total_shrines = len(st.session_state.df)
    done_shrines = int(st.session_state.df['visité'].sum())
    st.metric("Progression Globale", f"{done_shrines} / {total_shrines}")
    
    st.write("---")
    st.write("📋 **Détails des alentours :**")
    # Affichage du tableau avec statut
    st.dataframe(df_top[['name', 'distance_m', 'temps', 'visité']], hide_index=True)

with col1:
    # --- CONFIGURATION CARTE ---
    limites = [[-4000, -5000], [4000, 5000]]
    
    m = folium.Map(
        crs='Simple', 
        location=[y, x], 
        zoom_start=-2, 
        min_zoom=-3, 
        max_zoom=3
    )
    
    # Ajout de l'image de fond (Map TOTK)
    folium.raster_layers.ImageOverlay(
        image="TOTK_Hyrule_Map.png", 
        bounds=limites, 
        opacity=0.8
    ).add_to(m)

    # m.fit_bounds(limites)

    # Marqueur pour Link (Position actuelle)
    folium.Marker(
        [y, x], 
        tooltip="Link est ici", 
        icon=folium.Icon(color='green', icon='user', prefix='fa')
    ).add_to(m)

    # Marqueurs pour les sanctuaires à proximité
    for _, s in df_top.iterrows():
        est_fait = s['visité'] == 1
        # Couleur : Orange pour "à faire", Gris pour "visité"
        couleur = 'lightgray' if est_fait else 'orange'
        
        popup_txt = f"<b>{s['name']}</b><br>Statut: {'✅ Fait' if est_fait else '❌ À faire'}<br>Dist: {s['distance_m']:.0f}m"
        
        folium.Marker(
            [s['y'], s['x']], 
            popup=popup_txt, 
            icon=folium.Icon(color=couleur)
        ).add_to(m)

    # Affichage de la carte
    st_folium(m, width=800, height=600, returned_objects=[])