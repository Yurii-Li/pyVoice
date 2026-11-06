import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import threading
import asyncio
import os
import json
import webbrowser
import datetime
from typing import Optional

from pyvoice.core.config import load_api_key, save_api_key
from pyvoice.core.gemini import analyze_video
from pyvoice.core.pipeline import run_voiceover_pipeline
from pyvoice.ui.log_viewer import LogViewerWindow
from pyvoice.ui.fallback_dialog import VoiceFallbackDialog
from pyvoice.ui.script_editor import ScriptEditorWindow
from pyvoice.ui.task_spec_dialog import TaskSpecDialog
from pyvoice.ui.video_tools_window import TimelineVideoEditorWindow
from pyvoice.ui.shortcuts import enable_universal_shortcuts
from pyvoice.ui.update_dialog import UpdateDialog
from pyvoice.core.updater import check_for_updates
from pyvoice import __version__

# Налаштування сучасної темної теми CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class PyVoiceApp(ctk.CTk):
    """
    Головне вікно PyVoice AI з ультрасучасним інтерфейсом CustomTkinter
    у стилі Windows 11 / Dark Mode: заокруглені картки, неонові акценти,
    зручні тумблери та вбудована анімація.
    """
    def __init__(self):
        super().__init__()
        self.title("PyVoice AI - Авто-Озвучка дій у відео зі стоп-кадрами")
        self.minsize(720, 560)
        
        # Центрування вікна на екрані
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(820, max(720, screen_w - 60))
        height = min(740, max(560, screen_h - 80))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height - 40) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Універсальні гарячі клавіші (Ctrl+V, Ctrl+C, Ctrl+A) для української розкладки
        enable_universal_shortcuts(self)
            
        # Змінні даних
        self.api_key_var = tk.StringVar(value=load_api_key())
        self.input_video_path = tk.StringVar()
        self.output_video_path = tk.StringVar()
        
        # Варіанти озвучки за замовчуванням
        self.voice_var = tk.StringVar(value="Edge-TTS: Остап (🔥 Живий / Динамічний)")
        
        # Налаштування стилю та глибини озвучки
        self.video_topic_var = tk.StringVar()
        self.task_spec_text = ""
        self.style_var = tk.StringVar(value="Детальний туторіал (з привітанням, поясненням суті та користі дій)")
        self.custom_notes_var = tk.StringVar()
        self.include_intro_var = tk.BooleanVar(value=True)
        self.explain_purpose_var = tk.BooleanVar(value=True)
        self.include_outro_var = tk.BooleanVar(value=True)
        
        # Статус та логування
        self.status_var = tk.StringVar(value="🟢 Готовий до роботи")
        self.log_history = []
        self.log_window = None
        self.is_key_visible = False
        
        self.create_widgets()
        
        # Автоматичне збереження API ключа при введенні
        self.api_key_var.trace_add("write", lambda *a: save_api_key(self.api_key_var.get()))

        # Тиха перевірка оновлень при запуску через 2 секунди
        self.after(2000, lambda: self.check_updates_background(manual=False))

    def open_api_key_url(self):
        webbrowser.open("https://aistudio.google.com/app/apikey")

    def toggle_theme(self):
        """Перемикає тему оформлення (Dark / Light)"""
        current = ctk.get_appearance_mode()
        new_mode = "Light" if current == "Dark" else "Dark"
        ctk.set_appearance_mode(new_mode)
        self.btn_theme.configure(text="🌙 Темна" if new_mode == "Light" else "☀️ Світла")

    def _create_step_header(self, card, step_num: str, title: str, subtitle: str, bg_color: tuple, text_color: tuple):
        """Створює стильний уніфікований заголовок кроку із заокругленим номером-бейджів"""
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(14, 10))

        badge = ctk.CTkFrame(hdr, width=34, height=34, corner_radius=9, fg_color=bg_color)
        badge.pack(side="left", padx=(0, 12))
        badge.pack_propagate(False)

        ctk.CTkLabel(
            badge, 
            text=step_num, 
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=text_color
        ).place(relx=0.5, rely=0.5, anchor="center")

        tbox = ctk.CTkFrame(hdr, fg_color="transparent")
        tbox.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            tbox, 
            text=title, 
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=("gray10", "white")
        ).pack(anchor="w")

        ctk.CTkLabel(
            tbox, 
            text=subtitle, 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#64748b", "#94a3b8")
        ).pack(anchor="w")

    def create_widgets(self):
        # Встановлюємо глибокий преміальний фоновий колір
        self.configure(fg_color=("#f8fafc", "#090d16"))

        # -------------------------------------------------------------
        # 1. Верхня шапка додатку (Header Bar) у стилі Fluent / SaaS
        # -------------------------------------------------------------
        header_frame = ctk.CTkFrame(
            self, 
            height=62, 
            corner_radius=0, 
            fg_color=("#ffffff", "#0e1424"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        header_frame.pack(fill="x", side="top")

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", padx=18, pady=8)

        text_col = ctk.CTkFrame(title_box, fg_color="transparent")
        text_col.pack(side="left")

        title_row = ctk.CTkFrame(text_col, fg_color="transparent")
        title_row.pack(anchor="w")

        lbl_app = ctk.CTkLabel(
            title_row, 
            text="🎙️ PyVoice AI", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=("gray10", "white")
        )
        lbl_app.pack(side="left")

        # Версійний бейдж
        ver_badge = ctk.CTkFrame(title_row, corner_radius=6, fg_color=("#e0f2fe", "#082f49"))
        ver_badge.pack(side="left", padx=(8, 0))
        ctk.CTkLabel(
            ver_badge, 
            text=f"v{__version__}", 
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=("#0284c7", "#38bdf8")
        ).pack(padx=6, pady=1)

        lbl_sub = ctk.CTkLabel(
            text_col, 
            text="Розумна авто-озвучка дій у відео зі стоп-кадрами", 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#64748b", "#94a3b8")
        )
        lbl_sub.pack(anchor="w")

        # Панель дій праворуч
        right_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_box.pack(side="right", padx=16, pady=10)

        # Перемикач теми
        self.btn_theme = ctk.CTkButton(
            right_box, 
            text="☀️ Світла" if ctk.get_appearance_mode() == "Dark" else "🌙 Темна", 
            width=92, 
            height=30,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.toggle_theme
        )
        self.btn_theme.pack(side="left")

        # -------------------------------------------------------------
        # 2. Закріплений знизу Status Bar
        # -------------------------------------------------------------
        status_bar = ctk.CTkFrame(
            self, 
            height=44, 
            corner_radius=0, 
            fg_color=("#ffffff", "#0e1424"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        status_bar.pack(fill="x", side="bottom")

        self.progress_bar = ctk.CTkProgressBar(status_bar, mode="indeterminate", width=110, height=8, progress_color="#38bdf8")
        self.progress_bar.pack(side="right", padx=(8, 16), pady=14)
        self.progress_bar.set(0)

        btn_open_logs = ctk.CTkButton(
            status_bar, 
            text="📜 Журнал логів", 
            width=115, 
            height=28,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.open_log_window
        )
        btn_open_logs.pack(side="right", padx=(4, 0), pady=8)

        self.btn_update_check = ctk.CTkButton(
            status_bar, 
            text=f"🔄 Оновлення", 
            width=110, 
            height=28,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=lambda: self.check_updates_background(manual=True)
        )
        self.btn_update_check.pack(side="right", padx=(4, 0), pady=8)

        status_badge = ctk.CTkFrame(status_bar, fg_color=("#f1f5f9", "#111827"), corner_radius=8, border_width=1, border_color=("#e2e8f0", "#1e293b"))
        status_badge.pack(side="left", fill="x", expand=True, padx=(14, 8), pady=6)

        self.status_label = ctk.CTkLabel(
            status_badge, 
            textvariable=self.status_var, 
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=("#0f172a", "#f1f5f9"),
            anchor="w",
            cursor="hand2"
        )
        self.status_label.pack(side="left", fill="x", expand=True, padx=10, pady=2)
        self.status_label.bind("<Double-Button-1>", lambda e: self.open_log_window())

        # -------------------------------------------------------------
        # 3. Головний скролований контейнер із сучасними картками
        # -------------------------------------------------------------
        self.main_scroll = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self.main_scroll.pack(fill="both", expand=True, padx=14, pady=(8, 6))

        # =============================================================
        # КАРТКА 1: Налаштування ШІ-Сценариста
        # =============================================================
        card_ai = ctk.CTkFrame(
            self.main_scroll, 
            corner_radius=14, 
            fg_color=("#ffffff", "#111827"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        card_ai.pack(fill="x", pady=(0, 12), padx=4)

        self._create_step_header(
            card_ai, 
            "01", 
            "ШІ-Сценарист & Контекст завдання", 
            "Google Gemini Vision аналізує запис екрану та генерує таймкоди й текст",
            bg_color=("#e0e7ff", "#1e1b4b"),
            text_color=("#4338ca", "#818cf8")
        )

        grid_ai = ctk.CTkFrame(card_ai, fg_color="transparent")
        grid_ai.pack(fill="x", padx=16, pady=(0, 14))
        grid_ai.columnconfigure(1, weight=1)

        # Рядок 0: API Key
        ctk.CTkLabel(grid_ai, text="Gemini API Key:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", pady=5, padx=(0, 10))
        
        key_box = ctk.CTkFrame(grid_ai, fg_color="transparent")
        key_box.grid(row=0, column=1, columnspan=3, sticky="we", pady=5)
        key_box.columnconfigure(0, weight=1)

        self.api_entry = ctk.CTkEntry(
            key_box, 
            textvariable=self.api_key_var, 
            show="*", 
            placeholder_text="Вставте ваш ключ Google Gemini API...",
            height=34,
            corner_radius=8,
            fg_color=("#f8fafc", "#090d16"),
            border_color=("#cbd5e1", "#1e293b"),
            border_width=1
        )
        self.api_entry.grid(row=0, column=0, sticky="we", padx=(0, 6))

        self.btn_show_key = ctk.CTkButton(
            key_box, 
            text="👁️", 
            width=36, 
            height=34,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.toggle_key_visibility
        )
        self.btn_show_key.grid(row=0, column=1, padx=(0, 6))

        btn_get_key = ctk.CTkButton(
            key_box, 
            text="🔑 Отримати ключ", 
            width=130, 
            height=34,
            corner_radius=8,
            fg_color=("#4f46e5", "#4338ca"),
            hover_color=("#4338ca", "#3730a3"),
            font=ctk.CTkFont(weight="bold"),
            command=self.open_api_key_url
        )
        btn_get_key.grid(row=0, column=2)

        # Рядок 1: Тема / Контекст відео
        ctk.CTkLabel(grid_ai, text="Контекст відео:", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, sticky="w", pady=5, padx=(0, 10))
        entry_topic = ctk.CTkEntry(
            grid_ai, 
            textvariable=self.video_topic_var, 
            placeholder_text="Наприклад: Інструкція як налаштувати права доступу користувачів...",
            height=34,
            corner_radius=8,
            fg_color=("#f8fafc", "#090d16"),
            border_color=("#cbd5e1", "#1e293b"),
            border_width=1
        )
        entry_topic.grid(row=1, column=1, columnspan=3, sticky="we", pady=5)

        # Рядок 2: Технічне завдання (ТЗ)
        ctk.CTkLabel(grid_ai, text="Технічне завдання:", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, sticky="w", pady=5, padx=(0, 10))
        tz_box = ctk.CTkFrame(grid_ai, fg_color="transparent")
        tz_box.grid(row=2, column=1, columnspan=3, sticky="we", pady=5)

        ctk.CTkButton(
            tz_box, 
            text="📋 Редагувати ТЗ...", 
            width=135, 
            height=32,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.open_task_spec_editor
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            tz_box, 
            text="📂 З файлу...", 
            width=100, 
            height=32,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.browse_task_spec_file
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            tz_box, 
            text="❌", 
            width=34, 
            height=32,
            corner_radius=8,
            fg_color=("#ef4444", "#dc2626"),
            hover_color=("#dc2626", "#b91c1c"),
            command=self.clear_task_spec
        ).pack(side="left", padx=(0, 10))

        self.task_spec_status_label = ctk.CTkLabel(
            tz_box, 
            text="⚪ ТЗ не додано", 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray50", "gray60")
        )
        self.task_spec_status_label.pack(side="left", fill="x", expand=True)

        # Рядок 3: Стиль подачі
        ctk.CTkLabel(grid_ai, text="Стиль подачі:", font=ctk.CTkFont(weight="bold")).grid(row=3, column=0, sticky="w", pady=5, padx=(0, 10))
        styles = [
            "Детальний туторіал (з привітанням, поясненням суті та користі дій)",
            "Блогерський розмовний стиль (живі емоції, динаміка, звернення до глядачів)",
            "Офіційна презентація продукту (діловий тон, чітка демонстрація)",
            "Лаконічний опис дій (лише факти та кроки)",
            "Власний стиль"
        ]
        self.style_menu = ctk.CTkOptionMenu(
            grid_ai, 
            values=styles, 
            variable=self.style_var,
            height=34,
            corner_radius=8,
            fg_color=("#f8fafc", "#1e293b"),
            button_color=("#4f46e5", "#3730a3"),
            button_hover_color=("#4338ca", "#312e81"),
            dropdown_fg_color=("#ffffff", "#111827"),
            dropdown_hover_color=("#f1f5f9", "#1e293b"),
            text_color=("#0f172a", "#f8fafc"),
            dynamic_resizing=False
        )
        self.style_menu.grid(row=3, column=1, columnspan=3, sticky="we", pady=5)

        # Рядок 4: Сучасні тумблери (Switches)
        switches_box = ctk.CTkFrame(grid_ai, fg_color="transparent")
        switches_box.grid(row=4, column=0, columnspan=4, sticky="we", pady=(8, 5))

        ctk.CTkSwitch(
            switches_box, 
            text="👋 Привітання на початку (00:01)", 
            variable=self.include_intro_var,
            progress_color="#3b82f6",
            switch_width=40,
            switch_height=20
        ).pack(side="left", padx=(0, 18))

        ctk.CTkSwitch(
            switches_box, 
            text="💡 Пояснювати користь функцій", 
            variable=self.explain_purpose_var,
            progress_color="#3b82f6",
            switch_width=40,
            switch_height=20
        ).pack(side="left", padx=(0, 18))

        ctk.CTkSwitch(
            switches_box, 
            text="🏁 Підсумок у кінці", 
            variable=self.include_outro_var,
            progress_color="#3b82f6",
            switch_width=40,
            switch_height=20
        ).pack(side="left")

        # Рядок 5: Додаткові побажання
        ctk.CTkLabel(grid_ai, text="Додаткові побажання:", font=ctk.CTkFont(weight="bold")).grid(row=5, column=0, sticky="w", pady=5, padx=(0, 10))
        entry_notes = ctk.CTkEntry(
            grid_ai, 
            textvariable=self.custom_notes_var, 
            placeholder_text="Наприклад: Звертай увагу на нові фільтри у таблиці...",
            height=34,
            corner_radius=8,
            fg_color=("#f8fafc", "#090d16"),
            border_color=("#cbd5e1", "#1e293b"),
            border_width=1
        )
        entry_notes.grid(row=5, column=1, columnspan=3, sticky="we", pady=5)

        # =============================================================
        # КАРТКА 2: Вибір відео та запуск ШІ-Аналізу
        # =============================================================
        card_video = ctk.CTkFrame(
            self.main_scroll, 
            corner_radius=14, 
            fg_color=("#ffffff", "#111827"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        card_video.pack(fill="x", pady=(0, 12), padx=4)

        self._create_step_header(
            card_video, 
            "02", 
            "Вхідне відео та Підготовка монтажу", 
            "Оберіть вихідне відео або відкрийте вбудований візуальний відеомонтажер",
            bg_color=("#e0f2fe", "#082f49"),
            text_color=("#0284c7", "#38bdf8")
        )

        v_row = ctk.CTkFrame(card_video, fg_color="transparent")
        v_row.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(v_row, text="Вхідне відео:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        
        self.entry_input_vid = ctk.CTkEntry(
            v_row, 
            textvariable=self.input_video_path, 
            placeholder_text="Оберіть відеофайл запису екрану...",
            height=36,
            corner_radius=8,
            fg_color=("#f8fafc", "#090d16"),
            border_color=("#cbd5e1", "#1e293b"),
            border_width=1
        )
        self.entry_input_vid.pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            v_row, 
            text="📂 Огляд...", 
            width=95, 
            height=36,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.browse_video
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            v_row, 
            text="🎬 Відео-монтажер", 
            width=135, 
            height=36,
            corner_radius=8,
            fg_color=("#8b5cf6", "#7c3aed"),
            hover_color=("#7c3aed", "#6d28d9"),
            font=ctk.CTkFont(weight="bold"),
            command=self.open_video_tools
        ).pack(side="left")

        self.btn_analyze = ctk.CTkButton(
            card_video, 
            text="✨ Проаналізувати дії у відео через ШІ (Скласти сценарій озвучки)", 
            height=44,
            corner_radius=10,
            fg_color=("#4f46e5", "#4338ca"),
            hover_color=("#4338ca", "#3730a3"),
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self.start_ai_analysis
        )
        self.btn_analyze.pack(fill="x", padx=16, pady=(0, 16))

        # =============================================================
        # КАРТКА 3: Сценарій озвучки з таймкодами
        # =============================================================
        card_script = ctk.CTkFrame(
            self.main_scroll, 
            corner_radius=14, 
            fg_color=("#ffffff", "#111827"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        card_script.pack(fill="both", expand=True, pady=(0, 12), padx=4)

        s_top = ctk.CTkFrame(card_script, fg_color="transparent")
        s_top.pack(fill="x", padx=16, pady=(14, 8))

        # Зліва заголовок кроку 3
        badge3 = ctk.CTkFrame(s_top, width=34, height=34, corner_radius=9, fg_color=("#ede9fe", "#2e1065"))
        badge3.pack(side="left", padx=(0, 12))
        badge3.pack_propagate(False)

        ctk.CTkLabel(
            badge3, 
            text="03", 
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("#7c3aed", "#c084fc")
        ).place(relx=0.5, rely=0.5, anchor="center")

        tbox3 = ctk.CTkFrame(s_top, fg_color="transparent")
        tbox3.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            tbox3, 
            text="Сценарій озвучки з таймкодами", 
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=("gray10", "white")
        ).pack(anchor="w")

        ctk.CTkLabel(
            tbox3, 
            text="Переглядайте, редагуйте репліки або відкрийте картковий редактор", 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#64748b", "#94a3b8")
        ).pack(anchor="w")

        # Кнопки управління сценарієм праворуч
        btn_expand = ctk.CTkButton(
            s_top, 
            text="🗂️ Великий картковий редактор", 
            width=190, 
            height=32,
            font=ctk.CTkFont(weight="bold"),
            corner_radius=8,
            fg_color=("#7c3aed", "#6d28d9"),
            hover_color=("#6d28d9", "#5b21b6"),
            command=self.open_script_editor
        )
        btn_expand.pack(side="right")

        ctk.CTkButton(
            s_top, 
            text="💾 Зберегти", 
            width=85, 
            height=32,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.save_json_file
        ).pack(side="right", padx=(0, 6))

        ctk.CTkButton(
            s_top, 
            text="📂 Відкрити", 
            width=85, 
            height=32,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.load_json_file
        ).pack(side="right", padx=(0, 6))

        self.script_text = ctk.CTkTextbox(
            card_script, 
            height=125, 
            font=("Consolas", 11),
            corner_radius=8,
            fg_color=("#f8fafc", "#090d16"),
            border_color=("#cbd5e1", "#1e293b"),
            border_width=1
        )
        self.script_text.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        self.script_text.bind("<Double-Button-1>", lambda e: self.open_script_editor())

        # =============================================================
        # КАРТКА 4: Озвучення та Фінальний рендер
        # =============================================================
        card_render = ctk.CTkFrame(
            self.main_scroll, 
            corner_radius=14, 
            fg_color=("#ffffff", "#111827"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        card_render.pack(fill="x", pady=(0, 12), padx=4)

        self._create_step_header(
            card_render, 
            "04", 
            "Синтез голосу & Синхронізація стоп-кадрів", 
            "Оберіть природний ШІ-голос і згенеруйте фінальне синхронізоване відео",
            bg_color=("#d1fae5", "#064e3b"),
            text_color=("#059669", "#34d399")
        )

        grid_r = ctk.CTkFrame(card_render, fg_color="transparent")
        grid_r.pack(fill="x", padx=16, pady=(0, 16))
        grid_r.columnconfigure(1, weight=1)

        ctk.CTkLabel(grid_r, text="Голос та Рушій:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", pady=5, padx=(0, 10))
        voices = [
            "Edge-TTS: Остап (🔥 Живий / Динамічний)",
            "Edge-TTS: Поліна (🔥 Жива / Динамічна)",
            "Edge-TTS: Остап (Базовий / Швидкий)",
            "Edge-TTS: Поліна (Базова / Швидка)",
            "Google Gemini AI: Puck (🌟 Емоційний ШІ-Диктор)",
            "Google Gemini AI: Aoede (🌟 Емоційна ШІ-Дикторка)",
            "Google Gemini AI: Charon (🌟 Глибокий ШІ-Голос)",
            "Google Gemini AI: Kore (🌟 Чітка ШІ-Дикторка)",
            "Google Gemini AI: Fenrir (🌟 Впевнений ШІ-Голос)"
        ]
        self.voice_menu = ctk.CTkOptionMenu(
            grid_r, 
            values=voices, 
            variable=self.voice_var,
            height=36,
            corner_radius=8,
            fg_color=("#f8fafc", "#1e293b"),
            button_color=("#059669", "#047857"),
            button_hover_color=("#047857", "#065f46"),
            dropdown_fg_color=("#ffffff", "#111827"),
            dropdown_hover_color=("#f1f5f9", "#1e293b"),
            text_color=("#0f172a", "#f8fafc"),
            dynamic_resizing=False
        )
        self.voice_menu.grid(row=0, column=1, columnspan=2, sticky="we", pady=5)

        ctk.CTkLabel(grid_r, text="Куди зберегти:", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, sticky="w", pady=5, padx=(0, 10))
        self.entry_out_vid = ctk.CTkEntry(
            grid_r, 
            textvariable=self.output_video_path,
            placeholder_text="Шлях для збереження змонтованого відео...",
            height=36,
            corner_radius=8,
            fg_color=("#f8fafc", "#090d16"),
            border_color=("#cbd5e1", "#1e293b"),
            border_width=1
        )
        self.entry_out_vid.grid(row=1, column=1, sticky="we", pady=5, padx=(0, 6))

        ctk.CTkButton(
            grid_r, 
            text="📂 Огляд...", 
            width=95, 
            height=36,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.browse_output
        ).grid(row=1, column=2, pady=5)

        # Велика головна кнопка запуску рендеру (смарагдовий градієнтний вигляд)
        self.btn_render = ctk.CTkButton(
            grid_r, 
            text="🚀 Створити фінальне відео зі стоп-кадрами та озвучкою", 
            height=48,
            corner_radius=12,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=("#059669", "#059669"),
            hover_color=("#047857", "#047857"),
            command=self.start_rendering
        )
        self.btn_render.grid(row=2, column=0, columnspan=3, pady=(12, 0), sticky="we")

    def toggle_key_visibility(self):
        """Перемикає видимість символів API ключа"""
        self.is_key_visible = not self.is_key_visible
        self.api_entry.configure(show="" if self.is_key_visible else "*")
        self.btn_show_key.configure(text="🔒" if self.is_key_visible else "👁️")

    def open_task_spec_editor(self):
        """Відкриває повнорозмірне вікно редагування Технічного Завдання (ТЗ)"""
        TaskSpecDialog(self, self.task_spec_text, self.on_task_spec_saved)

    def on_task_spec_saved(self, new_text: str):
        self.task_spec_text = new_text.strip()
        self.update_task_spec_ui()
        if self.task_spec_text:
            chars = len(self.task_spec_text)
            words = len(self.task_spec_text.split())
            self.log_message(f"📋 Технічне завдання оновлено ({chars:,} симв., {words:,} слів).")
        else:
            self.log_message("📋 Технічне завдання очищено.")

    def browse_task_spec_file(self):
        filename = filedialog.askopenfilename(
            filetypes=[
                ("Текстові та Markdown файли", "*.txt *.md *.markdown *.json *.yaml *.yml *.log *.docx"),
                ("Усі файли", "*.*")
            ]
        )
        if filename:
            try:
                with open(filename, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self.on_task_spec_saved(content)
                self.log_message(f"📂 Завантажено ТЗ з файлу: {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Помилка", f"Не вдалося відкрити файл ТЗ:\n{str(e)}")

    def clear_task_spec(self):
        self.task_spec_text = ""
        self.update_task_spec_ui()
        self.log_message("📋 Технічне завдання видалено.")

    def update_task_spec_ui(self):
        if self.task_spec_text:
            chars = len(self.task_spec_text)
            words = len(self.task_spec_text.split())
            self.task_spec_status_label.configure(
                text=f"🟢 ТЗ активно ({chars:,} симв., {words:,} слів)",
                text_color=("#10b981", "#34d399")
            )
        else:
            self.task_spec_status_label.configure(
                text="⚪ ТЗ не додано",
                text_color=("gray50", "gray60")
            )

    def open_script_editor(self):
        content = self.script_text.get("1.0", tk.END).strip()
        def on_save(new_content: str):
            self.script_text.delete("1.0", tk.END)
            self.script_text.insert("1.0", new_content)
            self.log_message("✏️ Сценарій оновлено з великого редактора.")
            
        ScriptEditorWindow(self, content, on_save)

    def open_video_tools(self):
        init_path = self.input_video_path.get().strip()
        TimelineVideoEditorWindow(self, initial_video_path=init_path, on_use_video_callback=self.on_video_tools_result)

    def on_video_tools_result(self, video_path: str):
        self.input_video_path.set(video_path)
        self.log_message(f"📹 Встановлено змонтоване відео: {os.path.basename(video_path)}")

    def open_log_window(self):
        if self.log_window is not None and self.log_window.winfo_exists():
            from pyvoice.ui.shortcuts import bring_to_front
            bring_to_front(self.log_window, self)
        else:
            self.log_window = LogViewerWindow(self, self.log_history)

    def prompt_voice_fallback(self, error_message: str, current_voice: str) -> Optional[str]:
        result = {"chosen_voice": None}
        event = threading.Event()

        def _show():
            dialog = VoiceFallbackDialog(self, error_message, current_voice)
            self.wait_window(dialog)
            result["chosen_voice"] = dialog.chosen_voice
            event.set()

        self.after(0, _show)
        event.wait()
        return result["chosen_voice"]

    def log_message(self, message: str):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        full_entry = f"[{now_str}] {message}"
        self.log_history.append(full_entry)
        
        def _update():
            clean_status = message.replace("\n", " ")
            if len(clean_status) > 75:
                clean_status = clean_status[:72] + "..."
            self.status_var.set(clean_status)
            
            if self.log_window is not None and self.log_window.winfo_exists():
                self.log_window.append_log(full_entry)
                
        self.after(0, _update)

    def browse_video(self):
        filename = filedialog.askopenfilename(filetypes=[("Відео файли", "*.mp4 *.avi *.mov *.mkv")])
        if filename:
            self.input_video_path.set(filename)
            base, ext = os.path.splitext(filename)
            self.output_video_path.set(f"{base}_voiced_synced{ext}")
            self.log_message(f"📹 Обрано відео: {os.path.basename(filename)}")

    def browse_output(self):
        filename = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4 відео", "*.mp4")])
        if filename:
            self.output_video_path.set(filename)

    def load_json_file(self):
        filename = filedialog.askopenfilename(filetypes=[("JSON сценарії", "*.json")])
        if filename:
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    content = f.read()
                self.script_text.delete("1.0", tk.END)
                self.script_text.insert(tk.END, content)
                self.log_message(f"📂 Завантажено сценарій з {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Помилка", f"Не вдалося відкрити файл:\n{str(e)}")

    def save_json_file(self):
        content = self.script_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("Увага", "Текстове поле порожнє!")
            return
        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON файл", "*.json")])
        if filename:
            try:
                parsed = json.loads(content)
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(parsed, f, ensure_ascii=False, indent=2)
                self.log_message(f"💾 Сценарій збережено у {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Помилка JSON", f"Текст містить синтаксичну помилку JSON:\n{str(e)}")

    def set_ui_busy(self, busy: bool):
        def _set():
            state = "disabled" if busy else "normal"
            self.btn_analyze.configure(state=state)
            self.btn_render.configure(state=state)
            if busy:
                self.progress_bar.start()
            else:
                self.progress_bar.stop()
                self.progress_bar.set(0)
        self.after(0, _set)

    def start_ai_analysis(self):
        api_key = self.api_key_var.get().strip()
        video_path = self.input_video_path.get().strip()
        style_preset = self.style_var.get().strip()
        video_topic = self.video_topic_var.get().strip()
        task_spec = self.task_spec_text.strip()
        custom_notes = self.custom_notes_var.get().strip()
        include_intro = self.include_intro_var.get()
        explain_purpose = self.explain_purpose_var.get()
        include_outro = self.include_outro_var.get()

        if not api_key:
            messagebox.showerror(
                "Потрібен API Ключ", 
                "Будь ласка, введіть ваш Gemini API Key!\nНатисніть кнопку '🔑 Отримати ключ', якщо у вас його ще немає."
            )
            return

        if not video_path or not os.path.exists(video_path):
            messagebox.showerror("Помилка", "Будь ласка, оберіть існуючий відеофайл спочатку!")
            return

        save_api_key(api_key)
        self.set_ui_busy(True)
        self.log_message("🚀 Початок Vision AI аналізу відео...")

        thread = threading.Thread(
            target=self.run_ai_analysis_thread, 
            args=(api_key, video_path, style_preset, video_topic, task_spec, include_intro, explain_purpose, include_outro, custom_notes),
            daemon=True
        )
        thread.start()

    def run_ai_analysis_thread(self, api_key, video_path, style_preset, video_topic, task_spec, include_intro, explain_purpose, include_outro, custom_notes):
        try:
            items = analyze_video(
                api_key=api_key,
                video_path=video_path,
                style_preset=style_preset,
                video_topic=video_topic,
                task_spec=task_spec,
                include_intro=include_intro,
                explain_purpose=explain_purpose,
                include_outro=include_outro,
                custom_notes=custom_notes,
                log_callback=self.log_message
            )

            formatted_json = json.dumps(items, ensure_ascii=False, indent=2)
            
            def update_text():
                self.script_text.delete("1.0", tk.END)
                self.script_text.insert(tk.END, formatted_json)
                messagebox.showinfo("Успіх", f"ШІ успішно проаналізував відео та склав {len(items)} розгорнутих реплік!\nПерегляньте сценарій або відкрийте картковий редактор.")

            self.after(0, update_text)

        except Exception as e:
            error_str = str(e)
            self.log_message(f"❌ ПОМИЛКА: {error_str}")
            self.after(0, lambda: messagebox.showerror("Помилка ШІ-Аналізу", error_str))
        finally:
            self.set_ui_busy(False)

    def start_rendering(self):
        input_vid = self.input_video_path.get().strip()
        out_vid = self.output_video_path.get().strip()
        voice = self.voice_var.get()
        api_key = self.api_key_var.get().strip()
        script_content = self.script_text.get("1.0", tk.END).strip()

        if not input_vid or not os.path.exists(input_vid):
            messagebox.showerror("Помилка", "Оберіть дійсний вхідний відеофайл!")
            return

        if not out_vid:
            messagebox.showerror("Помилка", "Вкажіть шлях для збереження вихідного відео!")
            return

        if not script_content:
            messagebox.showerror("Помилка", "Сценарій озвучки порожній! Спочатку запустіть ШІ-аналіз або введіть JSON вручну.")
            return

        try:
            items = json.loads(script_content)
            if not isinstance(items, list) or len(items) == 0:
                raise ValueError("JSON має бути непорожнім списком реплік.")
        except Exception as e:
            messagebox.showerror("Помилка JSON", f"Помилка у структурі сценарію:\n{str(e)}")
            return

        self.set_ui_busy(True)
        self.log_message("🎬 Запуск озвучення та монтажу стоп-кадрів...")

        thread = threading.Thread(
            target=self.run_rendering_thread, 
            args=(input_vid, items, out_vid, voice, api_key),
            daemon=True
        )
        thread.start()

    def run_rendering_thread(self, input_vid, items, out_vid, voice, api_key):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(
                run_voiceover_pipeline(
                    input_vid, 
                    items, 
                    out_vid, 
                    voice, 
                    self.log_message,
                    api_key=api_key,
                    fallback_callback=self.prompt_voice_fallback
                )
            )
            
            self.after(0, lambda: messagebox.showinfo("Успіх", f"Відео успішно створено та збережено:\n{out_vid}"))
        except Exception as e:
            error_str = str(e)
            if "скасовано" in error_str.lower():
                self.log_message("🛑 Монтаж зупинено користувачем.")
            else:
                self.log_message(f"❌ ПОМИЛКА МОНТАЖУ: {error_str}")
                self.after(0, lambda: messagebox.showerror("Помилка монтажу", error_str))
        finally:
            self.set_ui_busy(False)

    def check_updates_background(self, manual: bool = False):
        if manual:
            self.btn_update_check.configure(text="🔄 Перевірка...", state="disabled")

        def _worker():
            try:
                update_info = check_for_updates(__version__)
                self.after(0, lambda: self._on_check_updates_complete(update_info, manual))
            except Exception as e:
                self.after(0, lambda: self._on_check_updates_error(str(e), manual))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_check_updates_complete(self, update_info, manual: bool):
        self.btn_update_check.configure(text=f"🔄 v{__version__}", state="normal")
        if update_info.has_update:
            self.btn_update_check.configure(
                text=f"🚀 Оновити ({update_info.latest_version})",
                fg_color=("#10b981", "#059669"),
                hover_color=("#059669", "#047857")
            )
            UpdateDialog(self, update_info)
        else:
            if manual:
                messagebox.showinfo(
                    "Оновлення", 
                    f"У вас встановлена найновіша версія PyVoice AI (v{__version__})! 🎉"
                )

    def _on_check_updates_error(self, err_msg: str, manual: bool):
        self.btn_update_check.configure(text=f"🔄 v{__version__}", state="normal")
        if manual:
            messagebox.showwarning(
                "Перевірка оновлень", 
                f"Не вдалося перевірити оновлення на GitHub:\n{err_msg}"
            )
