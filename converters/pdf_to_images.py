import tempfile
import zipfile
from pathlib import Path
from pdf2image import convert_from_path


def pdf_to_images(pdf_path: str, dpi: int = 200, fmt: str = "PNG") -> str:
    """Convert PDF pages to images. Returns path to a zip file."""
    images = convert_from_path(pdf_path, dpi=dpi)

    output_dir = Path(tempfile.mkdtemp())
    image_paths = []
    for i, img in enumerate(images):
        ext = fmt.lower()
        img_path = output_dir / f"page_{i+1:03d}.{ext}"
        img.save(str(img_path), fmt.upper())
        image_paths.append(str(img_path))

    zip_path = Path(tempfile.gettempdir()) / (Path(pdf_path).stem + "_images.zip")
    with zipfile.ZipFile(str(zip_path), "w") as zf:
        for img_path in image_paths:
            zf.write(img_path, Path(img_path).name)
    return str(zip_path)
