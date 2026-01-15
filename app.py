import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import numpy as np
import json

# 1. Configuration de la page
st.set_page_config(page_title="Radar Luca TOTK", layout="wide")

# 2. Préparation manuelle des identifiants (Correction de l'erreur binascii)
# On extrait les secrets et on répare la clé privée avant la connexion
if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
    creds_dict = {
        "type": st.secrets["connections"]["gsheets"]["type"],
        "project_id": st.secrets["connections"]["gsheets"]["project_id"],
        "private_key_id": st.secrets["connections"]["gsheets"]["private_key_id"],
        # Cette ligne transforme les \n textuels en vrais sauts de ligne
        "private_key": st.secrets["connections"]["gsheets"]["private_key"].replace("\\n", "\n"),
        "client_email": st.secrets["connections"]["gsheets"]["client_email"],
        "client_id": st.secrets["connections"]["gsheets"]["client_id"],
        "auth_uri": st.secrets["connections"]["gsheets"]["auth_uri"],
        "token_uri": st.secrets["connections"]["gsheets"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["connections"]["gsheets"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["connections"]["gsheets"]["client_x509_cert_url"],
    }
else:
    st.error("⚠️ Les Secrets GSheets ne sont pas configurés dans Streamlit Cloud.")
    st.stop()

# 3. Connexion à Google Sheets
url = "https://docs.google.com/spreadsheets/d/1Kw65ATn2m9YkDZunhRVwWqUHKDgIg2B3d6eGusNckDo/edit?usp=sharing"
# On utilise creds_dict pour forcer la clé corrigée
conn = st.connection("gsheets", type=GSheetsConnection, **creds_dict)

@st.cache_data(ttl=600)
def load_data():
    # Lit la feuille nommée "shrines"
    return conn.read(spreadsheet=url, worksheet="shrines")

# --- INITIALISATION INTELLIGENTE ---
if 'df' not in st.session_state:
    try:
        df_cloud = load_data()
        
        # Si le Google Sheet est vide (uniquement les entêtes ou rien)
        if df_cloud is None or df_cloud.empty or len(df_cloud) < 1:
            with open('02_shrines_details.json', 'r', encoding='utf-8') as f:
                local_data = json.load(f)
            df_init = pd.DataFrame(local_data.get('shrines', []))
            if 'visité' not in df_init.columns:
                df_init['visité'] = 0
            
            # On remplit le Google Sheet avec le contenu du JSON
            conn.update(spreadsheet=url, worksheet="shrines", data=df_init)
            st.session_state.df = df_init
            st.success("✅ Google Sheet initialisé avec succès !")
        else:
            st.session_state.df = df_cloud
    except Exception as e:
        st.error(f"❌ Erreur de connexion au Cloud : {e}")
        st.stop()

# 4. Barre latérale : Position de Link
st.sidebar.title("🎮 Pour Luca")
x = st.sidebar.number_input("Position X", value=-254.0)
y = st.sidebar.number_input("Position Y", value=107.0)
k = st.sidebar.slider("Sanctuaires proches", 1, 20, 10)
vitesse = st.sidebar.number_input("Vitesse (km/h)", value=8.5)

# 5. Calcul des plus proches
def get_nearest(df, px, py, k, speed):
    temp = df.copy()
    temp['distance_m'] = np.sqrt((temp['x'] - px)**2 + (temp['y'] - py)**2)
    res = temp.sort_values('distance_m').head(k).copy()
    speed_mps = speed / 3.6
    res['temps'] = res['distance_m'].apply(
        lambda d: f"{int((d/speed_mps)//60)}m {int((d/speed_mps)%60)}s"
    )
    return res

df_top = get_nearest(st.session_state.df, x, y, k, vitesse)

# 6. Interface Principale
st.title("🏹 Radar de Sanctuaires TOTK")

col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("Action")
    target = st.selectbox("Sélectionner un sanctuaire :", df_top['name'].tolist())
    
    # Récupérer l'état actuel
    current_status = st.session_state.df.loc[st.session_state.df['name'] == target, 'visité'].values[0]
    
    label = "✅ Marquer comme fait" if current_status == 0 else "↩️ Annuler la visite"
    
    if st.button(label, use_container_width=True, type="primary" if current_status == 0 else "secondary"):
        # Mise à jour locale
        idx = st.session_state.df[st.session_state.df['name'] == target].index[0]
        st.session_state.df.at[idx, 'visité'] = 1 - current_status
        
        # Sauvegarde sur Google Sheets
        conn.update(spreadsheet=url, worksheet="shrines", data=st.session_state.df)
        
        # Nettoyage et rafraîchissement
        st.cache_data.clear()
        st.rerun()
    
    progression = int(st.session_state.df['visité'].sum())
    st.metric("Progression", f"{progression} / 152")
    
    st.write("---")
    st.dataframe(df_top[['name', 'distance_m', 'temps', 'visité']], hide_index=True)

with col1:
    # --- CARTE ---
    limites = [[-4000, -5000], [4000, 5000]]
    m = folium.Map(crs='Simple', location=[y, x], zoom_start=0, zoom_min=-2, zoom_max=3)
    
    folium.raster_layers.ImageOverlay(
        image="TOTK_Hyrule_Map.png", 
        bounds=limites, 
        opacity=0.8
    ).add_to(m)

    # Marqueur Link
    folium.Marker(
        [y, x], 
        tooltip="Link", 
        icon=folium.Icon(color='green', icon='user', prefix='fa')
    ).add_to(m)

    # Marqueurs Sanctuaires
    for _, s in df_top.iterrows():
        couleur = 'lightgray' if s['visité'] == 1 else 'orange'
        folium.Marker(
            [s['y'], s['x']], 
            popup=s['name'], 
            icon=folium.Icon(color=couleur)
        ).add_to(m)

    st_folium(m, width=800, height=600, returned_objects=[])