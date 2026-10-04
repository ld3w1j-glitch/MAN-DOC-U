import io
import pytest
from PIL import Image
from app import create_app
from app.extensions import db
from app.models import User, Category, Product, Variant, DailyMenu, DailyMenuItem

PASSWORD = 'Teste-local-12345'

@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('SECRET_KEY', 'test-only-secret-key-never-use-in-production')
    app = create_app({'TESTING': True, 'WTF_CSRF_ENABLED': False})
    with app.app_context():
        db.create_all()
        users = [User(name=name, email=email, whatsapp=phone, role=role) for name,email,phone,role in [
            ('Principal', 'root@example.test', '5511987654321', 'superadmin'),
            ('Loja A', 'a@example.test', '5535987654321', 'admin'),
            ('Loja B', 'b@example.test', '5521987654321', 'admin')]]
        for u in users: u.set_password(PASSWORD)
        db.session.add_all(users); db.session.flush()
        category = Category(name='Casa', creator_id=1)
        simple = Product(name='Organizador A', description='Organizador de mesa em madeira.', price_cents=2990, stock=8, owner=users[1], category=category)
        varied = Product(name='Copo B', description='Copo com opções de acabamento.', price_cents=4990, stock=0, owner=users[2], category=category)
        varied.variants = [Variant(label='Natural', price_cents=None, stock=5), Variant(label='Escuro', price_cents=5990, stock=3)]
        db.session.add_all([category, simple, varied]); db.session.flush()
        from app.services.daily_menu import today
        menu=DailyMenu(date=today(),creator_id=1,published=True,title='Cardápio do dia')
        menu.items=[DailyMenuItem(product=simple,position=0),DailyMenuItem(product=varied,position=1)]
        db.session.add(menu); db.session.commit()
    yield app
    with app.app_context():
        db.session.remove(); db.engine.dispose()

@pytest.fixture
def client(app): return app.test_client()

@pytest.fixture
def login(client):
    def do(email='a@example.test'):
        response = client.post('/login', data={'email': email, 'password': PASSWORD})
        assert response.status_code == 302
        return client
    return do

@pytest.fixture
def product_data():
    return {'name':'Produto novo', 'description':'Descrição completa do produto.', 'price':'19,90', 'stock':'6', 'category_id':'1', 'active':'on'}

@pytest.fixture
def png():
    data=io.BytesIO()
    Image.new('RGB',(40,40),'#F6EFDF').save(data,'PNG')
    data.seek(0)
    return data
