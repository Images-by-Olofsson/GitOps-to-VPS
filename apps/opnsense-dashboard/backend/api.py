#!/usr/bin/env python3
import os
import json
import time
from flask import Flask, jsonify
from flask_cors import CORS
import requests
import urllib3
urllib3.disable_warnings()

app = Flask(__name__)
CORS(app)

OPNSENSE_HOST = os.getenv('OPNSENSE_HOST', 'https://opnsense.local:4443')
OPNSENSE_API_KEY = os.getenv('OPNSENSE_API_KEY')
OPNSENSE_API_SECRET = os.getenv('OPNSENSE_API_SECRET')

def make_opnsense_request(endpoint):
    try:
        url = f"{OPNSENSE_HOST}/api/{endpoint}"
        response = requests.get(url, auth=(OPNSENSE_API_KEY, OPNSENSE_API_SECRET), verify=False, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

@app.route('/api')
@app.route('/api.php')
def get_dashboard_data():
    ids_status = make_opnsense_request('ids/service/status')
    ids_settings = make_opnsense_request('ids/settings/get')
    
    ids_running = False
    ids_enabled = False
    ips_mode = False
    
    if ids_status:
        ids_running = 'running' in str(ids_status).lower()
    
    if ids_settings and 'ids' in ids_settings:
        gen = ids_settings.get('ids', {}).get('general', {})
        ids_enabled = gen.get('enabled') == '1'
        ips_mode = gen.get('ips') == '1'
    
    return jsonify({
        'timestamp': int(time.time()),
        'ids_running': ids_running,
        'ids_enabled': ids_enabled,
        'ips_mode': ips_mode,
        'alerts_24h': 0,
        'blocked_threats': 0,
        'packet_rate': 0,
        'threats': {'malware': 0, 'exploits': 0, 'sqli': 0, 'dos': 0, 'botnet': 0},
        'recent_alerts': [],
        'top_sources': [],
        'top_ports': [],
        'raw_status': ids_status,
        'raw_settings': ids_settings
    })

@app.route('/health')
def health_check():
    return jsonify({'status': 'ok', 'timestamp': int(time.time())})

if __name__ == '__main__':
    print(f"Starting OPNsense Dashboard API - Connecting to {OPNSENSE_HOST}")
    app.run(host='0.0.0.0', port=5000, debug=True)
