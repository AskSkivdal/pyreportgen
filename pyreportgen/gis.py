from pyreportgen.base import Component, _DATA_DIR
import pyreportgen.helpers as helpers
from PIL import Image, ImageDraw
import math
from io import BytesIO
import requests
import os.path as path

def deg2num(lat_deg, lon_deg, zoom):
  lat_rad = math.radians(lat_deg)
  n = 1 << zoom
  xtile = (lon_deg + 180.0) / 360.0 * n
  ytile = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
  return xtile, ytile

def num2deg(xtile, ytile, zoom):
    n = 1 << zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg

def translate(value, leftMin, leftMax, rightMin, rightMax):
    value *= 100000
    leftMin *= 100000
    leftMax *= 100000

    # Figure out how 'wide' each range is
    leftSpan = leftMax - leftMin
    rightSpan = rightMax - rightMin

    # Convert the left range into a 0-1 range (float)
    valueScaled = float(value - leftMin) / float(leftSpan)

    # Convert the 0-1 range into a value in the right range.
    return rightMin + (valueScaled * rightSpan)



def translate_coord(value, leftMin, leftMax, rightMin, rightMax):
    return (translate(value[0], leftMin[0], leftMax[0], rightMin[0], rightMax[0]), translate(value[1], leftMin[1], leftMax[1],  rightMin[1], rightMax[1]))

def open_image_from_url(url):
    try:
        response = requests.get(url, headers={"user-agent":"pyreportgen-library"})
        response.raise_for_status()  # Raise an HTTPError for bad responses
        img_data = BytesIO(response.content)
        img = Image.open(img_data)
        return img
    except Exception as e:
        print(f"Error: {e}")
        # Return a black image with size 1x1 in case of failure
        return Image.new("RGB", (1, 1), color="black")

class Map(Component):
    def __init__(self, bbox: tuple[tuple[float, float], tuple[float, float]], zoom=18, tile_host="https://tile.openstreetmap.org/{z}/{x}/{y}.png"):
        super().__init__()
        self.bottom_left: tuple[float, float] = (min(bbox[0][0], bbox[1][0]), min(bbox[0][1], bbox[1][1]))
        self.upper_right: tuple[float, float] = (max(bbox[0][0], bbox[1][0]), max(bbox[0][1], bbox[1][1]))
        self.zoom = zoom
        self.tile_host = tile_host
        self.image: Image.Image = None        
    
    def make_image(self) -> Image.Image:
        x, y = deg2num(self.bottom_left[0],self.bottom_left[1], self.zoom)

        start_xoverflow = (x - int(x))
        start_yoverflow = (y - int(y))
        from_tile = list((int(x), int(y)))

        x, y = deg2num(self.upper_right[0],self.upper_right[1], self.zoom)

        end_xoverflow = 1 - (x - int(x))
        end_yoverflow = 1 - (y - int(y))
        to_tile = list((int(x), int(y)))

        from_tile[1], to_tile[1] = to_tile[1], from_tile[1]

        grid_size = (to_tile[0] - from_tile[0] +1, to_tile[1] - from_tile[1] +1)

        tile_size = 256

        grid = [
            [
                self.tile_host.format(z=self.zoom,x=int(x), y=int(y)) 
                for x in range(from_tile[0], to_tile[0]+1)
            ] 
            for y in range(from_tile[1], to_tile[1]+1)
            ]

        full_image = Image.new('RGB',(tile_size*grid_size[0], tile_size*grid_size[1]), (0,0,0))

        images = grid_size[0] * grid_size[1]
        current_image = 0

        pb = helpers.ProgressBar(images, "Collecting tiles")

        for y, row in enumerate(grid):
            for x, tile in enumerate(row):
                current_image += 1
                im = open_image_from_url(tile)
                full_image.paste(im, (x*tile_size, y*tile_size))
                pb.print(current_image)



        image_size = full_image.size
        cropped = full_image.crop((int(tile_size*start_xoverflow),int(tile_size*start_yoverflow),image_size[0]-int(tile_size * end_xoverflow),image_size[1]-int(tile_size * end_yoverflow)))
        return cropped
    
    def render(self) -> str:
        self.image = self.make_image()
        name = helpers.random_filename("png")
        self.image.save(path.join(_DATA_DIR, name))
        return helpers.tagwrap("", "img", "Map", f"src='{name}'", False)

class MapGeoJson(Map):
    def __init__(self, geojson, zoom=17, tile_host="https://tile.openstreetmap.org/{z}/{x}/{y}.png", padding=0.001):
        coords: list[list[float]] = []
        
        for feature in geojson["features"]:
            geom = feature["geometry"]
            if geom["type"] == "Polygon":
                    for poly in geom["coordinates"]:
                        for point in poly:
                            coords.append(point.copy())
            elif geom["type"] == "LineString":
                    for point in geom["coordinates"]:
                        coords.append(point.copy())
            elif geom["type"] == "Point":
                    coords.append(geom["coordinates"].copy())
        
        for c in coords:
            c.reverse()

        bottom_left = coords[0].copy()
        upper_right = coords[0].copy()

        for c in coords:
            bottom_left[0] = min(bottom_left[0], c[0])
            bottom_left[1] = min(bottom_left[1], c[1])

            upper_right[0] = max(upper_right[0], c[0])
            upper_right[1] = max(upper_right[1], c[1])
        
        bottom_left[0] -= padding
        bottom_left[1] -= padding

        upper_right[0] += padding
        upper_right[1] += padding

        bbox = [bottom_left, upper_right]
        super().__init__(bbox, zoom, tile_host)
        self.geojson = geojson
        self.padding = padding

    def make_image(self):
        map = super().make_image()
        size = map.size

        draw = ImageDraw.Draw(map)

        for feature in self.geojson["features"]:
            if feature["type"] != "Feature":
                continue
            geom = feature["geometry"]
            
            if geom["type"] == "Point":
                geom["coordinates"].reverse()
                y, x = translate_coord(geom["coordinates"], self.bottom_left, self.upper_right, (1,0),(0,1))
                draw.regular_polygon(((int(x*size[0]), int((y)*size[1])), 6), 128, fill="red")
            elif geom["type"] == "LineString":
                points = []
                for i in geom["coordinates"]:
                    i.reverse()
                    y, x = translate_coord(i, self.bottom_left, self.upper_right, (1,0), (0, 1))
                    points.append((int(x*size[0]),int(y*size[1])))
                draw.line(points, fill="red", width=6)
            elif geom["type"] == "Polygon":
                for poly in geom["coordinates"]:
                    points = []
                    for i in poly:
                        i.reverse()
                        y, x = translate_coord(i, self.bottom_left, self.upper_right, (1,0), (0, 1))
                        points.append((int(x*size[0]),int(y*size[1])))
                    draw.polygon(points, fill=None, outline="red", width=6)
        return map

    
    def render(self) -> str:
        self.image = self.make_image()
        name = helpers.random_filename("png")
        self.image.save(path.join(_DATA_DIR, name))
        return helpers.tagwrap("", "img", "Map", f"src='{name}'", False)