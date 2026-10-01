"""Shared staff login. No tenant or account database; sessions expire in memory."""
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import parse_qs
from starlette.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

CONFIG = Path(os.environ.get('NEST_AUTH_FILE', str(Path(__file__).resolve().parents[1]/'.local/auth.json')))
COOKIE = 'nest_staff_session'
TTL = 8 * 60 * 60
ITERATIONS = 600_000

def password_record(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return {'salt': salt, 'digest': digest, 'iterations': ITERATIONS}

def verify(password, record):
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(record['salt']), record['iterations']).hex()
    return hmac.compare_digest(digest, record['digest'])

class StaffAuth:
    def __init__(self, config=CONFIG):
        self.config = config
        self.sessions = {}
        self.attempts = {}
        self.version = None

    def record(self):
        try:
            record = json.loads(self.config.read_text())
            if not (len(bytes.fromhex(record['salt'])) == 16 and len(bytes.fromhex(record['digest'])) == 32 and record['iterations'] == ITERATIONS):return None
        except (OSError, ValueError, KeyError, TypeError):return None
        if record['digest'] != self.version:
            self.sessions.clear()
            self.version = record['digest']
        return record

    def valid(self, request):
        token = request.cookies.get(COOKIE, '')
        key = hashlib.sha256(token.encode()).hexdigest()
        return self.sessions.get(key, 0) > time.time()

    def page(self, message='', status=200):
        html = Path(__file__).with_name('login.html').read_text(encoding='utf-8')
        return HTMLResponse(html.replace('<!--MESSAGE-->', message), status_code=status,
            headers={'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})

    async def dispatch(self, request, call_next):
        record = self.record()
        now = time.time()
        self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
        self.attempts = {key: value for key, value in self.attempts.items() if value[1] > now}
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            expected = f'{request.url.scheme}://{request.url.netloc}'
            if (origin and origin != expected) or request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'detail': 'Request blocked. Reload this website and try again.'}, 403)
        if not record:
            return self.page('Staff access is not configured. Run the password setup on the host computer.', 503)
        if request.url.path == '/login':
            if request.method == 'GET':
                return RedirectResponse('/', 303) if self.valid(request) else self.page()
            if request.method != 'POST':return JSONResponse({'detail': 'Method not allowed'}, 405)
            ip = request.client.host if request.client else 'unknown'
            count, reset = self.attempts.get(ip, (0, now + 900))
            if count >= 5 or len(self.attempts) >= 10000:
                response = self.page('Too many attempts. Try again in 15 minutes.', 429)
                response.headers['Retry-After'] = str(max(1, int(reset - now)))
                return response
            body = b''
            async for chunk in request.stream():
                body += chunk
                if len(body) > 4096:return JSONResponse({'detail': 'Request too large'}, 413)
            self.attempts[ip] = (count + 1, reset)
            try:password = parse_qs(body.decode('utf-8'), max_num_fields=4).get('password', [''])[0]
            except (UnicodeError, ValueError):password = ''
            if len(password) > 1024 or not await run_in_threadpool(verify, password, record):return self.page('Incorrect staff password.', 401)
            self.attempts.pop(ip, None)
            token = secrets.token_urlsafe(32)
            if len(self.sessions) >= 1000:self.sessions.pop(next(iter(self.sessions)))
            self.sessions[hashlib.sha256(token.encode()).hexdigest()] = now + TTL
            response = RedirectResponse('/', 303)
            secure = request.url.scheme == 'https' or os.environ.get('NEST_SECURE_COOKIE') == '1'
            response.set_cookie(COOKIE, token, max_age=TTL, httponly=True, secure=secure, samesite='strict', path='/')
            return response
        if not self.valid(request):
            return JSONResponse({'detail': 'Your session has ended. Sign in again.'}, 401) if request.url.path.startswith('/api/') else RedirectResponse('/login', 303)
        if request.url.path == '/logout' and request.method == 'POST':
            token = request.cookies.get(COOKIE, '')
            self.sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)
            response = RedirectResponse('/login', 303)
            response.delete_cookie(COOKIE, path='/', httponly=True, samesite='strict')
            return response
        return await call_next(request)
