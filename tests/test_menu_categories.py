import re
from sqlalchemy import select
from app.extensions import db
from app.models import Category, Product, DailyMenu, DailyMenuItem, User


def categorized_menu(app, extra_mains=0):
    assert app.test_cli_runner().invoke(args=['init-db']).exit_code == 0
    with app.app_context():
        categories = {cat.name: cat for cat in db.session.scalars(select(Category))}
        main = db.session.get(Product, 1)
        drink = db.session.get(Product, 2)
        main.category = categories['Pratos do dia']
        drink.category = categories['Bebidas']
        dessert = Product(name='Pudim da casa', description='Fatia individual com calda.',
            price_cents=900, stock=10, owner=main.owner, category=categories['Sobremesas'])
        db.session.add(dessert)
        menu = db.session.scalar(select(DailyMenu))
        menu.items.append(DailyMenuItem(product=dessert, position=2))
        for i in range(extra_mains):
            product = Product(name=f'Almoço {i:02}', description='Arroz, feijão e salada.',
                price_cents=2000+i, stock=10, owner=main.owner, category=main.category)
            menu.items.append(DailyMenuItem(product=product, position=i+3))
        db.session.commit()
        return {name: categories[name].id for name in ('Pratos do dia', 'Bebidas', 'Sobremesas')}


def section(html, category_id):
    match = re.search(r'<section class="mana-menu-section" data-menu-category="' + str(category_id) + r'".*?</section>', html, re.S)
    assert match is not None
    return match.group()


def test_all_three_sections_remain_visible_with_many_main_dishes(app, client):
    ids = categorized_menu(app, extra_mains=13)
    response = client.get('/')
    assert response.status_code == 200
    html = response.text
    main = section(html, ids['Pratos do dia'])
    drinks = section(html, ids['Bebidas'])
    desserts = section(html, ids['Sobremesas'])
    assert main.count('<article class="mana-dish">') == 14
    assert 'Organizador A' in main and 'Copo B' not in main and 'Pudim da casa' not in main
    assert 'Copo B' in drinks and 'Organizador A' not in drinks
    assert 'Pudim da casa' in desserts and 'Copo B' not in desserts
    assert html.index(main) < html.index(drinks) < html.index(desserts)


def test_category_filter_search_and_sort_stay_in_the_selected_category(app, client):
    ids = categorized_menu(app)
    html = client.get(f"/?categoria={ids['Bebidas']}&q=Copo&ordem=menor-preco").text
    assert 'Copo B' in section(html, ids['Bebidas'])
    assert 'Organizador A' not in html and 'Pudim da casa' not in html
    search_form = re.search(r'<form role="search".*?</form>', html, re.S).group()
    assert f'name="categoria" value="{ids["Bebidas"]}"' in search_form
    assert 'name="ordem" value="menor-preco"' in search_form
    assert f'data-menu-category="{ids["Sobremesas"]}"' not in client.get('/?q=Copo').text
    assert 'Não encontramos itens para esta seleção.' in client.get(f"/?categoria={ids['Bebidas']}&q=Pudim").text


def test_daily_selection_is_grouped_and_does_not_offer_unselected_dessert(app, client, login):
    ids = categorized_menu(app)
    login('root@example.test')
    html = client.get('/admin/cardapio-dia').text
    groups = re.findall(r'<fieldset class="mana-daily-products".*?</fieldset>', html, re.S)
    assert len(groups) == 3
    assert 'Pratos do dia' in groups[0] and 'Organizador A' in groups[0] and 'Copo B' not in groups[0]
    assert 'Bebidas' in groups[1] and 'Copo B' in groups[1]
    assert 'Sobremesas' in groups[2] and 'Pudim da casa' in groups[2]
    with app.app_context():
        day = db.session.scalar(select(DailyMenu)).date.isoformat()
        dessert_id = db.session.scalar(select(Product.id).where(Product.name == 'Pudim da casa'))
    response = client.post('/admin/cardapio-dia', data={
        'date': day, 'title': 'Cardápio de hoje', 'action': 'publish', 'product_id': ['1', '2'],
    })
    assert response.status_code == 303
    assert f'data-menu-category="{ids["Sobremesas"]}"' not in client.get('/').text
    assert client.get(f'/produto/{dessert_id}').status_code == 404


def test_default_categories_do_not_duplicate_or_reactivate_existing_data(app):
    with app.app_context():
        existing = Category(name='BEBIDAS', creator_id=2, active=False)
        db.session.add(existing)
        db.session.commit()
        existing_id = existing.id
        original_category = db.session.get(Product, 1).category_id
    runner = app.test_cli_runner()
    assert runner.invoke(args=['init-db']).exit_code == 0
    assert runner.invoke(args=['init-db']).exit_code == 0
    with app.app_context():
        categories = db.session.scalars(select(Category)).all()
        assert len(categories) == 4  # Casa + three defaults, including existing BEBIDAS.
        existing = db.session.get(Category, existing_id)
        assert existing.name == 'BEBIDAS' and not existing.active and existing.creator_id == 2
        assert db.session.get(Product, 1).category_id == original_category
        assert db.session.get(User, 2).email == 'a@example.test'


def test_first_admin_gets_default_categories_and_optional_demo(app, client):
    with app.app_context():
        db.drop_all()
        db.create_all()
    runner = app.test_cli_runner()
    password = 'Primeiro-teste-12345'
    result = runner.invoke(args=['criar-admin'], input=f'Atendimento\nadmin@example.test\n11987654321\n{password}\n{password}\n')
    assert result.exit_code == 0, result.output
    with app.app_context():
        assert {category.name for category in db.session.scalars(select(Category))} == {'Pratos do dia', 'Bebidas', 'Sobremesas'}
        assert db.session.scalar(select(Product.id).limit(1)) is None
    result = runner.invoke(args=['cardapio-exemplo'])
    assert result.exit_code == 0, result.output
    html = client.get('/').text
    assert html.count('class="mana-menu-section"') == 3
    assert 'Suco natural do dia' in html and 'Pudim da casa' in html
