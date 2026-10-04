"""Categorias do cardápio, sem alterar a classificação dos itens existentes."""
from sqlalchemy import select
from app.extensions import db
from app.models import Category, User

DEFAULT_CATEGORIES = ('Pratos do dia', 'Bebidas', 'Sobremesas')
SECTION_DETAILS = {
    'pratos do dia': ('dish', 'Escolha seu almoço de hoje.'),
    'bebidas': ('drink', 'Para acompanhar o seu pedido.'),
    'sobremesas': ('dessert', 'Um doce para finalizar.'),
}


def normalized(name):
    return ' '.join(name.split()).casefold()


def category_order(category):
    name = normalized(category.name)
    priorities = [normalized(value) for value in DEFAULT_CATEGORIES]
    return (priorities.index(name) if name in priorities else len(priorities), name)


def ordered_categories(categories):
    return sorted(categories, key=category_order)


def group_products(products):
    """Preserva a ordenação dos itens dentro de cada categoria."""
    sections = {}
    for product in products:
        category = product.category
        if category.id not in sections:
            icon, description = SECTION_DETAILS.get(normalized(category.name), ('tag', ''))
            sections[category.id] = {
                'category': category, 'products': [], 'icon': icon,
                'description': description,
            }
        sections[category.id]['products'].append(product)
    return sorted(sections.values(), key=lambda section: category_order(section['category']))


def ensure_default_categories(owner_id=None):
    """Executado na inicialização; preserva nomes, categorias e estados existentes."""
    if owner_id is None:
        owner_id = db.session.scalar(select(User.id).where(User.role == 'superadmin').order_by(User.id).limit(1))
    if owner_id is None:
        return
    existing = {normalized(category.name) for category in db.session.scalars(select(Category))}
    for name in DEFAULT_CATEGORIES:
        if normalized(name) not in existing:
            db.session.add(Category(name=name, creator_id=owner_id))
