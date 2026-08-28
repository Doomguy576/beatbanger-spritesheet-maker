"""Обработка изображений"""

from PIL import Image, ImageDraw, ImageFilter


class ImageProcessor:

    @staticmethod
    def split_spritesheet(image, cols, rows):
        fw = image.width // cols
        fh = image.height // rows
        frames = []
        for r in range(rows):
            for c in range(cols):
                x, y = c * fw, r * fh
                frames.append(image.crop((x, y, x + fw, y + fh)))
        return frames, fw, fh

    @staticmethod
    def assemble_spritesheet(frames, cols, rows, fw, fh):
        result = Image.new("RGBA", (cols * fw, rows * fh), (0, 0, 0, 0))
        for idx, frame in enumerate(frames):
            result.paste(frame, (idx % cols * fw, idx // cols * fh))
        return result

    @staticmethod
    def dilate_alpha(image, radius=1):
        r, g, b, a = image.split()
        return Image.merge("RGBA", (r, g, b, a.filter(ImageFilter.MaxFilter(radius * 2 + 1))))

    @staticmethod
    def flood_fill(image, x, y, color_rgba, thresh=50):
        if 0 <= x < image.width and 0 <= y < image.height:
            ImageDraw.floodfill(image, (x, y), color_rgba, thresh=thresh)
        return image

    @staticmethod
    def draw_brush_stroke(image, x1, y1, x2, y2, color_rgba, width):
        draw = ImageDraw.Draw(image)
        draw.line([(x1, y1), (x2, y2)], fill=color_rgba, width=width)
        return image

    @staticmethod
    def draw_eraser_stroke(image, x1, y1, x2, y2, width):
        """Стирает до прозрачности"""
        draw = ImageDraw.Draw(image)
        draw.line([(x1, y1), (x2, y2)], fill=(0, 0, 0, 0), width=width)
        return image

    @staticmethod
    def insert_head(base_frame, head_image, scale, offset_x, offset_y, rotation=0):
        if scale != 1.0:
            head = head_image.resize(
                (int(head_image.width * scale), int(head_image.height * scale)),
                Image.Resampling.LANCZOS)
        else:
            head = head_image
        
        # Поворот головы
        if rotation != 0:
            head = head.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)  # ← ИСПРАВЛЕНО
        
        x = (base_frame.width - head.width) // 2 + offset_x
        y = (base_frame.height - head.height) // 2 + offset_y
        temp = Image.new("RGBA", base_frame.size)
        temp.paste(head, (x, y))
        return Image.alpha_composite(base_frame, temp)