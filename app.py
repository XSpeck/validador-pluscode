import streamlit as st
import xml.etree.ElementTree as ET
from shapely.geometry import LineString, Point
from openlocationcode import openlocationcode as olc
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import gdown
import pandas as pd
import requests

# ======================
# Configurações
# ======================
LOCATIONIQ_KEY = "pk.66f355328aaad40fe69b57c293f66815"
file_id_kml = "1tuxvnc-2FHVVjtLHJ34LFpU3Uq5jiVul"
kml_path = "REDE_CLONIX.kml"
reference_lat = -28.6775
reference_lon = -49.3696

csv_ids = {
    "utp": "1UTp5gbAqppEhpIIp8qUvF83KARvwKego",
    "sem_viabilidade": "1Xo34rgfWQayl_4mJiPnTYlxWy356SpCK"
}
csv_files = {
    "utp": "utp.csv",
    "sem_viabilidade": "sem_viabilidade.csv"
}

if "refresh_clicked" not in st.session_state:
    st.session_state.refresh_clicked = False

def on_refresh():
    st.cache_data.clear()
    st.session_state.refresh_clicked = True

st.button("🔄 Atualizar arquivos", on_click=on_refresh)

if st.session_state.refresh_clicked:
    st.info("Arquivos atualizados! Por favor, recarregue (F5).")

@st.cache_data
def download_file(file_id, output):
    url = f"https://drive.google.com/uc?id={file_id}"
    gdown.download(url, output, quiet=True, fuzzy=True)
    return output

def load_lines_from_kml(path):
    namespaces = {'kml': 'http://www.opengis.net/kml/2.2'}
    tree = ET.parse(path)
    root = tree.getroot()
    lines = []
    for ls in root.findall(".//kml:LineString", namespaces):
        coords_elem = ls.find("kml:coordinates", namespaces)
        if coords_elem is not None and coords_elem.text:
            raw = coords_elem.text.strip().split()
            coords = [(float(c.split(',')[1]), float(c.split(',')[0])) for c in raw if len(c.split(','))>=2]
            lines.append(coords)
    return lines

@st.cache_data
def load_all_files():
    download_file(file_id_kml, kml_path)
    download_file(csv_ids["utp"], csv_files["utp"])
    download_file(csv_ids["sem_viabilidade"], csv_files["sem_viabilidade"])
    lines = load_lines_from_kml(kml_path)
    lines = [line for line in lines if line and len(line) > 0]
    df_utp = pd.read_csv(csv_files["utp"])
    df_sem = pd.read_csv(csv_files["sem_viabilidade"])
    return lines, df_utp, df_sem

def pluscode_to_coords(pluscode):
    if not olc.isFull(pluscode):
        pluscode = olc.recoverNearest(pluscode, reference_lat, reference_lon)
    decoded = olc.decode(pluscode)
    lat = (decoded.latitudeLo + decoded.latitudeHi) / 2
    lon = (decoded.longitudeLo + decoded.longitudeHi) / 2
    return lat, lon

def check_proximity(point, lines):
    pt = Point(point[1], point[0])
    closest = None
    for i, line in enumerate(lines):
        if not line:
            continue
        try:
            ln = LineString([(lon, lat) for lat, lon in line])
            if ln.is_empty:
                continue
            cp = ln.interpolate(ln.project(pt))
            if cp is None:
                continue
            dist = geodesic((point[0], point[1]), (cp.y, cp.x)).meters
            if closest is None or dist < closest[0]:
                closest = (dist, i+1)
        except Exception:
            continue
    return closest if closest else (None, None)

def reverse_geocode(lat, lon):
    url = f"https://us1.locationiq.com/v1/reverse?key={LOCATIONIQ_KEY}&lat={lat}&lon={lon}&format=json"
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("display_name", "Endereço não encontrado")
        else:
            return f"Erro na consulta LocationIQ: {resp.status_code}"
    except Exception as e:
        return f"Erro na consulta LocationIQ: {e}"

st.set_page_config(page_title="Validador de Projetos", layout="centered")
st.title("🔍 Validador de Projetos")

# Carrega arquivos e KML apenas uma vez
try:
    lines, df_utp, df_sem = load_all_files()
except Exception as e:
    st.error(f"Erro ao carregar arquivos: {e}")
    st.stop()

plus_code_input = st.text_input("Digite o Plus Code (ex: 8JV4+8XR)").strip().upper()

if plus_code_input:
    try:
        lat, lon = pluscode_to_coords(plus_code_input)
        coords_str = f"{lat:.6f}, {lon:.6f}"
        st.markdown("📍 Coordenadas (copie e cole em outro app)")
        st.code(coords_str, language="")
        

       # Botão Google Maps
        maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        st.markdown(
            f'<a href="{maps_url}" target="_blank" '
            f'style="display:inline-block;padding:0.5em 1em;background-color:#4285F4;'
            f'color:white;text-decoration:none;border-radius:5px;">🗺️ Abrir no Google Maps</a>',
            unsafe_allow_html=True
        )

        endereco = reverse_geocode(lat, lon)
        endereco_simples = ", ".join(endereco.split(",")[:3])
        st.markdown(f"🏠 **Endereço aproximado:** {endereco_simples}")

        dist_m, _ = check_proximity((lat, lon), lines)

        

        if dist_m is not None:
            if dist_m <= 25:
                st.success(f"✅ Temos viabilidade! Distância: {dist_m:.1f} metros")
            elif dist_m <= 500:
                st.warning(f"⚠️ Possível viabilidade. Distância: {dist_m:.1f} metros")
            else:
                st.error(f"❌ Não temos viabilidade. Distância: {dist_m:.1f} metros")
        else:
            st.error("❌ Não foi possível calcular a distância.")

        m = folium.Map(location=[lat, lon], zoom_start=17)
        for line in lines:
            folium.PolyLine(locations=line, color="blue").add_to(m)
        folium.Marker(location=[lat, lon], popup=plus_code_input, icon=folium.Icon(color="red")).add_to(m)
        st_folium(m, height=500)

    except Exception as e:
        st.error(f"Erro: {e}")

st.subheader("Atendemos UTP")
search_utp = st.text_input("🔎 Buscar UTP", key="search_utp").lower()
try:
    st.dataframe(df_utp[df_utp.apply(lambda r: search_utp in r.astype(str).str.lower().to_string(), axis=1)])
except Exception as e:
    st.warning(f"Erro ao filtrar UTP: {e}")

st.subheader("Prédios sem viabilidade")
search_sem = st.text_input("🔎 Buscar Prédios", key="search_sem_viab").lower()
try:
    st.dataframe(df_sem[df_sem.apply(lambda r: search_sem in r.astype(str).str.lower().to_string(), axis=1)])
except Exception as e:
    st.warning(f"Erro ao filtrar sem_viabilidade: {e}")






