import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import os
import tempfile
import cv2
from PIL import Image, ImageTk
from typing import List, Optional, Tuple, Callable, Dict

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame

from pyvoice.core.video import get_media_duration_seconds
from pyvoice.core.video_tools import (
    TimelineClip, 
    export_timeline_clips, 
    extract_audio_track
)

def format_time_str(seconds: float) -> str:
    """Форматує секунди у MM:SS.m"""
    m = int(seconds // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 10)
    return f"{m:02d}:{s:02d}.{ms}"

class TimelineVideoEditorWindow(tk.Toplevel):
    """
    Повнофункціональний візуальний відеомонтажер:
    - Плавне відтворення відео у реальному часі (30-60 FPS)
    - Синхронізована аудіодоріжка (звук з відео через pygame.mixer)
    - Графічний таймлайн із ножицями (Split) та зміною порядку фрагментів
    - Анімація лоадінгу всередині кнопки 'Експорт'
    """
    def __init__(self, parent, initial_video_path: str = "", on_use_video_callback: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.title("🎬 Візуальний Відео-Монтажер з Таймлайном та Звуком - PyVoice AI")
        self.geometry("980x720")
        self.minsize(850, 600)
        self.resizable(True, True)
        
        self.parent = parent
        self.on_use_video_callback = on_use_video_callback
        
        # Ініціалізація аудіоплеєра
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        except Exception:
            pass

        # Центрування вікна
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 490
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 360
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        # Стан таймлайну
        self.clips: List[TimelineClip] = []
        self.selected_clip_idx: Optional[int] = None
        self.current_time_sec: float = 0.0
        self.is_playing: bool = False
        self.is_exporting: bool = False
        
        # Кеш відео та аудіо
        self.current_cap: Optional[cv2.VideoCapture] = None
        self.current_cap_file: str = ""
        self.current_photo_image = None
        self.audio_cache: Dict[str, str] = {}
        self.temp_audio_dir = tempfile.mkdtemp()
        
        # Синхронізація відтворення у реальному часі
        self.play_start_real_time: float = 0.0
        self.play_start_video_time: float = 0.0
        self.active_playing_clip_idx: Optional[int] = None

        # Параметри таймлайну
        self.timeline_scale = 10.0  # пікселів на секунду
        self.is_scrubbing = False

        self.create_ui()

        # Якщо передано початкове відео — додаємо його на таймлайн
        if initial_video_path and os.path.exists(initial_video_path):
            self.add_clip_to_timeline(initial_video_path)

        # Гарячі клавіші
        self.bind("<space>", lambda e: self.toggle_play())
        self.bind("<s>", lambda e: self.split_at_playhead())
        self.bind("<Delete>", lambda e: self.delete_selected_clip())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.lift()
        self.focus_force()

    def create_ui(self):
        # 1. Верхня панель інструментів (Toolbar)
        toolbar = ttk.Frame(self, padding="6")
        toolbar.pack(fill=tk.X, side=tk.TOP)

        ttk.Button(toolbar, text="➕ Додати відео на таймлайн", command=self.browse_add_videos).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="✂️ Розрізати по курсору (S)", command=self.split_at_playhead).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="🗑 Видалити фрагмент (Del)", command=self.delete_selected_clip).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="⬅ Вліво", command=self.move_clip_left).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(toolbar, text="➡ Вправо", command=self.move_clip_right).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(toolbar, text="🧹 Очистити таймлайн", command=self.clear_timeline).pack(side=tk.LEFT)

        # Кнопка 'Експорт' з лаконічною назвою
        self.btn_export = ttk.Button(toolbar, text="💾 Експорт", command=self.export_timeline)
        self.btn_export.pack(side=tk.RIGHT)

        # 2. Центральна область: Відеоплеєр
        player_container = tk.Frame(self, bg="#181818")
        player_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 6))

        self.video_canvas = tk.Label(
            player_container, 
            bg="#111111", 
            text="🎬 Додайте відео для початку монтажу на таймлайні\n\n(Керування: Пробіл - Play/Pause, S - Ножиці, Del - Видалити)", 
            fg="#888888",
            font=("Segoe UI", 11)
        )
        self.video_canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        controls_frame = tk.Frame(player_container, bg="#222222", height=40)
        controls_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=4, pady=(0, 4))

        self.time_label = tk.Label(
            controls_frame, 
            text="⏱ 00:00.0 / 00:00.0", 
            font=("Consolas", 11, "bold"), 
            bg="#222222", 
            fg="#00e5ff"
        )
        self.time_label.pack(side=tk.LEFT, padx=10)

        center_btns = tk.Frame(controls_frame, bg="#222222")
        center_btns.pack(side=tk.LEFT, expand=True)

        tk.Button(center_btns, text="⏮ На початок", bg="#333333", fg="#ffffff", relief="flat", command=self.seek_start).pack(side=tk.LEFT, padx=2)
        tk.Button(center_btns, text="⏪ -1с", bg="#333333", fg="#ffffff", relief="flat", command=lambda: self.seek_relative(-1.0)).pack(side=tk.LEFT, padx=2)
        
        self.btn_play = tk.Button(center_btns, text=" ▶ ВІДТВОРИТИ ", bg="#0078d7", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief="flat", command=self.toggle_play)
        self.btn_play.pack(side=tk.LEFT, padx=6)

        tk.Button(center_btns, text="⏩ +1с", bg="#333333", fg="#ffffff", relief="flat", command=lambda: self.seek_relative(1.0)).pack(side=tk.LEFT, padx=2)
        tk.Button(center_btns, text="⏭ В кінець", bg="#333333", fg="#ffffff", relief="flat", command=self.seek_end).pack(side=tk.LEFT, padx=2)

        self.clip_info_label = tk.Label(
            controls_frame, 
            text="Фрагментів: 0", 
            font=("Segoe UI", 9), 
            bg="#222222", 
            fg="#cccccc"
        )
        self.clip_info_label.pack(side=tk.RIGHT, padx=10)

        # 3. Нижня область: Інтерактивний Таймлайн
        timeline_outer = ttk.LabelFrame(self, text=" 🎞️ Візуальний Таймлайн (Клікніть для переходу, тягніть червоний повзунок, 'S' - розрізати) ", padding="6")
        timeline_outer.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(0, 10))

        timeline_scroll_frame = ttk.Frame(timeline_outer)
        timeline_scroll_frame.pack(fill=tk.X, expand=True)

        self.timeline_hscroll = ttk.Scrollbar(timeline_scroll_frame, orient=tk.HORIZONTAL)
        self.timeline_hscroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.timeline_canvas = tk.Canvas(
            timeline_scroll_frame, 
            height=110, 
            bg="#1c1c1c", 
            highlightthickness=0,
            xscrollcommand=self.timeline_hscroll.set
        )
        self.timeline_canvas.pack(fill=tk.X, expand=True)
        self.timeline_hscroll.config(command=self.timeline_canvas.xview)

        self.timeline_canvas.bind("<Button-1>", self.on_timeline_click)
        self.timeline_canvas.bind("<B1-Motion>", self.on_timeline_drag)
        self.timeline_canvas.bind("<ButtonRelease-1>", self.on_timeline_release)

    # -------------------------------------------------------------
    # Управління таймлайном та кліпами
    # -------------------------------------------------------------
    def get_total_duration(self) -> float:
        return sum(clip.duration for clip in self.clips)

    def browse_add_videos(self):
        files = filedialog.askopenfilenames(
            parent=self,
            title="Оберіть одне або декілька відео для таймлайну",
            filetypes=[("Відео файли", "*.mp4 *.avi *.mov *.mkv")]
        )
        self.lift()
        self.focus_force()
        for f in files:
            self.add_clip_to_timeline(f)

    def add_clip_to_timeline(self, video_path: str):
        try:
            dur = get_media_duration_seconds(video_path)
            clip = TimelineClip(file_path=video_path, start_sec=0.0, end_sec=dur)
            self.clips.append(clip)
            if self.selected_clip_idx is None:
                self.selected_clip_idx = len(self.clips) - 1
                
            if video_path not in self.audio_cache:
                wav_file = os.path.join(self.temp_audio_dir, f"audio_{len(self.audio_cache)}.wav")
                threading.Thread(target=self._extract_audio_async, args=(video_path, wav_file), daemon=True).start()

            self.redraw_timeline()
            self.update_preview_frame(force_seek=True)
        except Exception as e:
            messagebox.showerror("Помилка відео", f"Не вдалося відкрити {os.path.basename(video_path)}:\n{str(e)}", parent=self)

    def _extract_audio_async(self, video_path: str, wav_path: str):
        if extract_audio_track(video_path, wav_path):
            self.audio_cache[video_path] = wav_path

    def delete_selected_clip(self):
        if self.selected_clip_idx is not None and 0 <= self.selected_clip_idx < len(self.clips):
            self.stop_audio()
            del self.clips[self.selected_clip_idx]
            if self.clips:
                self.selected_clip_idx = min(self.selected_clip_idx, len(self.clips) - 1)
            else:
                self.selected_clip_idx = None
            self.current_time_sec = min(self.current_time_sec, self.get_total_duration())
            self.redraw_timeline()
            self.update_preview_frame(force_seek=True)

    def move_clip_left(self):
        if self.selected_clip_idx is not None and self.selected_clip_idx > 0:
            self.stop_audio()
            idx = self.selected_clip_idx
            self.clips[idx], self.clips[idx - 1] = self.clips[idx - 1], self.clips[idx]
            self.selected_clip_idx = idx - 1
            self.redraw_timeline()
            self.update_preview_frame(force_seek=True)

    def move_clip_right(self):
        if self.selected_clip_idx is not None and self.selected_clip_idx < len(self.clips) - 1:
            self.stop_audio()
            idx = self.selected_clip_idx
            self.clips[idx], self.clips[idx + 1] = self.clips[idx + 1], self.clips[idx]
            self.selected_clip_idx = idx + 1
            self.redraw_timeline()
            self.update_preview_frame(force_seek=True)

    def clear_timeline(self):
        if self.clips and messagebox.askyesno("Очистити таймлайн", "Видалити всі відео з таймлайну?", parent=self):
            self.stop_audio()
            self.clips.clear()
            self.selected_clip_idx = None
            self.current_time_sec = 0.0
            self.redraw_timeline()
            self.update_preview_frame(force_seek=True)

    def split_at_playhead(self):
        """Ножиці: Розрізає фрагмент під поточним положенням червоного повзунка"""
        if not self.clips:
            return

        res = self.map_timeline_time_to_clip(self.current_time_sec)
        if not res:
            return
            
        clip_idx, local_time = res
        clip = self.clips[clip_idx]

        if local_time - clip.start_sec < 0.15 or clip.end_sec - local_time < 0.15:
            return

        self.stop_audio()
        clip1 = TimelineClip(file_path=clip.file_path, start_sec=clip.start_sec, end_sec=local_time)
        clip2 = TimelineClip(file_path=clip.file_path, start_sec=local_time, end_sec=clip.end_sec)

        self.clips[clip_idx:clip_idx+1] = [clip1, clip2]
        self.selected_clip_idx = clip_idx + 1
        self.redraw_timeline()
        self.update_preview_frame(force_seek=True)

    # -------------------------------------------------------------
    # Мапінг часу та відтворення
    # -------------------------------------------------------------
    def map_timeline_time_to_clip(self, timeline_sec: float) -> Optional[Tuple[int, float]]:
        accum = 0.0
        for idx, clip in enumerate(self.clips):
            dur = clip.duration
            if accum <= timeline_sec <= accum + dur:
                offset_inside = timeline_sec - accum
                return idx, clip.start_sec + offset_inside
            accum += dur
        if self.clips:
            last_idx = len(self.clips) - 1
            return last_idx, self.clips[last_idx].end_sec
        return None

    def toggle_play(self):
        if not self.clips:
            return
        self.is_playing = not self.is_playing
        if self.is_playing:
            total_dur = self.get_total_duration()
            if self.current_time_sec >= total_dur:
                self.current_time_sec = 0.0

            self.play_start_real_time = time.perf_counter()
            self.play_start_video_time = self.current_time_sec
            self.active_playing_clip_idx = None
            
            self.btn_play.config(text=" ⏸ ПАУЗА ", bg="#e67e22")
            self.start_audio_for_current_position()
            self.play_loop()
        else:
            self.btn_play.config(text=" ▶ ВІДТВОРИТИ ", bg="#0078d7")
            self.stop_audio()

    def start_audio_for_current_position(self):
        res = self.map_timeline_time_to_clip(self.current_time_sec)
        if not res:
            return
        clip_idx, source_time = res
        clip = self.clips[clip_idx]
        wav_file = self.audio_cache.get(clip.file_path)

        if wav_file and os.path.exists(wav_file):
            try:
                pygame.mixer.music.load(wav_file)
                pygame.mixer.music.play(start=source_time)
                self.active_playing_clip_idx = clip_idx
            except Exception:
                pass

    def stop_audio(self):
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

    def play_loop(self):
        if not self.is_playing:
            return

        total_dur = self.get_total_duration()
        now = time.perf_counter()
        elapsed = now - self.play_start_real_time
        target_time = self.play_start_video_time + elapsed

        if target_time >= total_dur:
            self.current_time_sec = total_dur
            self.toggle_play()
            self.redraw_timeline()
            self.update_preview_frame(force_seek=True)
            return

        self.current_time_sec = target_time

        res = self.map_timeline_time_to_clip(self.current_time_sec)
        if res:
            clip_idx, _ = res
            if clip_idx != self.active_playing_clip_idx:
                self.start_audio_for_current_position()

        self.redraw_timeline()
        self.update_preview_frame(force_seek=False)
        self.after(25, self.play_loop)

    def seek_start(self):
        self.stop_audio()
        self.current_time_sec = 0.0
        self.redraw_timeline()
        self.update_preview_frame(force_seek=True)

    def seek_end(self):
        self.stop_audio()
        self.current_time_sec = self.get_total_duration()
        self.redraw_timeline()
        self.update_preview_frame(force_seek=True)

    def seek_relative(self, delta_sec: float):
        self.stop_audio()
        total_dur = self.get_total_duration()
        self.current_time_sec = max(0.0, min(total_dur, self.current_time_sec + delta_sec))
        self.redraw_timeline()
        self.update_preview_frame(force_seek=True)

    # -------------------------------------------------------------
    # Рендеринг кадру прев'ю (Швидкісний OpenCV + PIL)
    # -------------------------------------------------------------
    def update_preview_frame(self, force_seek: bool = True):
        total_dur = self.get_total_duration()
        cur_str = format_time_str(self.current_time_sec)
        tot_str = format_time_str(total_dur)
        self.time_label.config(text=f"⏱ {cur_str} / {tot_str}")
        self.clip_info_label.config(text=f"Фрагментів: {len(self.clips)}")

        if not self.clips:
            self.video_canvas.config(
                image="",
                text="🎬 Додайте відео для початку монтажу на таймлайні\n\n(Керування: Пробіл - Play/Pause, S - Ножиці, Del - Видалити)"
            )
            return

        res = self.map_timeline_time_to_clip(self.current_time_sec)
        if not res:
            return

        clip_idx, source_time = res
        clip = self.clips[clip_idx]

        try:
            needs_open = (self.current_cap_file != clip.file_path or self.current_cap is None)
            if needs_open:
                if self.current_cap is not None:
                    self.current_cap.release()
                self.current_cap = cv2.VideoCapture(clip.file_path)
                self.current_cap_file = clip.file_path
                force_seek = True

            if force_seek:
                self.current_cap.set(cv2.CAP_PROP_POS_MSEC, source_time * 1000.0)

            ret, frame = self.current_cap.read()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                cw = max(200, self.video_canvas.winfo_width() - 10)
                ch = max(150, self.video_canvas.winfo_height() - 10)
                
                scale = min(cw / w, ch / h)
                nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                
                resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
                rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb_frame)
                self.current_photo_image = ImageTk.PhotoImage(img)
                self.video_canvas.config(image=self.current_photo_image, text="")
        except Exception:
            pass

    # -------------------------------------------------------------
    # Малювання графічного таймлайну
    # -------------------------------------------------------------
    def redraw_timeline(self):
        self.timeline_canvas.delete("all")
        total_dur = self.get_total_duration()
        canvas_width = max(self.timeline_canvas.winfo_width(), int((total_dur + 5.0) * self.timeline_scale) + 100)
        self.timeline_canvas.config(scrollregion=(0, 0, canvas_width, 110))

        # 1. Шкала часу (Ruler)
        ruler_y = 20
        self.timeline_canvas.create_line(0, ruler_y, canvas_width, ruler_y, fill="#444444", width=1)
        
        step_sec = 5 if self.timeline_scale >= 8 else 10
        for t in range(0, int(total_dur) + 30, step_sec):
            x = int(t * self.timeline_scale) + 20
            self.timeline_canvas.create_line(x, ruler_y - 6, x, ruler_y, fill="#777777", width=1)
            self.timeline_canvas.create_text(x, ruler_y - 12, text=format_time_str(t), fill="#888888", font=("Consolas", 7))

        # 2. Доріжка блоків кліпів
        track_y = 28
        track_h = 60
        accum_x = 20

        for idx, clip in enumerate(self.clips):
            clip_w = max(15, int(clip.duration * self.timeline_scale))
            x1 = accum_x
            x2 = accum_x + clip_w
            y1 = track_y
            y2 = track_y + track_h

            is_selected = (idx == self.selected_clip_idx)
            fill_color = "#1e4d79" if is_selected else "#283747"
            border_color = "#00e5ff" if is_selected else "#4a6572"
            border_w = 2 if is_selected else 1

            self.timeline_canvas.create_rectangle(
                x1, y1, x2, y2, 
                fill=fill_color, 
                outline=border_color, 
                width=border_w, 
                tags=f"clip_{idx}"
            )

            title_text = f"[{idx+1}] {clip.file_name}"
            sub_text = f"{clip.duration:.1f}с ({format_time_str(clip.start_sec)} - {format_time_str(clip.end_sec)})"
            
            self.timeline_canvas.create_text(
                x1 + 6, y1 + 16, 
                text=title_text, 
                anchor="w", 
                fill="#ffffff", 
                font=("Segoe UI", 8, "bold")
            )
            self.timeline_canvas.create_text(
                x1 + 6, y1 + 36, 
                text=sub_text, 
                anchor="w", 
                fill="#b0bec5", 
                font=("Segoe UI", 7)
            )

            self.timeline_canvas.create_line(x2, y1, x2, y2, fill="#000000", width=2)
            accum_x += clip_w

        # 3. Червоний повзунок поточної позиції (Playhead Cursor)
        playhead_x = int(self.current_time_sec * self.timeline_scale) + 20
        self.timeline_canvas.create_polygon(
            playhead_x - 6, 4,
            playhead_x + 6, 4,
            playhead_x + 6, 14,
            playhead_x, 22,
            playhead_x - 6, 14,
            fill="#ff3b30",
            outline="#ffffff"
        )
        self.timeline_canvas.create_line(playhead_x, 22, playhead_x, 105, fill="#ff3b30", width=2)

    # -------------------------------------------------------------
    # Інтерактивність миші на таймлайні
    # -------------------------------------------------------------
    def on_timeline_click(self, event):
        self.stop_audio()
        canvas_x = self.timeline_canvas.canvasx(event.x)
        self.is_scrubbing = True
        self.update_playhead_from_x(canvas_x)

        accum_x = 20
        for idx, clip in enumerate(self.clips):
            clip_w = max(15, int(clip.duration * self.timeline_scale))
            if accum_x <= canvas_x <= accum_x + clip_w:
                self.selected_clip_idx = idx
                break
            accum_x += clip_w

        self.redraw_timeline()
        self.update_preview_frame(force_seek=True)

    def on_timeline_drag(self, event):
        if self.is_scrubbing:
            canvas_x = self.timeline_canvas.canvasx(event.x)
            self.update_playhead_from_x(canvas_x)
            self.redraw_timeline()
            self.update_preview_frame(force_seek=True)

    def on_timeline_release(self, event):
        self.is_scrubbing = False

    def update_playhead_from_x(self, canvas_x: float):
        total_dur = self.get_total_duration()
        sec = max(0.0, (canvas_x - 20.0) / self.timeline_scale)
        self.current_time_sec = min(total_dur, sec)

    # -------------------------------------------------------------
    # Експорт з анімацією лоадінгу всередині кнопки
    # -------------------------------------------------------------
    def _animate_export_button(self, frame_idx: int = 0):
        """Анімує спінер лоадінгу прямо на кнопці Експорт"""
        if not self.is_exporting:
            return
        spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        sym = spinners[frame_idx % len(spinners)]
        self.btn_export.config(text=f"{sym} Експорт...")
        self.after(90, lambda: self._animate_export_button(frame_idx + 1))

    def export_timeline(self):
        if not self.clips:
            messagebox.showwarning("Увага", "Таймлайн порожній! Додайте відео для експорту.", parent=self)
            return

        out_path = filedialog.asksaveasfilename(
            parent=self,
            title="Зберегти змонтоване відео",
            defaultextension=".mp4",
            filetypes=[("MP4 відео", "*.mp4")]
        )
        self.lift()
        self.focus_force()
        if not out_path:
            return

        # Запуск анімації лоадінгу на кнопці
        self.is_exporting = True
        self.btn_export.config(state=tk.DISABLED)
        self._animate_export_button(0)

        def _worker():
            try:
                export_timeline_clips(self.clips, out_path, lambda m: None)
                self.after(100, lambda: self._on_export_complete(out_path, None))
            except Exception as e:
                self.after(100, lambda: self._on_export_complete(out_path, str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_export_complete(self, output_file: str, error_msg: Optional[str]):
        self.is_exporting = False
        self.btn_export.config(state=tk.NORMAL, text="💾 Експорт")

        if error_msg:
            messagebox.showerror("Помилка рендеру", error_msg, parent=self)
            return

        if messagebox.askyesno(
            "Монтаж завершено! 🎉",
            f"Відео успішно експортовано:\n{os.path.basename(output_file)}\n\nВстановити це змонтоване відео як вхідне для ШІ-озвучки в PyVoice AI?",
            parent=self
        ):
            if self.on_use_video_callback:
                self.on_use_video_callback(output_file)
            self.destroy()

    def on_close(self):
        self.is_playing = False
        self.is_exporting = False
        self.stop_audio()
        if self.current_cap is not None:
            self.current_cap.release()
        try:
            for f in os.listdir(self.temp_audio_dir):
                os.remove(os.path.join(self.temp_audio_dir, f))
            os.rmdir(self.temp_audio_dir)
        except Exception:
            pass
        self.destroy()

# Сумісний аліас для запуску
VideoToolsWindow = TimelineVideoEditorWindow
