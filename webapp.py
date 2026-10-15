"""Flask web UI: scan a UPI QR (upload or camera) and generate a watermarked DEMO receipt.

Gated behind a simple login so only people you've shared credentials with can use it.
"""

from __future__ import annotations

import io
import os
import secrets
import tempfile
from functools import wraps
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from receipt import generate_receipt
from scanner import QRScanError, parse_upi_uri

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY") or secrets.token_hex(32)

APP_USERNAME = os.environ.get("APP_USERNAME", "client")
_env_password = os.environ.get("APP_PASSWORD")
if _env_password:
    APP_PASSWORD_HASH = generate_password_hash(_env_password)
    _generated_password = None
else:
    _generated_password = secrets.token_urlsafe(9)
    APP_PASSWORD_HASH = generate_password_hash(_generated_password)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify(error="Session expired, please sign in again"), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == APP_USERNAME and check_password_hash(APP_PASSWORD_HASH, password):
            session["logged_in"] = True
            session["username"] = username
            return redirect(request.args.get("next") or url_for("index"))
        error = "Invalid username or password"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/scan-image", methods=["POST"])
@login_required
def scan_image():
    file = request.files.get("qr_image")
    if file is None or file.filename == "":
        return jsonify(error="No file uploaded"), 400

    data = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify(error="Could not read image"), 400

    detector = cv2.QRCodeDetector()
    text, points, _ = detector.detectAndDecode(img)
    if not text:
        return jsonify(error="No QR code detected in that image"), 422

    payload = parse_upi_uri(text)
    return jsonify(
        payee_name=payload.payee_name,
        payee_vpa=payload.payee_vpa,
        amount=payload.amount,
        note=payload.note,
        raw=payload.raw,
    )


@app.route("/api/decode-upi", methods=["POST"])
@login_required
def decode_upi():
    body = request.get_json(silent=True) or {}
    raw = body.get("raw", "")
    if not raw:
        return jsonify(error="No data to decode"), 400

    payload = parse_upi_uri(raw)
    return jsonify(
        payee_name=payload.payee_name,
        payee_vpa=payload.payee_vpa,
        amount=payload.amount,
        note=payload.note,
        raw=payload.raw,
    )


@app.route("/api/generate", methods=["POST"])
@login_required
def generate():
    body = request.get_json(silent=True) or {}

    payee_name = (body.get("payee_name") or "Unknown Payee").strip()
    payee_vpa = (body.get("payee_vpa") or "unknown@upi").strip()
    note = (body.get("note") or "").strip()
    raw = body.get("raw", "")
    amount = body.get("amount")

    try:
        amount = float(amount) if amount not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify(error="Invalid amount"), 400

    if amount is None or amount <= 0:
        return jsonify(error="Amount is required and must be positive"), 400

    payload = parse_upi_uri(raw) if raw else None
    if payload is None:
        from scanner import UpiPayload

        payload = UpiPayload(payee_vpa=payee_vpa, payee_name=payee_name, amount=amount, note=note, raw="")
    else:
        payload.payee_name = payee_name or payload.payee_name
        payload.payee_vpa = payee_vpa or payload.payee_vpa
        payload.note = note or payload.note

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "receipt.png"
        generate_receipt(payload, amount, out_path)
        buf = io.BytesIO(out_path.read_bytes())

    buf.seek(0)
    return send_file(buf, mimetype="image/png", as_attachment=False, download_name="demo_receipt.png")


if __name__ == "__main__":
    if _generated_password:
        print("=" * 60)
        print(" No APP_PASSWORD set - generated a one-time login:")
        print(f"   username: {APP_USERNAME}")
        print(f"   password: {_generated_password}")
        print(" Set APP_USERNAME / APP_PASSWORD env vars to control these.")
        print("=" * 60)
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=debug, host=host, port=port)
