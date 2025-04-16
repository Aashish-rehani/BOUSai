from flask import Flask, render_template, request
import pandas as pd
import folium
import pickle
import vonage
import os
import pywhatkit as kit
import pyautogui
import time
import threading

app = Flask(_name_)

# Paths and constants
BASE_DIR = os.path.dirname(os.path.abspath(_file_))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
MODEL_PATH = os.path.join(BASE_DIR, 'earthquake_model.pkl')
DATA_PATH = os.path.join(BASE_DIR, 'merged_earthquakes_complete_new.csv')

# Load model
try:
    earthquake_model = pickle.load(open(MODEL_PATH, 'rb'))
except FileNotFoundError:
    print("Model file not found. Please ensure 'earthquake_model.pkl' is in the same directory.")
    exit()

# Vonage credentials
VONAGE_API_KEY = '101d6a0bY'
VONAGE_API_SECRET = 'MeaLDc3kK52sWtnh'
VONAGE_FROM = 'Vonage APIs'
RECIPIENT_PHONE = '919460710456'

# WhatsApp recipient
WHATSAPP_NUMBER = '+918368246372'

# Load dataset
def load_data():
    df = pd.read_csv(DATA_PATH)
    for col in ['nst', 'gap', 'rms']:
        if col in df.columns:
            df[col].fillna(df[col].median(), inplace=True)
    return df

# Create map
def create_map(lat, lon, risk_level):
    m = folium.Map(location=[lat, lon], zoom_start=8)
    colors = {'High': 'red', 'Medium': 'orange', 'Low': 'green'}
    eq_data = load_data()

    for _, row in eq_data.iterrows():
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=3,
            color='blue',
            fill=True,
            fill_opacity=0.2
        ).add_to(m)

    folium.CircleMarker(
        location=[lat, lon],
        radius=10,
        color=colors[risk_level],
        fill=True,
        fill_opacity=0.7,
        popup=f"Risk: {risk_level}"
    ).add_to(m)

    if not os.path.exists(STATIC_DIR):
        os.makedirs(STATIC_DIR)

    map_file = f'map_{lat}_{lon}.html'
    map_path = os.path.join(STATIC_DIR, map_file)
    m.save(map_path)
    return map_file

# Send SMS via Vonage
def send_sms(lat, lon, risk_level):
    try:
        client = vonage.Client(key=VONAGE_API_KEY, secret=VONAGE_API_SECRET)
        sms = vonage.Sms(client)
        response = sms.send_message({
            "from": VONAGE_FROM,
            "to": RECIPIENT_PHONE,
            "text": f"🚨 Earthquake Alert!\nRisk: {risk_level}\nLocation: ({lat}, {lon})"
        })
        if response["messages"][0]["status"] == "0":
            print("SMS sent successfully.")
            return True
        else:
            print("SMS failed:", response["messages"][0]["error-text"])
            return False
    except Exception as e:
        print("Error sending SMS:", e)
        return False

# Modified WhatsApp function with proper delay and enter key press
def send_whatsapp(lat, lon, risk_level):
    message = f"""⚠ EARTHQUAKE ALERT ⚠

You are in a HIGH RISK ZONE.

📍 Location: ({lat}, {lon})
🚨 Risk Level: {risk_level}

Take precautions now:
• Move to open space or shelter
• Avoid windows/heavy objects
• Keep emergency supplies ready

Stay Safe!
- Team bousAI"""

    try:
        print("Opening WhatsApp Web to send message...")

        # Don't close the tab automatically
        kit.sendwhatmsg_instantly(
            phone_no=WHATSAPP_NUMBER,
            message=message,
            wait_time=20,         # Allow 20 seconds to open WhatsApp Web
            tab_close=False,      # Do not close automatically
            close_time=3          # Ignored if tab_close is False
        )

        print("Waiting for WhatsApp Web to load...")
        time.sleep(30)            # Give enough time to load and render the chat

        pyautogui.click()         # Focus the message input field
        time.sleep(1)
        pyautogui.press("enter")  # Send the message
        print("WhatsApp message sent successfully.")

        return True
    except Exception as e:
        print("WhatsApp sending failed:", e)
        return False

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        lat = float(request.form['latitude'])
        lon = float(request.form['longitude'])

        df = load_data()
        medians = df[['depth', 'gap', 'nst', 'rms']].median()
        features = [[lat, lon, medians['depth'], medians['gap'], medians['nst'], medians['rms']]]
        prediction = earthquake_model.predict(features)[0]

        if prediction >= 5.0:
            risk_level = "High"
        elif prediction >= 4.0:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        map_file = create_map(lat, lon, risk_level)
        sms_status = ""
        whatsapp_status = ""

        if risk_level == "High":
            sms_status = "Sent" if send_sms(lat, lon, risk_level) else "Failed"

            def whatsapp_thread():
                send_whatsapp(lat, lon, risk_level)

            threading.Thread(target=whatsapp_thread).start()
            whatsapp_status = "Sent"

        return render_template('result.html',
                               lat=lat,
                               lon=lon,
                               risk_level=risk_level,
                               map_url=map_file,
                               sms_status=sms_status,
                               whatsapp_status=whatsapp_status)

    except Exception as e:
        return f"Error: {str(e)}"

if _name_ == '_main_':
    app.run(debug=True)
