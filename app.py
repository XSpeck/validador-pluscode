import streamlit as st
import xml.etree.ElementTree as ET
from shapely.geometry import LineString, Point
from openlocationcode import openlocationcode as olc
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
import gdown
import pandas as pd

# ======================
# CONFIGURAÇÕES
# ======================
file_id_kml = "1tuxvnc-2FHVVjtLHJ34LFpU3Uq5jiVul"
kml_path = "REDE_CLONIX.kml"
dist_threshold_meters = 25
reference_area = "Criciúma, Brazil"

csv_ids = {
    "utp": "1UTp5gbAqppEhpIIp8qUvF83KARvwKego",
    "sem_viabilidade": "1Xo34rgfWQayl_4mJiPnTYlxWy356SpCK"
}
csv_files = {
    "utp": "utp.csv",
    "sem_viabilidade": "sem_viabilidade.csv"
}

# ======================
# FUNÇÕES DE DOWNLOAD
# ======================
@st.cache_data
def download_file(file_id, output):
    url = f"https://drive.google.com/uc?id={file_id}"
    gdown.download(url, output, quiet=True, fuzzy=True)
    return output

# ======================
# PLUS CODE → Coordenada
# ======================
def decode_plus_code(plus_code, locality_name):
    geolocator = Nominatim(user_agent="geoapi", timeout=10)
    location = geolocator.geocode(locality_name)
    if location is None:
        raise ValueError(f"Cidade de referência '{locality_name}' não encontrada.")
    full_code = olc.recoverNearest(plus_code, location.latitude, location.longitude)
    decoded = olc.decode(full_code)
    lat = (decoded.latitudeLo + decoded.latitudeHi) / 2
    lon = (decoded.longitudeLo + decoded.longitudeHi) / 2
    return lat, lon

# ======================
# Lê linhas do KML
# ======================
def load_lines_from_kml(path):
    namespaces = {'kml': 'http://www.opengis.net/kml/2.2'}
    tree = ET.parse(path)
    root = tree.getroot()
    lines = []
    for linestring in root.findall(".//kml:LineString", namespaces):
        coords_elem = linestring.find("kml:coordinates", namespaces)
        if coords_elem is not None and coords_elem.text:
            raw_coords = coords_elem.text.strip().split()
            coords = []
            for coord in raw_coords:
                parts = coord.strip().split(',')
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    coords.append((lat, lon))
            if coords:
                lines.append(coords)
    return lines

# ======================
# Verifica proximidade
# ======================
def check_proximity(point, lines):
    point_obj = Point(point[1], point[0])
    closest_dist = None
    closest_line = None
    for i, line in enumerate(lines):
        line_obj = LineString([(lon, lat) for lat, lon in line])
        closest_point = line_obj.interpolate(line_obj.project(point_obj))
        dist = geodesic((point[0], point[1]), (closest_point.y, closest_point.x)).meters
        if closest_dist is None or dist < closest_dist:
            closest_dist = dist
            closest_line = i + 1
    return closest_dist, closest_line

# ======================
# APP STREAMLIT
# ======================
st.set_page_config(page_title="Validador de Plus Code", layout="centered")

st.title("🔍 Validador de Projetos")
plus_code_input = st.text_input("Digite o Plus Code (formato curto, ex: 8JV4+8XR)").strip().upper()

if plus_code_input:
    try:
        # Baixar arquivos
        download_file(file_id_kml, kml_path)
        lines = load_lines_from_kml(kml_path)
        point_latlon = decode_plus_code(plus_code_input, reference_area)
        dist_m, line_index = check_proximity(point_latlon, lines)

        # Mapa
        m = folium.Map(location=point_latlon, zoom_start=17)
        for line in lines:
            folium.PolyLine(locations=line, color="blue").add_to(m)
        folium.Marker(location=point_latlon,
                      popup=f"PLUS CODE: {plus_code_input}",
                      icon=folium.Icon(color="red", icon="info-sign")).add_to(m)

        st_folium(m, height=500)

        # Mensagem de resultado com 3 níveis
        if dist_m is not None:
            if dist_m <= 25:
                st.success(f"✅ Temos viabilidade. O ponto está a {dist_m:.1f} metros da fibra (linha {line_index}).")
            elif dist_m <= 500:
                st.warning(f"⚠️ Possível viabilidade. O ponto está a {dist_m:.1f} metros da fibra (linha {line_index}). Entre em contato para verificar.")
            else:
                st.error(f"❌ Não temos viabilidade. O ponto está a {dist_m:.1f} metros da fibra mais próxima.")
        else:
            st.error("❌ Não foi possível calcular a distância.")

    except Exception as e:
        st.error(f"Erro: {e}")

# ======================
# TABELA 1: Atendemos UTP
# ======================
st.subheader("📋 Atendemos UTP")
try:
    download_file(csv_ids["utp"], csv_files["utp"])
    df_utp = pd.read_csv(csv_files["utp"])
    search_utp = st.text_input("🔎 Buscar na tabela 'Atendemos UTP'").lower()
    filtered_utp = df_utp[df_utp.apply(lambda row: search_utp in row.astype(str).str.lower().to_string(), axis=1)]
    st.dataframe(filtered_utp, use_container_width=True)
except Exception as e:
    st.warning(f"Erro ao carregar utp.csv: {e}")

# ======================
# TABELA 2: Prédios sem viabilidade
# ======================
st.subheader("📋 Prédios sem viabilidade")
try:
    download_file(csv_ids["sem_viabilidade"], csv_files["sem_viabilidade"])
    df_sem_viab = pd.read_csv(csv_files["sem_viabilidade"])
    search_sem_viab = st.text_input("🔎 Buscar na tabela 'Prédios sem viabilidade'").lower()
    filtered_sem_viab = df_sem_viab[df_sem_viab.apply(lambda row: search_sem_viab in row.astype(str).str.lower().to_string(), axis=1)]
    st.dataframe(filtered_sem_viab, use_container_width=True)
except Exception as e:
    st.warning(f"Erro ao carregar sem_viabilidade.csv: {e}")

