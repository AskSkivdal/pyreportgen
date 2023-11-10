from pyreportgen.base import Component, _DATA_DIR
import pyreportgen.helpers as helpers
# import the folium library
import folium
import io
from PIL import Image
import math
import time

def deg2num(lat_deg, lon_deg, zoom):
  lat_rad = math.radians(lat_deg)
  n = 1 << zoom
  xtile = int((lon_deg + 180.0) / 360.0 * n)
  ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
  return xtile, ytile


class MapGeoJson(Component):
    def __init__(self, geojson, zoom=16):
        super().__init__()
        self.geojson = geojson
        self.zoom = zoom
        self.path = helpers.random_path("png")

    
    def render(self) -> str:
        lat = []
        lng = []

        for f in self.geojson["features"]:
            if f["geometry"]["type"] == "Polygon":
                for outer_coords in f["geometry"]["coordinates"]:
                    for coords in outer_coords:
                        lat.append(coords[1])
                        lng.append(coords[0])

        lat = sum(lat) / len(lat)
        lng = sum(lng) / len(lng)
        print({"lat": lat, "lng": lng})

        # Sattelite
        #tiles = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'

        # OSM
        tiles = "https://tile.openstreetmap.org/{z}/{x}/{y}"

        
        m = folium.Map(location=[lat, lng], zoom_start=self.zoom, zoom_control=False)#, tiles=tiles, attr="Ersi")
        folium.GeoJson(self.geojson).add_to(m)
        

        img_data = m._to_png(3)
        img = Image.open(io.BytesIO(img_data))
        img.save(self.path)
        return helpers.tagwrap("", "img", "Map", f"src='{self.path.lstrip(_DATA_DIR+'/')}'", close=False)