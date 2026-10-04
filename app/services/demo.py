import click
from sqlalchemy import select
from app.extensions import db
from app.models import User, Category, Product, Variant, DailyMenu, DailyMenuItem

def register_demo(app):
    @app.cli.command('cardapio-exemplo')
    def demo():
        """Cria exemplos opcionais. Nunca executado automaticamente."""
        db.create_all()
        owner = db.session.scalar(select(User).where(User.role == 'superadmin', User.active.is_(True)).order_by(User.id))
        if not owner: raise click.ClickException('Crie o administrador principal primeiro.')
        if db.session.scalar(select(Product.id).limit(1)): raise click.ClickException('O cardápio já possui pratos. Nenhum exemplo foi adicionado.')
        entries = [('Pratos do dia', 'Frango com gostinho de casa', 'EXEMPLO: arroz, feijão, frango grelhado e salada. Ajuste ingredientes, preços e disponibilidade para seu cardápio real.', 2200),
                   ('Pratos do dia', 'Carne de panela caprichada', 'EXEMPLO: arroz, feijão, carne de panela, legumes e salada. Atualize para o prato real antes de divulgar.', 2600),
                   ('Pratos do dia', 'Almoço do jardim', 'EXEMPLO: arroz, feijão, legumes e salada. Atualize para o prato real antes de divulgar.', 2100),
                   ('Bebidas', 'Suco natural do dia', 'EXEMPLO: porção individual. Informe sabor e volume reais.', 700),
                   ('Sobremesas', 'Pudim da casa', 'EXEMPLO: uma fatia individual. Informe ingredientes, tamanho e valor reais.', 900)]
        categories = {}
        for cat, name, description, price in entries:
            if cat not in categories:
                categories[cat] = db.session.scalar(select(Category).where(Category.name == cat)) or Category(name=cat, creator_id=owner.id)
                db.session.add(categories[cat])
            p = Product(owner=owner, category=categories[cat], name=name, description=description, price_cents=price, stock=20, active=True, featured=True)
            if cat == 'Pratos do dia' and name != 'Almoço do jardim': p.variants = [Variant(label='Média', price_cents=price, stock=20), Variant(label='Grande', price_cents=price+500, stock=15)]
            db.session.add(p)
        from app.services.daily_menu import today
        db.session.flush()
        menu=DailyMenu(date=today(),title='Cardápio de exemplo',message='DEMONSTRAÇÃO - ajuste pratos e preços antes de divulgar.',creator_id=owner.id,published=True)
        menu.items=[DailyMenuItem(product=p,position=i) for i,p in enumerate(db.session.scalars(select(Product).order_by(Product.id)).all())]
        db.session.add(menu);db.session.commit()
        click.echo('5 exemplos adicionados em Pratos do dia, Bebidas e Sobremesas. Substitua por itens, fotos e valores reais antes de divulgar.')
