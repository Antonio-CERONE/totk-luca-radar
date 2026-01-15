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
# L'application va chercher les identifiants directement dans [connections.gsheets] des Secrets
url = "https://docs.google.com/spreadsheets/d/1Kw65ATn2m9YkDZunhRVwWqUHKDgIg2B3d6eGusNckDo/edit#gid=0"
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600)
def load_data():
    # Lit la feuille "shrines" du Google Sheet
    return conn.read(spreadsheet=url, worksheet="shrines")

# --- INITIALISATION DES DONNÉES ---
if 'df' not in st.session_state:
    try:
        df_cloud = load_data()
        
        # Si le Google Sheet est vide, on utilise le JSON local pour l'initialiser
        if df_cloud is None or df_cloud.empty:
            with open('02_shrines_details.json', 'r', encoding='utf-8') as f:
                local_data = json.load(f)
            df_init = pd.DataFrame(local_data.get('shrines', []))
            
            # Ajout de la colonne visite si absente
            if 'visité' not in df_init.columns:
                df_init['visité'] = 0
            
            # Envoi des données vers le Cloud
            conn.update(spreadsheet=url, worksheet="shrines", data=df_init)
            st.session_state.df = df_init
            st.success("✅ Google Sheet initialisé avec les données locales !")
        else:
            # On s'assure que la colonne 'visité' est bien de type numérique
            df_cloud['visité'] = pd.to_numeric(df_cloud['visité'], errors='coerce').fillna(0).astype(int)
            st.session_state.df = df_cloud
            
    except Exception as e:
        st.error(f"❌ Erreur lors de la connexion : {e}")
        st.info("Vérifiez que le compte de service est bien 'Éditeur' sur le Google Sheet.")
        st.stop()

# 3. Barre latérale : Entrées de Luca
st.sidebar.title("🎮 Guide de Luca")
x = st.sidebar.number_input("Position X", value=-254.0)
y = st.sidebar.number_input("Position Y", value=107.0)
k = st.sidebar.slider("Sanctuaires proches", 1, 20, 10)
vitesse = st.sidebar.number_input("Vitesse (km/h)", value=8.5)

# 4. Calcul des distances
def get_nearest(df, px, py, k, speed):
    temp = df.copy()
    # Distance euclidienne simplifiée (Zelda)
    temp['distance_m'] = np.sqrt((temp['x'] - px)**2 + (temp['y'] - py)**2)
    res = temp.sort_values('distance_m').head(k).copy()
    
    # Calcul du temps de trajet
    speed_mps = speed / 3.6
    res['temps'] = res['distance_m'].apply(
        lambda d: f"{int((d/speed_mps)//60)}m {int((d/speed_mps)%60)}s"
    )
    return res

df_top = get_nearest(st.session_state.df, x, y, k, vitesse)

# 5. Interface Principale
st.title("🏹 Radar de Sanctuaires (Cloud)")

col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("Action")
    target = st.selectbox("Sélectionner un sanctuaire :", df_top['name'].tolist())
    
    # Etat actuel
    current_status = st.session_state.df.loc[st.session_state.df['name'] == target, 'visité'].values[0]
    
    # Bouton de validation
    label = "✅ Marquer comme fait" if current_status == 0 else "↩️ Annuler la visite"
    if st.button(label, use_container_width=True, type="primary" if current_status == 0 else "secondary"):
        idx = st.session_state.df[st.session_state.df['name'] == target].index[0]
        st.session_state.df.at[idx, 'visité'] = 1 - current_status
        
        # Mise à jour Cloud
        conn.update(spreadsheet=url, worksheet="shrines", data=st.session_state.df)
        st.cache_data.clear()
        st.rerun()
    
    # Statistiques
    progression = int(st.session_state.df['visité'].sum())
    st.metric("Progression", f"{progression} / 152")
    st.write("---")
    st.dataframe(df_top[['name', 'distance_m', 'temps', 'visité']], hide_index=True)

with col1:
    # --- CARTE ---
    limites = [[-4000, -5000], [4000, 5000]]
    m = folium.Map(crs='Simple', location=[y, x], zoom_start=-1)
    
    # Fond de carte Zelda
    folium.raster_layers.ImageOverlay(
        image="TOTK_Hyrule_Map.png", 
        bounds=limites, 
        opacity=0.8
    ).add_to(m)

    # Position de Link
    folium.Marker(
        [y, x], 
        icon=folium.Icon(color='green', icon='user', prefix='fa')
    ).add_to(m)

    # Sanctuaires proches
    for _, s in df_top.iterrows():
        couleur = 'lightgray' if s['visité'] == 1 else 'orange'
        folium.Marker(
            [s['y'], s['x']], 
            popup=s['name'], 
            icon=folium.Icon(color=couleur)
        ).add_to(m)

    st_folium(m, width=800, height=600, returned_objects=[])