"""Interface discovery, hotplug event stream, and recommendations."""
import json
import queue

from flask import Blueprint, jsonify, Response, stream_with_context

from . import login_required
from ..hal import interfaces as hal
from ..hal import events
from ..core import recommendations

bp = Blueprint("interfaces", __name__)


@bp.get("/api/interfaces")
@login_required
def list_ifaces():
    return jsonify(hal.discover())


@bp.get("/api/recommendations")
@login_required
def recs():
    return jsonify(recommendations.recommendations())


@bp.get("/api/events")
@login_required
def event_stream():
    """Server-Sent Events: pushes interface-change notifications to the UI."""
    q = events.subscribe()

    @stream_with_context
    def gen():
        try:
            yield "event: hello\ndata: {}\n\n"
            while True:
                try:
                    msg = q.get(timeout=20)
                    yield f"data: {json.dumps(msg)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            events.unsubscribe(q)

    return Response(gen(), mimetype="text/event-stream")
