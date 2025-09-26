# api/save.py
from http.server import BaseHTTPRequestHandler
import json, os, requests, urllib.parse

class handler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_OPTIONS(self):
        # CORS preflight
        self._set_headers(204)

    def do_GET(self):
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        date = params.get('date', [None])[0]
        if not date:
            self._set_headers(400)
            self.wfile.write(json.dumps({'error':'missing date param'}).encode())
            return

        SUPABASE_URL = os.environ.get('SUPABASE_URL')
        SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
        if not SUPABASE_URL or not SUPABASE_KEY:
            self._set_headers(500)
            self.wfile.write(json.dumps({'error':'Supabase env vars not set'}).encode())
            return

        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/exercicios?select=json_data&data=eq.{date}"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}'
        }
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            rows = r.json()
            if rows:
                self._set_headers(200)
                self.wfile.write(json.dumps({'json_data': rows[0].get('json_data', {})}).encode())
            else:
                self._set_headers(200)
                self.wfile.write(json.dumps({'json_data': {}}).encode())
        else:
            self._set_headers(500)
            self.wfile.write(json.dumps({'error': r.text, 'status': r.status_code}).encode())

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        try:
            payload = json.loads(body)
            date = payload.get('date')
            json_data = payload.get('json') or payload.get('json_data') or payload.get('data') or {}
            if not date:
                self._set_headers(400)
                self.wfile.write(json.dumps({'error':'missing date field'}).encode())
                return

            SUPABASE_URL = os.environ.get('SUPABASE_URL')
            SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
            if not SUPABASE_URL or not SUPABASE_KEY:
                self._set_headers(500)
                self.wfile.write(json.dumps({'error':'Supabase env vars not set'}).encode())
                return

            # Upsert via PostgREST: on_conflict=data
            url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/exercicios?on_conflict=data"
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json',
                # Prefer merge duplicates faz o upsert (merge) usando PK/unique
                'Prefer': 'resolution=merge-duplicates'
            }
            body_req = {"data": date, "json_data": json_data}
            r = requests.post(url, headers=headers, json=body_req)

            if r.status_code in (200, 201, 204):
                self._set_headers(200)
                self.wfile.write(json.dumps({'ok': True}).encode())
            else:
                self._set_headers(500)
                self.wfile.write(json.dumps({'error': r.text, 'status': r.status_code}).encode())

        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({'error': str(e)}).encode())
