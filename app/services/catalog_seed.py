from pathlib import Path
from uuid import uuid4
from PIL import Image, ImageOps
from flask import current_app
from sqlalchemy import select
from app.extensions import db
from app.models import User, Category, Product, Variant
from app.services.menu_categories import ensure_default_categories

# 22 pratos consolidados a partir das fotos individuais e dos cardápios enviados.
# O arquivo "Marmita redonda com frango, arroz e feijão.png" é uma composição
# genérica/duplicada e não vira um 23º item do catálogo.
DISHES = [
    ("Almôndegas fritas ao molho vermelho.png", "Almôndegas fritas ao molho vermelho", "Almôndegas douradas servidas com molho vermelho e acompanhamentos caseiros."),
    ("Bife suíno acebolado com acompanhamentos.png", "Bife suíno acebolado", "Bife suíno acebolado com arroz, feijão e acompanhamentos do dia."),
    ("Costela de boi com mandioca.png", "Costela de boi com mandioca", "Costela bovina macia com mandioca e acompanhamentos da casa."),
    ("Costelinha barbecue com acompanhamentos.png", "Costelinha suína assada ao molho barbecue", "Costelinha suína assada com molho barbecue e acompanhamentos caprichados."),
    ("Costelinha suína frita com acompanhamentos.png", "Costelinha suína frita", "Costelinha suína frita com arroz, feijão e guarnições do dia."),
    ("Marmita de coxa e sobrecoxa assada.png", "Coxa e sobrecoxa assada", "Coxa e sobrecoxa assada com acompanhamentos caseiros."),
    ("Coxa assada com batatas e acompanhamentos.png", "Coxa e sobrecoxa cozida com batatas", "Coxa e sobrecoxa com batatas e acompanhamentos preparados no dia."),
    ("Feijoada completa do Maná do Céu.png", "Feijoada completa do Maná do Céu", "Feijoada completa com arroz, couve, farofa, vinagrete e complementos da casa."),
    ("Filé de tilápia dourado na marmita.png", "Filé de tilápia", "Filé de tilápia dourado com arroz, feijão e acompanhamentos do dia."),
    ("Fricassê de frango na marmita.png", "Fricassê de frango", "Fricassê de frango cremoso com acompanhamentos da casa."),
    ("Lasanha à bolonhesa com acompanhamentos.png", "Lasanha à bolonhesa", "Lasanha à bolonhesa com acompanhamentos selecionados para o almoço."),
    ("Marmita de filé de frango grelhado.png", "Filé de frango grelhado", "Filé de frango grelhado com arroz, feijão e acompanhamentos do dia."),
    ("Marmita de frango à milanesa.png", "Filé de frango à milanesa", "Filé de frango à milanesa crocante com acompanhamentos da casa."),
    ("Marmita de frango à parmegiana.png", "Filé de frango à parmegiana", "Filé de frango à parmegiana com molho, queijo e acompanhamentos caprichados."),
    ("Marmita de linguiça fininha frita.png", "Linguiça fininha frita", "Linguiça fininha frita com arroz, feijão e acompanhamentos do dia."),
    ("Marmita de omelete com queijo.png", "Omelete com queijo", "Omelete dourada com queijo e acompanhamentos da casa."),
    ("Omelete dourada de presunto e queijo.png", "Omelete com presunto e queijo", "Omelete dourada com presunto e queijo e acompanhamentos do dia."),
    ("Marmita de pernil assado fatiado.png", "Pernil assado fatiado", "Pernil assado fatiado com acompanhamentos tradicionais."),
    ("Pernil assado ao molho barbecue.png", "Pernil assado ao molho barbecue", "Pernil assado com molho barbecue e acompanhamentos especiais."),
    ("Tiras de frango ao creme de milho.png", "Tiras de frango ao creme de milho", "Tiras de frango ao creme de milho com acompanhamentos do dia."),
    ("Pernil de panela acebolado.jpg", "Pernil de panela acebolado", "Pernil de panela acebolado com arroz, feijão e acompanhamentos caseiros."),
    ("Strogonoff de frango.jpg", "Strogonoff de frango", "Strogonoff de frango cremoso com arroz, batata palha e acompanhamentos da casa."),
]

SEED_MARKER = 'catalogo_mana_22_pratos_v1_8.done'


def _seed_source_dir():
    return Path(current_app.static_folder) / 'seed' / 'pratos'


def _marker_path():
    return Path(current_app.config['DATA_DIR']) / SEED_MARKER


def _save_seed_image(path: Path):
    with Image.open(path) as im:
        im.load()
        im = ImageOps.exif_transpose(im)
        im.thumbnail((1800, 1800))
        im = im.convert('RGB')
        filename = uuid4().hex + '.webp'
        folder = Path(current_app.config['UPLOAD_FOLDER'])
        folder.mkdir(parents=True, exist_ok=True)
        im.save(folder / filename, 'WEBP', quality=88, method=4)
        return filename


def _ensure_sizes(product):
    """Prepara P/M/G apenas quando o prato ainda não possui variações."""
    if product.variants:
        return
    product.price_cents = 2000
    product.stock = 0
    product.variants = [
        Variant(label='P', price_cents=1800, stock=20),
        Variant(label='M', price_cents=2000, stock=20),
        Variant(label='G', price_cents=2600, stock=20),
    ]


def import_mana_catalog(owner_id=None, update_existing=False):
    """Cria os 22 pratos ausentes e coloca as fotos no catálogo.

    Não apaga nem duplica itens existentes. Com update_existing=True, completa
    foto/categoria/variações dos itens já cadastrados sem sobrescrever nome/preço
    customizados além das variações ausentes.
    """
    db.create_all()
    owner = db.session.get(User, owner_id) if owner_id else None
    if not owner:
        owner = db.session.scalar(select(User).where(User.active.is_(True)).order_by(User.id))
    if not owner:
        raise ValueError('Crie o administrador principal antes de importar os pratos do Maná do Céu.')

    ensure_default_categories(owner.id)
    category = db.session.scalar(select(Category).where(Category.name == 'Pratos do dia'))
    if not category:
        category = Category(name='Pratos do dia', creator_id=owner.id, active=True)
        db.session.add(category)
        db.session.flush()

    source_dir = _seed_source_dir()
    if not source_dir.is_dir():
        raise ValueError('A pasta de imagens de pratos não foi encontrada no projeto.')

    existing = {p.name.casefold(): p for p in db.session.scalars(select(Product)).all()}
    prepared = 0
    featured = {
        'Feijoada completa do Maná do Céu',
        'Filé de frango grelhado',
        'Fricassê de frango',
        'Filé de frango à parmegiana',
        'Costela de boi com mandioca',
        'Filé de tilápia',
    }

    for filename, name, description in DISHES:
        source = source_dir / filename
        if not source.is_file():
            continue
        product = existing.get(name.casefold())
        if product:
            changed = False
            if update_existing and not product.image:
                product.image = _save_seed_image(source)
                changed = True
            if update_existing and not product.category:
                product.category = category
                changed = True
            if update_existing and not product.description:
                product.description = description
                changed = True
            if update_existing and not product.variants:
                _ensure_sizes(product)
                changed = True
            if changed:
                prepared += 1
            continue

        product = Product(
            owner_id=owner.id,
            category=category,
            name=name,
            description=description,
            price_cents=2000,
            stock=0,
            active=True,
            featured=name in featured,
            image=_save_seed_image(source),
        )
        _ensure_sizes(product)
        db.session.add(product)
        existing[name.casefold()] = product
        prepared += 1

    db.session.commit()
    return prepared


def ensure_mana_catalog(owner_id=None):
    """Executa a carga automática uma única vez para esta versão do catálogo."""
    marker = _marker_path()
    if marker.exists():
        return 0
    prepared = import_mana_catalog(owner_id=owner_id, update_existing=True)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('22 pratos Maná do Céu preparados.\n', encoding='utf-8')
    return prepared


def reset_seed_marker():
    _marker_path().unlink(missing_ok=True)
