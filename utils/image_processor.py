# utils/image_processor.py

import base64
import io
from pathlib import Path
from PIL import Image


class ImageProcessor:
    """
    Handles all image loading, validation, and preprocessing
    before sending to the Gemini vision model.
    """

    # Gemini supports up to 20MB, we keep well under that
    MAX_SIZE_MB   = 15
    MAX_DIMENSION = 4096    # pixels — Gemini handles up to this well

    SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

    def load_from_file(self, file_path: str) -> bytes:
        """Load image bytes from a file path."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        if path.suffix.lower() not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format: {path.suffix}. "
                f"Supported: {self.SUPPORTED_FORMATS}"
            )

        with open(file_path, "rb") as f:
            data = f.read()

        size_mb = len(data) / (1024 * 1024)
        if size_mb > self.MAX_SIZE_MB:
            raise ValueError(f"Image too large: {size_mb:.1f}MB (max {self.MAX_SIZE_MB}MB)")

        return data

    def preprocess(self, image_bytes: bytes, file_path: str = "") -> bytes:
        """
        Resize image if it exceeds max dimensions.
        Convert to PNG for consistent handling.
        Returns processed image bytes.
        """
        img = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if needed (handles RGBA, palette mode, etc.)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # Resize if too large while maintaining aspect ratio
        w, h = img.size
        if w > self.MAX_DIMENSION or h > self.MAX_DIMENSION:
            ratio = min(self.MAX_DIMENSION / w, self.MAX_DIMENSION / h)
            new_w, new_h = int(w * ratio), int(h * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)

        # Save as PNG bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    def to_base64(self, image_bytes: bytes) -> str:
        """Convert image bytes to base64 string."""
        return base64.b64encode(image_bytes).decode("utf-8")

    def get_image_info(self, image_bytes: bytes) -> dict:
        """Get basic metadata about the image."""
        img = Image.open(io.BytesIO(image_bytes))
        return {
            "width":   img.size[0],
            "height":  img.size[1],
            "mode":    img.mode,
            "size_kb": round(len(image_bytes) / 1024, 1),
            "format":  img.format or "PNG",
        }

    def load_and_prepare(self, file_path: str) -> dict:
        """
        Full pipeline: load → preprocess → base64 encode.
        Returns everything the visual agent needs.
        """
        raw_bytes       = self.load_from_file(file_path)
        processed_bytes = self.preprocess(raw_bytes, file_path)
        info            = self.get_image_info(processed_bytes)

        return {
            "base64":    self.to_base64(processed_bytes),
            "bytes":     processed_bytes,
            "mime_type": "image/png",
            "file_path": file_path,
            "info":      info,
        }