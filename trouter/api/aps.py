"""Access Point management + the transactional apply/confirm flow."""
from flask import Blueprint, jsonify, request

from . import login_required, mutating
from ..core import config_manager, transaction

bp = Blueprint("aps", __name__)


@bp.get("/api/aps")
@login_required
def list_aps():
    return jsonify(config_manager.current_aps())


@bp.post("/api/aps/validate")
@mutating
def validate():
    aps = (request.get_json(silent=True) or {}).get("aps", [])
    findings, blocking = config_manager.validate(aps)
    return jsonify({"findings": findings, "blocked": blocking})


@bp.post("/api/aps/apply")
@mutating
def apply():
    """Validate + transactionally apply. Response includes a txid + deadline
    if confirmation is required (the default for connectivity-affecting changes).
    """
    body = request.get_json(silent=True) or {}
    aps = body.get("aps", [])
    require_confirm = body.get("require_confirm", True)
    result = config_manager.apply_aps(aps, actor=request.remote_addr,
                                      require_confirm=require_confirm)
    code = 200 if result.get("ok") else 400
    return jsonify(result), code


@bp.post("/api/aps/confirm")
@mutating
def confirm():
    txid = (request.get_json(silent=True) or {}).get("txid")
    return jsonify(config_manager.confirm(txid))


@bp.post("/api/aps/rollback")
@mutating
def rollback():
    txid = (request.get_json(silent=True) or {}).get("txid")
    return jsonify(config_manager.rollback(txid, reason="user-cancel"))


@bp.get("/api/aps/pending")
@login_required
def pending():
    """Used by the UI to resume a confirmation countdown after a page reload."""
    p = transaction.pending()
    return jsonify(p or {})
