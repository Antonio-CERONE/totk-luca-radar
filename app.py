import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection # Nécessite st-gsheets-connection dans requirements.txt
import numpy as np
import json

# 1. Configuration de la page
st.set_page_config(page_title="Radar Luca TOTK", layout="wide")

# 1b. Préparation des identifiants (Correction du format de la clé)
# Au lieu de modifier st.secrets, on crée un dictionnaire de configuration
if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
    secret_gsheets = dict(st.secrets["connections"]["gsheets"])
    # On nettoie la clé dans notre copie locale
    secret_gsheets["private_key"] = secret_gsheets["private_key"].replace("\\n", "\n")
else:
    st.error("Les secrets GSheets ne sont pas configurés dans Streamlit Cloud.")
    st.stop()

# 2. Connexion à Google Sheets
# Remplace 'url' par l'URL de ton Google Sheet partagé
url = "https://docs.google.com/spreadsheets/d/1Kw65ATn2m9YkDZunhRVwWqUHKDgIg2B3d6eGusNckDo/edit#gid=0"
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600) # Rafraîchir toutes les 10 minutes
def load_data():
    return conn.read(spreadsheet=url, worksheet="shrines")

# Initialisation intelligente
if 'df' not in st.session_state:
    df_cloud = load_data()
    
    if df_cloud.empty:
        # Si le Sheet est vide, on charge le JSON local pour "remplir" le Cloud
        with open('02_shrines_details.json', 'r', encoding='utf-8') as f:
            local_data = json.load(f)
        df_init = pd.DataFrame(local_data.get('shrines', []))
        if 'visité' not in df_init.columns:
            df_init['visité'] = 0
            
        # On envoie ces données vers Google Sheets pour la première fois
        conn.update(spreadsheet=url, worksheet="shrines", data=df_init)
        st.session_state.df = df_init
        st.success("Google Sheets initialisé avec les données locales !")
    else:
        st.session_state.df = df_cloud

# 3. Barre latérale
st.sidebar.title("🎮 Guide de Luca")
x = st.sidebar.number_input("Position X", value=-254.0)
y = st.sidebar.number_input("Position Y", value=107.0)
k = st.sidebar.slider("Sanctuaires proches", 1, 20, 10)
vitesse = st.sidebar.number_input("Vitesse (km/h)", value=8.5)

# 4. Calcul des plus proches
def get_nearest(df, px, py, k, speed):
    temp = df.copy()
    temp['distance_m'] = np.sqrt((temp['x'] - px)**2 + (temp['y'] - py)**2)
    res = temp.sort_values('distance_m').head(k).copy()
    speed_mps = speed / 3.6
    res['temps'] = res['distance_m'].apply(lambda d: f"{int((d/speed_mps)//60)}m {int((d/speed_mps)%60)}s")
    return res

df_top = get_nearest(st.session_state.df, x, y, k, vitesse)

# 5. Interface Principale
st.title("🏹 Radar de Sanctuaires (Sauvegarde Cloud)")

col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("Action")
    target = st.selectbox("Sélectionner un sanctuaire :", df_top['name'].tolist())
    
    current_status = st.session_state.df.loc[st.session_state.df['name'] == target, 'visité'].values[0]
    
    label = "✅ Marquer comme fait" if current_status == 0 else "↩️ Annuler la visite"
    
    if st.button(label, use_container_width=True, type="primary" if current_status == 0 else "secondary"):
        # Mise à jour locale
        idx = st.session_state.df[st.session_state.df['name'] == target].index[0]
        st.session_state.df.at[idx, 'visité'] = 1 - current_status
        
        # SAUVEGARDE SUR GOOGLE SHEETS
        conn.update(spreadsheet=url, worksheet="shrines", data=st.session_state.df)
        
        st.cache_data.clear()
        st.success(f"Sauvegardé dans Google Sheets !")
        st.rerun()
    
    st.metric("Progression", f"{int(st.session_state.df['visité'].sum())} / 152")
    st.dataframe(df_top[['name', 'distance_m', 'temps', 'visité']], hide_index=True)

with col1:
    # --- CARTE ---
    limites = [[-4000, -5000], [4000, 5000]]
    m = folium.Map(crs='Simple', location=[y, x], zoom_start=-1)
    
    folium.raster_layers.ImageOverlay(
        image="TOTK_Hyrule_Map.png", 
        bounds=limites, 
        opacity=0.8
    ).add_to(m)

    folium.Marker([y, x], tooltip="Link", icon=folium.Icon(color='green', icon='user', prefix='fa')).add_to(m)

    for _, s in df_top.iterrows():
        couleur = 'lightgray' if s['visité'] == 1 else 'orange'
        folium.Marker([s['y'], s['x']], popup=s['name'], icon=folium.Icon(color=couleur)).add_to(m)

    st_folium(m, width=800, height=600, returned_objects=[])