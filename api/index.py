from http.server import BaseHTTPRequestHandler
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

# === FUNGSI UTILITAS (dari script asli) ===

def normalize_url(url):
    url = url.replace(' | ', '').strip()
    if not urlparse(url).scheme:
        url = 'https://' + url
    return url

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except ValueError:
        return False

def is_login_page(url):
    try:
        url = normalize_url(url)
        if not is_valid_url(url):
            return False
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        login_indicators = [
            soup.find('input', {'type': 'password'}),
            soup.find('input', {'name': re.compile('password|pass|pwd', re.I)}),
            soup.find('input', {'name': re.compile('username|user|login|email', re.I)}),
            soup.find('form', {'method': re.compile('post', re.I)})
        ]
        return sum(1 for indicator in login_indicators if indicator) >= 2
    except Exception:
        return False

def detect_form_fields_and_tokens(url):
    try:
        url = normalize_url(url)
        if not is_valid_url(url):
            return None, None, None, None, None
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        forms = soup.find_all('form')
        if not forms:
            return None, None, None, None, None
        form = forms[0]
        action = form.get('action', url)
        if not action.startswith('http'):
            action = urljoin(url, action)
        method = form.get('method', 'post').lower()
        inputs = form.find_all('input')
        fields = {}
        for input_tag in inputs:
            name = input_tag.get('name')
            input_type = input_tag.get('type', 'text')
            value = input_tag.get('value', '')
            if name:
                fields[name] = {
                    'type': input_type,
                    'required': input_tag.get('required') is not None,
                    'value': value
                }
        tokens = {}
        hidden_inputs = form.find_all('input', {'type': 'hidden'})
        for hidden in hidden_inputs:
            name = hidden.get('name')
            value = hidden.get('value')
            if name and value:
                if re.search(r'csrf|token|auth|nonce', name, re.I):
                    tokens[name] = value
        for header_name, header_value in response.headers.items():
            if re.search(r'csrf|token|auth', header_name, re.I):
                tokens[header_name] = header_value
        return action, method, fields, tokens, session
    except Exception:
        return None, None, None, None, None

def detect_captcha(url):
    try:
        url = normalize_url(url)
        if not is_valid_url(url):
            return False
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        captcha_indicators = [
            'captcha' in response.text.lower(),
            soup.find('div', {'class': re.compile('captcha', re.I)}),
            soup.find('img', {'src': re.compile('captcha', re.I)}),
            'g-recaptcha' in response.text,
            'hcaptcha' in response.text
        ]
        return any(captcha_indicators)
    except Exception:
        return False

def attempt_login(action, method, fields, tokens, session, username, password):
    try:
        action = normalize_url(action)
        if not is_valid_url(action):
            return False, None, []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        payload = {}
        for name, info in fields.items():
            if info['value']:
                payload[name] = info['value']
            elif info['type'] == 'password':
                payload[name] = password
            else:
                payload[name] = username
        payload.update(tokens)
        initial_url = action
        if method.lower() == 'post':
            response = session.post(action, data=payload, headers=headers, timeout=10, allow_redirects=True)
        else:
            response = session.get(action, params=payload, headers=headers, timeout=10, allow_redirects=True)
        final_url = response.url
        soup = BeautifulSoup(response.text, 'html.parser')

        success_indicators = [
            (response.status_code == 200, "Status code is 200"),
            (final_url != initial_url, "Redirected to different page"),
            (soup.find('a', {'href': re.compile('logout|signout|sign-out|rememberme|forever', re.I)}) is not None, "Logout link present"),
            (soup.find('div', {'class': re.compile('Dashboard|profile|welcome|Appearance|Plugins|Comments', re.I)}) is not None, "Dashboard element found"),
            (any(kw.lower() in response.text.lower() for kw in ['welcome', 'Dashboard', 'profile', 'account', 'logged in', 'Appearance', 'Plugins']), "Success keywords found"),
            (soup.find('input', {'type': 'password'}) is None, "No password field present"),
            (soup.find('form', {'action': re.compile('login|signin|auth', re.I)}) is None, "No login form present"),
            (not any(err.lower() in response.text.lower() for err in ['error', 'invalid', 'incorrect', 'failed', 'try again']), "No error messages")
        ]
        failure_indicators = [
            (response.status_code in (401, 403, 400), "Unauthorized status"),
            (soup.find('input', {'type': 'password'}) is not None, "Password field still present"),
            (soup.find('form', {'action': re.compile('login|signin|auth', re.I)}) is not None, "Login form still present"),
            (soup.find('div', {'class': re.compile('fail|invalid|alert', re.I)}) is not None, "Error element found"),
            (any(err.lower() in response.text.lower() for err in ['invalid credentials', 'login failed', 'incorrect password', 'authentication failed', 'wrong username', 'access denied']), "Error message detected"),
            (re.search(r'login|err|error|fail', final_url.lower()), "URL indicates error")
        ]
        success_score = sum(1 for condition, _ in success_indicators if condition)
        failure_score = sum(1 for condition, _ in failure_indicators if condition)
        success_reasons = [reason for condition, reason in success_indicators if condition]
        failure_reasons = [reason for condition, reason in failure_indicators if condition]

        if success_score >= 5 and failure_score == 0 and "Logout link present" in success_reasons:
            return True, final_url, success_reasons
        elif failure_score > 0:
            return False, final_url, failure_reasons
        else:
            return False, final_url, []
    except Exception as e:
        return False, None, [str(e)]

def process_line(line):
    line = line.strip()
    if not line:
        return {"status": "error", "message": "Baris kosong", "details": "", "raw_line": line}

    parts = line.split(':', 2)
    if len(parts) != 3:
        return {"status": "error", "message": "Format salah (harus url:username:password)", "details": line, "raw_line": line}

    url_raw, username, password = parts
    url = normalize_url(url_raw)

    if not is_valid_url(url):
        return {"status": "error", "message": f"URL tidak valid: {url}", "details": "", "raw_line": line}

    if not is_login_page(url):
        return {"status": "error", "message": "Bukan halaman login", "details": url, "raw_line": line}

    action, method, fields, tokens, session = detect_form_fields_and_tokens(url)

    if not action or not fields:
        return {"status": "error", "message": "Tidak dapat mendeteksi form login", "details": url, "raw_line": line}

    if detect_captcha(url):
        return {"status": "captcha", "message": "Terdeteksi adanya captcha", "details": "Login tidak dapat diuji karena adanya captcha", "raw_line": line}

    success, final_url, reasons = attempt_login(action, method, fields, tokens, session, username, password)

    if success:
        return {
            "status": "success",
            "message": f"Login berhasil! Redirected to: {final_url}",
            "details": "; ".join(reasons),
            "raw_line": line
        }
    else:
        return {
            "status": "fail",
            "message": f"Login gagal. Final URL: {final_url or url}",
            "details": "; ".join(reasons) if reasons else "Kredensial salah atau proteksi login",
            "raw_line": line
        }

# === VERCEL HANDLER ===

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"error": "No body"})
                return

            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            line = data.get('line', '').strip()

            if not line:
                self._send_json(400, {"error": "Line is required"})
                return

            result = process_line(line)
            self._send_json(200, result)

        except Exception as e:
            self._send_json(500, {"status": "error", "message": str(e), "details": "", "raw_line": ""})

    def do_GET(self):
        self._send_json(200, {"message": "Login Scanner API - Use POST method"})

    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
