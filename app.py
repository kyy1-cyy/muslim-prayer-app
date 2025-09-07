# app.py (Full Corrected Version)

import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, g, jsonify
import requests
import json
from datetime import datetime
import threading
import time
from pywebpush import webpush
from dotenv import load_dotenv

# Load environment variables for VAPID keys
load_dotenv()

# Flask App Initialization
app = Flask(__name__)

# Call init_db() here to ensure the database is created
with app.app_context():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect('database.db')
        db.row_factory = sqlite3.Row
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            city TEXT,
            country TEXT,
            method INTEGER,
            notifications TEXT,
            subscription_info TEXT
        )
    ''')
    db.commit()

# Constants
DATABASE = 'database.db'
ALADHAN_API = "http://api.aladhan.com/v1/timingsByCity"

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY")
VAPID_CLAIMS = {"sub": "mailto:YOUR_EMAIL@example.com"}

# Function to get a database connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

# Function to get prayer times from the API
def get_prayer_times(city, country, method):
    try:
        url = f"{ALADHAN_API}?city={city}&country={country}&method={method}"
        response = requests.get(url)
        data = response.json()
        if data['code'] == 200:
            return data['data']['timings']
    except requests.exceptions.RequestException as e:
        print(f"Error fetching prayer times: {e}")
    return None

# Function to convert 24-hour time string to 12-hour format with AM/PM
def format_to_12h(time_str):
    if time_str:
        dt_obj = datetime.strptime(time_str, '%H:%M')
        return dt_obj.strftime('%I:%M %p')
    return None

# Function to select the best calculation method for a country
def get_best_method(country):
    country = country.lower()
    if country in ["australia"]:
        return 1
    elif country in ["united kingdom", "uk", "france", "belgium"]:
        return 2
    elif country in ["saudi arabia", "uae", "qatar", "kuwait"]:
        return 4
    elif country in ["pakistan", "india", "bangladesh"]:
        return 5
    elif country in ["egypt"]:
        return 3
    else:
        return 1

def send_push_notification(subscription_info, message):
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        print("VAPID keys not set. Push notification cannot be sent.")
        return

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"notification": {"title": "Prayer Reminder", "body": message}}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS
        )
        print("Push notification sent successfully!")
    except Exception as e:
        print(f"Error sending push notification: {e}")

# Background thread to check prayer times and send notifications
def notification_thread():
    with app.app_context():
        while True:
            db = get_db()
            settings = db.execute('SELECT * FROM settings WHERE id = 1').fetchone()

            if settings:
                city = settings['city']
                country = settings['country']
                method = settings['method']
                notifications = json.loads(settings['notifications'])
                subscription_info = json.loads(settings['subscription_info']) if settings['subscription_info'] else None

                if notifications and subscription_info:
                    timings = get_prayer_times(city, country, method)
                    if timings:
                        now = datetime.now()
                        current_time_str = now.strftime("%H:%M")

                        for prayer, time_str in timings.items():
                            if prayer.lower() in [n.lower() for n in notifications]:
                                if current_time_str == time_str:
                                    message = f"PRAY {prayer.upper()} NOW, OR REGRET IT LATER."
                                    send_push_notification(subscription_info, message)
                                    time.sleep(30) # Prevent multiple notifications

            time.sleep(60)

# Main Routes
@app.route('/')
def index():
    db = get_db()
    settings = db.execute('SELECT * FROM settings WHERE id = 1').fetchone()

    if not settings or not settings['city']:
        return render_template('index.html', no_location=True, vapid_public_key=VAPID_PUBLIC_KEY)

    city = settings['city']
    country = settings['country']
    method = settings['method']
    prayer_times = get_prayer_times(city, country, method)

    display_times = {}
    if prayer_times:
        prayers_to_show = ["Fajr", "Dhuhr", "Asr", "Sunset", "Maghrib", "Isha"]
        for prayer in prayers_to_show:
            time_str = prayer_times.get(prayer)
            if time_str:
                display_times[prayer] = format_to_12h(time_str)

    return render_template('index.html', prayer_times=display_times, city=city, country=country, vapid_public_key=VAPID_PUBLIC_KEY)

@app.route('/select', methods=['GET', 'POST'])
def select():
    db = get_db()
    settings = db.execute('SELECT * FROM settings WHERE id = 1').fetchone()

    if not settings or not settings['city']:
        return redirect(url_for('location'))

    selected_prayers = json.loads(settings['notifications']) if settings and settings['notifications'] else []

    if request.method == 'POST':
        selected = request.form.getlist('prayers')
        db.execute('UPDATE settings SET notifications = ? WHERE id = 1', (json.dumps(selected),))
        db.commit()
        return redirect(url_for('index'))

    all_prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
    return render_template('select.html', all_prayers=all_prayers, selected_prayers=selected_prayers)

@app.route('/location', methods=['GET', 'POST'])
def location():
    if request.method == 'POST':
        city = request.form['city']
        country = request.form['country']
        
        method = get_best_method(country)
        
        db = get_db()
        db.execute('INSERT OR REPLACE INTO settings (id, city, country, method, notifications) VALUES (?, ?, ?, ?, ?)',
                   (1, city, country, method, json.dumps([])))
        db.commit()
        return redirect(url_for('index'))
    return render_template('location.html')

@app.route("/push_subscribe", methods=["POST"])
def push_subscribe():
    subscription_info = request.get_json()
    if not subscription_info:
        return jsonify({"error": "No subscription data provided"}), 400
    
    db = get_db()
    db.execute("UPDATE settings SET subscription_info = ? WHERE id = 1", (json.dumps(subscription_info),))
    db.commit()
    
    return jsonify({"success": True}), 200

if __name__ == '__main__':
    threading.Thread(target=notification_thread, daemon=True).start()
    app.run(debug=True)
