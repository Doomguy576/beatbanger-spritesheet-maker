"""Константы и класс Preset"""

import json
from pathlib import Path

PRESETS_DIR = Path("presets")
PALETTE_FILE = PRESETS_DIR / "palette.json"
DEFAULT_GRID = (3, 2)
CANVAS_MAX_SIZE = 800
MAX_UNDO = 100


def load_palette():
    """Загрузить палитру из файла"""
    if PALETTE_FILE.exists():
        try:
            with open(PALETTE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []


def save_palette(colors):
    """Сохранить палитру в файл"""
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(PALETTE_FILE, 'w', encoding='utf-8') as f:
        json.dump(colors, f, indent=2)


class Preset:
    def __init__(self, name="untitled"):
        self.name = name
        self.base_image_path = None
        self.head_image_path = None
        self.grid_cols = DEFAULT_GRID[0]
        self.grid_rows = DEFAULT_GRID[1]
        self.frame_width = 0
        self.frame_height = 0
        self.fill_points = {}
        self.head_settings = {}
        self.brush_strokes = {}
        # Маски: {frame_idx: [[(x1,y1), (x2,y2), ...], ...]}
        self.masks = {}

    def to_dict(self):
        return {
            "name": self.name,
            "base_image_path": str(self.base_image_path) if self.base_image_path else None,
            "head_image_path": str(self.head_image_path) if self.head_image_path else None,
            "grid_cols": self.grid_cols,
            "grid_rows": self.grid_rows,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "fill_points": self.fill_points,
            "head_settings": self.head_settings,
            "brush_strokes": self.brush_strokes,
            "masks": self.masks
        }

    @classmethod
    def from_dict(cls, data):
        p = cls(data.get("name", "untitled"))
        p.base_image_path = data.get("base_image_path")
        p.head_image_path = data.get("head_image_path")
        p.grid_cols = data.get("grid_cols", DEFAULT_GRID[0])
        p.grid_rows = data.get("grid_rows", DEFAULT_GRID[1])
        p.frame_width = data.get("frame_width", 0)
        p.frame_height = data.get("frame_height", 0)
        p.fill_points = {int(k): v for k, v in data.get("fill_points", {}).items()}
        p.head_settings = {int(k): v for k, v in data.get("head_settings", {}).items()}
        p.brush_strokes = {int(k): v for k, v in data.get("brush_strokes", {}).items()}
        # Обратная совместимость — старые пресеты без masks
        raw_masks = data.get("masks", {})
        p.masks = {}
        for k, polygons in raw_masks.items():
            p.masks[int(k)] = [[tuple(pt) for pt in poly] for poly in polygons]
        return p

    def save(self, filepath=None):
        if filepath is None:
            filepath = PRESETS_DIR / f"{self.name}.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))