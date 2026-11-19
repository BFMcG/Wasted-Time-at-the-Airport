from pathlib import Path
from PIL import Image

class WebpConverter:
    '''
    Shrinks images and saves them as Webp files.
    '''

    def __init__(self, max_width, max_height, lossless=True):
        self.max_size = (max_width, max_height)
        self.lossless = lossless

    def convert_file(self, src):
        dest = src.with_suffix(".webp")
        with Image.open(src) as img:
            img = img.convert("RGBA")
            img.thumbnail(self.max_size, Image.Resampling.LANCZOS)
            img.save(dest, "WEBP", lossless=self.lossless, method=6)
        return dest

    def convert_folder(self, folder):
        for src in sorted(folder.glob("*.png")):
            dest = self.convert_file(src)
            before = src.stat().st_size / 1024
            after = dest.stat().st_size / 1024
            print(f"{src.name}: {before:,.0f} KB -> {after:,.1f} KB")

if __name__ == "__main__":
    images = Path(__file__).parent / "images"
    WebpConverter(512, 352).convert_folder(images / "full_name")
    WebpConverter(400, 68).convert_folder(images / "logo")