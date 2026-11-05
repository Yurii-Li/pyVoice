import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import webbrowser
from typing import Optional
from pyvoice.core.updater import UpdateInfo, download_and_apply_update

class UpdateDialog(tk.Toplevel):
    """
    Зручне діалогове вікно оновлення програми:
    - Показує поточну та нову версії
    - Відображає список змін (Release Notes)
    - Має прогрес-бар завантаження
    - Автоматично перезапускає програму
    """
    def __init__(self, parent, update_info: UpdateInfo):
        super().__init__(parent)
        self.title("🚀 Доступне оновлення - PyVoice AI")
        self.geometry("540x400")
        self.minsize(480, 350)
        self.resizable(True, True)

        self.parent = parent
        self.update_info = update_info
        self.is_downloading = False

        # Модальне вікно
        self.transient(parent)
        self.grab_set()

        # Центрування
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 270
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 200
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Шапка з іконкою
        hdr_frame = ttk.Frame(main_frame)
        hdr_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(hdr_frame, text="🎉", font=("Segoe UI", 28)).pack(side=tk.LEFT, padx=(0, 12))

        title_box = ttk.Frame(hdr_frame)
        title_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(
            title_box, 
            text=f"Знайдено нову версію: {self.update_info.latest_version}", 
            font=("Segoe UI", 12, "bold"),
            foreground="#27ae60"
        ).pack(anchor="w")

        size_mb = f"{self.update_info.asset_size / (1024*1024):.1f} МБ" if self.update_info.asset_size else ""
        ttk.Label(
            title_box, 
            text=f"Поточна версія: v{self.update_info.current_version}  •  Розмір: {size_mb}", 
            font=("Segoe UI", 9),
            foreground="#555555"
        ).pack(anchor="w")

        # 2. Опис релізу (Release Notes)
        notes_group = ttk.LabelFrame(main_frame, text=" Що нового у цьому релізі ", padding="8")
        notes_group.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        notes_scroll = ttk.Scrollbar(notes_group)
        notes_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.notes_text = tk.Text(
            notes_group,
            wrap=tk.WORD,
            height=6,
            font=("Segoe UI", 9),
            bg="#fdfefe",
            fg="#2c3e50",
            bd=1,
            relief="solid",
            yscrollcommand=notes_scroll.set
        )
        self.notes_text.pack(fill=tk.BOTH, expand=True)
        notes_scroll.config(command=self.notes_text.yview)

        notes_content = self.update_info.release_notes if self.update_info.release_notes else "Опис змін відсутній."
        self.notes_text.insert("1.0", notes_content)
        self.notes_text.config(state="disabled")

        # 3. Блок прогресу
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_frame.pack(fill=tk.X, pady=(0, 10))

        self.status_label = ttk.Label(
            self.progress_frame, 
            text="Натисніть 'Оновити зараз' для авто-завантаження.", 
            font=("Segoe UI", 9)
        )
        self.status_label.pack(anchor="w", pady=(0, 4))

        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X)

        # 4. Панель кнопок
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_cancel = ttk.Button(btn_frame, text="Пізніше", command=self.on_close)
        self.btn_cancel.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_update = ttk.Button(
            btn_frame, 
            text="🚀 Оновити зараз", 
            command=self.start_download
        )
        self.btn_update.pack(side=tk.RIGHT)

        btn_github = ttk.Button(
            btn_frame, 
            text="🌐 Відкрити на GitHub", 
            command=self.open_github_release
        )
        btn_github.pack(side=tk.LEFT)

    def open_github_release(self):
        url = f"https://github.com/Yurii-Li/pyVoice/releases/tag/{self.update_info.latest_version}"
        webbrowser.open(url)

    def start_download(self):
        if not self.update_info.download_url:
            messagebox.showerror(
                "Помилка", 
                "У цьому релізі на GitHub відсутній зібраний файл .exe.\nВи можете завантажити його вручну на сторінці релізів."
            )
            self.open_github_release()
            return

        if not getattr(sys, 'frozen', False):
            # Режим розробки (.py)
            res = messagebox.askyesno(
                "Режим розробки",
                "Ви зараз запускаєте програму через Python (.py), а не через .exe!\nАвтозаміна працює лише для зібраного .exe файлу.\n\nВідкрити сторінку релізу на GitHub для завантаження?"
            )
            if res:
                self.open_github_release()
            return

        self.is_downloading = True
        self.btn_update.config(state="disabled")
        self.btn_cancel.config(state="disabled")
        self.status_label.config(text="Завантаження оновлення... Будь ласка, зачекайте.")

        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self):
        try:
            def on_progress(downloaded: int, total: int):
                pct = int((downloaded / total) * 100) if total > 0 else 0
                mb_down = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                self.after(0, lambda: self._update_ui_progress(pct, mb_down, mb_total))

            download_and_apply_update(
                self.update_info.download_url, 
                progress_callback=on_progress
            )
        except Exception as e:
            self.after(0, lambda: self._handle_error(str(e)))

    def _update_ui_progress(self, percent: int, downloaded_mb: float, total_mb: float):
        self.progress_bar['value'] = percent
        self.status_label.config(text=f"Завантаження: {percent}% ({downloaded_mb:.1f} / {total_mb:.1f} МБ)")

    def _handle_error(self, err_msg: str):
        self.is_downloading = False
        self.btn_update.config(state="normal")
        self.btn_cancel.config(state="normal")
        self.status_label.config(text="❌ Помилка під час оновлення.")
        messagebox.showerror("Помилка оновлення", f"Не вдалося оновити програму:\n{err_msg}")

    def on_close(self):
        if self.is_downloading:
            return
        self.destroy()
