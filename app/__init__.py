from pathlib import Path
import click
from flask import Flask, render_template, session, request
from flask_login import current_user, logout_user
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from flask_wtf.csrf import CSRFError
from config import settings
from app.extensions import db, login_manager, csrf

@event.listens_for(Engine, 'connect')
def sqlite_configuration(connection, _):
    if connection.__class__.__module__.startswith('sqlite3'):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA busy_timeout=20000')
        cursor.close()

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(settings())
    if test_config: app.config.update(test_config)
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    db.init_app(app); login_manager.init_app(app); csrf.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Entre para acessar o painel.'
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        if not str(user_id).isdigit(): return None
        user = db.session.get(User, int(user_id))
        if not user or not user.active or session.get('session_version') != user.session_version: return None
        return user

    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.site.routes import site_bp
    from app.admin.management import management_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(management_bp, url_prefix='/admin')
    app.register_blueprint(site_bp)

    from app.services.validation import brl
    app.jinja_env.filters['brl'] = brl
    app.jinja_env.filters['price_input'] = lambda cents: f'{(cents or 0)/100:.2f}'
    @app.context_processor
    def common():
        from app.services.restaurant import settings as restaurant_settings, receiver
        from app.services.daily_menu import current_menu
        row = restaurant_settings()
        return {'cart_count':sum(session.get('cart', {}).values()), 'version':'1.9.0', 'restaurant':row, 'attendant':receiver(row), 'daily_menu':current_menu()}

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; font-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://wa.me https://api.whatsapp.com https://web.whatsapp.com"
        if request.endpoint and not request.endpoint.startswith('static') and request.endpoint != 'site.media':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(CSRFError)
    def csrf_error(_): return render_template('error.html', code=400, message='A página expirou. Volte, atualize a página e tente novamente.'), 400
    @app.errorhandler(413)
    def too_large(_): return render_template('error.html', code=413, message='O conjunto de imagens é grande demais. Use até 8 MB por imagem e envie menos arquivos de uma vez.'), 413
    for code, message in [(400,'Não foi possível concluir essa solicitação.'),(403,'Você não tem permissão para acessar este conteúdo.'),(404,'Não encontramos essa página.'),(500,'Não foi possível concluir a operação. Tente novamente em instantes.')]:
        def handler(error, code=code, message=message):
            db.session.rollback()
            return render_template('error.html', code=code, message=message), code
        app.register_error_handler(code, handler)

    @app.cli.command('init-db')
    def init_db():
        db.create_all()
        from app.services.menu_categories import ensure_default_categories
        from app.services.catalog_seed import ensure_mana_catalog
        ensure_default_categories()
        imported = 0
        if db.session.scalar(select(User.id).limit(1)):
            imported = ensure_mana_catalog()
        db.session.commit()
        click.echo('Banco preparado. Os dados existentes foram preservados.')
        if imported: click.echo(f'{imported} pratos da marca foram importados para o catálogo.')

    @app.cli.command('criar-admin')
    def create_admin():
        from app.services import validation as v
        db.create_all()
        if db.session.scalar(select(User.id).limit(1)):
            raise click.ClickException('O primeiro administrador já existe. Crie novas contas pelo painel.')
        try:
            user = User(name=v.text(click.prompt('Seu nome público'), 'Nome', 90),
                        email=v.email(click.prompt('E-mail de acesso')),
                        whatsapp=v.phone(click.prompt('WhatsApp com DDD')), role='superadmin')
            user.set_password(v.password(click.prompt('Senha (mínimo 10 caracteres)', hide_input=True, confirmation_prompt=True)))
            db.session.add(user); db.session.flush()
            from app.services.menu_categories import ensure_default_categories
            from app.services.catalog_seed import ensure_mana_catalog
            ensure_default_categories(user.id)
            db.session.commit()
            imported = ensure_mana_catalog(user.id)
        except ValueError as e: raise click.ClickException(str(e))
        click.echo('Administrador principal criado. Acesse /login.')
        if 'imported' in locals() and imported: click.echo(f'{imported} pratos da marca foram importados automaticamente.')


    @app.cli.command('importar-pratos-mana')
    def import_mana_dishes():
        from app.services.catalog_seed import import_mana_catalog
        update = click.confirm('Completar também fotos e tamanhos ausentes em pratos já existentes?', default=True)
        imported = import_mana_catalog(update_existing=update)
        click.echo(f'{imported} pratos preparados/atualizados para o catálogo.' if imported else 'Os 22 pratos já estão preparados no catálogo.')

    @app.cli.command('redefinir-senha')
    @click.argument('email')
    def reset_password(email):
        from app.services.validation import password
        user = db.session.scalar(select(User).where(User.email == email.lower().strip()))
        if not user: raise click.ClickException('Administrador não encontrado.')
        try: user.set_password(password(click.prompt('Nova senha', hide_input=True, confirmation_prompt=True)))
        except ValueError as e: raise click.ClickException(str(e))
        user.session_version += 1
        db.session.commit()
        click.echo('Senha atualizada. As sessões anteriores foram encerradas.')
    from app.services.demo import register_demo
    register_demo(app)
    return app
