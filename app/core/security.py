from functools import wraps
from flask import abort
from flask_login import current_user, login_required

def superadmin_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_superadmin: abort(403)
        return fn(*args, **kwargs)
    return wrapped

def require_owner(product):
    if product.owner_id != current_user.id and not current_user.is_superadmin:
        abort(403)
