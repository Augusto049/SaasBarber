import os
from PIL import Image, ImageDraw, ImageFont

def create_brand_pngs():
    os.makedirs("app/static/img", exist_ok=True)
    
    # 1. Favicon / App Icon (64x64 e 192x192)
    for size in [64, 192, 512]:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Círculo escuro com borda dourada
        pad = int(size * 0.05)
        draw.ellipse([pad, pad, size - pad, size - pad], fill=(15, 23, 42, 255), outline=(245, 158, 11, 255), width=max(2, int(size * 0.03)))
        
        # Coroa / Tesoura estilizada central
        cx, cy = size // 2, size // 2
        r = int(size * 0.22)
        # Borda interna sutil
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=None, outline=(253, 230, 138, 180), width=max(1, int(size * 0.015)))
        
        filename = f"app/static/img/favicon-{size}.png" if size != 64 else "app/static/img/favicon.png"
        img.save(filename)
        print(f"Gerado: {filename}")

if __name__ == "__main__":
    create_brand_pngs()
