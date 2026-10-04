import secrets
from urllib.parse import urlencode
from flask import session
from sqlalchemy import select
from app.extensions import db
from app.models import RestaurantSettings, User
from app.services.cart import resolve_cart
from app.services.validation import text, phone, money, brl

PAYMENTS = {'pix': 'Pix', 'card': 'Cartão na entrega / retirada', 'cash': 'Dinheiro'}

def settings():
    # Read-only requests never create settings or example products.
    row = db.session.get(RestaurantSettings, 1)
    if row is None:
        row = RestaurantSettings(accepting_orders=True, delivery_enabled=True, pickup_enabled=True,
            pix_enabled=True, card_enabled=True, cash_enabled=True, pickup_address='', hours_text='', notice='')
    return row

def receiver(row=None):
    row = row or settings()
    if row.attendant_id:
        return row.attendant if row.attendant and row.attendant.active else None
    return db.session.scalar(select(User).where(User.active.is_(True), User.role == 'superadmin').order_by(User.id).limit(1))

def kitchen_cart():
    groups, errors = resolve_cart()
    items = [item for group in groups for item in group['items']]
    return items, errors, sum(item['total'] for item in items)

def checkout_key():
    if not session.get('checkout_key'):
        session['checkout_key'] = secrets.token_urlsafe(24)
    return session['checkout_key']

def validate_details(form, row, subtotal):
    name = text(form.get('name'), 'Seu nome', 80, 2)
    contact = phone(form.get('phone'))
    mode = form.get('fulfillment')
    if mode not in ('delivery', 'pickup') or (mode == 'delivery' and not row.delivery_enabled) or (mode == 'pickup' and not row.pickup_enabled):
        raise ValueError('Escolha uma modalidade de entrega disponível.')
    address = ''
    if mode == 'delivery':
        street = text(form.get('street'), 'Rua', 140)
        number = text(form.get('number'), 'Número ou S/N', 20)
        district = text(form.get('district'), 'Bairro', 80)
        city = text(form.get('city'), 'Cidade', 80)
        state = text(form.get('state'), 'UF', 2, 2).upper()
        if state not in ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'):
            raise ValueError('Informe uma UF válida.')
        complement = text(form.get('complement'), 'Complemento', 100, 0)
        postcode = text(form.get('postcode'), 'CEP', 9, 0)
        import re
        if postcode and not re.fullmatch(r'\d{5}-?\d{3}', postcode): raise ValueError('CEP inválido. Use 8 números.')
        address = f'{street}, {number} - {district}, {city}/{state}'
        if complement: address += f' | Complemento: {complement}'
        if postcode: address += f' | CEP: {postcode}'
    elif not row.pickup_address:
        raise ValueError('O local de retirada precisa ser confirmado pelo atendimento. Escolha entrega ou aguarde a configuração da retirada.')
    payment = form.get('payment_method')
    allowed = {'pix': row.pix_enabled, 'card': row.card_enabled, 'cash': row.cash_enabled}
    if payment not in allowed or not allowed[payment]: raise ValueError('Escolha uma forma de pagamento disponível.')
    fee = row.delivery_fee_cents if mode == 'delivery' else 0
    total = subtotal + (fee or 0)
    change = None
    if payment == 'cash' and form.get('change_for', '').strip():
        change = money(form.get('change_for'))
        if change < total: raise ValueError('O valor para troco deve cobrir o total conhecido do pedido.')
    return dict(name=name, contact=contact, fulfillment=mode, address=address,
        reference=text(form.get('reference'), 'Referência', 160, 0) if mode == 'delivery' else '',
        requested_time=text(form.get('requested_time'), 'Horário desejado', 100, 0) or 'O quanto antes',
        payment_method=payment, cash_change_cents=change, delivery_fee_cents=fee, total_cents=total,
        pickup_address=row.pickup_address if mode == 'pickup' else '',
        notes=text(form.get('notes'), 'Observações', 500, 0))

def order_message(order, details, items):
    lines = [f'Olá! Quero fazer um pedido na Maná do Céu. Pedido #{order.id:05d}', '', '*PRATOS*']
    for item in items:
        option = f" ({item['variant'].label})" if item['variant'] else ''
        lines += [f"{item['quantity']} × {item['product'].name}{option} [MC-{item['product'].id:05d}]",
                  f"Unitário: {brl(item['price'])} | Subtotal: {brl(item['total'])}"]
    subtotal = sum(item['total'] for item in items)
    lines += ['', '*VALORES*', f'Pratos: {brl(subtotal)}',
        'Entrega: a confirmar' if details.delivery_fee_cents is None else f'Taxa de entrega: {brl(details.delivery_fee_cents)}',
        f"{'Subtotal conhecido' if details.delivery_fee_cents is None else 'Total'}: {brl(details.total_cents)}",
        '', '*CLIENTE*', f'Nome: {order.customer_name}', f'WhatsApp: +{order.customer_phone}', '', '*RECEBIMENTO*']
    if details.fulfillment == 'delivery':
        lines += ['Entrega no endereço:', details.address]
        if details.reference: lines.append('Referência: '+details.reference)
    else: lines += ['Retirada no local: '+details.pickup_address]
    lines += ['Horário desejado: '+details.requested_time+' (a confirmar)', '', '*PAGAMENTO*', PAYMENTS[details.payment_method]]
    if details.payment_method == 'cash':
        lines.append('Troco para: '+brl(details.cash_change_cents) if details.cash_change_cents else 'Sem troco solicitado')
    if details.payment_method == 'pix': lines.append('Por favor, confirme a chave Pix e o valor final.')
    if order.notes: lines += ['', '*OBSERVAÇÕES*', order.notes]
    lines += ['', 'Aguardo a confirmação da disponibilidade, do prazo e do valor final. Pagamento ainda não realizado pelo site.']
    return '\n'.join(lines)

def whatsapp_link(attendant, message):
    return 'https://wa.me/' + attendant.whatsapp + '?' + urlencode({'text': message})
