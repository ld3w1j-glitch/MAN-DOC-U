from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session, send_file
from flask_login import current_user, login_required
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import Product, ProductImage, Variant, VariantImage, Category, User, PendingOrderItem
from app.core.security import require_owner, superadmin_required
from app.services import validation as v
from app.services.uploads import save_image, save_images, remove_image, save_profile_image, remove_profile_image, profile_image_path, profile_image_exists
from app.services.menu_categories import ordered_categories, group_products

admin_bp = Blueprint('admin', __name__)

@admin_bp.context_processor
def profile_photo_context():
    return {'has_profile_photo': current_user.is_authenticated and profile_image_exists(current_user.id)}

def scope(query):
    return query if current_user.is_superadmin else query.where(Product.owner_id == current_user.id)

@admin_bp.get('/')
@login_required
def dashboard():
    products = db.session.scalars(scope(select(Product)).order_by(Product.created_at.desc())).all()
    return render_template('admin/dashboard.html', products=products[:6], count=len(products),
        active=sum(p.active for p in products), stock=sum(p.available_stock for p in products),
        low=sum(p.available_stock <= 3 for p in products))

@admin_bp.get('/produtos')
@login_required
def products():
    q = request.args.get('q', '').strip()[:100]
    query = scope(select(Product))
    if q: query = query.where(Product.name.icontains(q, autoescape=True))
    page = db.paginate(query.order_by(Product.created_at.desc()), page=request.args.get('pagina', 1, type=int), per_page=20, error_out=False)
    return render_template('admin/products.html', page=page, q=q)

def product_form(product=None):
    categories = db.session.scalars(select(Category).where(Category.active.is_(True)).order_by(Category.name)).all()
    if product and product.category not in categories: categories.append(product.category)
    categories = ordered_categories(categories)
    if request.method == 'POST':
        new_files, old_files = [], []
        try:
            name = v.text(request.form.get('name'), 'Nome', 140)
            description = v.text(request.form.get('description'), 'Descrição', 5000, 5)
            price = v.money(request.form.get('price'))
            stock = v.integer(request.form.get('stock', '0'), 'Estoque')
            cat = db.session.get(Category, v.integer(request.form.get('category_id'), 'Categoria', 1))
            if not cat or (not cat.active and (not product or product.category_id != cat.id)):
                raise ValueError('Escolha uma categoria ativa.')

            labels = request.form.getlist('variant_label')
            ids = request.form.getlist('variant_id')
            prices = request.form.getlist('variant_price')
            stocks = request.form.getlist('variant_stock')
            image_files = request.files.getlist('variant_image')
            image_files += [None] * (len(labels) - len(image_files))
            if not (len(labels) == len(ids) == len(prices) == len(stocks)) or len(labels) > 50:
                raise ValueError('Lista de variações inválida. Use até 50 opções.')
            variants = []
            seen_labels, seen_ids = set(), set()
            for label, vid, amount, qty, image_file in zip(labels, ids, prices, stocks, image_files):
                label = v.text(label, 'Variação', 100)
                if label.casefold() in seen_labels: raise ValueError('Não repita o nome das variações.')
                seen_labels.add(label.casefold())
                variant = None
                if vid:
                    variant = db.session.get(Variant, v.integer(vid, 'Variação', 1))
                    if not product or not variant or variant.product_id != product.id or variant.id in seen_ids:
                        raise ValueError('A variação não pertence a este produto.')
                    seen_ids.add(variant.id)
                variants.append((variant, label, v.money(amount, True), v.integer(qty, 'Estoque da variação'), image_file))

            new_primary = save_image(request.files.get('image'))
            if new_primary: new_files.append(new_primary)
            new_gallery = save_images(request.files.getlist('gallery_images'), 8)
            new_files.extend(new_gallery)
            variant_uploads = []
            for _, _, _, _, image_file in variants:
                saved = save_image(image_file)
                variant_uploads.append(saved)
                if saved: new_files.append(saved)

            if product is None:
                product = Product(owner_id=current_user.id)
                db.session.add(product)
            old_primary = product.image
            remove_primary = request.form.get('remove_image') == 'on'
            next_primary = new_primary or (None if remove_primary else old_primary)

            remove_gallery_ids = set(request.form.getlist('remove_gallery_image'))
            kept_gallery = []
            for item in product.gallery:
                if str(item.id) in remove_gallery_ids: old_files.append(item.filename)
                else: kept_gallery.append(item)
            if (1 if next_primary else 0) + len(kept_gallery) + len(new_gallery) > 8:
                raise ValueError('Use no máximo 8 imagens no total para cada produto.')

            product.name, product.description, product.price_cents = name, description, price
            product.stock, product.category = (0 if variants else stock), cat
            product.active = request.form.get('active') == 'on'
            product.featured = request.form.get('featured') == 'on'
            product.image = next_primary
            if old_primary and old_primary != next_primary: old_files.append(old_primary)
            product.gallery = kept_gallery + [ProductImage(filename=filename) for filename in new_gallery]
            for index, item in enumerate(product.gallery): item.sort_order = index

            remove_variant_images = set(request.form.getlist('remove_variant_image'))
            existing_variants = list(product.variants)
            keep = []
            for (variant, label, amount, qty, _), uploaded in zip(variants, variant_uploads):
                variant = variant or Variant()
                variant.label, variant.price_cents, variant.stock = label, amount, qty
                if uploaded:
                    if variant.image: old_files.append(variant.image)
                    variant.image_record = VariantImage(filename=uploaded)
                elif variant.id and str(variant.id) in remove_variant_images and variant.image_record:
                    old_files.append(variant.image)
                    variant.image_record = None
                keep.append(variant)
            for removed in existing_variants:
                if removed not in keep and removed.image: old_files.append(removed.image)
            product.variants = keep
            db.session.commit()
            for filename in set(old_files): remove_image(filename)
            flash('Produto salvo com suas imagens e variações.', 'success')
            return redirect(url_for('admin.products'), 303)
        except (ValueError, IntegrityError) as e:
            db.session.rollback()
            for filename in set(new_files): remove_image(filename)
            flash(str(e) if isinstance(e, ValueError) else 'Não foi possível salvar. Confira os dados.', 'error')
            return render_template('admin/product_form.html', product=product if product and product.id else None, categories=categories), 400
    return render_template('admin/product_form.html', product=product, categories=categories)

@admin_bp.route('/produtos/novo', methods=['GET', 'POST'])
@login_required
def new_product(): return product_form()

@admin_bp.route('/produtos/<int:product_id>/editar', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    p = db.get_or_404(Product, product_id)
    require_owner(p)
    return product_form(p)

@admin_bp.post('/produtos/<int:product_id>/excluir')
@login_required
def delete_product(product_id):
    p = db.get_or_404(Product, product_id)
    require_owner(p)
    if db.session.scalar(select(PendingOrderItem.id).where(PendingOrderItem.product_id == p.id).limit(1)):
        p.active = False; db.session.commit()
        flash('Produto com histórico de pedidos: foi ocultado da vitrine para preservar os registros.', 'success')
        return redirect(url_for('admin.products'), 303)
    images = p.image_files + [variant.image for variant in p.variants if variant.image]
    db.session.delete(p)
    db.session.commit()
    for filename in set(images): remove_image(filename)
    flash('Produto excluído.', 'success')
    return redirect(url_for('admin.products'), 303)

@admin_bp.route('/categorias', methods=['GET', 'POST'])
@login_required
def categories():
    if request.method == 'POST':
        try:
            cat_id = request.form.get('category_id')
            cat = db.get_or_404(Category, v.integer(cat_id, 'Categoria', 1)) if cat_id else Category(creator_id=current_user.id)
            if cat_id and cat.creator_id != current_user.id and not current_user.is_superadmin: abort(403)
            cat.name = v.text(request.form.get('name'), 'Categoria', 70)
            cat.active = request.form.get('active') == 'on'
            db.session.add(cat)
            db.session.commit()
            flash('Categoria salva.', 'success')
        except (ValueError, IntegrityError) as e:
            db.session.rollback()
            flash(str(e) if isinstance(e, ValueError) else 'Já existe uma categoria com esse nome.', 'error')
        return redirect(url_for('admin.categories'), 303)
    cats = db.session.scalars(select(Category).order_by(Category.name)).all()
    return render_template('admin/categories.html', categories=ordered_categories(cats))

@admin_bp.post('/categorias/<int:category_id>/excluir')
@login_required
def delete_category(category_id):
    cat = db.get_or_404(Category, category_id)
    if cat.creator_id != current_user.id and not current_user.is_superadmin: abort(403)
    if cat.products: flash('Esta categoria tem produtos. Mova os produtos ou desative a categoria.', 'error')
    else:
        db.session.delete(cat); db.session.commit(); flash('Categoria excluída.', 'success')
    return redirect(url_for('admin.categories'), 303)

@admin_bp.get('/perfil/foto')
@login_required
def profile_photo():
    path = profile_image_path(current_user.id)
    if not path.is_file():
        abort(404)
    response = send_file(path, mimetype='image/webp', conditional=True, max_age=0)
    response.headers['Cache-Control'] = 'private, no-store'
    return response

@admin_bp.post('/perfil/foto')
@login_required
def update_profile_photo():
    try:
        save_profile_image(request.files.get('profile_image'), current_user.id)
        flash('Foto de perfil atualizada.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.profile'), 303)

@admin_bp.post('/perfil/foto/remover')
@login_required
def delete_profile_photo():
    remove_profile_image(current_user.id)
    flash('Foto de perfil removida.', 'success')
    return redirect(url_for('admin.profile'), 303)

@admin_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        try:
            name, email, phone = v.text(request.form.get('name'), 'Nome', 90), v.email(request.form.get('email')), v.phone(request.form.get('whatsapp'))
            pwd = request.form.get('new_password', '')
            if pwd:
                v.password(pwd)
                if not current_user.check_password(request.form.get('current_password', '')): raise ValueError('A senha atual está incorreta.')
            current_user.name, current_user.email, current_user.whatsapp = name, email, phone
            if pwd:
                current_user.set_password(pwd)
                current_user.session_version += 1
            db.session.commit()
            session['session_version'] = current_user.session_version
            flash('Perfil atualizado. Seus produtos já usam essas informações.', 'success')
            return redirect(url_for('admin.profile'), 303)
        except (ValueError, IntegrityError) as e:
            db.session.rollback()
            flash(str(e) if isinstance(e, ValueError) else 'Esse e-mail já está em uso.', 'error')
    return render_template('admin/profile.html')

@admin_bp.route('/administradores', methods=['GET', 'POST'])
@superadmin_required
def users():
    if request.method == 'POST':
        try:
            u = User(name=v.text(request.form.get('name'), 'Nome', 90), email=v.email(request.form.get('email')), whatsapp=v.phone(request.form.get('whatsapp')), role='admin', active=True)
            u.set_password(v.password(request.form.get('password')))
            db.session.add(u); db.session.commit()
            flash('Administrador criado. Ele pode entrar e cadastrar os próprios produtos.', 'success')
            return redirect(url_for('admin.users'), 303)
        except (ValueError, IntegrityError) as e:
            db.session.rollback()
            flash(str(e) if isinstance(e, ValueError) else 'Esse e-mail já está em uso.', 'error')
    users = db.session.scalars(select(User).order_by(User.created_at)).all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/administradores/<int:user_id>/editar', methods=['GET', 'POST'])
@superadmin_required
def edit_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id: return redirect(url_for('admin.profile'))
    if user.is_superadmin: abort(403)
    if request.method == 'POST':
        try:
            user.name = v.text(request.form.get('name'), 'Nome', 90)
            user.email = v.email(request.form.get('email'))
            user.whatsapp = v.phone(request.form.get('whatsapp'))
            user.active = request.form.get('active') == 'on'
            pwd = request.form.get('password', '')
            if pwd: user.set_password(v.password(pwd))
            user.session_version += 1
            db.session.commit()
            flash('Administrador atualizado.', 'success')
            return redirect(url_for('admin.users'), 303)
        except (ValueError, IntegrityError) as e:
            db.session.rollback()
            flash(str(e) if isinstance(e, ValueError) else 'Esse e-mail já está em uso.', 'error')
    return render_template('admin/user_edit.html', user=user)


@admin_bp.route('/atendimento', methods=['GET', 'POST'])
@superadmin_required
def restaurant_settings():
    from app.services.restaurant import settings
    from app.models import RestaurantSettings
    row = settings()
    users = db.session.scalars(select(User).where(User.active.is_(True)).order_by(User.name)).all()
    if request.method == 'POST':
        try:
            attendant_id = v.integer(request.form.get('attendant_id'), 'Responsável', 1)
            attendant = db.session.get(User, attendant_id)
            if not attendant or not attendant.active: raise ValueError('Escolha um responsável ativo.')
            delivery = request.form.get('delivery_enabled') == 'on'
            pickup = request.form.get('pickup_enabled') == 'on'
            if not delivery and not pickup: raise ValueError('Ative entrega, retirada ou ambas.')
            pickup_address = v.text(request.form.get('pickup_address'), 'Local de retirada', 240, 0)
            if pickup and not pickup_address: raise ValueError('Informe o endereço do local de retirada.')
            pix = request.form.get('pix_enabled') == 'on'
            card = request.form.get('card_enabled') == 'on'
            cash = request.form.get('cash_enabled') == 'on'
            if not any((pix, card, cash)): raise ValueError('Escolha ao menos uma forma de pagamento.')
            from app.admin.management import cost
            raw_fee = request.form.get('delivery_fee', '').strip()
            fee = cost(raw_fee) if raw_fee else None
            hours = v.text(request.form.get('hours_text'), 'Horários', 180, 0)
            notice = v.text(request.form.get('notice'), 'Aviso do cardápio', 240, 0)
            if row.id is None: row.id = 1
            row.attendant_id = attendant_id; row.delivery_enabled = delivery; row.pickup_enabled = pickup
            row.delivery_fee_cents = fee; row.pickup_address = pickup_address
            row.accepting_orders = request.form.get('accepting_orders') == 'on'
            row.pix_enabled = pix; row.card_enabled = card; row.cash_enabled = cash
            row.hours_text = hours; row.notice = notice
            db.session.add(row); db.session.commit()
            flash('Atendimento e opções de pedido atualizados.', 'success')
            return redirect(url_for('admin.restaurant_settings'), 303)
        except ValueError as exc:
            db.session.rollback(); flash(str(exc), 'error')
            return render_template('admin/restaurant_settings.html', settings=row, users=users), 400
    return render_template('admin/restaurant_settings.html', settings=row, users=users)


@admin_bp.route('/cardapio-dia', methods=['GET', 'POST'])
@superadmin_required
def daily_menu_editor():
    from app.models import DailyMenu, DailyMenuItem
    from app.services.daily_menu import today, parse_date, menu_products
    from app.services.status_image import creative_pages
    from datetime import timedelta
    try:
        day = parse_date(request.form.get('date') if request.method == 'POST' else request.args.get('data', today().isoformat()))
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('admin.daily_menu_editor'), 303)
    menu = db.session.scalar(select(DailyMenu).where(DailyMenu.date == day))
    products = db.session.scalars(select(Product).join(Product.owner).join(Product.category).where(
        Product.active.is_(True), User.active.is_(True), Category.active.is_(True)).order_by(Category.name, Product.name)).all()
    if request.method == 'POST':
        try:
            title = v.text(request.form.get('title'), 'Título do cardápio', 90)
            message = v.text(request.form.get('message'), 'Mensagem do dia', 180, 0)
            selected = list(dict.fromkeys(v.integer(item, 'Prato', 1) for item in request.form.getlist('product_id')))
            allowed = {p.id for p in products}
            if any(pid not in allowed for pid in selected):
                raise ValueError('Selecione apenas pratos ativos do cardápio.')
            if len(selected) > 60:
                raise ValueError('Selecione até 60 pratos por dia.')
            publish = request.form.get('action') == 'publish'
            if publish and not selected:
                raise ValueError('Selecione ao menos um prato para publicar o cardápio.')
            if request.form.get('action') not in ('draft', 'publish'):
                raise ValueError('Ação inválida.')
            menu = menu or DailyMenu(date=day, creator_id=current_user.id)
            menu.title = title
            menu.message = message
            menu.published = publish
            existing = {item.product_id: item for item in menu.items}
            menu.items = [existing.get(pid) or DailyMenuItem(product_id=pid) for pid in selected]
            for i, item in enumerate(menu.items):
                item.position = i
            db.session.add(menu)
            db.session.commit()
            flash('Cardápio publicado. Os criativos do dia estão prontos para baixar.' if publish else 'Rascunho salvo. Os clientes ainda não veem este cardápio.', 'success')
            return redirect(url_for('admin.daily_menu_editor', data=day.isoformat(), gerado='1' if publish else ''), 303)
        except (ValueError, IntegrityError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else 'Outro administrador alterou esta data. Atualize e tente novamente.', 'error')
    menu_list = menu_products(menu) if menu else []
    return render_template('admin/daily_menu.html',
        menu=menu,
        day=day,
        sections=group_products(products),
        selected={item.product_id for item in menu.items} if menu else set(),
        previous=(day - timedelta(days=1)).isoformat(),
        following=(day + timedelta(days=1)).isoformat(),
        status_count=creative_pages(len(menu_list), 'status') if menu else 0,
        post_count=creative_pages(len(menu_list), 'post') if menu else 0)


@admin_bp.get('/cardapio-dia/<day_string>/status/<int:page_number>.png')
@superadmin_required
def daily_status_png(day_string, page_number):
    from io import BytesIO
    from app.models import DailyMenu
    from app.services.daily_menu import parse_date, menu_products
    from app.services.restaurant import settings
    from app.services.status_image import build_status_images
    try:
        day = parse_date(day_string)
    except ValueError:
        abort(404)
    menu = db.session.scalar(select(DailyMenu).where(DailyMenu.date == day))
    if not menu:
        abort(404)
    try:
        images = build_status_images(menu, menu_products(menu), settings())
    except ValueError:
        abort(400)
    if not 1 <= page_number <= len(images):
        abort(404)
    response = send_file(BytesIO(images[page_number - 1]), mimetype='image/png', as_attachment=request.args.get('baixar') == '1',
        download_name=f'Mana_Cardapio_Status_{day.isoformat()}_{page_number:02}.png')
    response.headers['Cache-Control'] = 'no-store'
    return response


@admin_bp.get('/cardapio-dia/<day_string>/status.zip')
@superadmin_required
def daily_status_zip(day_string):
    from io import BytesIO
    from zipfile import ZipFile, ZIP_DEFLATED
    from app.models import DailyMenu
    from app.services.daily_menu import parse_date, menu_products
    from app.services.restaurant import settings
    from app.services.status_image import build_status_images
    try:
        day = parse_date(day_string)
    except ValueError:
        abort(404)
    menu = db.session.scalar(select(DailyMenu).where(DailyMenu.date == day))
    if not menu:
        abort(404)
    try:
        images = build_status_images(menu, menu_products(menu), settings())
    except ValueError:
        abort(400)
    bio = BytesIO()
    with ZipFile(bio, 'w', ZIP_DEFLATED) as z:
        for i, im in enumerate(images):
            z.writestr(f'Mana_Cardapio_Status_{day.isoformat()}_{i + 1:02}.png', im)
    bio.seek(0)
    return send_file(bio, mimetype='application/zip', as_attachment=True, download_name=f'Mana_Status_{day.isoformat()}.zip')


@admin_bp.get('/cardapio-dia/<day_string>/post/<int:page_number>.png')
@superadmin_required
def daily_post_png(day_string, page_number):
    from io import BytesIO
    from app.models import DailyMenu
    from app.services.daily_menu import parse_date, menu_products
    from app.services.restaurant import settings
    from app.services.status_image import build_post_images
    try:
        day = parse_date(day_string)
    except ValueError:
        abort(404)
    menu = db.session.scalar(select(DailyMenu).where(DailyMenu.date == day))
    if not menu:
        abort(404)
    try:
        images = build_post_images(menu, menu_products(menu), settings())
    except ValueError:
        abort(400)
    if not 1 <= page_number <= len(images):
        abort(404)
    response = send_file(BytesIO(images[page_number - 1]), mimetype='image/png', as_attachment=request.args.get('baixar') == '1',
        download_name=f'Mana_Cardapio_Post_{day.isoformat()}_{page_number:02}.png')
    response.headers['Cache-Control'] = 'no-store'
    return response


@admin_bp.get('/cardapio-dia/<day_string>/post.zip')
@superadmin_required
def daily_post_zip(day_string):
    from io import BytesIO
    from zipfile import ZipFile, ZIP_DEFLATED
    from app.models import DailyMenu
    from app.services.daily_menu import parse_date, menu_products
    from app.services.restaurant import settings
    from app.services.status_image import build_post_images
    try:
        day = parse_date(day_string)
    except ValueError:
        abort(404)
    menu = db.session.scalar(select(DailyMenu).where(DailyMenu.date == day))
    if not menu:
        abort(404)
    try:
        images = build_post_images(menu, menu_products(menu), settings())
    except ValueError:
        abort(400)
    bio = BytesIO()
    with ZipFile(bio, 'w', ZIP_DEFLATED) as z:
        for i, im in enumerate(images):
            z.writestr(f'Mana_Cardapio_Post_{day.isoformat()}_{i + 1:02}.png', im)
    bio.seek(0)
    return send_file(bio, mimetype='application/zip', as_attachment=True, download_name=f'Mana_Posts_{day.isoformat()}.zip')
