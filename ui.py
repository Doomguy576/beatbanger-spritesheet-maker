"""Интерфейс редактора спрайтшитов"""

import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
from PIL import Image, ImageTk

from config import PRESETS_DIR, CANVAS_MAX_SIZE, MAX_UNDO
from operations import OperationsManager
from spritesheet import ImageProcessor
from config import load_palette

class SpriteEditorUI:

    def __init__(self, root):
        self.root = root
        self.root.title("Sprite Editor - Beat Banger Anomalies")
        self.root.geometry("1400x900")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Состояние
        self.preset = None
        self.base_image = None
        self.head_image = None
        self.frames = []
        self.original_frames = []
        self.frame_width = 0
        self.frame_height = 0
        self.current_frame = 0
        self.current_color = "#FF0000"
        self.mode = tk.StringVar(value="fill")

        # Палитра
        self.palette = load_palette()

        # Canvas
        self.canvas = None
        self.canvas_image = None
        self.scale_factor = 1.0
        self.canvas_offset_x = 0
        self.canvas_offset_y = 0

        # Zoom/Pan
        self.zoom_level = 1.0
        self.view_x = 0
        self.view_y = 0
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.space_pressed = False
        
        # Кэш увеличенного изображения
        self._cached_image = None
        self._cached_image_size = (0, 0)
        self._canvas_image_id = None

        # Кисть/Ластик
        self.last_x = 0
        self.last_y = 0
        self.current_stroke_points = []
        self.brush_line_ids = []

        # Маски
        self.current_polygon_points = []  # Точки текущего незаконченного полигона

        # Undo/Redo
        self.undo_stack = []
        self.redo_stack = []

        # Анимация
        self.animating = False
        self.anim_after_id = None

        # Опции
        self.use_dilate = tk.BooleanVar(value=False)
        self.delete_on_all_frames = tk.BooleanVar(value=False)

        # Флаг несохранённых изменений
        self.is_dirty = False

        # Менеджер операций
        self.ops = OperationsManager(self)

        self.create_ui()

        # Горячие клавиши
        self.root.bind("<Control-z>", lambda e: self.ops.undo())
        self.root.bind("<Control-y>", lambda e: self.ops.redo())
        self.root.bind("<Control-Shift-Z>", lambda e: self.ops.redo())
        self.root.bind("<Control-s>", lambda e: self.ops.save_preset())
        self.root.bind("<space>", lambda e: self._on_space_press())
        self.root.bind("<KeyRelease-space>", lambda e: self._on_space_release())
        self.root.bind("m", lambda e: self._set_mode("mask"))
        self.root.bind("<Return>", lambda e: self._on_enter_press())
        self.root.bind("<Escape>", lambda e: self._on_escape_press())
        
        # Переключение режимов
        self.root.bind("a", lambda e: self._set_mode("fill"))
        self.root.bind("s", lambda e: self._set_mode("brush"))
        self.root.bind("d", lambda e: self._set_mode("eraser"))
        self.root.bind("f", lambda e: self._set_mode("picker"))
        
        # Zoom
        self.root.bind("<Control-plus>", lambda e: self._zoom_in())
        self.root.bind("<Control-equal>", lambda e: self._zoom_in())
        self.root.bind("<Control-minus>", lambda e: self._zoom_out())
        self.root.bind("<Control-0>", lambda e: self._zoom_reset())
        self.root.bind("<Control-1>", lambda e: self._zoom_set(1.0))
        self.root.bind("<Control-2>", lambda e: self._zoom_set(2.0))
        self.root.bind("q", lambda e: self._zoom_fit())
        
        # Предпросмотр
        self.root.bind("<space>", lambda e: self._toggle_animation_safe())

    def mark_dirty(self):
        self.is_dirty = True

    def mark_clean(self):
        self.is_dirty = False

    def check_unsaved_changes(self):
        if self.is_dirty:
            result = messagebox.askyesnocancel(
                "Несохранённые изменения",
                "Есть несохранённые изменения. Сохранить перед переключением?")
            if result is None:
                return False
            elif result:
                self.ops.save_preset()
        return True

    def push_undo(self, action):
        self.undo_stack.append(action)
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    # ==================================================================
    # UI
    # ==================================================================

    def create_ui(self):
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left = ttk.Frame(main, width=260)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        left.pack_propagate(False)
        self.create_left_panel(left)

        center = ttk.Frame(main)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.create_center_panel(center)

        right = ttk.Frame(main, width=280)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        right.pack_propagate(False)
        self.create_right_panel(right)

    def create_left_panel(self, p):
        ttk.Label(p, text="Пресеты", font=("Arial", 12, "bold")).pack(pady=5)

        lf = ttk.Frame(p)
        lf.pack(fill=tk.BOTH, expand=True, pady=5)
        self.presets_lb = tk.Listbox(lf)
        self.presets_lb.pack(fill=tk.BOTH, expand=True)
        self.presets_lb.bind("<<ListboxSelect>>", self.ops.on_preset_select)
        self.refresh_presets_list()

        bf = ttk.Frame(p)
        bf.pack(fill=tk.X, pady=5)
        for txt, cmd in [("Новый", self.ops.new_preset), ("Загрузить", self.ops.load_preset),
                         ("Сохранить", self.ops.save_preset), ("Удалить", self.ops.delete_preset)]:
            ttk.Button(bf, text=txt, command=cmd).pack(fill=tk.X, pady=2)

        ttk.Separator(p, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(p, text="Изображения", font=("Arial", 10, "bold")).pack(pady=5)
        ttk.Button(p, text="Загрузить Base Image", command=self.ops.load_base_image).pack(fill=tk.X, pady=2)
        ttk.Button(p, text="Загрузить Head Image", command=self.ops.load_head_image).pack(fill=tk.X, pady=2)

        ttk.Separator(p, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(p, text="Грид", font=("Arial", 10, "bold")).pack(pady=5)
        gf = ttk.Frame(p)
        gf.pack(fill=tk.X, pady=5)
        ttk.Label(gf, text="Кол:").pack(side=tk.LEFT, padx=2)
        self.grid_cols_var = tk.StringVar(value="3")
        ttk.Entry(gf, textvariable=self.grid_cols_var, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(gf, text="Стр:").pack(side=tk.LEFT, padx=2)
        self.grid_rows_var = tk.StringVar(value="2")
        ttk.Entry(gf, textvariable=self.grid_rows_var, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Button(gf, text="OK", command=self.ops.apply_grid).pack(side=tk.LEFT, padx=5)

        ttk.Separator(p, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Button(p, text="Экспорт PNG", command=self.ops.export_image).pack(fill=tk.X, pady=5)

    def create_center_panel(self, p):
        # Кадры
        self.frame_nav = ttk.Frame(p)
        self.frame_nav.pack(fill=tk.X, pady=5)
        ttk.Label(self.frame_nav, text="Кадр:").pack(side=tk.LEFT, padx=5)
        self.frame_var = tk.IntVar(value=0)
        self.frame_radios = []
        for i in range(6):
            rb = ttk.Radiobutton(self.frame_nav, text=str(i), variable=self.frame_var,
                                 value=i, command=self.on_frame_change)
            rb.pack(side=tk.LEFT, padx=2)
            self.frame_radios.append(rb)


        # Режимы
        mf = ttk.Frame(p)
        mf.pack(fill=tk.X, pady=5)
        ttk.Label(mf, text="Режим:").pack(side=tk.LEFT, padx=5)
        for txt, val in [("Заливка", "fill"), ("Кисть", "brush"), ("Ластик", "eraser"),
                         ("Пипетка", "picker"), ("Маска", "mask")]:
            ttk.Radiobutton(mf, text=txt, variable=self.mode, value=val,
                            command=self.on_mode_change).pack(side=tk.LEFT, padx=2)

        # Undo/Redo + Предпросмотр
        uf = ttk.Frame(p)
        uf.pack(fill=tk.X, pady=3)
        ttk.Button(uf, text="↩ Undo", command=self.ops.undo).pack(side=tk.LEFT, padx=5)
        ttk.Button(uf, text="↪ Redo", command=self.ops.redo).pack(side=tk.LEFT, padx=5)
        ttk.Separator(uf, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        self.anim_btn = ttk.Button(uf, text="▶ Предпросмотр", command=self.ops.toggle_animation)
        self.anim_btn.pack(side=tk.LEFT, padx=5)
        ttk.Label(uf, text="Задержка(мс):").pack(side=tk.LEFT, padx=5)
        self.anim_delay_var = tk.StringVar(value="200")
        ttk.Entry(uf, textvariable=self.anim_delay_var, width=6).pack(side=tk.LEFT, padx=2)

        # Zoom/Pan UI
        zoom_frame = ttk.Frame(p)
        zoom_frame.pack(fill=tk.X, pady=3)
        
        ttk.Button(zoom_frame, text="-", command=self._zoom_out, width=2).pack(side=tk.LEFT, padx=2)
        self.zoom_var = tk.StringVar(value="100%")
        ttk.Label(zoom_frame, textvariable=self.zoom_var, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="+", command=self._zoom_in, width=2).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="Сброс", command=self._zoom_reset).pack(side=tk.LEFT, padx=5)
        ttk.Button(zoom_frame, text="Вписать (Q)", command=self._zoom_fit).pack(side=tk.LEFT, padx=5)
        
        # Ползунки X/Y
        pan_frame = ttk.Frame(p)
        pan_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(pan_frame, text="X:").pack(side=tk.LEFT, padx=2)
        self.pan_x_scale = tk.Scale(pan_frame, from_=-1000, to=1000, orient=tk.HORIZONTAL,
                                     length=200, command=self._on_pan_x_change, showvalue=0)
        self.pan_x_scale.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(pan_frame, text="Y:").pack(side=tk.LEFT, padx=2)
        self.pan_y_scale = tk.Scale(pan_frame, from_=-1000, to=1000, orient=tk.HORIZONTAL,
                                     length=200, command=self._on_pan_y_change, showvalue=0)
        self.pan_y_scale.pack(side=tk.LEFT, padx=2)

        # Canvas
        self.canvas = tk.Canvas(p, bg="#404040", cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)
        self.canvas.bind("<Button-2>", self._on_pan_start)  # Средняя кнопка
        self.canvas.bind("<B2-Motion>", self._on_pan_move)
        self.canvas.bind("<ButtonRelease-2>", self._on_pan_end)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)  # Linux
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)  # Linux

    def create_right_panel(self, p):
        # Цвет
        ttk.Label(p, text="Цвет", font=("Arial", 10, "bold")).pack(pady=5)
        cf = ttk.Frame(p)
        cf.pack(fill=tk.X, pady=5)
        self.color_preview = tk.Label(cf, bg=self.current_color, width=5, relief=tk.SUNKEN)
        self.color_preview.pack(side=tk.LEFT, padx=5)
        ttk.Button(cf, text="Выбрать", command=self.choose_color).pack(side=tk.LEFT, padx=5)
        ttk.Button(cf, text="Палитра", command=self.open_palette_window).pack(side=tk.LEFT, padx=5)


        palette_frame = ttk.Frame(p)
        palette_frame.pack(fill=tk.X, pady=5)
        ttk.Label(palette_frame, text="Палитра:", font=("Arial", 9)).pack(anchor=tk.W, padx=5)

        rf = ttk.Frame(p)
        rf.pack(fill=tk.X, pady=5)
        for lbl, var, col in [("R:", "r_var", 0), ("G:", "g_var", 2), ("B:", "b_var", 4)]:
            ttk.Label(rf, text=lbl).grid(row=0, column=col, padx=2)
            sv = tk.StringVar(value="255" if col == 0 else "0")
            setattr(self, var, sv)
            ttk.Entry(rf, textvariable=sv, width=5).grid(row=0, column=col + 1, padx=2)
        ttk.Button(p, text="Применить RGB", command=self.apply_rgb).pack(pady=5)

        # Кисть/Ластик
        ttk.Separator(p, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(p, text="Кисть/Ластик", font=("Arial", 10, "bold")).pack(pady=5)
        bf = ttk.Frame(p)
        bf.pack(fill=tk.X, pady=5)
        ttk.Label(bf, text="Толщина:").pack(side=tk.LEFT, padx=5)
        self.brush_width_var = tk.StringVar(value="3")
        ttk.Entry(bf, textvariable=self.brush_width_var, width=5).pack(side=tk.LEFT, padx=5)

        # Опции
        ttk.Separator(p, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(p, text="Опции", font=("Arial", 10, "bold")).pack(pady=5)
        ttk.Checkbutton(p, text="Авто-расширение контура",
                        variable=self.use_dilate, command=self.update_canvas).pack(anchor=tk.W, padx=5)
        ttk.Checkbutton(p, text="Удалять точки на всех кадрах",
                        variable=self.delete_on_all_frames).pack(anchor=tk.W, padx=5)

        # Маски
        ttk.Separator(p, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(p, text="Маски (поверх головы)", font=("Arial", 10, "bold")).pack(pady=5)
        ttk.Label(p, text="ЛКМ — точка, Enter — замкнуть\nПКМ — удалить точку, Esc — отменить",
                  font=("Arial", 8), justify=tk.LEFT).pack(anchor=tk.W, padx=5)
        ttk.Button(p, text="Очистить маски кадра",
                   command=lambda: self.ops.clear_masks(self.current_frame)).pack(fill=tk.X, pady=2)

        # Точки заливки
        ttk.Separator(p, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(p, text="Точки заливки", font=("Arial", 10, "bold")).pack(pady=5)
        ttk.Button(p, text="Применить ко всем кадрам",
                   command=self.ops.apply_fill_to_all_frames).pack(fill=tk.X, pady=2)
        ttk.Button(p, text="Очистить точки кадра",
                   command=self.ops.clear_fill_points).pack(fill=tk.X, pady=2)
        ttk.Button(p, text="Группы заливок",
                   command=self.open_fill_groups_window).pack(fill=tk.X, pady=2)

        # Голова
        ttk.Separator(p, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(p, text="Голова", font=("Arial", 10, "bold")).pack(pady=5)
        for lbl, var, default in [("Масштаб:", "scale_var", "1.0"),
                                   ("Offset X:", "offset_x_var", "0"),
                                   ("Offset Y:", "offset_y_var", "-200"),
                                   ("Поворот (°):", "rotation_var", "0")]:
            ttk.Label(p, text=lbl).pack(anchor=tk.W, padx=5)
            sv = tk.StringVar(value=default)
            setattr(self, var, sv)
            ttk.Entry(p, textvariable=sv, width=10).pack(anchor=tk.W, padx=5, pady=2)
        ttk.Button(p, text="Применить к кадру", command=self.ops.apply_head_settings).pack(pady=5)
        ttk.Button(p, text="Применить ко всем", command=self.ops.apply_head_all_frames).pack(pady=2)

    # ==================================================================
    # Пресеты (UI)
    # ==================================================================

    def refresh_presets_list(self):
        self.presets_lb.delete(0, tk.END)
        if PRESETS_DIR.exists():
            for f in sorted(PRESETS_DIR.glob("*.json")):
                if f.name != "palette.json":  # Исключаем палитру
                    self.presets_lb.insert(tk.END, f.stem)

    def update_frame_radios(self):
        for rb in self.frame_radios:
            rb.destroy()
        self.frame_radios.clear()
        total = self.preset.grid_cols * self.preset.grid_rows
        for i in range(total):
            rb = ttk.Radiobutton(self.frame_nav, text=str(i), variable=self.frame_var,
                                 value=i, command=self.on_frame_change)
            rb.pack(side=tk.LEFT, padx=2)
            self.frame_radios.append(rb)

    # ==================================================================
    # Canvas (рендеринг)
    # ==================================================================

    def update_canvas(self, fast_pan=False):
        if not self.frames:
            return
        
        df = self.get_display_frame(self.current_frame, always_head=self.animating)
        
        # Базовый масштаб
        max_dim = max(df.width, df.height)
        base_scale = min(CANVAS_MAX_SIZE / max_dim, 1.0)
        self.scale_factor = base_scale * self.zoom_level
        
        # Размер увеличенного изображения
        nw, nh = int(df.width * self.scale_factor), int(df.height * self.scale_factor)
        
        self.canvas.update_idletasks()
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        
        # Вычисляем смещение
        self.canvas_offset_x = (cw - nw) // 2 - int(self.view_x * self.scale_factor)
        self.canvas_offset_y = (ch - nh) // 2 - int(self.view_y * self.scale_factor)
        
        # Быстрый pan — просто двигаем существующее изображение
        if fast_pan and self._canvas_image_id is not None:
            self.canvas.coords(self._canvas_image_id, self.canvas_offset_x, self.canvas_offset_y)
            self._update_markers()
            return
        
        # Полный рендер — только если изменилось содержимое или zoom
        if self._cached_image_size != (nw, nh) or self._cached_image is None:
            dr = df.resize((nw, nh), Image.Resampling.LANCZOS)
            self._cached_image = ImageTk.PhotoImage(dr)
            self._cached_image_size = (nw, nh)
            # Нужно пересоздать item на canvas
            self.canvas.delete("all")
            self._canvas_image_id = self.canvas.create_image(
                self.canvas_offset_x, self.canvas_offset_y,
                anchor=tk.NW, image=self._cached_image)
        else:
            # Изображение то же, только двигаем
            self.canvas.delete("all")
            self._canvas_image_id = self.canvas.create_image(
                self.canvas_offset_x, self.canvas_offset_y,
                anchor=tk.NW, image=self._cached_image)
        
        self._update_markers()
        
        # Обновляем UI
        self.zoom_var.set(f"{int(self.zoom_level * 100)}%")
        self.pan_x_scale.set(int(self.view_x))
        self.pan_y_scale.set(int(self.view_y))
    
    def _update_markers(self):
        """Обновить маркеры точек заливки (без перерисовки изображения)"""
        # Удаляем только маркеры (не изображение)
        for item in self.canvas.find_all():
            if item != self._canvas_image_id:
                self.canvas.delete(item)
        self.draw_points()

    def get_display_frame(self, fi, always_head=False):
        """Получить кадр для отображения"""
        source_frame = self.frames[fi].copy()
        
        if self.use_dilate.get():
            source_frame = ImageProcessor.dilate_alpha(source_frame, radius=1)
        
        # Начинаем с source_frame
        frame = source_frame.copy()
        
        # Вставляем голову поверх
        if self.head_image and fi in self.preset.head_settings:
            if always_head or fi == self.current_frame:
                s = self.preset.head_settings[fi]
                frame = ImageProcessor.insert_head(
                    frame, self.head_image,
                    s["scale"], s["offset_x"], s["offset_y"],
                    s.get("rotation", 0))
        
        # Применяем маски поверх головы
        if fi in self.preset.masks and self.preset.masks[fi]:
            frame = ImageProcessor.apply_masks(frame, source_frame, self.preset.masks[fi])
        
        return frame

    def draw_points(self):
        if self.animating:
            return
        ox, oy = self.canvas_offset_x, self.canvas_offset_y
        sf = self.scale_factor
        
        # Точки заливки
        if self.current_frame in self.preset.fill_points:
            for pt in self.preset.fill_points[self.current_frame]:
                cx = int(pt[0] * sf) + ox
                cy = int(pt[1] * sf) + oy
                self.canvas.create_oval(cx-4, cy-4, cx+4, cy+4,
                                        fill=pt[2], outline="white", width=2)
        
        # Маски текущего кадра (замкнутые полигоны)
        if self.current_frame in self.preset.masks:
            for polygon in self.preset.masks[self.current_frame]:
                if len(polygon) < 3:
                    continue
                # Полупрозрачная заливка
                screen_pts = []
                for x, y in polygon:
                    screen_pts.extend([int(x * sf) + ox, int(y * sf) + oy])
                self.canvas.create_polygon(screen_pts, outline="#00FF00",
                                           fill="#00FF00", stipple="gray25", width=2)
                # Точки полигона
                for x, y in polygon:
                    cx = int(x * sf) + ox
                    cy = int(y * sf) + oy
                    self.canvas.create_oval(cx-3, cy-3, cx+3, cy+3,
                                            fill="#00FF00", outline="white", width=1)
        
        # Текущий незаконченный полигон
        if self.current_polygon_points:
            screen_pts = []
            for x, y in self.current_polygon_points:
                screen_pts.extend([int(x * sf) + ox, int(y * sf) + oy])
            if len(screen_pts) >= 4:
                self.canvas.create_line(screen_pts, fill="#FFFF00", width=2)
            for x, y in self.current_polygon_points:
                cx = int(x * sf) + ox
                cy = int(y * sf) + oy
                self.canvas.create_oval(cx-4, cy-4, cx+4, cy+4,
                                        fill="#FFFF00", outline="white", width=2)

    def canvas_to_frame(self, ex, ey):
        # Учитываем zoom и pan
        x = int((ex - self.canvas_offset_x) / self.scale_factor)
        y = int((ey - self.canvas_offset_y) / self.scale_factor)
        return x, y

    def in_bounds(self, x, y):
        return 0 <= x < self.frame_width and 0 <= y < self.frame_height

    # ==================================================================
    # Обработчики canvas
    # ==================================================================

    def on_canvas_click(self, event):
        if not self.frames:
            return
        x, y = self.canvas_to_frame(event.x, event.y)
        if not self.in_bounds(x, y):
            return
        
        m = self.mode.get()
        if m == "fill":
            self.ops.add_fill_point(x, y)
            self.update_canvas()
        elif m == "picker":
            pixel = self.frames[self.current_frame].getpixel((x, y))
            if len(pixel) == 4 and pixel[3] > 0:
                color = f"#{pixel[0]:02X}{pixel[1]:02X}{pixel[2]:02X}"
                self.set_color(color)
        elif m == "mask":
            self.ops.add_mask_point(x, y)
            self.update_canvas()
        elif m in ("brush", "eraser"):
            self.last_x, self.last_y = x, y
            self.current_stroke_points = []

    def on_canvas_drag(self, event):
        if self.mode.get() not in ("brush", "eraser") or not self.frames:
            return
        x, y = self.canvas_to_frame(event.x, event.y)
        x = max(0, min(x, self.frame_width - 1))
        y = max(0, min(y, self.frame_height - 1))

        self.current_stroke_points.append((self.last_x, self.last_y, x, y))

        ox, oy = self.canvas_offset_x, self.canvas_offset_y
        sf = self.scale_factor
        try:
            w = int(self.brush_width_var.get())
        except ValueError:
            w = 3

        lid = self.canvas.create_line(
            self.last_x * sf + ox, self.last_y * sf + oy,
            x * sf + ox, y * sf + oy,
            fill=self.current_color, width=max(1, w * sf), capstyle=tk.ROUND)
        self.brush_line_ids.append(lid)

        self.last_x, self.last_y = x, y

    def on_canvas_release(self, event):
        if self.mode.get() not in ("brush", "eraser") or not self.frames:
            return
        if not self.current_stroke_points:
            return

        is_eraser = (self.mode.get() == "eraser")
        self.ops.add_brush_stroke(self.current_stroke_points, is_eraser=is_eraser)

        self.current_stroke_points.clear()
        self.brush_line_ids.clear()
        self.update_canvas()

    def on_canvas_right_click(self, event):
        if not self.frames:
            return
        x, y = self.canvas_to_frame(event.x, event.y)
        thresh = 15 / self.scale_factor
        
        m = self.mode.get()
        
        # В режиме маски — удаляем точки полигонов
        if m == "mask":
            best_poly, best_pt, best_d = -1, -1, float('inf')
            if self.current_frame in self.preset.masks:
                for pi, polygon in enumerate(self.preset.masks[self.current_frame]):
                    for ti, (px, py) in enumerate(polygon):
                        d = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
                        if d < best_d and d < thresh:
                            best_d, best_poly, best_pt = d, pi, ti
            
            if best_poly >= 0:
                self.ops.remove_mask_point(self.current_frame, best_poly, best_pt)
                self.update_canvas()
            return
        
        # В остальных режимах — удаляем точки заливки
        best_i, best_d = -1, float('inf')
        if self.current_frame in self.preset.fill_points:
            for i, pt in enumerate(self.preset.fill_points[self.current_frame]):
                d = ((pt[0]-x)**2 + (pt[1]-y)**2)**0.5
                if d < best_d and d < thresh:
                    best_d, best_i = d, i
        
        if best_i >= 0:
            if self.delete_on_all_frames.get():
                pt = self.preset.fill_points[self.current_frame][best_i]
                self.ops.remove_fill_point_all_frames(pt[0], pt[1])
            else:
                self.ops.remove_fill_point(self.current_frame, best_i)
            self.mark_dirty()
            self.update_canvas()

    # ==================================================================
    # Режимы и кадры
    # ==================================================================

    def on_frame_change(self):
        old_frame = self.current_frame
        self.current_frame = self.frame_var.get()
        
        # Сбрасываем кэш при смене кадра
        if old_frame != self.current_frame:
            self._invalidate_cache()
        
        if self.current_frame in self.preset.head_settings:
            s = self.preset.head_settings[self.current_frame]
            self.scale_var.set(str(s["scale"]))
            self.offset_x_var.set(str(s["offset_x"]))
            self.offset_y_var.set(str(s["offset_y"]))
            self.rotation_var.set(str(s.get("rotation", 0)))
        self.update_canvas()

    def on_mode_change(self):
        cursors = {"fill": "cross", "brush": "pencil", "eraser": "pencil",
                   "picker": "crosshair", "mask": "pencil"}
        self.canvas.config(cursor=cursors.get(self.mode.get(), "arrow"))

    # ==================================================================
    # Цвет
    # ==================================================================
    def set_color(self, color):
        """Установить цвет из палитры или пипетки"""
        self.current_color = color.upper()
        self.color_preview.config(bg=self.current_color)
        self.r_var.set(str(int(self.current_color[1:3], 16)))
        self.g_var.set(str(int(self.current_color[3:5], 16)))
        self.b_var.set(str(int(self.current_color[5:7], 16)))
    
    def choose_color(self):
        c = colorchooser.askcolor(initialcolor=self.current_color)
        if c[1]:
            self.current_color = c[1].upper()
            self.color_preview.config(bg=self.current_color)
            self.r_var.set(str(int(self.current_color[1:3], 16)))
            self.g_var.set(str(int(self.current_color[3:5], 16)))
            self.b_var.set(str(int(self.current_color[5:7], 16)))

    def apply_rgb(self):
        try:
            r, g, b = int(self.r_var.get()), int(self.g_var.get()), int(self.b_var.get())
            if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
                raise ValueError
            self.current_color = f"#{r:02X}{g:02X}{b:02X}"
            self.color_preview.config(bg=self.current_color)
        except ValueError:
            messagebox.showerror("Ошибка", "RGB 0-255")

    # ==================================================================
    # Закрытие
    # ==================================================================

    def on_close(self):
        if not self.check_unsaved_changes():
            return
        self.ops.stop_animation()
        self.root.destroy()

    # ==================================================================
    # Окно палитры
    # ==================================================================

    def open_palette_window(self):
        """Открыть окно палитры"""
        from config import save_palette
        
        win = tk.Toplevel(self.root)
        win.title("Глобальная палитра")
        win.geometry("400x300")
        win.transient(self.root)
        
        ttk.Label(win, text="Глобальная палитра", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Сетка цветов
        grid_frame = ttk.Frame(win)
        grid_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        cols = 8
        for i, color in enumerate(self.palette):
            row, col = divmod(i, cols)
            btn = tk.Label(grid_frame, bg=color, width=4, height=2,
                          relief=tk.RAISED, cursor="hand2")
            btn.grid(row=row, column=col, padx=2, pady=2)
            btn.bind("<Button-1>", lambda e, c=color: self._palette_select(c, win))
            btn.bind("<Button-3>", lambda e, c=color: self._palette_remove(c, win))
        
        # Кнопки
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="+ Добавить текущий",
                   command=lambda: self._palette_add(win)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Закрыть",
                   command=win.destroy).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(win, text="ЛКМ — выбрать, ПКМ — удалить",
                  font=("Arial", 9)).pack(pady=5)

    def _palette_select(self, color, win):
        """Выбрать цвет из палитры"""
        self.set_color(color)
        win.destroy()

    def _palette_add(self, win):
        """Добавить текущий цвет в палитру"""
        self.ops.add_to_palette(self.current_color)
        from config import load_palette
        self.palette = load_palette()
        win.destroy()
        self.open_palette_window()  # Перерисовать окно

    def _palette_remove(self, color, win):
        """Удалить цвет из палитры"""
        self.ops.remove_from_palette(color)
        from config import load_palette
        self.palette = load_palette()
        win.destroy()
        self.open_palette_window()  # Перерисовать окно

    # ==================================================================
    # Окно групп заливок
    # ==================================================================

    def open_fill_groups_window(self):
        """Открыть окно групп точек заливки"""
        if not self.frames:
            messagebox.showinfo("Инфо", "Нет изображения")
            return
        
        win = tk.Toplevel(self.root)
        win.title("Группы заливок")
        win.geometry("400x500")
        win.transient(self.root)
        
        ttk.Label(win, text="Группы заливок", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Переключатель области
        scope_var = tk.StringVar(value="current")
        sf = ttk.Frame(win)
        sf.pack(pady=5)
        ttk.Radiobutton(sf, text="Текущий кадр", variable=scope_var,
                        value="current", command=lambda: refresh_groups()).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(sf, text="Все кадры", variable=scope_var,
                        value="all", command=lambda: refresh_groups()).pack(side=tk.LEFT, padx=5)
        
        # Список групп
        list_frame = ttk.Frame(win)
        list_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        def refresh_groups():
            for w in list_frame.winfo_children():
                w.destroy()
            
            groups = self.ops.get_fill_groups(scope_var.get())
            if not groups:
                ttk.Label(list_frame, text="Нет точек заливки").pack(pady=20)
                return
            
            for g in groups:
                row = ttk.Frame(list_frame)
                row.pack(fill=tk.X, pady=2)
                
                # Цвет
                color_lbl = tk.Label(row, bg=g["color"], width=3, relief=tk.SUNKEN)
                color_lbl.pack(side=tk.LEFT, padx=5)
                
                # Информация
                ttk.Label(row, text=f"{g['color']} ({g['count']} точек)").pack(side=tk.LEFT, padx=5)
                
                # Кнопки
                ttk.Button(row, text="Выбрать",
                           command=lambda c=g["color"]: self._group_select(c, win)).pack(side=tk.LEFT, padx=2)
                ttk.Button(row, text="Изменить на текущий",
                           command=lambda c=g["color"]: self._group_recolor(c, win, scope_var.get())).pack(side=tk.LEFT, padx=2)
        
        refresh_groups()
        
        ttk.Button(win, text="Закрыть", command=win.destroy).pack(pady=10)

    def _group_select(self, color, win):
        """Выбрать цвет группы как текущий"""
        self.set_color(color)
        win.destroy()

    def _group_recolor(self, old_color, win, scope):
        """Изменить цвет группы на текущий"""
        self.ops.change_fill_group_color(old_color, self.current_color, scope)
        win.destroy()
        self.open_fill_groups_window()  # Перерисовать окно

    # ==================================================================
    # Горячие клавиши - вспомогательные методы
    # ==================================================================

    def _set_mode(self, mode):
        """Установить режим из горячей клавиши"""
        focused = self.root.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry)):
            return
        self.mode.set(mode)
        self.on_mode_change()

    def _toggle_animation_safe(self):
        """Безопасное переключение анимации (игнорирует пробел в полях ввода)"""
        # Проверяем, не находится ли фокус в поле ввода
        focused_widget = self.root.focus_get()
        if isinstance(focused_widget, (tk.Entry, ttk.Entry)):
            return  # Не переключаем анимацию, если фокус в поле ввода
        
        self.ops.toggle_animation()

    # ==================================================================
    # Zoom/Pan
    # ==================================================================

    def _zoom_in(self):
        if self.zoom_level < 16.0:
            self.zoom_level *= 2.0
            self._invalidate_cache()
            self.update_canvas()

    def _zoom_out(self):
        if self.zoom_level > 0.25:
            self.zoom_level /= 2.0
            self._invalidate_cache()
            self.update_canvas()

    def _zoom_reset(self):
        self.zoom_level = 1.0
        self.view_x = 0
        self.view_y = 0
        self._invalidate_cache()
        self.update_canvas()

    def _zoom_fit(self):
        if not self.frames:
            return
        self.zoom_level = 1.0
        self.view_x = 0
        self.view_y = 0
        self._invalidate_cache()
        self.update_canvas()

    def _invalidate_cache(self):
        """Сбросить кэш — вызвать при любом изменении содержимого кадра"""
        self._cached_image = None
        self._cached_image_size = (0, 0)

    def _on_pan_x_change(self, value):
        """Ползунок X"""
        self.view_x = int(value)
        self.update_canvas(fast_pan=True)

    def _on_pan_y_change(self, value):
        """Ползунок Y"""
        self.view_y = int(value)
        self.update_canvas(fast_pan=True)

    def _on_space_press(self):
        focused = self.root.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry)):
            return
        self.space_pressed = True
        self.canvas.config(cursor="fleur")

    def _on_space_release(self):
        self.space_pressed = False
        self.on_mode_change()

    def _on_pan_start(self, event):
        self.is_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.canvas.config(cursor="fleur")

    def _on_pan_move(self, event):
        if not self.is_panning:
            return
        
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        
        self.view_x -= dx / self.scale_factor
        self.view_y -= dy / self.scale_factor
        
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        
        # Быстрый pan — без перерисовки изображения
        self.canvas_offset_x += dx
        self.canvas_offset_y += dy
        self.update_canvas(fast_pan=True)

    def _on_pan_end(self, event):
        self.is_panning = False
        self.on_mode_change()

    def _on_mouse_wheel(self, event):
        # Определяем направление
        if event.num == 4 or event.delta > 0:
            factor = 2.0
        elif event.num == 5 or event.delta < 0:
            factor = 0.5
        else:
            return
        
        if factor > 1 and self.zoom_level >= 16.0:
            return
        if factor < 1 and self.zoom_level <= 0.25:
            return
        
        self._zoom_to_cursor(event.x, event.y, factor)

    def _zoom_to_cursor(self, cx, cy, factor):
        """Zoom к курсору — точка под курсором остаётся на том же месте экрана"""
        # Координаты курсора в пикселях кадра (ДО зума)
        fx = (cx - self.canvas_offset_x) / self.scale_factor
        fy = (cy - self.canvas_offset_y) / self.scale_factor
        
        # Меняем zoom
        self.zoom_level *= factor
        self._invalidate_cache()
        
        # Пересчитываем scale_factor
        df = self.get_display_frame(self.current_frame, always_head=self.animating)
        max_dim = max(df.width, df.height)
        base_scale = min(CANVAS_MAX_SIZE / max_dim, 1.0)
        new_scale = base_scale * self.zoom_level
        
        self.canvas.update_idletasks()
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        
        # После зума курсор должен остаться над той же точкой кадра (fx, fy)
        # canvas_x = (cw - nw)/2 - view_x * new_scale + fx * new_scale
        # Приравниваем canvas_x = cx:
        # cx = (cw - nw)/2 - view_x * new_scale + fx * new_scale
        # view_x = fx - (cx - (cw - nw)/2) / new_scale
        
        nw = int(df.width * new_scale)
        nh = int(df.height * new_scale)
        
        self.view_x = fx - (cx - (cw - nw) / 2) / new_scale
        self.view_y = fy - (cy - (ch - nh) / 2) / new_scale
        
        self.update_canvas()
    # ==================================================================
    # Маски — вспомогательные методы
    # ==================================================================

    def _on_enter_press(self):
        """Enter — замкнуть текущий полигон маски"""
        focused = self.root.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry)):
            return
        if self.mode.get() != "mask":
            return
        if self.ops.close_polygon():
            self.update_canvas()

    def _on_escape_press(self):
        """Esc — отменить текущий полигон"""
        focused = self.root.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry)):
            return
        self.ops.cancel_current_polygon()