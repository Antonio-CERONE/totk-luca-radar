import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import numpy as np
import json
import os

# 1. Configuration de la page
st.set_page_config(page_title="Radar Luca TOTK", layout="wide")

# 2. CRÉATION DU FICHIER DE CONNEXION (La méthode de secours ultime)
# On récupère les secrets un par un et on recrée le fichier JSON que Google attend
try:
    creds = {
        "type": st.secrets["gsheets"]["type"],
        "project_id": st.secrets["gsheets"]["project_id"],
        "private_key_id": st.secrets["gsheets"]["private_key_id"],
        "private_key": st.secrets["gsheets"]["private_key"].replace("\\n", "\n"),
        "client_email": st.secrets["gsheets"]["client_email"],
        "client_id": st.secrets["gsheets"]["client_id"],
        "auth_uri": st.secrets["gsheets"]["auth_uri"],
        "token_uri": st.secrets["gsheets"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["gsheets"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["gsheets"]["client_x509_cert_url"]
    }
    
    # On écrit ce dictionnaire dans un fichier temporaire sur le serveur
    with open("google_creds.json", "w") as f:
        json.dump(creds, f)
except Exception as e:
    st.error(f"Erreur lors de la lecture des Secrets : {e}")
    st.stop()

# 3. Connexion via le fichier JSON
url = "https://docs.google.com/spreadsheets/d/1Kw65ATn2m9YkDZunhRVwWqUHKDgIg2B3d6eGusNckDo/edit#gid=0"
# On dit au connecteur d'utiliser le fichier qu'on vient de créer
conn = st.connection("gsheets", type=GSheetsConnection, key_path="google_creds.json")

@st.cache_data(ttl=60)
def load_data():
    return conn.read(spreadsheet=url, worksheet="shrines")

# --- INITIALISATION ---
if 'df' not in st.session_state:
    try:
        df_cloud = load_data()
        if df_cloud is None or df_cloud.empty:
            with open('02_shrines_details.json', 'r', encoding='utf-8') as f:
                local_data = json.load(f)
            df_init = pd.DataFrame(local_data.get('shrines', []))
            df_init['visité'] = 0
            conn.update(spreadsheet=url, worksheet="shrines", data=df_init)
            st.session_state.df = df_init
        else:
            st.session_state.df = df_cloud
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        st.stop()

# --- RESTE DE L'INTERFACE (Barre latérale et Carte) ---
st.sidebar.title("🎮 Guide de Luca")
x = st.sidebar.number_input("Position X", value=-254.0)
y = st.sidebar.number_input("Position Y", value=107.0)
k = st.sidebar.slider("Proches", 1, 20, 10)

def get_nearest(df, px, py, k):
    temp = df.copy()
    temp['distance_m'] = np.sqrt((temp['x'] - px)**2 + (temp['y'] - py)**2)
    return temp.sort_values('distance_m').head(k)

df_top = get_nearest(st.session_state.df, x, y, k)

st.title("🏹 Radar de Sanctuaires")
col1, col2 = st.columns([2, 1])

with col2:
    target = st.selectbox("Sanctuaire :", df_top['name'].tolist())
    curr = st.session_state.df.loc[st.session_state.df['name'] == target, 'visité'].values[0]
    if st.button("Valider visite"):
        idx = st.session_state.df[st.session_state.df['name'] == target].index[0]
        st.session_state.df.at[idx, 'visité'] = 1 - curr
        conn.update(spreadsheet=url, worksheet="shrines", data=st.session_state.df)
        st.cache_data.clear()
        st.rerun()
    st.metric("Progression", f"{int(st.session_state.df['visité'].sum())}/152")

with col1:
    m = folium.Map(crs='Simple', location=[y, x], zoom_start=-1)
    folium.raster_layers.ImageOverlay(image="TOTK_Hyrule_Map.png", bounds=[[-4000, -5000], [4000, 5000]]).add_to(m)
    folium.Marker([y, x], icon=folium.Icon(color='green')).add_to(m)
    for _, s in df_top.iterrows():
        folium.Marker([s['y'], s['x']], popup=s['name'], icon=folium.Icon(color='lightgray' if s['visité']==1 else 'orange')).add_to(m)
    st_folium(m, width=800, height=600, returned_objects=[])