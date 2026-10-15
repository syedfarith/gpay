"""Generates a watermarked DEMO payment-receipt image (dark "Paid to" style).

This is a prototyping/design tool only. Every image produced is stamped
with a real, non-removable "DEMO" watermark tiled across the whole frame,
plus an explicit "DEMO" badge in the layout itself, and the UI deliberately
avoids copying any real payment app's logo or trademark so it can never be
mistaken for a genuine receipt.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from scanner import UpiPayload

WIDTH, HEIGHT = 948, 1233

COLOR_BG = (0, 0, 0)
COLOR_CHECK = (26, 115, 232)
COLOR_TEXT = (235, 235, 235)
COLOR_MUTED = (150, 150, 155)
COLOR_WATERMARK = (255, 255, 255, 75)
COLOR_DEMO_BADGE = (220, 60, 60)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        ["segoeuib.ttf", "arialbd.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"]
        if bold
        else ["segoeui.ttf", "arial.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"]
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_watermark(img: Image.Image) -> Image.Image:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    font = _font(40, bold=True)
    text = "DEMO - NOT A REAL PAYMENT"

    step_x, step_y = 420, 220
    for y in range(-step_y, img.height + step_y, step_y):
        for x in range(-step_x, img.width + step_x, step_x):
            tile = Image.new("RGBA", (420, 120), (0, 0, 0, 0))
            tdraw = ImageDraw.Draw(tile)
            tdraw.text((0, 0), text, font=font, fill=COLOR_WATERMARK)
            tile = tile.rotate(30, expand=True)
            overlay.paste(tile, (x, y), tile)

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def generate_receipt(payload: UpiPayload, amount_override: float | None, out_path: str | Path) -> Path:
    amount = amount_override if amount_override is not None else payload.amount
    if amount is None:
        raise ValueError("No amount provided by QR code or override")

    now = datetime.now()
    txn_id = f"DEMO{uuid.uuid4().hex[:12].upper()}"

    img = Image.new("RGB", (WIDTH, HEIGHT), COLOR_BG)
    draw = ImageDraw.Draw(img)
    cx = WIDTH / 2

    # DEMO badge, top-right, part of the layout itself (not just the watermark)
    badge_text = "DEMO MODE"
    badge_font = _font(20, bold=True)
    badge_w = draw.textlength(badge_text, font=badge_font)
    bx0, by0 = WIDTH - badge_w - 70, 36
    draw.rounded_rectangle(
        [bx0, by0, bx0 + badge_w + 28, by0 + 40], radius=10, fill=(40, 15, 15), outline=COLOR_DEMO_BADGE, width=2
    )
    draw.text((bx0 + 14, by0 + 8), badge_text, font=badge_font, fill=(255, 150, 150))

    # Success check circle
    r = 100

    cy = 240
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=COLOR_CHECK)

    check_w = 14
    check_pts = [(cx - 46, cy + 2), (cx - 12, cy + 36), (cx + 54, cy - 32)]
    draw.line(check_pts, fill=(255, 255, 255), width=check_w, joint="curve")
    for px, py in check_pts:
        rr = check_w / 2
        draw.ellipse([px - rr, py - rr, px + rr, py + rr], fill=(255, 255, 255))

    # Amount
    draw.text((cx, 420), f"₹{amount:,.0f}", font=_font(96, bold=True), fill=COLOR_TEXT, anchor="ma")

    # Paid to / name / vpa
    draw.text((cx, 560), "Paid to", font=_font(32), fill=COLOR_MUTED, anchor="ma")
    draw.text((cx, 610), payload.payee_name.upper(), font=_font(50, bold=True), fill=COLOR_TEXT, anchor="ma")
    draw.text((cx, 700), payload.payee_vpa, font=_font(32), fill=COLOR_MUTED, anchor="ma")

    # Timestamp
    hour12 = now.hour % 12 or 12
    timestamp = f"{now.day} {now.strftime('%B %Y')}, {hour12}:{now.strftime('%M')} {now.strftime('%p').lower()}"
    draw.text((cx, 770), timestamp, font=_font(30), fill=COLOR_MUTED, anchor="ma")

    if payload.note:
        draw.text((cx, 820), payload.note, font=_font(24), fill=COLOR_MUTED, anchor="ma")

    # Transaction id, kept visible as part of making this clearly a demo artifact
    draw.text((cx, HEIGHT - 220), f"Txn ID: {txn_id}", font=_font(20), fill=COLOR_MUTED, anchor="ma")

    # Powered by UPI badge
    draw.text((cx, HEIGHT - 150), "POWERED BY", font=_font(16, bold=True), fill=COLOR_MUTED, anchor="ma")

    upi_font = _font(38, bold=True)
    upi_bbox = draw.textbbox((0, 0), "UPI", font=upi_font)
    upi_w = upi_bbox[2] - upi_bbox[0]
    upi_h = upi_bbox[3] - upi_bbox[1]

    arrow_w, arrow_h, gap = 18, 24, 8
    total_w = upi_w + gap + arrow_w
    group_top = HEIGHT - 122
    text_x = cx - total_w / 2
    draw.text((text_x, group_top), "UPI", font=upi_font, fill=COLOR_TEXT, anchor="la")

    arrow_x = text_x + upi_w + gap
    arrow_cy = group_top + upi_h / 2
    draw.polygon(
        [
            (arrow_x, arrow_cy - arrow_h / 2),
            (arrow_x + arrow_w, arrow_cy),
            (arrow_x, arrow_cy + arrow_h / 2),
        ],
        fill=COLOR_TEXT,
    )

    draw.text(
        (cx, HEIGHT - 82), "UNIFIED PAYMENTS INTERFACE", font=_font(14), fill=COLOR_MUTED, anchor="ma"
    )
    draw.text(
        (cx, HEIGHT - 40),
        "Demo image only - not a real financial record",
        font=_font(15),
        fill=COLOR_MUTED,
        anchor="ma",
    )

    img = _draw_watermark(img)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path
