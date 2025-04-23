import json
import random
import math
from shapely.geometry import shape, Point
from shapely.ops import nearest_points
import matplotlib.pyplot as plt
import asyncio

class GeoPolygonAnalyzer:
    def __init__(self, geojson_path, distance_threshold=100, min_neighbors=3):
        self.geojson_path = geojson_path
        self.distance_threshold = distance_threshold
        self.min_neighbors = min_neighbors
        self.current_localization = None
        self.current_point = None
        self.polygons = []
        self.descriptions = []
        self.names = []
        self.bounds = None
        self._load_geojson()
    
    def _load_geojson(self):
        with open(self.geojson_path) as f:
            data = json.load(f)

        for feature in data["features"]:
            print(feature)
            
            if feature["geometry"]["type"] == "Polygon":
                self.polygons.append(shape(feature["geometry"]))
                self.names.append(feature["properties"].get("name", "Unnamed"))
                self.descriptions.append(feature["properties"].get("description", "No description available"))
        
        minx, miny, maxx, maxy = self.polygons[0].bounds
        for poly in self.polygons:
            x1, y1, x2, y2 = poly.bounds
            minx, miny = min(minx, x1), min(miny, y1)
            maxx, maxy = max(maxx, x2), max(maxy, y2)
        self.bounds = (minx, miny, maxx, maxy)
              
    def get_direction(self, from_point, to_point):
        dx = to_point.x - from_point.x
        dy = to_point.y - from_point.y
        angle = math.degrees(math.atan2(dy, dx)) % 360
        if 45 <= angle < 135:
            return "North"
        elif 135 <= angle < 225:
            return "West"
        elif 225 <= angle < 315:
            return "South"
        else:
            return "East"

    def analyze_point(self, pt):
        all_dists = [
            (
                pt.distance((nearest_pt := nearest_points(poly.boundary, pt)[0])) * 111139,  
                name,
                description,
                nearest_pt,  
                self.get_direction(nearest_pt, pt),  
                idx 
            )
            for idx, (name, description, poly) in enumerate(zip(self.names, self.descriptions, self.polygons))
        ]
    
        nearest_two = sorted(all_dists, key=lambda x: x[0])[:2]
        return nearest_two

    def plot_analysis(self, pt: Point, analysis_results):
        minx, miny, maxx, maxy = self.bounds
        fig, ax = plt.subplots(figsize=(10, 10))
        for poly in self.polygons:
            x, y = poly.exterior.xy
            ax.plot(x, y, color="black", linewidth=1)

        ax.plot(pt.x, pt.y, "bo", markersize=8)
        for dist, name, poly, near_pt, direction, idx in analysis_results:
            ax.plot([pt.x, near_pt.x], [pt.y, near_pt.y], 'r--')
            ax.text(near_pt.x, near_pt.y, f"{name}\n{round(dist)}m\n{direction}", fontsize=6, color="red")

        ax.set_xlim(minx, maxx)
        ax.set_ylim(miny, maxy)
        ax.set_aspect("equal")
        ax.set_title("GeoSpatial Analysis")
        ax.grid(True)
        plt.show()

if __name__ == "__main__":   
    map_path = r"G:\RAGa\geolocalizer\gjson.json"
    analyzer = GeoPolygonAnalyzer(map_path, distance_threshold=100, min_neighbors=3)
    current_location  = Point(77.99301596481246,30.26926905394356)
    results = analyzer.analyze_point(current_location)
    print(results)
