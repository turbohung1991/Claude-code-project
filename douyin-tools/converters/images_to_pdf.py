import os
from pathlib import Path
from PIL import Image


def images_to_pdf(image_paths: list[str]) -> str:
    """Combine multiple images into a single PDF."""
    images = []
    for path in image_paths:
        img = Image.open(path)
        if img.mode in ("RGBA", "PA", "LA"):
            background = Image.new("RGB", img.size, "white")
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[3])
            elif img.mode == "PA":
                background.paste(img, mask=img.split()[1])
            else:
                background.paste(img)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")
        images.append(img)

    output_path = str(Path(image_paths[0]).with_suffix("")) + "_combined.pdf"
    first = images[0]
    rest = images[1:] if len(images) > 1 else []
    first.save(output_path, "PDF", save_all=True, append_images=rest)
    return output_path
