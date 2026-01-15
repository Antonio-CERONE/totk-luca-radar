import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import numpy as np
import json
import re # Import pour le nettoyage de texte

# 1. Configuration de la page
st.set_page_config(page_title="Radar Luca TOTK", layout="wide")

# --- FONCTION DE NETTOYAGE DE LA CLÉ ---
def get_clean_creds():
    try:
        raw_key = st.secrets["connections"]["gsheets"]["private_key"]
        
        # 1. On extrait la partie entre les balises BEGIN et END
        if "-----BEGIN PRIVATE KEY-----" in raw_key:
            inner_key = raw_key.split("-----BEGIN PRIVATE KEY-----")[1].split("-----END PRIVATE KEY-----")[0]
        else:
            inner_key = raw_key

        # 2. Nettoyage radical : on enlève TOUT ce qui n'est pas un caractère Base64
        # On supprime les \n, les espaces, les tabulations, etc.
        clean_inner_key = re.sub(r'\s+', '', inner_key)
        
        # 3. On reconstruit la clé proprement avec des vrais sauts de ligne
        formatted_key = "-----BEGIN PRIVATE KEY-----\n" + clean_inner_key + "\n-----END PRIVATE KEY-----\n"
        
        # 4. On crée le dictionnaire de configuration
        creds = {
            "type": st.secrets["connections"]["gsheets"]["type"],
            "project_id": st.secrets["connections"]["gsheets"]["project_id"],
            "private_key_id": st.secrets["connections"]["gsheets"]["private_key_id"],
            "private_key": formatted_key,
            "client_email": st.secrets["connections"]["gsheets"]["client_email"],
            "client_id": st.secrets["connections"]["gsheets"]["client_id"],
            "auth_uri": st.secrets["connections"]["gsheets"]["auth_uri"],
            "token_uri": st.secrets["connections"]["gsheets"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["connections"]["gsheets"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["connections"]["gsheets"]["client_x509_cert_url"]
        }
        return creds
    except Exception as e:
        st.error(f"Erreur de lecture des secrets : {e}")
        st.stop()

# 2. Connexion à Google Sheets
url = "https://docs.google.com/spreadsheets/d/1Kw65ATn2m9YkDZunhRVwWqUHKDgIg2B3d6eGusNckDo/edit#gid=0"

# On force l'utilisation des identifiants nettoyés
creds_dict = get_clean_creds()
conn = st.connection("gsheets", type=GSheetsConnection, service_account_info=creds_dict)

@st.cache_data(ttl=600)
def load_data():
    return conn.read(spreadsheet=url, worksheet="shrines")

# --- INITIALISATION DES DONNÉES ---
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
            st.success("✅ Google Sheet initialisé !")
        else:
            # Conversion propre de la colonne visité
            df_cloud['visité'] = pd.to_numeric(df_cloud['visité'], errors='coerce').fillna(0).astype(int)
            st.session_state.df = df_cloud
    except Exception as e:
        st.error(f"❌ Erreur : {e}")
        st.stop()

# 3. Barre latérale
st.sidebar.title("🎮 Bienvenue à toi Luca")
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
        idx = st.session_state.df[st.session_state.df['name'] == target].index[0]
        st.session_state.df.at[idx, 'visité'] = 1 - current_status
        conn.update(spreadsheet=url, worksheet="shrines", data=st.session_state.df)
        st.cache_data.clear()
        st.rerun()
    
    st.metric("Progression", f"{int(st.session_state.df['visité'].sum())} / 152")
    st.dataframe(df_top[['name', 'distance_m', 'temps', 'visité']], hide_index=True)

with col1:
    # --- CONFIGURATION CARTE AGRANDIE ET ZOOM ---
    limites = [[-4000, -5000], [4000, 5000]]
    
    # On centre la carte sur la position actuelle de LINK (y, x)
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

    # Marqueur Link (toujours au centre au chargement)
    folium.Marker(
        [y, x], 
        tooltip="Link est ici", 
        icon=folium.Icon(color='green', icon='user', prefix='fa')
    ).add_to(m)

    # Sanctuaires
    for _, s in df_top.iterrows():
        couleur = 'lightgray' if s['visité'] == 1 else 'orange'
        folium.Marker(
            [s['y'], s['x']], 
            popup=s['name'], 
            icon=folium.Icon(color=couleur)
        ).add_to(m)

    # Affichage de la carte en plus grand (1000px de large, 800px de haut)
    st_folium(m, width=1000, height=800, returned_objects=[])