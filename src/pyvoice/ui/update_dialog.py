import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
import sys
import os
import tempfile
import webbrowser
from typing import Optional
from pyvoice.core.updater import UpdateInfo, download_update_file, launch_installer_and_exit
from pyvoice.ui.shortcuts import bring_to_front

class UpdateDialog(ctk.CTkToplevel):
    """
    Сучасне діалогове вікно оновлення програми на базі CustomTkinter:
    - Відображає нову версію, розмір та опис релізу
    - Плавний неоновий прогрес-бар завантаження
    - Автоматично оновлює додаток через Inno Setup
    """
    def __init__(self, parent, update_info: UpdateInfo):
        super().__init__(parent)
        self.title("🚀 Доступне оновлення - PyVoice AI")
        self.geometry("560x440")
        self.minsize(500, 380)
        self.resizable(True, True)

        self.parent = parent
        self.update_info = update_info
        self.is_downloading = False

        # Модальне вікно
        self.transient(parent)
        self.grab_set()

        # Центрування
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 280
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 220
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        bring_to_front(self, parent)

    def create_widgets(self):
        self.configure(fg_color=("#f8fafc", "#090d16"))
        main_frame = ctk.CTkFrame(
            self, 
            corner_radius=14,
            fg_color=("#ffffff", "#0e1424"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        main_frame.pack(fill="both", expand=True, padx=14, pady=14)

        # 1. Шапка з іконкою
        hdr_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        hdr_frame.pack(fill="x", padx=16, pady=(16, 10))

        icon_frame = ctk.CTkFrame(hdr_frame, width=44, height=44, corner_radius=12, fg_color=("#d1fae5", "#064e3b"))
        icon_frame.pack(side="left", padx=(0, 14))
        icon_frame.pack_propagate(False)
        ctk.CTkLabel(icon_frame, text="🎉", font=ctk.CTkFont(size=22)).place(relx=0.5, rely=0.5, anchor="center")

        title_box = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)

        lbl_title = ctk.CTkLabel(
            title_box, 
            text=f"Знайдено нову версію: {self.update_info.latest_version}", 
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=("#10b981", "#34d399")
        )
        lbl_title.pack(anchor="w")

        size_mb = f"{self.update_info.asset_size / (1024*1024):.1f} МБ" if self.update_info.asset_size else ""
        lbl_sub = ctk.CTkLabel(
            title_box, 
            text=f"Поточна версія: v{self.update_info.current_version}  •  Розмір інсталятора: {size_mb}", 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#64748b", "#94a3b8")
        )
        lbl_sub.pack(anchor="w")

        # 2. Опис релізу (Release Notes)
        notes_group = ctk.CTkFrame(
            main_frame, 
            corner_radius=10, 
            fg_color=("#f1f5f9", "#111827"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        notes_group.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        lbl_notes_hdr = ctk.CTkLabel(
            notes_group, 
            text="📋 Що нового у цьому релізі:", 
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        )
        lbl_notes_hdr.pack(anchor="w", padx=12, pady=(10, 4))

        self.notes_text = ctk.CTkTextbox(
            notes_group, 
            height=120, 
            font=("Segoe UI", 10),
            corner_radius=8,
            fg_color=("#ffffff", "#090d16"),
            border_color=("#cbd5e1", "#1e293b"),
            border_width=1
        )
        self.notes_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        notes_content = self.update_info.release_notes if self.update_info.release_notes else "Опис змін відсутній."
        self.notes_text.insert("1.0", notes_content)
        self.notes_text.configure(state="disabled")

        # 3. Блок прогресу
        self.progress_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=16, pady=(0, 12))

        self.status_label = ctk.CTkLabel(
            self.progress_frame, 
            text="Натисніть 'Оновити зараз' для автоматичного завантаження та оновлення.", 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#64748b", "#94a3b8")
        )
        self.status_label.pack(anchor="w", pady=(0, 4))

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, mode='determinate', height=8, progress_color="#10b981")
        self.progress_bar.pack(fill="x", pady=(2, 0))
        self.progress_bar.set(0)

        # 4. Панель кнопок
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 16), side="bottom")

        self.btn_cancel = ctk.CTkButton(
            btn_frame, 
            text="Пізніше", 
            width=90,
            height=34,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.on_close
        )
        self.btn_cancel.pack(side="right", padx=(8, 0))

        self.btn_update = ctk.CTkButton(
            btn_frame, 
            text="🚀 Оновити зараз", 
            width=140,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(weight="bold"),
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            command=self.start_download
        )
        self.btn_update.pack(side="right")

        btn_github = ctk.CTkButton(
            btn_frame, 
            text="🌐 Відкрити на GitHub", 
            width=140,
            fg_color=("gray75", "#27272a"),
            hover_color=("gray65", "#3f3f46"),
            command=self.open_github_release
        )
        btn_github.pack(side="left")

    def open_github_release(self):
        url = f"https://github.com/Yurii-Li/pyVoice/releases/tag/{self.update_info.latest_version}"
        webbrowser.open(url)

    def start_download(self):
        if not self.update_info.download_url:
            messagebox.showerror(
                "Помилка", 
                "У цьому релізі на GitHub відсутній інсталятор .exe.\nВи можете завантажити його вручну на сторінці релізів."
            )
            self.open_github_release()
            return

        if not getattr(sys, 'frozen', False):
            # Режим розробки (.py)
            res = messagebox.askyesno(
                "Режим розробки",
                "Ви зараз запускаєте програму через Python (.py), а не через встановлений .exe!\nАвтооновлення призначене для встановленої програми.\n\nВідкрити сторінку релізу на GitHub для завантаження?"
            )
            if res:
                self.open_github_release()
            return

        self.is_downloading = True
        self.btn_update.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        self.status_label.configure(text="Завантаження оновлення... Будь ласка, зачекайте.")

        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self):
        try:
            temp_dir = tempfile.mkdtemp(prefix="pyvoice_inno_")
            installer_name = self.update_info.asset_name or "PyVoiceAI-Setup.exe"
            installer_path = os.path.join(temp_dir, installer_name)

            def on_progress(downloaded: int, total: int):
                pct = int((downloaded / total) * 100) if total > 0 else 0
                mb_down = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                self.after(0, lambda: self._update_ui_progress(pct, mb_down, mb_total))

            # 1. Завантаження інсталятора Inno Setup
            download_update_file(
                self.update_info.download_url,
                target_path=installer_path,
                progress_callback=on_progress
            )

            # 2. Повідомляємо інтерфейс і запускаємо інсталяцію
            self.after(0, lambda: self._trigger_restart(installer_path))

        except Exception as e:
            self.after(0, lambda: self._handle_error(str(e)))

    def _trigger_restart(self, installer_path: str):
        self.status_label.configure(text="✅ Завантажено 100%! Встановлення та перезапуск...")
        self.update_idletasks()
        # Запускаємо Inno Setup через 300мс і виходимо
        self.after(300, lambda: launch_installer_and_exit(installer_path))

    def _update_ui_progress(self, percent: int, downloaded_mb: float, total_mb: float):
        fraction = min(percent / 100.0, 1.0)
        self.progress_bar.set(fraction)
        self.status_label.configure(text=f"Завантаження: {percent}% ({downloaded_mb:.1f} / {total_mb:.1f} МБ)")

    def _handle_error(self, err_msg: str):
        self.is_downloading = False
        self.btn_update.configure(state="normal")
        self.btn_cancel.configure(state="normal")
        self.status_label.configure(text="❌ Помилка під час оновлення.")
        messagebox.showerror("Помилка оновлення", f"Не вдалося оновити програму:\n{err_msg}")

    def on_close(self):
        if self.is_downloading:
            return
        self.destroy()
