import re
from decimal import Decimal, InvalidOperation

def text(value, label, maximum=140, minimum=1):
    value = (value or '').strip()
    if not minimum <= len(value) <= maximum:
        raise ValueError(f'{label}: use entre {minimum} e {maximum} caracteres.')
    return value

def integer(value, label='Quantidade', minimum=0, maximum=1000000):
    if not re.fullmatch(r'\d+', str(value or '')):
        raise ValueError(f'{label}: informe um número inteiro.')
    result = int(value)
    if not minimum <= result <= maximum:
        raise ValueError(f'{label}: informe um valor entre {minimum} e {maximum}.')
    return result

def money(value, optional=False):
    value = (value or '').strip().replace('R$', '').strip()
    if not value and optional: return None
    if ',' in value: value = value.replace('.', '').replace(',', '.')
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount <= 0 or amount > Decimal('9999999.99') or amount != amount.quantize(Decimal('.01')):
            raise ValueError
        return int(amount * 100)
    except (ValueError, InvalidOperation):
        raise ValueError('Preço inválido. Use um valor positivo com até duas casas decimais.')

def email(value):
    result = text(value, 'E-mail', 180).lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', result): raise ValueError('Informe um e-mail válido.')
    return result

def phone(value):
    digits = re.sub(r'\D', '', value or '')
    if len(digits) in (10, 11): digits = '55' + digits
    if len(digits) not in (12, 13) or not digits.startswith('55') or digits[2] == '0' or len(set(digits[4:])) < 2:
        raise ValueError('Informe um WhatsApp brasileiro com DDD. Exemplo de formato: (35) 9xxxx-xxxx.')
    return digits

def password(value):
    if not 10 <= len(value or '') <= 128:
        raise ValueError('A senha precisa ter entre 10 e 128 caracteres.')
    return value

def brl(cents):
    return 'R$ ' + f'{(cents or 0) / 100:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
