import json
import requests

# 1. Load credentials saved in credentials.json
with open('credentials.json') as f:
    creds = json.load(f)

client_id = creds['clientId']
client_secret = creds['clientSecret']

# 2. Request access token via OAuth2
token_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"

payload = {
    'grant_type': 'client_credentials',
    'client_id': client_id,
    'client_secret': client_secret
}

print("Obtaining OAuth2 access token...")
auth_response = requests.post(token_url, data=payload)

if auth_response.status_code == 200:
    token = auth_response.json().get('access_token')
    print("OAuth2 token successfully retrieved!\n")
    
    # 3. Query live data covering the European bounding box
    headers = {'Authorization': f'Bearer {token}'}
    api_url = 'https://opensky-network.org/api/states/all'
    
    # Bounding box covering the 15 European hubs
    params = {
        'lamin': 34.0,  # South (Spain/Italy)
        'lamax': 60.0,  # North (UK/Scandinavia)
        'lomin': -10.0, # West (UK/Ireland)
        'lomax': 30.0   # East (Eastern Europe/Turkey)
    }

    response = requests.get(api_url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        states = data.get('states', [])
        print(f"Total flights tracked across Europe right now: {len(states)}")

        # 4. Filter by known cargo operator callsign prefixes
        cargo_prefixes = ('CLX', 'GEC', 'BOX', 'DHK', 'FDX', 'UPS', 'ABX', 'BCS')
        
        cargo_flights = [
            s for s in states 
            if s[1] and s[1].strip().startswith(cargo_prefixes)
        ]

        print(f"CARGO flights identified: {len(cargo_flights)}\n")
        print("--- First Cargo Flights Detected ---")
        
        for flight in cargo_flights[:5]:
            callsign = flight[1].strip()
            icao24 = flight[0]
            longitude = flight[5]
            latitude = flight[6]
            altitude_m = flight[7]
            
            print(f"Callsign: {callsign:<8} | ICAO24: {icao24} | Lat: {latitude} | Lon: {longitude} | Alt: {altitude_m}m")
            
    else:
        print(f"API request error: {response.status_code}")
else:
    print(f"OAuth2 authentication error: {auth_response.status_code}")
    print(auth_response.text)