import hashlib
from datetime import timedelta
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy import select, delete, func
from app.extensions import db
from app.models import User, LoginAttempt, now

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()[:180]
        ip = request.remote_addr or 'unknown'
        keys = [hashlib.sha256(v.encode()).hexdigest() for v in ('email:'+email, 'ip:'+ip)]
        cutoff = now() - timedelta(minutes=15)
        db.session.execute(delete(LoginAttempt).where(LoginAttempt.created_at < cutoff))
        count = db.session.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.key.in_(keys)))
        if count >= 16:
            db.session.commit()
            return render_template('auth/login.html', error='Muitas tentativas. Aguarde 15 minutos e tente novamente.'), 429
        user = db.session.scalar(select(User).where(User.email == email))
        if user and user.active and user.check_password(request.form.get('password', '')[:128]):
            cart = session.get('cart', {})
            session.clear()
            session['cart'] = cart
            login_user(user)
            session.permanent = True
            session['session_version'] = user.session_version
            db.session.execute(delete(LoginAttempt).where(LoginAttempt.key.in_(keys)))
            db.session.commit()
            return redirect(url_for('admin.dashboard'))
        db.session.add_all([LoginAttempt(key=k) for k in keys])
        db.session.commit()
        return render_template('auth/login.html', error='E-mail ou senha inválidos.'), 401
    return render_template('auth/login.html')

@auth_bp.post('/logout')
@login_required
def logout():
    logout_user()
    session.pop('session_version', None)
    flash('Você saiu do painel.', 'success')
    return redirect(url_for('site.home'))
