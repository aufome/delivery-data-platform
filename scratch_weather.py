import json
import urllib.request

url = "https://archive-api.open-meteo.com/v1/archive?latitude=12.9716&longitude=77.5946&start_date=2022-03-15&end_date=2022-03-15&hourly=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())
    print(list(data.keys()))
    print(data["hourly"]["time"][:3])
    print(data["hourly"]["temperature_2m"][:3])
