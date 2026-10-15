from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

import cv2


class QRScanError(Exception):
    pass


@dataclass
class UpiPayload:
    payee_vpa: str
    payee_name: str
    amount: float | None
    note: str
    raw: str


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "\u2026"


def _name_from_vpa(vpa: str) -> str:
    local = vpa.split("@", 1)[0]
    words = [w for w in re.split(r"[._\-+]+", local) if w]
    return _collapse(" ".join(w[:1].upper() + w[1:] for w in words))


def parse_upi_uri(data: str) -> UpiPayload:
    data = (data or "").strip()
    parsed = urlparse(data)
    params = parse_qs(parsed.query)

    if parsed.scheme != "upi" and "pa" not in params and "pn" not in params:
        raw_name = _truncate(_collapse(unquote(data)), 40) or "Unknown Payee"
        return UpiPayload(payee_vpa="demo@upi", payee_name=raw_name, amount=None, note="", raw=data)

    vpa = _collapse(params.get("pa", [""])[0]) or "unknown@upi"
    name = _collapse(params.get("pn", [""])[0]) or _name_from_vpa(vpa) or "Unknown Payee"
    name = _truncate(name, 48)

    amount: float | None = None
    amount_raw = params.get("am", [None])[0]
    if amount_raw:
        try:
            parsed_amount = float(amount_raw)
        except ValueError:
            parsed_amount = 0.0
        amount = parsed_amount if parsed_amount > 0 else None

    return UpiPayload(
        payee_vpa=vpa,
        payee_name=name,
        amount=amount,
        note=_collapse(params.get("tn", [""])[0]),
        raw=data,
    )


def scan_image_file(path: str) -> UpiPayload:
    img = cv2.imread(path)
    if img is None:
        raise QRScanError(f"Could not read image: {path}")

    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(img)
    if not data:
        raise QRScanError("No QR code detected in image")

    return parse_upi_uri(data)


def scan_from_webcam(camera_index: int = 0) -> UpiPayload:
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise QRScanError("Could not open webcam")

    detector = cv2.QRCodeDetector()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                raise QRScanError("Failed to read from webcam")

            data, points, _ = detector.detectAndDecode(frame)
            if points is not None:
                pts = points.astype(int).reshape(-1, 2)
                cv2.polylines(frame, [pts], True, (0, 255, 0), 2)

            cv2.imshow("Scan QR - press q to cancel", frame)

            if data:
                cv2.waitKey(300)
                return parse_upi_uri(data)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                raise QRScanError("Scan cancelled by user")
    finally:
        cap.release()
        cv2.destroyAllWindows()
