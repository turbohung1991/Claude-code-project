from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS


def get_image_info(image_path: str) -> str:
    """Extract image metadata and return formatted text."""
    img = Image.open(image_path)
    lines = [
        f"文件名: {Path(image_path).name}",
        f"格式: {img.format}",
        f"模式: {img.mode}",
        f"尺寸: {img.width} x {img.height} px",
        f"文件大小: {Path(image_path).stat().st_size:,} bytes",
    ]

    dpi = img.info.get("dpi")
    if dpi:
        lines.append(f"DPI: {dpi[0]:.0f} x {dpi[1]:.0f}")

    exif_data = img._getexif()
    if exif_data:
        lines.append("\n--- EXIF 信息 ---")
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)
            if len(str(value)) > 200:
                value = str(value)[:200] + "..."
            lines.append(f"  {tag_name}: {value}")

    return "\n".join(lines)
