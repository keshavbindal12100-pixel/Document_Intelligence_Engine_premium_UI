import cv2
import numpy as np
from PIL import Image


class ImageProcessor:
    """Production image enhancement pipeline for OCR accuracy optimization."""

    @staticmethod
    def load_image(image_input: bytes | Image.Image | np.ndarray) -> np.ndarray:
        """Convert input bytes, PIL Image, or ndarray into a BGR/Grayscale OpenCV numpy array."""
        if isinstance(image_input, bytes):
            image_array = np.frombuffer(image_input, dtype=np.uint8)
            img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Failed to decode image from bytes.")
            return img
        elif isinstance(image_input, Image.Image):
            rgb = image_input.convert("RGB")
            return cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
        elif isinstance(image_input, np.ndarray):
            return image_input.copy()
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

    @staticmethod
    def to_pil_image(image_cv: np.ndarray) -> Image.Image:
        """Convert OpenCV image array to PIL Image."""
        if len(image_cv.shape) == 2:
            return Image.fromarray(image_cv)
        elif len(image_cv.shape) == 3 and image_cv.shape[2] == 3:
            rgb = cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB)
            return Image.fromarray(rgb)
        elif len(image_cv.shape) == 3 and image_cv.shape[2] == 4:
            rgba = cv2.cvtColor(image_cv, cv2.COLOR_BGRA2RGBA)
            return Image.fromarray(rgba)
        return Image.fromarray(image_cv)

    def to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """Convert image to single-channel grayscale if not already."""
        if len(image.shape) == 2:
            return image
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def resize_for_ocr(
        self,
        image: np.ndarray,
        min_width: int = 1200,
        max_width: int = 3500,
    ) -> np.ndarray:
        """Resize image to an optimal DPI resolution for Tesseract OCR."""
        height, width = image.shape[:2]
        if width < min_width:
            scale = min_width / float(width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        elif width > max_width:
            scale = max_width / float(width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        return image

    def reduce_noise(self, gray_image: np.ndarray) -> np.ndarray:
        """Apply noise reduction using fast bilateral filter or Gaussian blur."""
        return cv2.bilateralFilter(gray_image, d=7, sigmaColor=50, sigmaSpace=50)

    def enhance_contrast(self, gray_image: np.ndarray) -> np.ndarray:
        """Enhance local contrast using Contrast Limited Adaptive Histogram Equalization (CLAHE)."""
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray_image)

    def calculate_skew_angle(self, gray_image: np.ndarray) -> float:
        """Calculate skew angle of text lines using minAreaRect on foreground contours."""
        # Invert colors: text as foreground white
        thresh = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 100:
            return 0.0

        rect = cv2.minAreaRect(coords)
        angle = rect[-1]

        # OpenCV minAreaRect returns angle in [-90, 0)
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # If angle is negligible (< 0.5 degrees), do not rotate
        if abs(angle) < 0.5 or abs(angle) > 45:
            return 0.0

        return angle

    def rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """Rotate image by angle in degrees around center with white background padding."""
        if abs(angle) < 0.1:
            return image

        height, width = image.shape[:2]
        center = (width // 2, height // 2)

        rot_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        cos = np.abs(rot_matrix[0, 0])
        sin = np.abs(rot_matrix[0, 1])

        new_width = int((height * sin) + (width * cos))
        new_height = int((height * cos) + (width * sin))

        rot_matrix[0, 2] += (new_width / 2) - center[0]
        rot_matrix[1, 2] += (new_height / 2) - center[1]

        border_value = 255 if len(image.shape) == 2 else (255, 255, 255)
        return cv2.warpAffine(
            image,
            rot_matrix,
            (new_width, new_height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=border_value,
        )

    def deskew(self, gray_image: np.ndarray) -> np.ndarray:
        """Detect and correct skew orientation."""
        angle = self.calculate_skew_angle(gray_image)
        if abs(angle) > 0.5:
            return self.rotate_image(gray_image, angle)
        return gray_image

    def apply_threshold(self, gray_image: np.ndarray, method: str = "otsu") -> np.ndarray:
        """Binarize grayscale image to high-contrast black & white."""
        if method == "adaptive":
            return cv2.adaptiveThreshold(
                gray_image,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=15,
                C=8,
            )
        # Default Otsu thresholding
        _, binary = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    def crop_borders(self, image: np.ndarray, margin: int = 8) -> np.ndarray:
        """Crop large empty or black scanner borders from document edge."""
        gray = self.to_grayscale(image)
        border_pixels = np.concatenate([gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]])
        mean_border = float(np.mean(border_pixels))

        # A white page can contain several disconnected text/table regions. A
        # contour union on that page can collapse the crop to one large table
        # row (or barcode), losing the invoice header. Only crop when there is
        # clear evidence of a dark scanner border around the document.
        if mean_border >= 100:
            return image
        _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return image

        x_min, y_min = image.shape[1], image.shape[0]
        x_max, y_max = 0, 0
        min_area = (image.shape[0] * image.shape[1]) * 0.0005

        found_valid = False
        for cnt in contours:
            if cv2.contourArea(cnt) > min_area:
                x, y, w, h = cv2.boundingRect(cnt)
                x_min = min(x_min, x)
                y_min = min(y_min, y)
                x_max = max(x_max, x + w)
                y_max = max(y_max, y + h)
                found_valid = True

        if not found_valid:
            return image

        x1 = max(0, x_min - margin)
        y1 = max(0, y_min - margin)
        x2 = min(image.shape[1], x_max + margin)
        y2 = min(image.shape[0], y_max + margin)

        if (x2 - x1) > 50 and (y2 - y1) > 50:
            return image[y1:y2, x1:x2]
        return image

    def preprocess_pipeline(
        self,
        image_input: bytes | Image.Image | np.ndarray,
        apply_binarization: bool = True,
        auto_crop: bool = True,
        auto_deskew: bool = True,
    ) -> tuple[np.ndarray, Image.Image]:
        """Execute full preprocessing pipeline.
        Returns: (OpenCV ndarray, PIL Image)
        """
        img = self.load_image(image_input)
        img_resized = self.resize_for_ocr(img)
        gray = self.to_grayscale(img_resized)

        # Contrast enhancement
        enhanced = self.enhance_contrast(gray)

        # Noise reduction
        denoised = self.reduce_noise(enhanced)

        # Deskewing
        processed = self.deskew(denoised) if auto_deskew else denoised

        # Cropping
        if auto_crop:
            processed = self.crop_borders(processed)

        # Binarization
        if apply_binarization:
            final_cv = self.apply_threshold(processed, method="otsu")
        else:
            final_cv = processed

        pil_image = self.to_pil_image(final_cv)
        return final_cv, pil_image


image_processor = ImageProcessor()
