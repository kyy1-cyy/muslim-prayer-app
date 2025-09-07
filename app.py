# app.py (Full Corrected Version)

import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, g
import requests
import json
from datetime import datetime
import threading
import time

# Flask App Initialization
app = Flask(__name__)

# Constants
DATABASE = 'database.db'
# API for Prayer Times
ALADHAN_API = "http://api.aladhan.com/v1/timingsByCity"

# Function to get a database connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

# Initialize the database
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                city TEXT,
                country TEXT,
                method INTEGER,
                notifications TEXT
            )
        ''')
        db.commit()

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
        # Parse the 24-hour time string
        dt_obj = datetime.strptime(time_str, '%H:%M')
        # Format it into a 12-hour time string with AM/PM
        return dt_obj.strftime('%I:%M %p')
    return None

# Function to select the best calculation method for a country
def get_best_method(country):
    country = country.lower()
    if country in ["australia"]:
        # The Muslim Pro app uses a method similar to MWL/ISNA in Australia, let's use MWL (Method 1)
        return 1
    elif country in ["united kingdom", "uk", "france", "belgium"]:
        # Islamic Society of North America (ISNA) is common in parts of Europe
        return 2
    elif country in ["saudi arabia", "uae", "qatar", "kuwait"]:
        # Umm al-Qura is the standard in Saudi Arabia and the Gulf
        return 4
    elif country in ["pakistan", "india", "bangladesh"]:
        # University of Islamic Sciences, Karachi
        return 5
    elif country in ["egypt"]:
        # Egyptian General Authority of Survey
        return 3
    else:
        # Default to Muslim World League for most other countries
        return 1

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

                if notifications:
                    timings = get_prayer_times(city, country, method)
                    if timings:
                        now = datetime.now()
                        current_time_str = now.strftime("%H:%M")

                        for prayer, time_str in timings.items():
                            # We only want to send notifications for the main prayers
                            if prayer.lower() in [n.lower() for n in notifications]:
                                # You would implement push notification logic here
                                if current_time_str == time_str:
                                    print(f"NOTIFICATION: PRAY {prayer.upper()} NOW, OR REGRET IT LATER.")
                                    # To prevent spamming the log, we'll sleep for a short period
                                    time.sleep(30)

            # Check every minute
            time.sleep(60)

# Main Routes
@app.route('/')
def index():
    db = get_db()
    settings = db.execute('SELECT * FROM settings WHERE id = 1').fetchone()

    # If no settings are found, redirect to the location page
    if not settings or not settings['city']:
        return render_template('index.html', no_location=True)

    city = settings['city']
    country = settings['country']
    method = settings['method']
    prayer_times = get_prayer_times(city, country, method)

    # Convert times for display to 12-hour format and filter the list
    display_times = {}
    if prayer_times:
        # Define the order and which prayers to show
        prayers_to_show = ["Fajr", "Dhuhr", "Asr", "Sunset", "Maghrib", "Isha"]

        for prayer in prayers_to_show:
            time_str = prayer_times.get(prayer)
            if time_str:
                display_times[prayer] = format_to_12h(time_str)

    return render_template('index.html', prayer_times=display_times, city=city, country=country)

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

        # Use the new function to get the best method for the country
        method = get_best_method(country)

        db = get_db()
        db.execute('INSERT OR REPLACE INTO settings (id, city, country, method, notifications) VALUES (?, ?, ?, ?, ?)',
                   (1, city, country, method, json.dumps([])))
        db.commit()
        return redirect(url_for('index'))
    return render_template('location.html')

@app.before_request
def before_request():
    # Initialize the database before each request if it hasn't been already.
    # This is a simple approach for SQLite in a stateless environment.
    if not hasattr(g, '_database_initialized'):
        init_db()
        g._database_initialized = True

if __name__ == '__main__':
    # The notification thread is started here for local development.
    # For production, a more robust solution like a separate worker process would be better.
    threading.Thread(target=notification_thread, daemon=True).start()
    app.run(debug=True)
