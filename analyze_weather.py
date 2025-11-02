import pandas as pd
import openai
import os
from datetime import datetime, timedelta

# --- Configuration ---
# The CSV file to read data from
CSV_FILE_PATH = "weather_forecast_log.csv"

# --- Main Functions ---

def load_api_key():
    """
    Securely loads the OpenAI API key from an environment variable.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        print("Please set it by running:")
        print("  (Linux/macOS) export OPENAI_API_KEY='your_new_key_here'")
        print("  (Windows CMD)   set OPENAI_API_KEY=your_new_key_here")
        print("  (Windows PS)    $env:OPENAI_API_KEY='your_new_key_here'")
        return None
    return api_key

def read_latest_forecast(filepath):
    """
    Reads the CSV and returns a DataFrame of the most recent 48-hour forecast.
    """
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Error: The file {filepath} was not found.")
        print("Please run get_weather.py first to create it.")
        return None
    except pd.errors.EmptyDataError:
        print(f"Error: The file {filepath} is empty.")
        return None

    # --- Find the most RECENTLY fetched data ---
    # Convert 'fetched_at' to datetime objects to find the latest
    df['fetched_at'] = pd.to_datetime(df['fetched_at'])
    latest_fetch_time = df['fetched_at'].max()
    latest_df = df[df['fetched_at'] == latest_fetch_time].copy()
    
    # --- Filter for the next 48 hours ---
    # Convert 'forecast_time' to datetime objects
    latest_df['forecast_time'] = pd.to_datetime(latest_df['forecast_time'])
    
    # Get the current time and the cutoff time 48 hours from now
    now = datetime.now()
    cutoff_time = now + timedelta(days=2)
    
    # Select rows where the forecast is between now and the cutoff
    next_48h_df = latest_df[
        (latest_df['forecast_time'] > now) & 
        (latest_df['forecast_time'] <= cutoff_time)
    ]
    
    if next_48h_df.empty:
        print("No forecast data found for the next 48 hours.")
        return None
        
    return next_48h_df

def format_data_for_prompt(df):
    """
    Converts the DataFrame into a simple string for the AI prompt.
    """
    # Select only the most important columns for the AI
    columns_to_include = [
        'forecast_time', 
        'temp_c', 
        'humidity_percent', 
        'weather_condition', 
        'precipitation_prob_percent'
    ]
    
    # Use 'to_string' to create a nicely formatted, simple text table
    data_string = df[columns_to_include].to_string(index=False)
    return data_string

def get_ai_recommendation(api_key, data_string):
    """
    Sends the data and the user's prompt to the OpenAI API.
    """
    try:
        client = openai.OpenAI(api_key=api_key)
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")
        return None

    # Prompt: ask for a single, formal sentence in French advising which crops to water.
    user_prompt_instruction = (
        "À partir des données de prévision ci‑dessous, indiquez en une seule phrase "
        "formelle en français quelles cultures (oignons, tomates, menthe) doivent être arrosées "
        "aujourd'hui et si un arrosage est nécessaire. Prenez en compte les besoins différents "
        "en eau par culture, la probabilité de pluie et la date dans l'année. Répondez en une seule phrase." 
    )

    # System prompt to enforce tone and language
    system_prompt = (
        "Vous êtes un assistant agricole professionnel. Répondez en français formel, par une seule phrase concise."
    )
    
    # Combine the data and the instruction
    full_prompt = f"Forecast Data:\n{data_string}\n\nInstruction:\n{user_prompt_instruction}"
    
    print("\nSending request to OpenAI API...")
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=150,
            temperature=0.3
        )

        # Extract the assistant content
        advice = response.choices[0].message.content
        return advice

    except openai.AuthenticationError:
        print("Error: OpenAI Authentication Failed. Check your API key.")
        return None
    except Exception as e:
        print(f"Error during OpenAI API call: {e}")
        return None

# --- Main Execution ---
if __name__ == "__main__":
    
    # 1. Load the API key
    api_key = load_api_key()
    
    if api_key:
        # 2. Read the latest forecast data from the CSV
        forecast_df = read_latest_forecast(CSV_FILE_PATH)
        
        if forecast_df is not None:
            # 3. Format the data for the prompt
            data_string = format_data_for_prompt(forecast_df)
            
            # 4. Get the AI recommendation
            recommendation = get_ai_recommendation(api_key, data_string)
            
            if recommendation:
                # 5. Print the final result
                print("\n--- AI Recommendation (Tunisian Dialect) ---")
                print(recommendation)
 # Write recommendation to recommendation.txt in the same directory
                try:
                    with open("recommendation.txt", "w", encoding="utf-8") as f:
                        f.write(recommendation)
                except Exception as e:
                    print(f"Error writing recommendation.txt: {e}")
# ...existing code...