import os, requests
from dotenv import load_dotenv
import urllib.parse

load_dotenv()

GOONG_API_KEY = os.getenv("GOONG_API_KEY")
def get_coordinates_from_goong(address, api_key=GOONG_API_KEY):
    try:
        encoded_address = urllib.parse.quote_plus(address)
        url = f"https://rsapi.goong.io/v2/geocode?address={encoded_address}&api_key={api_key}"
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()
        if data['status'] == 'OK' and len(data['results']) > 0:
            location = data['results'][0]['geometry']['location']
            return {
                'address': data['results'][0].get('formatted_address'),
                'x': location['lat'],
                'y': location['lng']
            }
        else:
            print("No results found for the given address.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"An error occurred during the API request: {e}")
        return None
    
if __name__ == "__main__":
    print(get_coordinates_from_goong("vinhome, quận 9"))
