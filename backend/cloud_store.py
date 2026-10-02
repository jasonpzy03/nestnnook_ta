"""Small Upstash REST adapter. Cloud failures never fall back to local state."""
import hashlib
import json
import os
import re
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit
from urllib.error import HTTPError

class StorageError(Exception):
    def __init__(self,message,code='storage_unavailable'):
        super().__init__(message)
        self.code=code

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def cloud_enabled():
    return bool(os.getenv('VERCEL') or os.getenv('UPSTASH_REDIS_REST_URL') or os.getenv('UPSTASH_REDIS_REST_TOKEN'))

class RedisStore:
    def __init__(self):
        self.url=os.getenv('UPSTASH_REDIS_REST_URL','').strip().rstrip('/')
        self.token=os.getenv('UPSTASH_REDIS_REST_TOKEN','').strip()
        if not self.url or not self.token:
            raise StorageError('Cloud storage is not configured.','redis_credentials_missing')
        try:parsed=urlsplit(self.url)
        except ValueError:
            raise StorageError('Cloud storage is not configured.','redis_rest_url_invalid') from None
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or not self.token:
            raise StorageError('Cloud storage is not configured.','redis_rest_url_invalid')
        prefix=os.getenv('NEST_REDIS_PREFIX','nestnnook:'+os.getenv('VERCEL_ENV','development'))
        if not re.fullmatch(r'[a-zA-Z0-9:_-]{1,100}',prefix):raise StorageError('Invalid storage prefix.','redis_prefix_invalid')
        self.prefix=prefix

    def command(self,*args):
        request=Request(self.url,data=json.dumps(args).encode(),headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'},method='POST')
        try:
            with build_opener(NoRedirect).open(request,timeout=8) as response:
                payload=json.load(response)
            if isinstance(payload,dict) and 'error' in payload:
                raise StorageError('Cloud storage rejected the command.','redis_command_rejected')
            if not isinstance(payload,dict) or 'result' not in payload:raise ValueError()
            return payload['result']
        except StorageError:raise
        except HTTPError as exc:
            code={401:'redis_auth_failed',403:'redis_access_denied',429:'redis_rate_limited'}.get(exc.code,'redis_http_error')
            raise StorageError('Cloud storage is temporarily unavailable.',code) from None
        except (ValueError,UnicodeError):
            raise StorageError('Cloud storage is temporarily unavailable.','redis_response_invalid') from None
        except Exception as exc:
            raise StorageError('Cloud storage is temporarily unavailable.','redis_connection_failed') from None

    def key(self,kind,value=''):
        return self.prefix+':'+kind+(':'+hashlib.sha256(value.encode()).hexdigest() if value else '')

    def valid(self,token,version):
        return bool(token) and self.command('GET',self.key('session',token))==version

    def create_session(self,token,version,ttl):
        self.command('SET',self.key('session',token),version,'EX',ttl)

    def revoke(self,token):
        if token:self.command('DEL',self.key('session',token))

    def reserve_attempt(self,ip):
        # One atomic operation prevents parallel invocations evading the limit.
        script="""local n=tonumber(redis.call('GET',KEYS[1]) or '0')
        if n>=5 then return {0,redis.call('TTL',KEYS[1])} end
        n=redis.call('INCR',KEYS[1])
        if n==1 then redis.call('EXPIRE',KEYS[1],900) end
        return {1,redis.call('TTL',KEYS[1])}"""
        return self.command('EVAL',script,1,self.key('attempt',ip))

    def clear_attempts(self,ip):
        self.command('DEL',self.key('attempt',ip))

    def addresses(self):
        values=self.command('HVALS',self.key('addresses'))
        if not isinstance(values,list) or any(not isinstance(x,str) for x in values):raise StorageError('Invalid saved addresses.')
        return sorted(values,key=str.casefold)

    def add_address(self,address):
        script="""local existing=redis.call('HGET',KEYS[1],ARGV[1])
        if existing then return existing end
        if redis.call('HLEN',KEYS[1])>=500 then return false end
        redis.call('HSET',KEYS[1],ARGV[1],ARGV[2])
        return ARGV[2]"""
        return self.command('EVAL',script,1,self.key('addresses'),address.casefold(),address)
