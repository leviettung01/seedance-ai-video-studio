import os
from PIL import Image, ImageDraw, ImageFilter

def create_studio_icon(size):
    # Create canvas with high resolution supersampling
    scale = 4
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Background rounded box
    corner_radius = int(canvas_size * 0.24)
    padding = int(canvas_size * 0.05)
    box = [padding, padding, canvas_size - padding, canvas_size - padding]
    
    # Outer dark background
    draw.rounded_rectangle(box, radius=corner_radius, fill=(15, 23, 42, 255), outline=(245, 158, 11, 230), width=int(scale * 1.5))
    
    # Inner subtle glow gradient
    glow_box = [padding + scale*2, padding + scale*2, canvas_size - padding - scale*2, canvas_size - padding - scale*2]
    draw.rounded_rectangle(glow_box, radius=corner_radius - scale*2, fill=(24, 18, 12, 255))

    # 2. Draw Play Triangle (Cyber Orange / Gold)
    # Triangle points
    cx = canvas_size / 2
    cy = canvas_size / 2
    r = canvas_size * 0.28
    
    p1 = (cx - r * 0.6, cy - r * 0.8)
    p2 = (cx + r * 0.9, cy)
    p3 = (cx - r * 0.6, cy + r * 0.8)
    
    draw.polygon([p1, p2, p3], fill=(255, 107, 0, 255))
    
    # 3. Draw Lightning Bolt across (Electric Amber / Gold)
    # Coordinates for lightning spark
    lx = cx + r * 0.1
    ly = cy - r * 0.1
    lw = r * 0.75
    
    bolt_points = [
        (lx + lw * 0.2, ly - lw * 0.8),
        (lx - lw * 0.4, ly),
        (lx, ly),
        (lx - lw * 0.3, ly + lw * 0.9),
        (lx + lw * 0.5, ly - lw * 0.1),
        (lx + lw * 0.1, ly - lw * 0.1),
    ]
    draw.polygon(bolt_points, fill=(254, 240, 138, 255), outline=(15, 23, 42, 255))

    # Downsample with Lanczos for ultra crisp anti-aliasing
    final_img = img.resize((size, size), Image.Resampling.LANCZOS)
    return final_img

# Output directories
dirs = [
    r"f:\Seedance\Dola_Bypass_30s_Viet_Hoa",
    r"f:\Seedance\Dola_Bypass_30s_Viet_Hoa\without watermark"
]

for d in dirs:
    os.makedirs(d, exist_ok=True)
    for s in [16, 48, 128]:
        icon = create_studio_icon(s)
        out_path = os.path.join(d, f"icon{s}.png")
        icon.save(out_path, "PNG")
        print(f"Saved {out_path}")

print("All PNG icons generated successfully!")
