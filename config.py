import os
import secrets
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

def settings():
    data = Path(os.getenv('DATA_DIR', str(BASE_DIR / 'instance'))).resolve()
    production = os.getenv('APP_ENV') == 'production'
    if os.getenv('REQUIRE_DATA_VOLUME') == '1':
        railway_mount = os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
        if os.getenv('RAILWAY_PROJECT_ID'):
            mounted = railway_mount == str(data)
        else:
            mounted = data.is_mount()
        if not mounted:
            raise RuntimeError(f'Configure um volume persistente montado em {data} antes de iniciar a Maná do Céu.')
    data.mkdir(parents=True, exist_ok=True)
    secret = os.getenv('SECRET_KEY', '').strip()
    if production and secret and len(secret) < 32:
        raise RuntimeError('SECRET_KEY, quando informada, precisa ter pelo menos 32 caracteres.')
    if not secret:
        secret_file = data / 'secret.key'
        if not secret_file.exists():
            try:
                with secret_file.open('x') as f:
                    f.write(secrets.token_hex(32))
                secret_file.chmod(0o600)
            except FileExistsError:
                pass
        secret = secret_file.read_text().strip()
    return dict(
        SECRET_KEY=secret,
        SQLALCHEMY_DATABASE_URI='sqlite:///' + str(data / 'mana_do_ceu.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={'connect_args': {'timeout': 20}},
        DATA_DIR=data,
        UPLOAD_FOLDER=data / 'uploads',
        MAX_CONTENT_LENGTH=64 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=production,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        WTF_CSRF_TIME_LIMIT=12 * 60 * 60,
        PUBLIC_BASE_URL=os.getenv('PUBLIC_BASE_URL', '').rstrip('/'),
        TRUSTED_HOSTS=[v.strip() for v in os.getenv('TRUSTED_HOSTS', '').split(',') if v.strip()] or None,
    )
