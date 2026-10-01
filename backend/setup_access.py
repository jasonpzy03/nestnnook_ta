"""Run python -m backend.setup_access to set or change the shared staff password."""
import argparse
import getpass
import os
import secrets
from .auth import CONFIG, password_record
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--generate', action='store_true', help='Generate an initial password in a private local text file')
    args = parser.parse_args()
    if args.generate and CONFIG.exists():raise SystemExit('Access is already configured. Run without --generate to change the password.')
    if args.generate:password = secrets.token_urlsafe(18)
    else:
        password = getpass.getpass('New staff password (at least 12 characters): ')
        if len(password)<12 or len(password)>1024:raise SystemExit('Use between 12 and 1024 characters.')
        if password != getpass.getpass('Confirm password: '):raise SystemExit('Passwords do not match.')
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG.with_suffix('.tmp')
    temporary.write_text(json.dumps(password_record(password)), encoding='utf-8')
    os.chmod(temporary, 0o600)
    temporary.replace(CONFIG)
    initial = CONFIG.parent/'initial-login.txt'
    if args.generate:
        initial.write_text('Nest & Nook staff sign in\n\nWebsite: http://localhost:8000\nStaff password: '+password+'\n\nSave this password in your password manager, then delete this file.\nChange it on the host computer with:\n.venv\\Scripts\\python.exe -m backend.setup_access\n', encoding='utf-8')
        os.chmod(initial, 0o600)
        print('Initial password saved to:', initial)
    elif initial.exists():initial.unlink()
    print('Staff password configured. Existing sessions are revoked on their next request.')
if __name__=='__main__':main()
