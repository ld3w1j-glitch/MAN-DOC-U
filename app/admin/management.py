"""Pedidos sujeitos à aprovação e custos por vendedor, adaptados do estudo Chapa do Bairro."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime
from math import floor, isfinite
from sqlalchemy import text as sql_text
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import select
from app.extensions import db
from app.models import Supply, ProductSupply, Product, PendingOrder, Variant, Expense, now
from app.services.validation import text, integer, brl

management_bp = Blueprint('management', __name__)

def quantity(value, label, positive=False):
    try:
        n = float(Decimal(str(value or '0').replace(',', '.')))
        if not isfinite(n) or n > 1000000 or (n <= 0 if positive else n < 0): raise ValueError
        return n
    except (InvalidOperation, ValueError):
        raise ValueError(f'{label}: informe uma quantidade válida.')

def cost(value):
    try:
        n = Decimal(str(value or '0').replace('R$', '').strip().replace(',', '.'))
        if not n.is_finite() or n < 0 or n > 9999999 or n.as_tuple().exponent < -2: raise ValueError
        return int(n * 100)
    except (InvalidOperation, ValueError):
        raise ValueError('Custo: informe um valor em reais com até duas casas decimais.')

def product_cost(product):
    lines = db.session.scalars(select(ProductSupply).where(ProductSupply.product_id == product.id)).all()
    value = sum((Decimal(str(line.quantity)) * Decimal(line.supply.cost_cents) *
                (1 + Decimal(str(line.supply.waste_percent)) / 100) for line in lines), Decimal(0))
    return int(value.quantize(Decimal('1'), rounding=ROUND_HALF_UP))

@management_bp.route('/insumos', methods=['GET', 'POST'])
@login_required
def supplies():
    if request.method == 'POST':
        try:
            sid = request.form.get('id')
            supply = db.session.get(Supply, integer(sid, 'Insumo', 1)) if sid else Supply(owner_id=current_user.id)
            if supply is None or supply.owner_id != current_user.id: abort(403)
            supply.name = text(request.form.get('name'), 'Nome', 120)
            supply.kind = request.form.get('kind')
            if supply.kind not in ('insumo', 'embalagem', 'outro'): raise ValueError('Selecione o tipo de custo.')
            supply.unit = text(request.form.get('unit'), 'Unidade', 20)
            supply.stock = quantity(request.form.get('stock'), 'Estoque')
            supply.minimum = quantity(request.form.get('minimum'), 'Estoque mínimo')
            supply.cost_cents = cost(request.form.get('cost'))
            supply.waste_percent = quantity(request.form.get('waste'), 'Perda')
            if supply.waste_percent > 100: raise ValueError('Perda: máximo de 100%.')
            db.session.add(supply); db.session.commit()
            flash('Custo salvo.', 'success')
            return redirect(url_for('management.supplies'), 303)
        except ValueError as exc:
            db.session.rollback(); flash(str(exc), 'error')
    rows = db.session.scalars(select(Supply).where(Supply.owner_id == current_user.id).order_by(Supply.kind, Supply.name)).all()
    return render_template('admin/supplies.html', supplies=rows, brl=brl)

@management_bp.post('/insumos/<int:supply_id>/excluir')
@login_required
def delete_supply(supply_id):
    supply = db.get_or_404(Supply, supply_id)
    if supply.owner_id != current_user.id: abort(403)
    if db.session.scalar(select(ProductSupply.id).where(ProductSupply.supply_id == supply_id).limit(1)):
        flash('Retire esse custo das fichas técnicas antes de excluir.', 'error')
    else:
        db.session.delete(supply); db.session.commit(); flash('Custo excluído.', 'success')
    return redirect(url_for('management.supplies'), 303)

@management_bp.route('/despesas', methods=['GET', 'POST'])
@login_required
def expenses():
    if request.method == 'POST':
        try:
            amount = cost(request.form.get('amount'))
            if amount <= 0: raise ValueError('A despesa deve ter valor positivo.')
            db.session.add(Expense(owner_id=current_user.id,
                description=text(request.form.get('description'), 'Descrição', 150),
                category=text(request.form.get('category'), 'Categoria', 60), amount_cents=amount))
            db.session.commit(); flash('Despesa registrada.', 'success')
            return redirect(url_for('management.expenses'), 303)
        except ValueError as exc:
            db.session.rollback(); flash(str(exc), 'error')
    rows = db.session.scalars(select(Expense).where(Expense.owner_id == current_user.id).order_by(Expense.incurred_at.desc()).limit(200)).all()
    return render_template('admin/expenses.html', expenses=rows)

@management_bp.post('/despesas/<int:expense_id>/excluir')
@login_required
def delete_expense(expense_id):
    item = db.get_or_404(Expense, expense_id)
    if item.owner_id != current_user.id: abort(403)
    db.session.delete(item); db.session.commit()
    return redirect(url_for('management.expenses'), 303)

@management_bp.get('/resultado')
@login_required
def result():
    today = now()
    try:
        year = integer(request.args.get('ano', str(today.year)), 'Ano', 2000, 2100)
        month = integer(request.args.get('mes', str(today.month)), 'Mês', 1, 12)
    except ValueError: abort(400)
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    orders = db.session.scalars(select(PendingOrder).where(PendingOrder.seller_id == current_user.id,
        PendingOrder.status == 'aprovado', PendingOrder.decided_at >= start, PendingOrder.decided_at < end)).all()
    expenses = db.session.scalars(select(Expense).where(Expense.owner_id == current_user.id,
        Expense.incurred_at >= start, Expense.incurred_at < end)).all()
    revenue = sum(o.total_cents for o in orders)
    direct_cost = sum(i.subtotal_cost_cents for o in orders for i in o.items)
    overhead = sum(e.amount_cents for e in expenses)
    return render_template('admin/result.html', orders=orders, expenses=expenses, revenue=revenue,
        direct_cost=direct_cost, overhead=overhead, net=revenue-direct_cost-overhead, year=year, month=month)

@management_bp.route('/ficha/<int:product_id>', methods=['GET', 'POST'])
@login_required
def recipe(product_id):
    product = db.get_or_404(Product, product_id)
    if product.owner_id != current_user.id: abort(403)
    if request.method == 'POST':
        try:
            supply = db.session.get(Supply, integer(request.form.get('supply_id'), 'Insumo', 1))
            if not supply or supply.owner_id != current_user.id: abort(403)
            qty = quantity(request.form.get('quantity'), 'Quantidade usada', True)
            line = db.session.scalar(select(ProductSupply).where(ProductSupply.product_id == product.id, ProductSupply.supply_id == supply.id))
            if line: line.quantity = qty
            else: db.session.add(ProductSupply(product_id=product.id, supply_id=supply.id, quantity=qty))
            db.session.commit(); flash('Ficha técnica atualizada.', 'success')
            return redirect(url_for('management.recipe', product_id=product.id), 303)
        except ValueError as exc:
            db.session.rollback(); flash(str(exc), 'error')
    lines = db.session.scalars(select(ProductSupply).where(ProductSupply.product_id == product.id)).all()
    supplies = db.session.scalars(select(Supply).where(Supply.owner_id == current_user.id).order_by(Supply.name)).all()
    return render_template('admin/recipe.html', product=product, lines=lines, supplies=supplies,
                           unit_cost=product_cost(product), brl=brl)

@management_bp.post('/ficha/<int:product_id>/item/<int:line_id>/excluir')
@login_required
def delete_recipe_item(product_id, line_id):
    product = db.get_or_404(Product, product_id)
    if product.owner_id != current_user.id: abort(403)
    line = db.get_or_404(ProductSupply, line_id)
    if line.product_id != product.id: abort(403)
    db.session.delete(line); db.session.commit()
    return redirect(url_for('management.recipe', product_id=product.id), 303)

@management_bp.get('/estudo')
@login_required
def study():
    products = db.session.scalars(select(Product).where(Product.owner_id == current_user.id).order_by(Product.name)).all()
    count = min(request.args.get('quantidade', 10, type=int), 100000)
    count = max(1, count)
    rows = []
    for product in products:
        lines = db.session.scalars(select(ProductSupply).where(ProductSupply.product_id == product.id)).all()
        unit_cost = product_cost(product)
        capacity = min((floor(line.supply.stock / line.quantity) for line in lines if line.quantity > 0), default=product.available_stock)
        capacity = min(capacity, product.available_stock)
        price = product.display_price
        rows.append(dict(product=product, cost=unit_cost, price=price, margin=price-unit_cost,
                         capacity=capacity, count=count, projected=(price-unit_cost)*count,
                         feasible=min(count, capacity), tracked=bool(lines)))
    return render_template('admin/study.html', rows=rows, count=count, brl=brl)

@management_bp.get('/pedidos')
@login_required
def orders():
    query = select(PendingOrder)
    if not current_user.is_superadmin: query = query.where(PendingOrder.seller_id == current_user.id)
    rows = db.session.scalars(query.order_by(PendingOrder.created_at.desc()).limit(200)).all()
    return render_template('admin/orders.html', orders=rows, brl=brl)

@management_bp.post('/pedidos/<int:order_id>/<decision>')
@login_required
def decide(order_id, decision):
    if decision not in ('aprovar', 'recusar'): abort(404)
    # BEGIN IMMEDIATE serializes approvals in SQLite, preventing overselling.
    db.session.rollback()
    if db.engine.dialect.name == 'sqlite': db.session.execute(sql_text('BEGIN IMMEDIATE'))
    order = db.get_or_404(PendingOrder, order_id)
    if order.seller_id != current_user.id and not current_user.is_superadmin: abort(403)
    if order.status != 'pendente':
        flash('Este pedido já foi analisado.', 'error')
        return redirect(url_for('management.orders'), 303)
    if decision == 'aprovar':
        consumption = {}
        for item in order.items:
            product = db.session.get(Product, item.product_id)
            variant = db.session.get(Variant, item.variant_id) if item.variant_id else None
            if not product or not product.public or (item.variant_id and (not variant or variant.product_id != product.id)) or (not item.variant_id and product.variants):
                flash('Um produto não está mais disponível. Revise o pedido.', 'error')
                return redirect(url_for('management.orders'), 303)
            stock = variant.stock if variant else product.stock
            if stock < item.quantity:
                flash(f'Estoque insuficiente para {item.product_name}.', 'error')
                return redirect(url_for('management.orders'), 303)
            for line in db.session.scalars(select(ProductSupply).where(ProductSupply.product_id == item.product_id)):
                sid = line.supply_id
                if sid not in consumption: consumption[sid] = [line.supply, 0]
                consumption[sid][1] += line.quantity * item.quantity
        for supply, used in consumption.values():
            if supply.stock + 0.000001 < used:
                flash(f'Estoque insuficiente de {supply.name} para aprovar o pedido.', 'error')
                return redirect(url_for('management.orders'), 303)
        for item in order.items:
            product = db.session.get(Product, item.product_id)
            variant = db.session.get(Variant, item.variant_id) if item.variant_id else None
            if variant: variant.stock -= item.quantity
            else: product.stock -= item.quantity
        for supply, used in consumption.values(): supply.stock = max(0, round(supply.stock-used, 6))
        order.status = 'aprovado'
    else: order.status = 'recusado'
    order.decided_at = now()
    db.session.commit()
    flash('Pedido atualizado. Avise o cliente pelo WhatsApp, se houver contato.', 'success')
    return redirect(url_for('management.orders'), 303)
