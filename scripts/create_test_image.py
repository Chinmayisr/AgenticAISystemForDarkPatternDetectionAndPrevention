# scripts/create_test_image.py
# Run this to generate a test image with visible dark patterns

from PIL import Image, ImageDraw, ImageFont
import os

os.makedirs("inputs", exist_ok=True)

img  = Image.new("RGB", (900, 700), color="#ffffff")
draw = ImageDraw.Draw(img)

# ── Page header ─────────────────────────────────────────────────────────
draw.rectangle([0, 0, 900, 50], fill="#232f3e")
draw.text((20, 15), "ShopNow.com - Product Page", fill="white")

# ── DP01 False Urgency banner (for reference — handled by NLP agent) ─────
draw.rectangle([0, 55, 900, 90], fill="#ff6600")
draw.text((20, 65), "⚡ FLASH SALE! Only 2 left in stock! Ends in 00:08:44", fill="white")

# ── Fake sponsored section (DP09 Disguised Ads) ──────────────────────────
draw.text((20, 110), "RECOMMENDED FOR YOU", fill="#111111")
# Three product cards — all styled identically, one tiny "Sponsored" label
for i, x in enumerate([20, 310, 600]):
    draw.rectangle([x, 130, x+270, 280], outline="#dddddd", width=1)
    draw.rectangle([x, 130, x+270, 200], fill="#f0f0f0")
    draw.text((x+10, 210), f"Product {i+1}", fill="#111111")
    draw.text((x+10, 230), f"₹{(i+1)*499}", fill="#b12704")
    if i == 1:   # tiny sponsored label — barely visible
        draw.text((x+200, 133), "Sponsored", fill="#cccccc")

# ── DP06 Interface Interference — Pre-checked boxes ──────────────────────
draw.rectangle([20, 310, 880, 430], outline="#dddddd", width=1)
draw.text((30, 320), "ORDER OPTIONS", fill="#111111")

# Pre-checked boxes with confusing labels
draw.rectangle([35, 345, 50, 360], outline="#333", width=2, fill="#0070f3")  # pre-checked
draw.text((60, 345), "Add Premium Protection Plan $4.99/month (auto-renews)", fill="#333333")

draw.rectangle([35, 375, 50, 390], outline="#333", width=2, fill="#0070f3")  # pre-checked
draw.text((60, 375), "Donate $1 to charity (pre-selected)", fill="#333333")

# Confusing opt-out label
draw.rectangle([35, 405, 50, 420], outline="#333", width=2)  # unchecked
draw.text((60, 405), "Uncheck if you do not wish to NOT receive promotional emails", fill="#333333")

# ── DP06 — Deceptive button styling ──────────────────────────────────────
draw.rectangle([20, 450, 880, 540], outline="#dddddd", width=1)
draw.text((30, 460), "CHECKOUT OPTIONS", fill="#111111")

# Big green accept
draw.rectangle([30, 480, 280, 525], fill="#e47911")
draw.text((60, 496), "Place Order →  $89.97", fill="white")

# Tiny grey decline
draw.text((310, 502), "No thanks, I don't want to save", fill="#aaaaaa")

# ── DP13 Rogue — Fake download buttons ───────────────────────────────────
draw.rectangle([0, 550, 900, 700], fill="#f8f8f8")
draw.text((20, 560), "DOWNLOAD VLC MEDIA PLAYER", fill="#111111")

# Three download buttons — classic rogue pattern
draw.rectangle([20, 585, 280, 635], fill="#4CAF50")
draw.text((55, 603), "⬇ DOWNLOAD NOW", fill="white")

draw.rectangle([310, 585, 570, 635], fill="#2196F3")
draw.text((340, 603), "⬇ Free Download", fill="white")

draw.rectangle([600, 585, 860, 635], fill="#FF5722")
draw.text((640, 603), "⬇ Get It Here", fill="white")

draw.text((20, 650), "* Note: Only the MIDDLE button is the real VLC download.", fill="#999999")

img.save("inputs/test_dark_patterns.png")
print("✅ Test image created: inputs/test_dark_patterns.png")