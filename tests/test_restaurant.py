import re
import pytest
from sqlalchemy import select,func
from app.extensions import db
from app.models import Product,Variant,PendingOrder,OrderDetails,RestaurantSettings,User
from test_store import checkout_data,prepared_message

def add(client):client.post('/carrinho/adicionar/1',data={'quantity':'2'})

def test_delivery_message_and_stored_snapshot(app,client):
    add(client)
    response=client.post('/pedido/finalizar',data=checkout_data(client,reference='Portão azul',complement='Apto 4',requested_time='12h30',notes='Sem cebola'))
    path,msg=prepared_message(client,response)
    for text in ('Cliente de Teste','+5535987654321','Rua do Teste, 25','Centro','Pouso Alegre/MG','Apto 4','Portão azul','12h30','Pix','Sem cebola','Entrega: a confirmar'):
        assert text in msg
    with app.app_context():
        d=db.session.scalar(select(OrderDetails));assert d.order.customer_phone=='5535987654321'
        assert d.order.status=='pendente' and d.total_cents==5980 and d.delivery_fee_cents is None
        assert db.session.get(Product,1).stock==8
    assert client.get(response.location).status_code==200
    assert app.test_client().get(response.location).status_code==404

@pytest.mark.parametrize('extra',[{'name':''},{'phone':'123'},{'street':''},{'district':''},{'city':''},{'state':'XX'},{'postcode':'123'},{'fulfillment':'fake'},{'payment_method':'bitcoin'},{'payment_method':'cash','change_for':'20'},{'reference':'x'*161}])
def test_invalid_checkout_preserves_cart_without_order(app,client,extra):
    add(client);response=client.post('/pedido/finalizar',data=checkout_data(client,**extra))
    assert response.status_code==400
    with app.app_context():assert db.session.scalar(select(func.count()).select_from(PendingOrder))==0
    with client.session_transaction() as sess:assert sess['cart']['1:0']==2

def test_pickup_cash_no_delivery_fee(app,client):
    with app.app_context():
        db.session.add(RestaurantSettings(id=1,pickup_address='Rua Cozinha, 100',delivery_fee_cents=800));db.session.commit()
    add(client)
    path,msg=prepared_message(client,client.post('/pedido/finalizar',data=checkout_data(client,fulfillment='pickup',payment_method='cash',change_for='100,00',street='',number='',district='',city='',state='')))
    assert 'Retirada no local: Rua Cozinha, 100' in msg and 'R$ 59,80' in msg and 'Troco para: R$ 100,00' in msg
    with app.app_context():
        d=db.session.scalar(select(OrderDetails));assert d.delivery_fee_cents==0 and d.total_cents==5980 and d.address==''

def test_fixed_delivery_fee_not_spoofed(app,client):
    with app.app_context():db.session.add(RestaurantSettings(id=1,delivery_fee_cents=800));db.session.commit()
    add(client)
    response=client.post('/pedido/finalizar',data=checkout_data(client,delivery_fee='0',total_cents='1'))
    _,msg=prepared_message(client,response);assert 'Taxa de entrega: R$ 8,00' in msg and 'Total: R$ 67,80' in msg

def test_double_submit_is_idempotent(app,client):
    add(client);data=checkout_data(client)
    a=client.post('/pedido/finalizar',data=data);b=client.post('/pedido/finalizar',data=data)
    assert a.location==b.location and a.status_code==b.status_code==303
    with app.app_context():assert db.session.scalar(select(func.count()).select_from(PendingOrder))==1

def test_stale_cart_form_rejected(app,client):
    add(client);data=checkout_data(client)
    client.post('/carrinho/atualizar',data={'key':'1:0','quantity':'1'})
    assert client.post('/pedido/finalizar',data=data).status_code==400
    with app.app_context():assert db.session.scalar(select(func.count()).select_from(PendingOrder))==0

def test_paused_or_disabled_attendant_blocks_orders(app,client):
    add(client);data=checkout_data(client)
    with app.app_context():
        row=RestaurantSettings(id=1,accepting_orders=False);db.session.add(row);db.session.commit()
    assert client.post('/pedido/finalizar',data=data).status_code==400
    with app.app_context():
        row=db.session.get(RestaurantSettings,1);row.accepting_orders=True;row.attendant_id=2;db.session.get(User,2).active=False;db.session.commit()
    assert client.post('/pedido/finalizar',data=data).status_code==400

def test_central_admin_approval_deducts_multiple_owners_once(app,client,login):
    add(client);client.post('/carrinho/adicionar/2',data={'quantity':'1','variant_id':'2'})
    client.post('/pedido/finalizar',data=checkout_data(client));login('root@example.test')
    assert client.post('/admin/pedidos/1/aprovar').status_code==303
    assert client.post('/admin/pedidos/1/aprovar').status_code==303
    with app.app_context():
        assert db.session.get(Product,1).stock==6 and db.session.get(Variant,2).stock==2
        assert db.session.get(PendingOrder,1).status=='aprovado'

def test_admin_configuration_permissions_and_free_delivery(app,client,login):
    login();assert client.get('/admin/atendimento').status_code==403
    client.post('/logout');login('root@example.test')
    assert client.get('/admin/atendimento').status_code==200
    data={'attendant_id':'2','accepting_orders':'on','delivery_enabled':'on','pickup_enabled':'on',
          'pickup_address':'Rua Teste, 25','delivery_fee':'0,00','pix_enabled':'on','hours_text':'11h às 14h'}
    assert client.post('/admin/atendimento',data=data).status_code==303
    with app.app_context():
        row=db.session.get(RestaurantSettings,1);assert row.attendant_id==2 and row.delivery_fee_cents==0 and row.pix_enabled and not row.cash_enabled
    assert '11h às 14h' in client.get('/').text

def test_checkout_csrf_and_customer_data_escaping(app,client):
    add(client);data=checkout_data(client,name='<script>alert(1)</script>',notes='<script>bad</script>')
    app.config['WTF_CSRF_ENABLED']=True
    assert client.post('/pedido/finalizar',data=data).status_code==400
    body=client.get('/carrinho').text
    data['csrf_token']=re.search(r'name="csrf_token"[^>]*value="([^\"]+)"',body).group(1)
    response=client.post('/pedido/finalizar',data=data)
    body=client.get(response.location).text
    assert '&lt;script&gt;' in body and '<script>alert(1)</script>' not in body
