from collections import OrderedDict
from flask import session
from app.extensions import db
from app.models import Product, Variant
from app.services.validation import integer, brl

MAX_LINES = 30

def selection(product, variant_id, quantity):
    if not product or not product.public: raise ValueError('Este produto não está mais disponível.')
    from app.services.daily_menu import is_on_menu
    if not is_on_menu(product): raise ValueError('Este prato não está no cardápio de hoje. Escolha uma opção disponível.')
    qty = integer(quantity, minimum=1, maximum=999)
    variant = None
    if product.variants:
        vid = integer(variant_id, 'Variação', 1)
        variant = db.session.get(Variant, vid)
        if not variant or variant.product_id != product.id: raise ValueError('Escolha uma variação válida para este produto.')
    elif variant_id not in (None, '', '0', 0):
        raise ValueError('Este produto não possui essa variação.')
    stock = variant.stock if variant else product.stock
    if qty > stock: raise ValueError(f'{product.name}: há apenas {stock} unidade(s) disponível(is).')
    cents = variant.price_cents if variant and variant.price_cents else product.price_cents
    return dict(product=product, variant=variant, quantity=qty, price=cents, total=cents * qty, stock=stock,
                key=f'{product.id}:{variant.id if variant else 0}')

def add_item(product, variant_id, quantity):
    item = selection(product, variant_id, quantity)
    cart = dict(session.get('cart', {}))
    old = cart.get(item['key'], 0)
    item = selection(product, variant_id, old + item['quantity'])
    if item['key'] not in cart and len(cart) >= MAX_LINES: raise ValueError('Seu pedido pode ter até 30 itens diferentes.')
    cart[item['key']] = item['quantity']
    session['cart'] = cart

def resolve_cart():
    groups = OrderedDict()
    errors = []
    for key, quantity in session.get('cart', {}).items():
        product = None
        try:
            pid, vid = map(int, key.split(':'))
            product = db.session.get(Product, pid)
            item = selection(product, vid, quantity)
            seller = product.owner
            group = groups.setdefault(seller.id, dict(seller=seller, items=[], total=0))
            group['items'].append(item)
            group['total'] += item['total']
        except (ValueError, TypeError):
            errors.append(dict(key=key, name=product.name if product else 'Produto removido'))
    return list(groups.values()), errors
