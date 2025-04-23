from app.localizer import GeoPolygonAnalyzer, Point

map_path=r"./gjson.json"
geopoly = GeoPolygonAnalyzer(map_path)

def current_location(lat,long):
    """Placeholder for image analysis functionality."""
    pt=Point(lat,long)   
    results = geopoly.analyze_point(pt)     
    # returns distance , name , point object with <POINT (lat,long)> , 
    # direction angle if not inside a perimeter else inside  and building id
    final_string=""
    for i in results:
         final_string=f"{i[1]} is {int(i[0])} m away from you at {int(i[3])} degrees"
    # TODO: Implement actual image analysis logic
    print(final_string)
    
    return final_string

if __name__ =="__main__":
 current_location(77.99301596481246,30.26926905394356)