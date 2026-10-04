"""Criação inicial interativa. Não recria senhas nem altera contas existentes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.extensions import db
from app.models import User
from app.services.menu_categories import ensure_default_categories
from app.services.catalog_seed import ensure_mana_catalog
from sqlalchemy import select

app = create_app()
with app.app_context():
    db.create_all()
    first = db.session.scalar(select(User.id).limit(1))
if not first:
    # Invoke the same interactive command used by Flask, with a real app context.
    from flask.cli import ScriptInfo
    try:
        app.cli.main(args=['criar-admin'], prog_name='Maná do Céu', obj=ScriptInfo(create_app=lambda: app), standalone_mode=False)
    except Exception as exc:
        print(f'Não foi possível configurar: {exc}')
        sys.exit(1)
with app.app_context():
    ensure_default_categories()
    owner_id = db.session.scalar(select(User.id).order_by(User.id))
    imported = ensure_mana_catalog(owner_id=owner_id)
    print(f'{imported} pratos da marca preparados para o catálogo.' if imported else 'Catálogo de pratos já existente: nada importado.')
print('Maná do Céu pronta. Painel: http://127.0.0.1:5000/login')
