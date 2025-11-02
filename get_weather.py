import requests
import pandas as pd
import os
from datetime import datetime

# --- Configuration ---
# IMPORTANT: The API key must be provided via the environment variable
# OPENWEATHERMAP_API_KEY to avoid committing secrets to the repository.
API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")

if not API_KEY:
    print("Error: OPENWEATHERMAP_API_KEY environment variable not set.")
    print("Please set it before running this script. Example (PowerShell):")
    print("  $env:OPENWEATHERMAP_API_KEY = 'your_api_key_here'")
    # Do not exit here so the file remains importable in other contexts;
    # the fetch function will handle missing key gracefully.

# === LOCATION TO BE SET BY YOUR WEBSITE ===
# This is where your website's logic will provide the location.
# For now, I'm using Tunis as a placeholder.
# You will replace these values dynamically.
# Default placeholders (to be replaced by the website or runtime)
LATITUDE = 36.8065  # Exemple: Tunis
LONGITUDE = 10.1815 # Exemple: Tunis
# ==========================================

# OpenWeatherMap 5-day/3-hour Forecast API endpoint
API_URL = "https://api.openweathermap.org/data/2.5/forecast"

# The name of the CSV file where data will be saved
CSV_FILE_PATH = "weather_forecast_log.csv"

def fetch_weather_api(lat, lon, api_key):
    """
    Fetches 5-day/3-hour forecast data from OpenWeatherMap for a given location.
    
    Args:
        lat (float): Latitude of the location.
        lon (float): Longitude of the location.
        api_key (str): Your OpenWeatherMap API key.

    Returns:
        list: A list of dictionaries, each representing a 3-hour forecast.
              Returns None if the API request fails or data is invalid.
    """
    print(f"Fetching weather data for (Lat: {lat}, Lon: {lon}) at {datetime.now()}...")
    
    # Parameters for the API request
    params = {
        'lat': lat,
        'lon': lon,
        'appid': api_key,
        'units': 'metric'  # Use 'metric' for Celsius, 'imperial' for Fahrenheit
    }
    
    try:
        # Make the API request
        response = requests.get(API_URL, params=params)
        
        # This will raise an HTTPError if the response was unsuccessful (e.g., 401, 404, 500)
        response.raise_for_status()  
        
        api_data = response.json()
        
        # --- Process the API Data ---
        processed_data = []
        
        # 'city' info is useful for logging, so we'll grab it
        city_name = api_data.get('city', {}).get('name', 'Unknown')
        
        # The 'list' key contains all the 3-hour forecast entries
        for forecast in api_data['list']:
            processed_data.append({
                'location_name': city_name,
                'latitude': lat,
                'longitude': lon,
                'forecast_time': forecast['dt_txt'],
                'temp_c': forecast['main']['temp'],
                'feels_like_c': forecast['main']['feels_like'],
                'temp_min_c': forecast['main']['temp_min'],
                'temp_max_c': forecast['main']['temp_max'],
                'humidity_percent': forecast['main']['humidity'],
                'weather_condition': forecast['weather'][0]['description'],
                'wind_speed_mps': forecast['wind']['speed'],
                # 'pop' is probability of precipitation (from 0.0 to 1.0)
                'precipitation_prob_percent': forecast.get('pop', 0) * 100, 
                'cloudiness_percent': forecast['clouds']['all'],
            })
        
        print(f"Successfully fetched {len(processed_data)} forecast entries for {city_name}.")
        return processed_data

    except requests.exceptions.HTTPError as e:
        # Handle specific HTTP errors (like 401 Unauthorized - bad API key)
        if e.response.status_code == 401:
            print("Error: API request failed. Check your API_KEY. (401 Unauthorized)")
        else:
            print(f"Error: HTTP request failed: {e}")
        return None
    except requests.exceptions.RequestException as e:
        # Handle other network-related errors (DNS failure, connection timeout, etc.)
        print(f"Error: API request failed. Check network connection. {e}")
        return None
    except KeyError as e:
        # This error happens if the API response is not what we expect
        print(f"Error: Failed to parse API data. Key not found: {e}. Response may have changed.")
        return None

def save_to_csv(data_list, filepath):
    """
    Appends a list of forecast data to a CSV file.
    If the file doesn't exist, it creates it and adds a header.

    Args:
        data_list (list): The list of processed forecast dictionaries.
        filepath (str): The path to the CSV file.
    """
    if not data_list:
        print("No data to save.")
        return

    # Convert our list of dictionaries to a pandas DataFrame
    df = pd.DataFrame(data_list)
    
    # Add a 'fetched_at' timestamp to every row
    # This is crucial for knowing *when* this forecast was retrieved
    df['fetched_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check if the CSV file already exists
    file_exists = os.path.isfile(filepath)
    
    try:
        # Append to the CSV file. 
        # If it doesn't exist (file_exists is False), write the header.
        df.to_csv(filepath, mode='a', header=not file_exists, index=False)
        print(f"Successfully saved/appended data to {filepath}")
    except IOError as e:
        print(f"Error: Could not write to CSV file at {filepath}. Check permissions. {e}")

# --- Main Execution ---
# This is the code that runs when you execute `python get_weather.py`
if __name__ == "__main__":
    
    # 1. Fetch the data
    #    This is where you would pass your dynamic location
    weather_data = fetch_weather_api(LATITUDE, LONGITUDE, API_KEY)
    
    # 2. Save the data (only if fetching was successful)
    if weather_data:
        save_to_csv(weather_data, CSV_FILE_PATH)
