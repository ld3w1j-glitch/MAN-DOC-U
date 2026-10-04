from datetime import date, datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.extensions import db
from app.models import DailyMenu, DailyMenuItem

def today():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).date()

def parse_date(value):
    try:
        result = date.fromisoformat(value)
        if not 2000 <= result.year <= 2100: raise ValueError
        return result
    except (TypeError, ValueError): raise ValueError('Escolha uma data válida para o cardápio.')

def current_menu():
    return db.session.scalar(select(DailyMenu).where(DailyMenu.date == today(), DailyMenu.published.is_(True)))

def current_product_ids():
    return select(DailyMenuItem.product_id).join(DailyMenu).where(DailyMenu.date == today(), DailyMenu.published.is_(True))

def is_on_menu(product):
    return bool(db.session.scalar(select(DailyMenuItem.id).join(DailyMenu).where(
        DailyMenuItem.product_id == product.id, DailyMenu.date == today(), DailyMenu.published.is_(True)).limit(1)))

def menu_products(menu):
    return [item.product for item in menu.items if item.product and item.product.public]
