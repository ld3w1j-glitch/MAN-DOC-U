from datetime import timedelta
from io import BytesIO
from zipfile import ZipFile
from PIL import Image
from sqlalchemy import select
from app.extensions import db
from app.models import DailyMenu,DailyMenuItem,Product
from app.services.daily_menu import today

def menu_date(app):
    with app.app_context():return today().isoformat()

def test_only_selected_dishes_visible_and_orderable(app,client,login):
    login('root@example.test');day=menu_date(app)
    assert client.post('/admin/cardapio-dia',data={'date':day,'title':'Nosso almoço','product_id':['1'],'action':'publish'}).status_code==303
    html=client.get('/').text
    assert 'Organizador A' in html and 'Copo B' not in html and 'Nosso almoço' in html
    assert client.get('/produto/2').status_code==404
    assert client.post('/carrinho/adicionar/2',data={'quantity':'1','variant_id':'1'}).location=='/produto/2'
    with client.session_transaction() as s:assert not s.get('cart')
    assert client.get('/admin/produtos').status_code==200
    with app.app_context():assert db.session.get(Product,2) is not None

def test_future_menu_does_not_replace_today_and_draft_hides_today(app,client,login):
    login('root@example.test');day=menu_date(app)
    with app.app_context():future=(today()+timedelta(days=1)).isoformat()
    client.post('/admin/cardapio-dia',data={'date':future,'title':'Amanhã','product_id':['2'],'action':'publish'})
    assert 'Organizador A' in client.get('/').text
    client.post('/admin/cardapio-dia',data={'date':day,'title':'Rascunho','product_id':['1'],'action':'draft'})
    assert 'Organizador A' not in client.get('/').text
    assert client.get('/produto/1').status_code==404

def test_status_png_dimensions_content_and_auth(app,client,login):
    day=menu_date(app)
    assert client.get(f'/admin/cardapio-dia/{day}/status/1.png').status_code==302
    login('root@example.test')
    assert client.get('/admin/cardapio-dia').status_code==200
    response=client.get(f'/admin/cardapio-dia/{day}/status/1.png?baixar=1')
    assert response.status_code==200 and response.mimetype=='image/png'
    im=Image.open(BytesIO(response.data));assert im.size==(1080,1920)
    assert im.getpixel((0,0))==(243,242,238)
    assert 'attachment' in response.headers['Content-Disposition']
    assert client.get(f'/admin/cardapio-dia/{day}/status/2.png').status_code==404

def test_large_daily_menu_exports_all_pngs(app,client,login):
    login('root@example.test');day=menu_date(app)
    with app.app_context():
        menu=db.session.scalar(select(DailyMenu))
        original=db.session.get(Product,1)
        for i in range(8):
            p=Product(name='Prato longo com arroz, feijão e salada '+str(i),description='Feito com capricho.',price_cents=99999,stock=10,owner=original.owner,category=original.category)
            db.session.add(p);menu.items.append(DailyMenuItem(product=p,position=i+2))
        db.session.commit()
    response=client.get(f'/admin/cardapio-dia/{day}/status.zip')
    assert response.status_code==200
    with ZipFile(BytesIO(response.data)) as z:
        assert len(z.namelist())==2
        for n in z.namelist():assert Image.open(BytesIO(z.read(n))).size==(1080,1920)

def test_daily_menu_permissions_and_empty_publish_rejected(app,client,login):
    login();assert client.get('/admin/cardapio-dia').status_code==403
    client.post('/logout');login('root@example.test');day=menu_date(app)
    response=client.post('/admin/cardapio-dia',data={'date':day,'title':'Novo','action':'publish'})
    assert 'Selecione ao menos um prato' in response.text
    with app.app_context():assert len(db.session.scalar(select(DailyMenu)).items)==2

def test_daily_menu_changes_invalidate_old_cart(app,client):
    client.post('/carrinho/adicionar/2',data={'quantity':'1','variant_id':'1'})
    with app.app_context():
        menu=db.session.scalar(select(DailyMenu));menu.items=[item for item in menu.items if item.product_id!=2];db.session.commit()
    assert 'Alguns pratos precisam de revisão' in client.get('/carrinho').text
