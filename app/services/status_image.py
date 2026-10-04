"""Geração local de artes do cardápio usando as fotos dos pratos."""
from io import BytesIO
from math import ceil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from flask import current_app
from app.services.validation import brl
from app.services.restaurant import receiver

BLUE = '#2664AE'
ORANGE = '#F1892C'
CREAM = '#F3F2EE'
DARK = '#193654'
MUTED = '#5B6D7E'
LINE = '#D7E1ED'
WHITE = '#FFFFFF'
STORY_PER_PAGE = 4
POST_PER_PAGE = 4


def font(size, bold=False, display=False):
    fonts = Path(current_app.static_folder) / 'fonts'
    filename = 'LilitaOne-Regular.ttf' if display else ('Fredoka-Bold.ttf' if bold else 'NunitoSans.ttf')
    return ImageFont.truetype(str(fonts / filename), size)


def wrapped(draw, text, f, width):
    lines = []
    line = ''
    for word in (text or '').split():
        parts = [word]
        if draw.textlength(word, font=f) > width:
            parts = []
            part = ''
            for char in word:
                if part and draw.textlength(part + char, font=f) > width:
                    parts.append(part)
                    part = char
                else:
                    part += char
            if part:
                parts.append(part)
        for wordpart in parts:
            nextline = (line + ' ' + wordpart).strip()
            if line and draw.textlength(nextline, font=f) > width:
                lines.append(line)
                line = wordpart
            else:
                line = nextline
    if line:
        lines.append(line)
    return lines


def textblock(draw, x, y, text, size, width, color=DARK, bold=False, max_lines=None, display=False, line_gap=1.18):
    f = font(size, bold, display)
    lines = wrapped(draw, text, f, width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        line = lines[-1]
        while line and draw.textlength(line + '…', font=f) > width:
            line = line[:-1]
        lines[-1] = (line or '').rstrip() + '…'
    for line in lines:
        draw.text((x, y), line, font=f, fill=color)
        y += int(size * line_gap)
    return y


def art(canvas, name, box):
    im = Image.open(Path(current_app.static_folder) / 'img/status' / name).convert('RGBA')
    im.thumbnail((box[2], box[3]), Image.Resampling.LANCZOS)
    canvas.alpha_composite(im, (box[0] + (box[2] - im.width) // 2, box[1] + (box[3] - im.height) // 2))


def product_image(product, size):
    if not product.cover_image:
        return None
    path = Path(current_app.config['UPLOAD_FOLDER']) / product.cover_image
    if not path.is_file():
        return None
    with Image.open(path) as im:
        im.load()
        im = ImageOps.exif_transpose(im).convert('RGB')
        return ImageOps.fit(im, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def rounded_mask(size, radius):
    mask = Image.new('L', size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def paste_rounded(base, im, xy, radius):
    rgba = im.convert('RGBA')
    mask = rounded_mask(rgba.size, radius)
    # Pillow Image.alpha_composite() does not accept a mask as the third
    # argument; that value is interpreted as a source box and raises ValueError.
    # paste() is the correct masked-composition operation for rounded photos.
    base.paste(rgba, xy, mask)


def _phone_display(settings):
    person = receiver(settings)
    if not person:
        return ''
    number = person.whatsapp[2:]
    return '(' + number[:2] + ') ' + number[2:-4] + '-' + number[-4:]


def _footer_lines(settings):
    info = []
    if settings.hours_text:
        info.append(settings.hours_text)
    if settings.delivery_enabled:
        info.append('Entrega' + (' • taxa a confirmar' if settings.delivery_fee_cents is None else ' • ' + brl(settings.delivery_fee_cents)))
    if settings.pickup_enabled and settings.pickup_address:
        info.append('Retirada: ' + settings.pickup_address)
    return ' | '.join(info)


def _story_card(canvas, draw, product, box):
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=28, fill=WHITE, outline=LINE, width=2)
    photo_h = 208
    photo = product_image(product, (w - 30, photo_h))
    if photo:
        paste_rounded(canvas, photo, (x + 15, y + 15), 22)
    else:
        draw.rounded_rectangle((x + 15, y + 15, x + w - 15, y + 15 + photo_h), radius=22, fill='#E8EEF5')
        art(canvas, 'panela.png', (x + w - 175, y + 20, 140, 140))
        textblock(draw, x + 30, y + 78, 'Foto do prato', 24, w - 60, BLUE, True, 1)
    price = brl(product.display_price)
    pw = draw.textlength(price, font=font(28, True))
    draw.rounded_rectangle((x + w - pw - 54, y + 26, x + w - 22, y + 74), radius=22, fill=ORANGE)
    draw.text((x + w - pw - 38, y + 36), price, font=font(28, True), fill=WHITE)
    textblock(draw, x + 20, y + photo_h + 34, product.name, 28, w - 40, BLUE, True, 2)
    note = 'A partir de ' + ' / '.join(v.label for v in product.variants) if product.variants else product.description
    if not product.available_stock:
        note = 'ESGOTADO'
    textblock(draw, x + 20, y + photo_h + 106, note, 20, w - 40, MUTED, False, 3)


def _post_card(canvas, draw, product, box):
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=24, fill=WHITE, outline=LINE, width=2)
    photo = product_image(product, (w - 24, 170))
    if photo:
        paste_rounded(canvas, photo, (x + 12, y + 12), 18)
    else:
        draw.rounded_rectangle((x + 12, y + 12, x + w - 12, y + 182), radius=18, fill='#E8EEF5')
    textblock(draw, x + 16, y + 194, product.name, 22, w - 32, BLUE, True, 2)
    draw.text((x + 16, y + h - 38), brl(product.display_price), font=font(24, True), fill=ORANGE)


def _encode(im):
    bio = BytesIO()
    im.convert('RGB').save(bio, 'PNG', optimize=True)
    return bio.getvalue()


def creative_pages(total_items, kind='status'):
    per_page = STORY_PER_PAGE if kind == 'status' else POST_PER_PAGE
    return max(1, ceil(total_items / per_page)) if total_items else 0


def build_status_images(menu, products, settings):
    if not products:
        raise ValueError('Selecione ao menos um prato ativo para gerar a imagem.')
    total_pages = creative_pages(len(products), 'status')
    days = ['SEGUNDA-FEIRA', 'TERÇA-FEIRA', 'QUARTA-FEIRA', 'QUINTA-FEIRA', 'SEXTA-FEIRA', 'SÁBADO', 'DOMINGO']
    outputs = []
    for page in range(total_pages):
        im = Image.new('RGBA', (1080, 1920), CREAM)
        draw = ImageDraw.Draw(im)
        draw.rounded_rectangle((48, 38, 1032, 300), radius=34, fill=WHITE)
        art(im, 'marca.png', (74, 52, 300, 215))
        art(im, 'folhas.png', (880, 54, 105, 120))
        textblock(draw, 390, 56, menu.title.upper(), 46, 560, BLUE, True, 2, display=True)
        textblock(draw, 390, 165, f'{days[menu.date.weekday()]} • {menu.date:%d/%m/%Y}', 26, 560, BLUE, True, 1)
        if menu.message:
            textblock(draw, 390, 206, menu.message, 22, 570, MUTED, False, 2)
        items = products[page * STORY_PER_PAGE:(page + 1) * STORY_PER_PAGE]
        positions = [
            (48, 348, 470, 430),
            (562, 348, 470, 430),
            (48, 812, 470, 430),
            (562, 812, 470, 430),
        ]
        for product, pos in zip(items, positions):
            _story_card(im, draw, product, pos)
        free_top = 1274
        draw.rounded_rectangle((48, free_top, 1032, 1768), radius=30, fill=BLUE)
        textblock(draw, 80, free_top + 28, 'DEU FOME?', 46, 380, WHITE, True, 1, display=True)
        textblock(draw, 80, free_top + 88, 'Monte seu pedido', 34, 420, WHITE, True, 1, display=True)
        textblock(draw, 80, free_top + 148, 'Peça pelo WhatsApp e confirme disponibilidade, entrega e pagamento com o atendimento.', 24, 510, WHITE, False, 4)
        phone = _phone_display(settings)
        if phone:
            draw.rounded_rectangle((80, free_top + 270, 490, free_top + 340), radius=22, fill=ORANGE)
            textblock(draw, 102, free_top + 287, phone, 34, 350, WHITE, True, 1)
        footer_info = _footer_lines(settings)
        textblock(draw, 80, free_top + 376, footer_info, 20, 520, WHITE, False, 4)
        art(im, 'panela.png', (730, free_top + 66, 220, 220))
        art(im, 'faixa.png', (0, 1848, 1080, 48))
        if total_pages > 1:
            draw.text((945, 1894), f'{page + 1}/{total_pages}', font=font(20, True), fill=BLUE)
        outputs.append(_encode(im))
    return outputs


def build_post_images(menu, products, settings):
    if not products:
        raise ValueError('Selecione ao menos um prato ativo para gerar a imagem.')
    total_pages = creative_pages(len(products), 'post')
    outputs = []
    for page in range(total_pages):
        im = Image.new('RGBA', (1080, 1080), CREAM)
        draw = ImageDraw.Draw(im)
        draw.rounded_rectangle((36, 30, 1044, 170), radius=32, fill=WHITE)
        art(im, 'marca.png', (54, 38, 240, 130))
        textblock(draw, 322, 42, menu.title.upper(), 34, 520, BLUE, True, 2, display=True)
        textblock(draw, 322, 110, f'{menu.date:%d/%m/%Y}', 23, 300, BLUE, True, 1)
        if menu.message:
            textblock(draw, 850, 44, menu.message, 17, 160, MUTED, False, 4)
        items = products[page * POST_PER_PAGE:(page + 1) * POST_PER_PAGE]
        boxes = [
            (36, 200, 490, 320),
            (554, 200, 490, 320),
            (36, 540, 490, 320),
            (554, 540, 490, 320),
        ]
        for product, pos in zip(items, boxes):
            _post_card(im, draw, product, pos)
        draw.rounded_rectangle((36, 888, 1044, 1038), radius=28, fill=BLUE)
        textblock(draw, 66, 915, 'CARDÁPIO DO DIA', 28, 280, WHITE, True, 1, display=True)
        phone = _phone_display(settings)
        if phone:
            textblock(draw, 66, 960, phone, 30, 320, WHITE, True, 1)
        footer_info = _footer_lines(settings)
        textblock(draw, 420, 916, footer_info, 18, 560, WHITE, False, 4)
        if total_pages > 1:
            draw.text((966, 1000), f'{page + 1}/{total_pages}', font=font(20, True), fill=WHITE)
        outputs.append(_encode(im))
    return outputs
