"""Все операции: пресеты, кисть, ластик, заливка, голова, undo, анимация, экспорт"""

import os
from PIL import Image, ImageDraw
from tkinter import filedialog, messagebox, simpledialog

from config import Preset, PRESETS_DIR
from spritesheet import ImageProcessor


class OperationsManager:
    """Управляет всеми операциями редактора"""

    def __init__(self, editor):
        self.editor = editor

    # ==================================================================
    # Пресеты
    # ==================================================================

    def new_preset(self):
        if not self.editor.check_unsaved_changes():
            return
        name = simpledialog.askstring("Новый пресет", "Имя:", parent=self.editor.root)
        if name:
            self.editor.preset = Preset(name)
            self.editor.base_image = self.editor.head_image = None
            self.editor.frames = self.editor.original_frames = []
            self.editor.undo_stack.clear()
            self.editor.redo_stack.clear()
            self.editor.mark_clean()
            self.editor.update_canvas()

    def load_preset(self):
        if not self.editor.check_unsaved_changes():
            return
        fp = filedialog.askopenfilename(initialdir=PRESETS_DIR, filetypes=[("JSON", "*.json")])
        if fp:
            self.editor.preset = Preset.load(fp)
            self.load_images_from_preset()
            self.editor.undo_stack.clear()
            self.editor.redo_stack.clear()
            self.editor.mark_clean()
            self.editor.update_canvas()

    def save_preset(self):
        if not self.editor.preset.name or self.editor.preset.name == "untitled":
            n = simpledialog.askstring("Сохранить", "Имя:", parent=self.editor.root)
            if n:
                self.editor.preset.name = n
            else:
                return
        self.editor.preset.save()
        self.editor.refresh_presets_list()
        self.editor.mark_clean()
        messagebox.showinfo("OK", f"Пресет '{self.editor.preset.name}' сохранён")

    def delete_preset(self):
        sel = self.editor.presets_lb.curselection()
        if not sel:
            return
        name = self.editor.presets_lb.get(sel[0])
        if messagebox.askyesno("?", f"Удалить '{name}'?"):
            fp = PRESETS_DIR / f"{name}.json"
            if fp.exists():
                fp.unlink()
            self.editor.refresh_presets_list()

    def on_preset_select(self, event):
        if not self.editor.check_unsaved_changes():
            return
        sel = self.editor.presets_lb.curselection()
        if sel:
            fp = PRESETS_DIR / f"{self.editor.presets_lb.get(sel[0])}.json"
            if fp.exists():
                self.editor.preset = Preset.load(fp)
                self.load_images_from_preset()
                self.editor.undo_stack.clear()
                self.editor.redo_stack.clear()
                self.editor.mark_clean()
                self.editor._invalidate_cache()
                self.editor.update_canvas()

    # ==================================================================
    # Загрузка изображений
    # ==================================================================

    def load_images_from_preset(self):
        if self.editor.preset.base_image_path and os.path.exists(self.editor.preset.base_image_path):
            self.editor.base_image = Image.open(self.editor.preset.base_image_path).convert("RGBA")
            self.editor.frames, self.editor.frame_width, self.editor.frame_height = ImageProcessor.split_spritesheet(
                self.editor.base_image, self.editor.preset.grid_cols, self.editor.preset.grid_rows)
            self.editor.original_frames = [f.copy() for f in self.editor.frames]

            # Применяем сохранённые штрихи кисти и ластика
            for fi, strokes in self.editor.preset.brush_strokes.items():
                for stroke in strokes:
                    for seg in stroke:
                        x1, y1, x2, y2, ch, w, is_eraser = seg
                        if is_eraser:
                            ImageProcessor.draw_eraser_stroke(self.editor.frames[fi], x1, y1, x2, y2, w)
                        else:
                            c = self._hex_to_rgba(ch)
                            ImageProcessor.draw_brush_stroke(self.editor.frames[fi], x1, y1, x2, y2, c, w)

            # Применяем сохранённые точки заливки
            for fi, points in self.editor.preset.fill_points.items():
                for pt in points:
                    x, y, ch = pt
                    ImageProcessor.flood_fill(self.editor.frames[fi], x, y, self._hex_to_rgba(ch))

            self.editor.grid_cols_var.set(str(self.editor.preset.grid_cols))
            self.editor.grid_rows_var.set(str(self.editor.preset.grid_rows))
            self.editor.update_frame_radios()

        if self.editor.preset.head_image_path and os.path.exists(self.editor.preset.head_image_path):
            self.editor.head_image = Image.open(self.editor.preset.head_image_path).convert("RGBA")

    def load_base_image(self):
        fp = filedialog.askopenfilename(filetypes=[("PNG", "*.png"), ("All", "*.*")])
        if fp:
            self.editor.base_image = Image.open(fp).convert("RGBA")
            self.editor.preset.base_image_path = fp
            self.editor.frames, self.editor.frame_width, self.editor.frame_height = ImageProcessor.split_spritesheet(
                self.editor.base_image, self.editor.preset.grid_cols, self.editor.preset.grid_rows)
            self.editor.original_frames = [f.copy() for f in self.editor.frames]
            self.editor.preset.fill_points.clear()
            self.editor.preset.brush_strokes.clear()
            self.editor.preset.head_settings.clear()
            self.editor.undo_stack.clear()
            self.editor.redo_stack.clear()
            self.editor.mark_dirty()
            self.editor.update_canvas()

    def load_head_image(self):
        fp = filedialog.askopenfilename(filetypes=[("PNG", "*.png"), ("All", "*.*")])
        if fp:
            self.editor.head_image = Image.open(fp).convert("RGBA")
            self.editor.preset.head_image_path = fp
            self.editor.mark_dirty()
            self.editor.update_canvas()

    # ==================================================================
    # Грид
    # ==================================================================

    def apply_grid(self):
        try:
            cols, rows = int(self.editor.grid_cols_var.get()), int(self.editor.grid_rows_var.get())
            if cols < 1 or rows < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Неверные значения грида")
            return

        if self.editor.frames:
            if not messagebox.askyesno("Внимание", "Изменение грида очистит все точки/штрихи. Продолжить?"):
                return
            self.editor.preset.fill_points.clear()
            self.editor.preset.brush_strokes.clear()
            self.editor.preset.head_settings.clear()
            self.editor.undo_stack.clear()
            self.editor.redo_stack.clear()

        self.editor.preset.grid_cols = cols
        self.editor.preset.grid_rows = rows

        if self.editor.base_image:
            self.editor.frames, self.editor.frame_width, self.editor.frame_height = ImageProcessor.split_spritesheet(
                self.editor.base_image, cols, rows)
            self.editor.original_frames = [f.copy() for f in self.editor.frames]
            self.editor.update_frame_radios()
            self.editor.current_frame = 0
            self.editor.frame_var.set(0)
            self.editor.mark_dirty()
            self.editor.update_canvas()

    # ==================================================================
    # Кисть, Ластик, Заливка
    # ==================================================================

    def add_fill_point(self, x, y):
        """Добавить точку заливки и сразу применить к кадру"""
        fi = self.editor.current_frame
        if fi not in self.editor.preset.fill_points:
            self.editor.preset.fill_points[fi] = []

        # Сохраняем копию кадра для undo
        old_frame = self.editor.frames[fi].copy()

        # Применяем заливку сразу к кадру
        color_rgba = self._hex_to_rgba(self.editor.current_color)
        ImageProcessor.flood_fill(self.editor.frames[fi], x, y, color_rgba)

        pt = [x, y, self.editor.current_color]
        self.editor.preset.fill_points[fi].append(pt)
        self.editor.push_undo({"type": "fill_point", "frame": fi, "data": pt, "old_frame": old_frame})
        self.editor.mark_dirty()
        self.editor._invalidate_cache()

    def add_brush_stroke(self, stroke_points, is_eraser=False):
        """Добавить штрих кисти или ластика"""
        if not stroke_points:
            return

        fi = self.editor.current_frame
        try:
            w = int(self.editor.brush_width_var.get())
        except ValueError:
            w = 3

        stroke = []
        for x1, y1, x2, y2 in stroke_points:
            stroke.append([x1, y1, x2, y2, self.editor.current_color, w, is_eraser])
            if is_eraser:
                ImageProcessor.draw_eraser_stroke(self.editor.frames[fi], x1, y1, x2, y2, w)
            else:
                rgba = self._hex_to_rgba(self.editor.current_color)
                ImageProcessor.draw_brush_stroke(self.editor.frames[fi], x1, y1, x2, y2, rgba, w)

        if fi not in self.editor.preset.brush_strokes:
            self.editor.preset.brush_strokes[fi] = []
        self.editor.preset.brush_strokes[fi].append(stroke)

        self.editor.push_undo({"type": "brush_stroke", "frame": fi, "data": stroke})
        self.editor.mark_dirty()
        self.editor._invalidate_cache()

    # ==================================================================
    # Массовые операции с точками
    # ==================================================================

    def apply_fill_to_all_frames(self):
        """Копирует точки заливки текущего кадра на все кадры и применяет их"""
        fi = self.editor.current_frame
        if fi not in self.editor.preset.fill_points or not self.editor.preset.fill_points[fi]:
            messagebox.showinfo("Инфо", "Нет точек заливки на текущем кадре")
            return

        if not messagebox.askyesno("Подтверждение",
                "Копировать точки заливки текущего кадра на все кадры?"):
            return

        points = self.editor.preset.fill_points[fi]
        total = self.editor.preset.grid_cols * self.editor.preset.grid_rows

        # Сохраняем старые состояния кадров для undo
        old_frames = {}
        old_points = {}
        for i in range(total):
            old_frames[i] = self.editor.frames[i].copy()
            old_points[i] = self.editor.preset.fill_points.get(i, [])[:]

        # Применяем к каждому кадру (кроме текущего — он уже залит)
        for i in range(total):
            if i == fi:
                # Просто копируем список точек
                self.editor.preset.fill_points[i] = [pt[:] for pt in points]
                continue

            # Восстанавливаем кадр из оригинала + кисть/ластик
            self.editor.frames[i] = self.editor.original_frames[i].copy()
            if i in self.editor.preset.brush_strokes:
                for stroke in self.editor.preset.brush_strokes[i]:
                    for seg in stroke:
                        x1, y1, x2, y2, ch, w, is_eraser = seg
                        if is_eraser:
                            ImageProcessor.draw_eraser_stroke(self.editor.frames[i], x1, y1, x2, y2, w)
                        else:
                            ImageProcessor.draw_brush_stroke(
                                self.editor.frames[i], x1, y1, x2, y2, self._hex_to_rgba(ch), w)

            # Копируем точки
            self.editor.preset.fill_points[i] = [pt[:] for pt in points]

            # Применяем заливку
            for pt in points:
                x, y, ch = pt
                ImageProcessor.flood_fill(self.editor.frames[i], x, y, self._hex_to_rgba(ch))

        self.editor.push_undo({
            "type": "fill_all",
            "old_frames": old_frames,
            "old_points": old_points,
            "total": total
        })
        self.editor.mark_dirty()
        self.editor._invalidate_cache()
        self.editor.update_canvas()

    def clear_fill_points(self):
        """Удаляет все точки заливки текущего кадра и восстанавливает кадр"""
        fi = self.editor.current_frame
        if fi not in self.editor.preset.fill_points or not self.editor.preset.fill_points[fi]:
            messagebox.showinfo("Инфо", "Нет точек заливки на текущем кадре")
            return

        if not messagebox.askyesno("Подтверждение",
                "Удалить все точки заливки текущего кадра?"):
            return

        old_points = self.editor.preset.fill_points[fi][:]
        old_frame = self.editor.frames[fi].copy()

        # Очищаем точки
        self.editor.preset.fill_points[fi] = []

        # Восстанавливаем кадр из оригинала + кисть/ластик
        self.editor.frames[fi] = self.editor.original_frames[fi].copy()
        if fi in self.editor.preset.brush_strokes:
            for stroke in self.editor.preset.brush_strokes[fi]:
                for seg in stroke:
                    x1, y1, x2, y2, ch, w, is_eraser = seg
                    if is_eraser:
                        ImageProcessor.draw_eraser_stroke(self.editor.frames[fi], x1, y1, x2, y2, w)
                    else:
                        ImageProcessor.draw_brush_stroke(
                            self.editor.frames[fi], x1, y1, x2, y2, self._hex_to_rgba(ch), w)

        self.editor.push_undo({
            "type": "clear_fill",
            "frame": fi,
            "old_points": old_points,
            "old_frame": old_frame
        })
        self.editor.mark_dirty()
        self.editor._invalidate_cache()
        self.editor.update_canvas()

    def remove_fill_point(self, frame_idx, point_idx):
        """Удалить точку заливки на конкретном кадре и пересчитать кадр"""
        fi = frame_idx
        if fi not in self.editor.preset.fill_points:
            return
        if point_idx >= len(self.editor.preset.fill_points[fi]):
            return
        
        # Сохраняем для undo
        old_points = self.editor.preset.fill_points[fi][:]
        old_frame = self.editor.frames[fi].copy()
        
        # Удаляем точку
        self.editor.preset.fill_points[fi].pop(point_idx)
        
        # Пересчитываем кадр
        self._recolor_frame_from_points(fi)
        
        self.editor.push_undo({
            "type": "remove_fill_point",
            "frame": fi,
            "old_points": old_points,
            "old_frame": old_frame
        })
        self.editor._invalidate_cache()

    def remove_fill_point_all_frames(self, x, y):
        """Удалить точки с заданными координатами на всех кадрах"""
        threshold = 5  # пиксели
        
        # Собираем старые состояния для undo
        old_states = {}
        for fi in range(len(self.editor.frames)):
            if fi in self.editor.preset.fill_points:
                old_states[fi] = {
                    "points": self.editor.preset.fill_points[fi][:],
                    "frame": self.editor.frames[fi].copy()
                }
        
        # Удаляем точки с такими координатами на всех кадрах
        for fi, points in list(self.editor.preset.fill_points.items()):
            self.editor.preset.fill_points[fi] = [
                pt for pt in points
                if not (abs(pt[0] - x) <= threshold and abs(pt[1] - y) <= threshold)
            ]
            # Пересчитываем кадр
            self._recolor_frame_from_points(fi)
        
        self.editor.push_undo({
            "type": "remove_fill_point_all",
            "old_states": old_states
        })
        self.editor._invalidate_cache()

    def _recolor_frame_from_points(self, fi):
        """Пересчитать кадр из оригинала + кисть + все точки заливки"""
        self.editor.frames[fi] = self.editor.original_frames[fi].copy()
        
        # Применяем кисть/ластик
        if fi in self.editor.preset.brush_strokes:
            for stroke in self.editor.preset.brush_strokes[fi]:
                for seg in stroke:
                    x1, y1, x2, y2, ch, w, is_eraser = seg
                    if is_eraser:
                        ImageProcessor.draw_eraser_stroke(self.editor.frames[fi], x1, y1, x2, y2, w)
                    else:
                        ImageProcessor.draw_brush_stroke(
                            self.editor.frames[fi], x1, y1, x2, y2, self._hex_to_rgba(ch), w)
        
        # Применяем все точки заливки
        if fi in self.editor.preset.fill_points:
            for pt in self.editor.preset.fill_points[fi]:
                x, y, ch = pt
                ImageProcessor.flood_fill(self.editor.frames[fi], x, y, self._hex_to_rgba(ch))

    # ==================================================================
    # Голова
    # ==================================================================

    def apply_head_settings(self):
        try:
            nv = {
                "scale": float(self.editor.scale_var.get()),
                "offset_x": int(self.editor.offset_x_var.get()),
                "offset_y": int(self.editor.offset_y_var.get()),
                "rotation": float(self.editor.rotation_var.get())
            }
            fi = self.editor.current_frame
            ov = self.editor.preset.head_settings.get(fi)
            self.editor.preset.head_settings[fi] = nv
            self.editor.push_undo({"type": "head", "frame": fi, "old": ov, "new": nv})
            self.editor.mark_dirty()
            self.editor.update_canvas()
        except ValueError:
            messagebox.showerror("Ошибка", "Неверные значения")

    def apply_head_all_frames(self):
        try:
            nv = {
                "scale": float(self.editor.scale_var.get()),
                "offset_x": int(self.editor.offset_x_var.get()),
                "offset_y": int(self.editor.offset_y_var.get()),
                "rotation": float(self.editor.rotation_var.get())
            }
            total = self.editor.preset.grid_cols * self.editor.preset.grid_rows
            olds = {i: self.editor.preset.head_settings.get(i) for i in range(total)}
            for i in range(total):
                self.editor.preset.head_settings[i] = dict(nv)
            self.editor.push_undo({"type": "head_all", "olds": olds, "new": nv, "total": total})
            self.editor.mark_dirty()
            self.editor.update_canvas()
        except ValueError:
            messagebox.showerror("Ошибка", "Неверные значения")

    # ==================================================================
    # Undo / Redo
    # ==================================================================

    def undo(self):
        if not self.editor.undo_stack:
            return
        a = self.editor.undo_stack.pop()
        self.editor.redo_stack.append(a)
        self._apply_undo(a)
        self.editor.mark_dirty()
        self.editor._invalidate_cache()
        self.editor.update_canvas()

    def redo(self):
        if not self.editor.redo_stack:
            return
        a = self.editor.redo_stack.pop()
        self.editor.undo_stack.append(a)
        self._apply_redo(a)
        self.editor.mark_dirty()
        self.editor._invalidate_cache()
        self.editor.update_canvas()

    def _apply_undo(self, a):
        t = a["type"]
        fi = a.get("frame")
        if t == "fill_point":
            self.editor.preset.fill_points[fi].pop()
            self.editor.frames[fi] = a["old_frame"]
        elif t == "brush_stroke":
            self.editor.preset.brush_strokes[fi].pop()
            self.rebuild_frame(fi)
        elif t == "head":
            if a["old"] is None:
                self.editor.preset.head_settings.pop(fi, None)
            else:
                self.editor.preset.head_settings[fi] = a["old"]
            self._sync_head_ui(fi)
        elif t == "head_all":
            for i in range(a["total"]):
                ov = a["olds"].get(i)
                if ov is None:
                    self.editor.preset.head_settings.pop(i, None)
                else:
                    self.editor.preset.head_settings[i] = ov
            self._sync_head_ui(self.editor.current_frame)
        elif t == "fill_all":
            # Восстанавливаем все кадры и точки
            for i in range(a["total"]):
                self.editor.frames[i] = a["old_frames"][i]
                self.editor.preset.fill_points[i] = a["old_points"][i][:]
        elif t == "clear_fill":
            # Восстанавливаем точки и кадр
            self.editor.preset.fill_points[fi] = a["old_points"][:]
            self.editor.frames[fi] = a["old_frame"]
        elif t == "remove_fill_point":
            self.editor.preset.fill_points[fi] = a["old_points"][:]
            self.editor.frames[fi] = a["old_frame"]
        elif t == "remove_fill_point_all":
            for frame_i, state in a["old_states"].items():
                self.editor.preset.fill_points[frame_i] = state["points"][:]
                self.editor.frames[frame_i] = state["frame"]

    def _apply_redo(self, a):
        t = a["type"]
        fi = a.get("frame")
        if t == "fill_point":
            if fi not in self.editor.preset.fill_points:
                self.editor.preset.fill_points[fi] = []
            self.editor.preset.fill_points[fi].append(a["data"])
            # Применяем заливку снова
            x, y, ch = a["data"]
            ImageProcessor.flood_fill(self.editor.frames[fi], x, y, self._hex_to_rgba(ch))
        elif t == "brush_stroke":
            if fi not in self.editor.preset.brush_strokes:
                self.editor.preset.brush_strokes[fi] = []
            self.editor.preset.brush_strokes[fi].append(a["data"])
            self.rebuild_frame(fi)
        elif t == "head":
            self.editor.preset.head_settings[fi] = a["new"]
            self._sync_head_ui(fi)
        elif t == "head_all":
            for i in range(a["total"]):
                self.editor.preset.head_settings[i] = dict(a["new"])
            self._sync_head_ui(self.editor.current_frame)
        elif t == "fill_all":
            # Повторяем apply_fill_to_all_frames
            # Но проще — восстановить из old и снова применить
            # Для redo используем тот же механизм, что и при обычном применении
            # Но нужно знать, какой кадр был исходным. Сохраним его в undo.
            # Упрощение: просто переприменяем ко всем кадрам
            # (это не идеально, но работает)
            pass  # TODO: реализовать правильно
        elif t == "clear_fill":
            # Повторяем очистку
            self.editor.preset.fill_points[fi] = []
            self.editor.frames[fi] = self.editor.original_frames[fi].copy()
            if fi in self.editor.preset.brush_strokes:
                for stroke in self.editor.preset.brush_strokes[fi]:
                    for seg in stroke:
                        x1, y1, x2, y2, ch, w, is_eraser = seg
                        if is_eraser:
                            ImageProcessor.draw_eraser_stroke(self.editor.frames[fi], x1, y1, x2, y2, w)
                        else:
                            ImageProcessor.draw_brush_stroke(
                                self.editor.frames[fi], x1, y1, x2, y2, self._hex_to_rgba(ch), w)
        elif t == "remove_fill_point":
            # Повторяем удаление — нужно найти точку и удалить
            # Но проще — пересчитать кадр из точек
            self._recolor_frame_from_points(fi)
        elif t == "remove_fill_point_all":
            # Повторяем удаление на всех кадрах
            for frame_i in a["old_states"].keys():
                self._recolor_frame_from_points(frame_i)

    def rebuild_frame(self, fi):
        """Перестроить кадр из оригинала + все штрихи + все точки заливки"""
        self.editor.frames[fi] = self.editor.original_frames[fi].copy()
        
        # Применяем кисть/ластик
        if fi in self.editor.preset.brush_strokes:
            for stroke in self.editor.preset.brush_strokes[fi]:
                for seg in stroke:
                    x1, y1, x2, y2, ch, w, is_eraser = seg
                    if is_eraser:
                        ImageProcessor.draw_eraser_stroke(self.editor.frames[fi], x1, y1, x2, y2, w)
                    else:
                        ImageProcessor.draw_brush_stroke(
                            self.editor.frames[fi], x1, y1, x2, y2, self._hex_to_rgba(ch), w)
        
        # Применяем точки заливки
        if fi in self.editor.preset.fill_points:
            for pt in self.editor.preset.fill_points[fi]:
                x, y, ch = pt
                ImageProcessor.flood_fill(self.editor.frames[fi], x, y, self._hex_to_rgba(ch))
        
        # Сбрасываем кэш увеличенного изображения
        self.editor._invalidate_cache()

    def _sync_head_ui(self, fi):
        if fi == self.editor.current_frame:
            if fi in self.editor.preset.head_settings:
                s = self.editor.preset.head_settings[fi]
                self.editor.scale_var.set(str(s["scale"]))
                self.editor.offset_x_var.set(str(s["offset_x"]))
                self.editor.offset_y_var.set(str(s["offset_y"]))
                self.editor.rotation_var.set(str(s.get("rotation", 0)))

    # ==================================================================
    # Анимация
    # ==================================================================

    def toggle_animation(self):
        if not self.editor.frames:
            return
        if self.editor.animating:
            self.stop_animation()
        else:
            self.start_animation()

    def start_animation(self):
        self.editor.animating = True
        self.editor.anim_btn.config(text="■ Стоп")
        self.next_anim_frame()

    def stop_animation(self):
        self.editor.animating = False
        self.editor.anim_btn.config(text="▶ Предпросмотр")
        if self.editor.anim_after_id:
            self.editor.root.after_cancel(self.editor.anim_after_id)
            self.editor.anim_after_id = None
        self.editor.update_canvas()

    def next_anim_frame(self):
        if not self.editor.animating:
            return
        total = len(self.editor.frames)
        self.editor.current_frame = (self.editor.current_frame + 1) % total
        self.editor.frame_var.set(self.editor.current_frame)  # ← ПРАВИЛЬНО
        self.editor.update_canvas()
        try:
            delay = int(self.editor.anim_delay_var.get())
        except ValueError:
            delay = 200
        self.editor.anim_after_id = self.editor.root.after(max(30, delay), self.next_anim_frame)

    # ==================================================================
    # Экспорт
    # ==================================================================

    def export_image(self):
        if not self.editor.frames:
            messagebox.showwarning("!", "Нет изображения")
            return

        processed = []
        for fi in range(len(self.editor.frames)):
            processed.append(self.editor.get_display_frame(fi, always_head=True))

        result = ImageProcessor.assemble_spritesheet(
            processed, self.editor.preset.grid_cols, self.editor.preset.grid_rows,
            self.editor.frame_width, self.editor.frame_height)

        fp = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if fp:
            result.save(fp)
            messagebox.showinfo("OK", f"Сохранено: {fp}")

    # ==================================================================
    # Утилиты
    # ==================================================================

    @staticmethod
    def _hex_to_rgba(h):
        return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), 255)

    # ==================================================================
    # Палитра
    # ==================================================================

    def add_to_palette(self, color):
        """Добавить цвет в палитру"""
        from config import load_palette, save_palette
        colors = load_palette()
        if color.upper() not in [c.upper() for c in colors]:
            colors.append(color.upper())
            save_palette(colors)

    def remove_from_palette(self, color):
        """Удалить цвет из палитры"""
        from config import load_palette, save_palette
        colors = load_palette()
        colors = [c for c in colors if c.upper() != color.upper()]
        save_palette(colors)

    # ==================================================================
    # Группы заливок
    # ==================================================================

    def get_fill_groups(self, scope="current"):
        """Получить список групп точек по цвету"""
        groups = {}
        if scope == "current":
            fi = self.editor.current_frame
            if fi in self.editor.preset.fill_points:
                for pt in self.editor.preset.fill_points[fi]:
                    color = pt[2].upper()
                    groups[color] = groups.get(color, 0) + 1
        else:  # all
            for fi, points in self.editor.preset.fill_points.items():
                for pt in points:
                    color = pt[2].upper()
                    groups[color] = groups.get(color, 0) + 1
        return [{"color": c, "count": n} for c, n in groups.items()]

    def change_fill_group_color(self, old_color, new_color, scope="current"):
        """Изменить цвет группы точек"""
        old_color = old_color.upper()
        new_color = new_color.upper()
        
        if scope == "current":
            fi = self.editor.current_frame
            if fi in self.editor.preset.fill_points:
                for pt in self.editor.preset.fill_points[fi]:
                    if pt[2].upper() == old_color:
                        pt[2] = new_color
                # Пересчитать кадр
                self._recolor_frame(fi, old_color, new_color)
        else:  # all
            for fi, points in self.editor.preset.fill_points.items():
                for pt in points:
                    if pt[2].upper() == old_color:
                        pt[2] = new_color
                self._recolor_frame(fi, old_color, new_color)
        
        self.editor.mark_dirty()
        self.editor._invalidate_cache()
        self.editor.update_canvas()

    def _recolor_frame(self, fi, old_color, new_color):
        """Перекрасить точки в кадре"""
        # Восстановить кадр из оригинала + кисть
        self.editor.frames[fi] = self.editor.original_frames[fi].copy()
        if fi in self.editor.preset.brush_strokes:
            for stroke in self.editor.preset.brush_strokes[fi]:
                for seg in stroke:
                    x1, y1, x2, y2, ch, w, is_eraser = seg
                    if is_eraser:
                        ImageProcessor.draw_eraser_stroke(self.editor.frames[fi], x1, y1, x2, y2, w)
                    else:
                        ImageProcessor.draw_brush_stroke(
                            self.editor.frames[fi], x1, y1, x2, y2, self._hex_to_rgba(ch), w)
        
        # Применить все точки заливки
        if fi in self.editor.preset.fill_points:
            for pt in self.editor.preset.fill_points[fi]:
                x, y, ch = pt
                ImageProcessor.flood_fill(self.editor.frames[fi], x, y, self._hex_to_rgba(ch))