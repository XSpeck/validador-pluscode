import streamlit as st
import xml.etree.ElementTree as ET
from shapely.geometry import LineString, Point
from openlocationcode import openlocationcode as olc
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
import gdown

# ======================
# CONFIGURAÇÕES
# ======================
file_id = "1tuxvnc-2FHVVjtLHJ34LFpU3Uq5jiVul"
kml_path = "REDE_CLONIX.kml"
dist_threshold_meters = 25
reference_area = "Criciúma, Brazil"

# ======================
# BAIXAR KML
# ======================
@st.cache_data
def download_kml(file_id, output):
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
def check_proximity(point, lines, threshold_meters):
    point_obj = Point(point[1], point[0])
    for i, line in enumerate(lines):
        line_obj = LineString([(lon, lat) for lat, lon in line])
        closest_point = line_obj.interpolate(line_obj.project(point_obj))
        dist = geodesic((point[0], point[1]), (closest_point.y, closest_point.x)).meters
        if dist <= threshold_meters:
            return True, dist, i + 1
    return False, None, None

# ======================
# STREAMLIT APP
# ======================
st.set_page_config(page_title="Validador de Plus Code", layout="centered")

st.title("🔍 Validador de Projetos")
plus_code_input = st.text_input("Digite o Plus Code (formato curto, ex: 8JV4+8XR)").strip().upper()

if plus_code_input:
    try:
        download_kml(file_id, kml_path)
        lines = load_lines_from_kml(kml_path)
        point_latlon = decode_plus_code(plus_code_input, reference_area)
        is_close, dist_m, line_index = check_proximity(point_latlon, lines, dist_threshold_meters)

        # Mapa
        m = folium.Map(location=point_latlon, zoom_start=17)
        for line in lines:
            folium.PolyLine(locations=line, color="blue").add_to(m)
        folium.Marker(location=point_latlon,
                      popup=f"PLUS CODE: {plus_code_input}",
                      icon=folium.Icon(color="red", icon="info-sign")).add_to(m)

        st_folium(m, height=500)

        # Resultado
        if is_close:
            st.success(f"✅ O ponto está a {dist_m:.1f} metros da fibra mais proxima")
        else:
            st.error(f"❌ O ponto está a mais de 25 metros de qualquer fibra.({dist_m:.1f})")

    except Exception as e:
        st.error(f"Erro: {e}")




