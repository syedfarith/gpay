"""CLI: scan a UPI QR code and generate a watermarked DEMO receipt image."""

from __future__ import annotations

import argparse
from pathlib import Path

from receipt import generate_receipt
from scanner import QRScanError, scan_from_webcam, scan_image_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan a UPI QR and generate a DEMO payment receipt image.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", help="Path to an image file containing the QR code")
    source.add_argument("--webcam", action="store_true", help="Scan using the webcam")

    parser.add_argument("--camera-index", type=int, default=0, help="Webcam index (default 0)")
    parser.add_argument("--amount", type=float, default=None, help="Override/supply amount if not in the QR")
    parser.add_argument("--out", default="receipts/demo_receipt.png", help="Output image path")

    args = parser.parse_args()

    try:
        payload = scan_image_file(args.image) if args.image else scan_from_webcam(args.camera_index)
    except QRScanError as exc:
        print(f"Scan failed: {exc}")
        raise SystemExit(1)

    print(f"Decoded payee: {payload.payee_name} ({payload.payee_vpa})")
    if payload.amount:
        print(f"Amount from QR: {payload.amount}")

    try:
        out_path = generate_receipt(payload, args.amount, args.out)
    except ValueError as exc:
        print(f"Could not generate receipt: {exc}")
        print("Hint: pass --amount if the QR code has no amount encoded.")
        raise SystemExit(1)

    print(f"Demo receipt saved to: {Path(out_path).resolve()}")


if __name__ == "__main__":
    main()
