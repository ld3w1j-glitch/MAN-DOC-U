import re
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort, current_app, send_from_directory
from sqlalchemy import select, or_, func
from app.extensions import db
from app.models import Product, ProductImage, VariantImage, Category, User, Variant, PendingOrder, PendingOrderItem, OrderDetails
from app.services.cart import selection, add_item, resolve_cart
from app.services.validation import integer, text, phone
from app.services import restaurant as kitchen
from app.services.daily_menu import current_product_ids, is_on_menu, current_menu, menu_products
from app.services.menu_categories import ordered_categories, group_products
import secrets
from sqlalchemy.exc import IntegrityError

site_bp = Blueprint('site', __name__)

@site_bp.get('/')
def home():
    q = request.args.get('q', '').strip()[:100]
    category_id = request.args.get('categoria', type=int)
    order = request.args.get('ordem', 'recentes')
    query = select(Product).join(Product.owner).join(Product.category).where(Product.active.is_(True), User.active.is_(True), Category.active.is_(True))
    query = query.where(Product.id.in_(current_product_ids()))
    if q:
        escaped = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.where(or_(Product.name.ilike(f'%{escaped}%', escape='\\'), Product.description.ilike(f'%{escaped}%', escape='\\')))
    if category_id: query = query.where(Product.category_id == category_id)
    variant_price = select(func.min(func.coalesce(Variant.price_cents, Product.price_cents))).where(Variant.product_id == Product.id).correlate(Product).scalar_subquery()
    display_price = func.coalesce(variant_price, Product.price_cents)
    ordering = {'menor-preco': display_price.asc(), 'maior-preco': display_price.desc(), 'nome': Product.name.asc()}
    query = query.order_by(ordering.get(order, Product.created_at.desc()), Product.id.desc())
    # A published daily menu has at most 60 items. Show every category together,
    # so drinks and desserts are never hidden behind a page of main dishes.
    products = db.session.scalars(query).all()
    categories = db.session.scalars(select(Category).where(Category.active.is_(True)).order_by(Category.name)).all()
    menu = current_menu()
    hero_slides = menu_products(menu)[:8] if menu else products[:8]
    return render_template('site/home.html', sections=group_products(products),
        total=len(products), categories=ordered_categories(categories), q=q,
        category_id=category_id, order=order, hero_slides=hero_slides)

@site_bp.get('/produto/<int:product_id>')
def product(product_id):
    p = db.get_or_404(Product, product_id)
    if not p.public or not is_on_menu(p): abort(404)
    return render_template('site/product.html', product=p)

@site_bp.post('/produto/<int:product_id>/whatsapp')
def direct_whatsapp(product_id):
    # A direct selection still goes through delivery/payment details.
    return add(product_id)

@site_bp.post('/carrinho/adicionar/<int:product_id>')
def add(product_id):
    p = db.get_or_404(Product, product_id)
    try:
        add_item(p, request.form.get('variant_id'), request.form.get('quantity', '1'))
        session.pop('checkout_key', None)
        flash('Item adicionado ao seu pedido.', 'success')
        return redirect(url_for('site.cart'), 303)
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('site.product', product_id=p.id), 303)

@site_bp.get('/carrinho')
def cart():
    return render_cart()

@site_bp.post('/carrinho/atualizar')
def update_cart():
    key = request.form.get('key', '')
    cart = dict(session.get('cart', {}))
    if key not in cart: abort(400)
    try:
        qty = integer(request.form.get('quantity'), maximum=999)
        if qty == 0: cart.pop(key)
        else:
            pid, vid = map(int, key.split(':'))
            selection(db.session.get(Product, pid), vid, qty)
            cart[key] = qty
        session['cart'] = cart
        session.pop('checkout_key', None)
    except ValueError as e: flash(str(e), 'error')
    return redirect(url_for('site.cart'), 303)

def render_cart(status=200):
    items, errors, total = kitchen.kitchen_cart()
    return render_template('site/cart.html', items=items, errors=errors, total=total,
        checkout_key=kitchen.checkout_key(), payments=kitchen.PAYMENTS), status

@site_bp.post('/pedido/finalizar')
def checkout():
    row = kitchen.settings()
    responsible = kitchen.receiver(row)
    if not row.accepting_orders or not responsible:
        flash('O atendimento está indisponível neste momento. Tente novamente mais tarde.', 'error')
        return render_cart(400)
    submitted_key = request.form.get('submission_key', '')
    # Repeated submission of the same form retrieves the existing request.
    existing = db.session.scalar(select(OrderDetails).where(OrderDetails.submission_key == submitted_key)) if submitted_key else None
    if existing and session.get('last_order_token') == existing.token:
        return redirect(url_for('site.prepared_order', token=existing.token), 303)
    if not submitted_key or submitted_key != session.get('checkout_key'):
        flash('Seu pedido mudou ou esta página expirou. Revise os dados e tente novamente.', 'error')
        return render_cart(400)
    items, errors, total = kitchen.kitchen_cart()
    if errors or not items:
        flash('Revise os pratos e as quantidades antes de finalizar.', 'error')
        return render_cart(400)
    try:
        values = kitchen.validate_details(request.form, row, total)
        # Validate totals and quantities against current database values only.
        order = create_pending(responsible, items, values['name'], values['notes'], values['contact'], commit=False)
        details = OrderDetails(order=order, token=secrets.token_urlsafe(24), submission_key=submitted_key,
            message='', **{key:values[key] for key in ('fulfillment','address','reference','requested_time',
            'payment_method','cash_change_cents','delivery_fee_cents','total_cents','pickup_address')})
        db.session.add(details); db.session.flush()
        details.message = kitchen.order_message(order, details, items)
        db.session.commit()
        session['last_order_token'] = details.token
        session['cart'] = {}
        session.pop('checkout_key', None)
        return redirect(url_for('site.prepared_order', token=details.token), 303)
    except ValueError as e:
        db.session.rollback(); flash(str(e), 'error')
        return render_cart(400)
    except IntegrityError:
        db.session.rollback()
        existing = db.session.scalar(select(OrderDetails).where(OrderDetails.submission_key == submitted_key))
        if not existing: raise
        session['last_order_token'] = existing.token; session['cart'] = {}; session.pop('checkout_key', None)
        return redirect(url_for('site.prepared_order', token=existing.token), 303)

@site_bp.get('/pedido/<token>')
def prepared_order(token):
    if not re.fullmatch(r'[A-Za-z0-9_-]{32}', token): abort(404)
    details = db.session.scalar(select(OrderDetails).where(OrderDetails.token == token))
    if not details or session.get('last_order_token') != token: abort(404)
    order = details.order
    link = kitchen.whatsapp_link(order.seller, details.message) if order.seller.active else None
    return render_template('site/prepared.html', details=details, order=order, whatsapp_link=link, payments=kitchen.PAYMENTS)

@site_bp.get('/midia/<filename>')
def media(filename):
    if not re.fullmatch(r'[a-f0-9]{32}\.webp', filename): abort(404)
    p = db.session.scalar(select(Product).where(Product.image == filename))
    if not p:
        p = db.session.scalar(select(Product).join(ProductImage).where(ProductImage.filename == filename))
    if not p:
        p = db.session.scalar(select(Product).join(Variant).join(VariantImage).where(VariantImage.filename == filename))
    if not p: abort(404)
    if not p.public:
        from flask_login import current_user
        if not current_user.is_authenticated or not (current_user.is_superadmin or p.owner_id == current_user.id): abort(404)
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, max_age=3600)

@site_bp.get('/health')
def health():
    db.session.execute(select(1))
    return {'status':'ok', 'app':'Mana do Ceu', 'version':'1.9.0'}

def create_pending(seller, items, name='', notes='', contact=None, commit=True):
    from app.admin.management import product_cost
    order = PendingOrder(seller_id=seller.id, customer_name=name or 'Cliente não informado',
                         customer_phone=contact, notes=notes, total_cents=sum(i['total'] for i in items))
    for item in items:
        order.items.append(PendingOrderItem(product_id=item['product'].id,
            variant_id=item['variant'].id if item['variant'] else None,
            product_name=item['product'].name,
            variant_name=item['variant'].label if item['variant'] else None,
            quantity=item['quantity'], unit_price_cents=item['price'],
            unit_cost_cents=product_cost(item['product'])))
    db.session.add(order)
    if commit: db.session.commit()
    return order
