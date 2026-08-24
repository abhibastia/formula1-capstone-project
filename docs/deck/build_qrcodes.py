"""Generate the GitHub/LinkedIn QR codes for the closing slide.

    python3 docs/deck/build_qrcodes.py

Writes docs/assets/qr_github.png and docs/assets/qr_linkedin.png. Same reason
the deck and architecture diagram are code: the URLs live here once, and a
changed profile is a one-line edit and a rerun rather than a re-scanned image.
"""

from pathlib import Path

import qrcode
from qrcode.constants import ERROR_CORRECT_M

GITHUB_URL = "https://github.com/abhibastia/formula1-capstone-project"
LINKEDIN_URL = "https://www.linkedin.com/in/abhisek-bastia/"

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def build(url: str, out: Path) -> None:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#15151E", back_color="white")
    img.save(out)
    print(f"wrote {out}")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    build(GITHUB_URL, ASSETS / "qr_github.png")
    build(LINKEDIN_URL, ASSETS / "qr_linkedin.png")


if __name__ == "__main__":
    main()
