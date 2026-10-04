import io
import os
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import pytest
from sqlalchemy import select
from werkzeug.datastructures import MultiDict
from app import create_app
from app.extensions import db
from app.models import User, Product, Category, Variant
from config import settings
from conftest import PASSWORD

def message(response):
    assert response.status_code == 303
    url=urlparse(response.location)
    assert url.hostname == 'wa.me'
    return url.path, parse_qs(url.query)['text'][0]

def test_catalog_without_customer_login_and_search(client):
    for route in ('/','/produto/1','/produto/2','/carrinho','/login','/health'):
        assert client.get(route).status_code == 200
    html=client.get('/?q=Organizador').text
    assert 'Organizador A' in html and 'Copo B' not in html
    assert 'Organizador A' not in client.get('/?q=%25').text

def test_unauthenticated_admin_and_csrf(app,client,product_data):
    assert client.get('/admin/').status_code == 302
    app.config['WTF_CSRF_ENABLED']=True
    assert client.post('/login',data={'email':'a@example.test','password':PASSWORD}).status_code == 400
    token=re.search(r'name="csrf_token"[^>]*value="([^"]+)"',client.get('/login').text).group(1)
    assert client.post('/login',data={'email':'a@example.test','password':PASSWORD,'csrf_token':token}).status_code == 302
    assert client.post('/admin/produtos/novo',data=product_data).status_code == 400

def test_only_owner_or_principal_can_edit_or_delete(app,client,login,product_data):
    login()
    assert client.get('/admin/produtos/2/editar').status_code == 403
    assert client.post('/admin/produtos/2/editar',data=product_data).status_code == 403
    assert client.post('/admin/produtos/2/excluir').status_code == 403
    assert 'Copo B' not in client.get('/admin/produtos').text
    client.post('/logout');login('root@example.test')
    assert client.get('/admin/produtos/2/editar').status_code == 200
    with app.app_context(): assert db.session.get(Product,2).owner_id == 3

def test_create_product_upload_and_owner_cannot_be_spoofed(app,client,login,product_data,png):
    login()
    product_data.update(owner_id='3',image=(png,'foto.png'))
    assert client.post('/admin/produtos/novo',data=product_data).status_code == 303
    with app.app_context():
        p=db.session.scalar(select(Product).where(Product.name=='Produto novo'))
        assert p.owner_id == 2 and p.price_cents == 1990
        photo=p.image
        assert Path(app.config['UPLOAD_FOLDER'],photo).exists()
    assert client.get('/midia/'+photo).status_code == 200

def test_fake_image_rejected_without_creating_product(app,client,login,product_data):
    login()
    product_data['image']=(io.BytesIO(b'<script>bad</script>'),'fake.png')
    assert client.post('/admin/produtos/novo',data=product_data).status_code == 400
    with app.app_context(): assert db.session.scalar(select(Product).where(Product.name=='Produto novo')) is None

def test_owner_delete_removes_photo_and_cart_demands_review(app,client,login,product_data,png):
    login()
    product_data['image']=(png,'foto.png')
    client.post('/admin/produtos/novo',data=product_data)
    with app.app_context():
        p=db.session.scalar(select(Product).where(Product.name=='Produto novo'))
        pid,photo=p.id,p.image
    client.post(f'/carrinho/adicionar/{pid}',data={'quantity':'1'})
    assert client.post(f'/admin/produtos/{pid}/excluir').status_code == 303
    assert client.get(f'/produto/{pid}').status_code == 404
    assert not Path(app.config['UPLOAD_FOLDER'],photo).exists()
    assert client.post('/pedido/finalizar',data=checkout_data(client)).status_code == 400

@pytest.mark.parametrize('price',['0','-1','NaN','9.999','9999999999999'])
def test_invalid_price_cannot_be_saved(client,login,product_data,price):
    login();product_data['price']=price
    assert client.post('/admin/produtos/novo',data=product_data).status_code == 400

def test_variants_round_trip_and_stable_ids(app,client,login,product_data):
    login()
    data=MultiDict(product_data)
    for key,values in {'variant_id':['',''],'variant_label':['P','G'],'variant_price':['','29,90'],'variant_stock':['2','4']}.items():data.setlist(key,values)
    assert client.post('/admin/produtos/novo',data=data).status_code == 303
    with app.app_context():
        p=db.session.scalar(select(Product).where(Product.name=='Produto novo'))
        pid=p.id; ids=[str(v.id) for v in p.variants]
        assert p.available_stock == 6 and p.variants[1].price_cents == 2990
    data.setlist('variant_id',ids);data.setlist('variant_stock',['1','4'])
    assert client.post(f'/admin/produtos/{pid}/editar',data=data).status_code == 303
    with app.app_context():
        p=db.session.get(Product,pid)
        assert [str(v.id) for v in p.variants] == ids and p.available_stock == 5
    data.setlist('variant_id',['1',ids[1]])
    assert client.post(f'/admin/produtos/{pid}/editar',data=data).status_code == 400

def checkout_data(client, **extra):
    client.get('/carrinho')
    with client.session_transaction() as sess: key=sess['checkout_key']
    data={'name':'Cliente de Teste','phone':'35987654321','fulfillment':'delivery',
        'street':'Rua do Teste','number':'25','district':'Centro','city':'Pouso Alegre','state':'MG',
        'payment_method':'pix','submission_key':key}
    data.update(extra);return data

def prepared_message(client, response):
    import html
    assert response.status_code==303 and response.location.startswith('/pedido/')
    body=client.get(response.location).text
    target=html.unescape(re.search(r'href="(https://wa.me/[^"]+)"',body).group(1))
    url=urlparse(target)
    return url.path,parse_qs(url.query)['text'][0]

def test_attendant_phone_and_server_price_are_used(app,client,login):
    from app.models import RestaurantSettings
    login()
    assert client.post('/admin/perfil',data={'name':'Responsável A','email':'a@example.test','whatsapp':'(35) 99876-5432'}).status_code == 303
    with app.app_context():
        db.session.add(RestaurantSettings(id=1,attendant_id=2));db.session.commit()
    client.post('/produto/1/whatsapp',data={'quantity':'2','price':'0.01','seller_id':'3','whatsapp':'5521999999999'})
    path,msg=prepared_message(client,client.post('/pedido/finalizar',data=checkout_data(client, price='0.01',total='0',seller_id='3')))
    assert path=='/5535998765432' and '2 × Organizador A' in msg and 'R$ 59,80' in msg and 'MC-00001' in msg
    with app.app_context(): assert db.session.get(Product,1).stock==8

def test_cart_combines_owners_for_one_attendant(client):
    client.post('/carrinho/adicionar/1',data={'quantity':'2'})
    client.post('/carrinho/adicionar/2',data={'quantity':'1','variant_id':'2'})
    html=client.get('/carrinho').text
    assert 'Organizador A' in html and 'Copo B' in html and 'Principal' in html
    path,msg=prepared_message(client,client.post('/pedido/finalizar',data=checkout_data(client)))
    assert path=='/5511987654321' and 'Organizador A' in msg and 'Copo B' in msg and 'Escuro' in msg and 'R$ 119,70' in msg
    with client.session_transaction() as sess: assert not sess.get('cart')

@pytest.mark.parametrize('data',[{'quantity':'0'},{'quantity':'-1'},{'quantity':'999'},{'quantity':'1','variant_id':'1'}])
def test_invalid_selection_does_not_open_whatsapp(client,data):
    response=client.post('/produto/1/whatsapp',data=data)
    assert response.status_code == 303 and 'wa.me' not in response.location

def test_cart_stock_change_requires_review_and_can_remove(app,client):
    client.post('/carrinho/adicionar/1',data={'quantity':'3'})
    with app.app_context():
        db.session.get(Product,1).stock=1;db.session.commit()
    assert client.get('/carrinho').status_code == 200
    assert client.post('/pedido/finalizar',data=checkout_data(client)).status_code == 400
    client.post('/carrinho/atualizar',data={'key':'1:0','quantity':'0'})
    with client.session_transaction() as session: assert session['cart'] == {}

def test_team_management_and_revoked_session(app,client,login):
    login()
    assert client.get('/admin/administradores').status_code == 403
    other=app.test_client();other.post('/login',data={'email':'a@example.test','password':PASSWORD})
    client.post('/logout');login('root@example.test')
    assert client.get('/admin/administradores').status_code == 200
    response=client.post('/admin/administradores',data={'name':'Novo','email':'novo@example.test','whatsapp':'11987654322','password':PASSWORD,'role':'superadmin'})
    assert response.status_code == 303
    with app.app_context(): assert db.session.scalar(select(User).where(User.email=='novo@example.test')).role == 'admin'
    client.post('/admin/administradores/2/editar',data={'name':'Loja A','email':'a@example.test','whatsapp':'35987654321'})
    assert other.get('/admin/').status_code == 302
    assert client.get('/produto/1').status_code == 404

def test_category_permissions_and_cannot_delete_in_use(app,client,login):
    login()
    assert client.post('/admin/categorias',data={'category_id':'1','name':'Outro','active':'on'}).status_code == 403
    client.post('/admin/categorias',data={'name':'Nova','active':'on'})
    with app.app_context(): assert db.session.scalar(select(Category).where(Category.name=='Nova')).creator_id == 2
    client.post('/logout');login('root@example.test')
    client.post('/admin/categorias/1/excluir')
    with app.app_context(): assert db.session.get(Category,1) is not None
    client.post('/admin/categorias',data={'category_id':'1','name':'Casa'})
    assert client.get('/produto/1').status_code == 404

def test_catalog_sort_matches_variant_price(app,client):
    with app.app_context():
        db.session.get(Variant,1).price_cents=1000;db.session.commit()
    html=client.get('/?ordem=menor-preco').text
    assert html.index('Copo B') < html.index('Organizador A')

def test_setup_preserves_accounts_and_data_after_restart(app):
    runner=app.test_cli_runner()
    assert runner.invoke(args=['init-db']).exit_code == 0
    assert runner.invoke(args=['criar-admin']).exit_code != 0
    another=create_app({'TESTING':True})
    with another.app_context():
        assert db.session.get(User,2).check_password(PASSWORD)
        assert db.session.get(Product,1).name == 'Organizador A'
        db.session.remove();db.engine.dispose()

def test_password_reset_revokes_other_sessions(app,client,login):
    login()
    result=app.test_cli_runner().invoke(args=['redefinir-senha','a@example.test'],input='Nova-senha-12345\nNova-senha-12345\n')
    assert result.exit_code == 0
    assert client.get('/admin/').status_code == 302

def test_wrong_login_rate_limit(client):
    for _ in range(8):
        assert client.post('/login',data={'email':'a@example.test','password':'errada'}).status_code == 401
    assert client.post('/login',data={'email':'a@example.test','password':'errada'}).status_code == 429

def test_railway_volume_and_generated_secret_are_persistent(monkeypatch,tmp_path):
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('DATA_DIR',str(tmp_path))
    monkeypatch.setenv('REQUIRE_DATA_VOLUME','1')
    monkeypatch.setenv('RAILWAY_PROJECT_ID','test-project')
    monkeypatch.delenv('RAILWAY_VOLUME_MOUNT_PATH',raising=False)
    monkeypatch.delenv('SECRET_KEY',raising=False)
    with pytest.raises(RuntimeError,match='volume persistente'):
        settings()
    assert not (tmp_path/'secret.key').exists()
    monkeypatch.setenv('RAILWAY_VOLUME_MOUNT_PATH',str(tmp_path))
    key=settings()['SECRET_KEY']
    assert len(key)==64 and settings()['SECRET_KEY']==key
    assert (tmp_path/'secret.key').read_text()==key
    monkeypatch.setenv('SECRET_KEY','muito-curta')
    with pytest.raises(RuntimeError,match='pelo menos 32'):
        settings()
