from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests
import sqlite3
import os
import openai
import subprocess
from threading import Thread
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException

openai.api_key = ''  # Replace with your actual OpenAI API key

app = Flask(__name__)

# Define the database path
database_path = 'database'
db_file_path = os.path.join(database_path, 'traffic_analysis.db')

# Ensure the database directory exists
if os.path.exists(database_path):
    if not os.path.isdir(database_path):
        raise Exception(f"{database_path} exists but is not a directory")
else:
    os.makedirs(database_path)

# Initialize the database
def init_db():
    conn = sqlite3.connect(db_file_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS analysis
                      (id INTEGER PRIMARY KEY, traffic TEXT, analysis TEXT)''')
    conn.commit()
    conn.close()

# Start mitmproxy
def start_mitmproxy():
    subprocess.run(["mitmdump", "-s", "mitmproxy_script.py"])

@app.route('/start', methods=['POST'])
def start():
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({"error": "URL is required"}), 400

        # Start mitmproxy in a separate thread
        mitmproxy_thread = Thread(target=start_mitmproxy)
        mitmproxy_thread.start()

        # Set up Selenium WebDriver
        options = webdriver.ChromeOptions()
        options.add_argument('--proxy-server=http://localhost:8080')  # Set the proxy to mitmproxy
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        # Navigate to the URL
        driver.get(url)

        # Wait for the search box to be present on the page
        wait = WebDriverWait(driver, 20)
        search_box = wait.until(EC.presence_of_element_located((By.NAME, "q")))

        # Example interaction with the page
        search_box.send_keys("bug bounty")
        search_box.send_keys(Keys.RETURN)

        # Close the browser
        driver.quit()

        # Wait for mitmproxy to capture traffic (example: 10 seconds)
        mitmproxy_thread.join(timeout=10)

        return jsonify({"status": "success"}), 200
    except NoSuchElementException as e:
        return jsonify({"error": f"Element not found: {str(e)}"}), 500
    except TimeoutException as e:
        return jsonify({"error": f"Timeout waiting for element: {str(e)}"}), 500
    except WebDriverException as e:
        return jsonify({"error": f"Selenium WebDriver error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def scrape_bugcrowd():
    try:
        url = "https://bugcrowd.com/ultramobile"  # Example URL, adjust to the actual URL
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        bugs = []
        for bug in soup.find_all('div', class_='bug'):
            title = bug.find('h2').text
            description = bug.find('p').text
            bugs.append({'title': title, 'description': description})

        return bugs
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def analyze_bug(bug):
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=f"Analyze and classify the following bug:\nTitle: {bug['title']}\nDescription: {bug['description']}",
            max_tokens=150
        )
        return response.choices[0].text
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def analyze_bugs(bugs):
    try:
        analyzed_bugs = []
        for bug in bugs:
            analysis = analyze_bug(bug)
            analyzed_bugs.append({
                'title': bug['title'],
                'description': bug['description'],
                'analysis': analysis
            })
        return analyzed_bugs
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/bugcrowd-analysis', methods=['GET'])
def bugcrowd_analysis():
    try:
        bugs = scrape_bugcrowd()
        analyzed_bugs = analyze_bugs(bugs)

        # Save the analysis to the database
        conn = sqlite3.connect(db_file_path)
        cursor = conn.cursor()
        for bug in analyzed_bugs:
            cursor.execute('''INSERT INTO analysis (traffic, analysis) VALUES (?, ?)''',
                           (f"Title: {bug['title']}\nDescription: {bug['description']}", bug['analysis']))
        conn.commit()
        conn.close()

        return jsonify(analyzed_bugs), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(port=5000, debug=True)
