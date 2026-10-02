"""Shared staff login with Redis sessions in cloud and memory sessions locally."""
import ipaddress
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from pathlib import Path
from urllib.parse import parse_qs
from starlette.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .cloud_store import RedisStore, StorageError, cloud_enabled

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
            raw=os.getenv('NEST_STAFF_PASSWORD_RECORD')
            record = json.loads(raw if raw else self.config.read_text() if not cloud_enabled() else '{}')
            if not (len(bytes.fromhex(record['salt'])) == 16 and len(bytes.fromhex(record['digest'])) == 32 and record['iterations'] == ITERATIONS):return None
        except (OSError, ValueError, KeyError, TypeError, AttributeError):return None
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
        try:
            return await self._dispatch(request,call_next)
        except StorageError as exc:
            logging.getLogger(__name__).error('Staff access/storage failure: %s',exc.code)
            return JSONResponse({'detail':'Staff access or cloud storage is temporarily unavailable. Try again later.'},503)

    async def _dispatch(self, request, call_next):
        store=RedisStore() if cloud_enabled() else None
        record = self.record()
        now = time.time()
        self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
        self.attempts = {key: value for key, value in self.attempts.items() if value[1] > now}
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            scheme='https' if os.getenv('VERCEL') else request.url.scheme
            expected = f'{scheme}://{request.url.netloc}'
            if (origin and origin != expected) or request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'detail': 'Request blocked. Reload this website and try again.'}, 403)
        if not record:
            return self.page('Staff access is not configured. Configure the staff password on the server.', 503)
        token=request.cookies.get(COOKIE,'')
        authenticated=await run_in_threadpool(store.valid,token,record['digest']) if store else self.valid(request)
        if request.url.path == '/login':
            if request.method == 'GET':
                return RedirectResponse('/', 303) if authenticated else self.page()
            if request.method != 'POST':return JSONResponse({'detail': 'Method not allowed'}, 405)
            ip = request.client.host if request.client else 'unknown'
            if os.getenv('VERCEL'):
                try:ip=str(ipaddress.ip_address(request.headers.get('x-forwarded-for','').split(',')[0].strip()))
                except ValueError:pass
            if store:
                allowed,retry=await run_in_threadpool(store.reserve_attempt,ip)
                count,reset=(0 if allowed else 5),now+max(1,retry)
            else:count, reset = self.attempts.get(ip, (0, now + 900))
            if count >= 5 or len(self.attempts) >= 10000:
                response = self.page('Too many attempts. Try again in 15 minutes.', 429)
                response.headers['Retry-After'] = str(max(1, int(reset - now)))
                return response
            body = b''
            async for chunk in request.stream():
                body += chunk
                if len(body) > 4096:return JSONResponse({'detail': 'Request too large'}, 413)
            if not store:self.attempts[ip] = (count + 1, reset)
            try:password = parse_qs(body.decode('utf-8'), max_num_fields=4).get('password', [''])[0]
            except (UnicodeError, ValueError):password = ''
            if len(password) > 1024 or not await run_in_threadpool(verify, password, record):return self.page('Incorrect staff password.', 401)
            if store:await run_in_threadpool(store.clear_attempts,ip)
            else:self.attempts.pop(ip, None)
            token = secrets.token_urlsafe(32)
            if len(self.sessions) >= 1000:self.sessions.pop(next(iter(self.sessions)))
            if store:await run_in_threadpool(store.create_session,token,record['digest'],TTL)
            else:self.sessions[hashlib.sha256(token.encode()).hexdigest()] = now + TTL
            response = RedirectResponse('/', 303)
            secure = request.url.scheme == 'https' or os.environ.get('NEST_SECURE_COOKIE') == '1' or bool(os.environ.get('VERCEL'))
            response.set_cookie(COOKIE, token, max_age=TTL, httponly=True, secure=secure, samesite='strict', path='/')
            return response
        if not authenticated:
            return JSONResponse({'detail': 'Your session has ended. Sign in again.'}, 401) if request.url.path.startswith('/api/') else RedirectResponse('/login', 303)
        if request.url.path == '/logout' and request.method == 'POST':
            token = request.cookies.get(COOKIE, '')
            if store:await run_in_threadpool(store.revoke,token)
            else:self.sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)
            response = RedirectResponse('/login', 303)
            response.delete_cookie(COOKIE, path='/', httponly=True, samesite='strict')
            return response
        return await call_next(request)
