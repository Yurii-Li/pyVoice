import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import asyncio
import os
import json
import webbrowser
import datetime

from pyvoice.core.config import load_app_config, save_app_config
from pyvoice.core.gemini import analyze_video
from pyvoice.core.pipeline import run_voiceover_pipeline
from pyvoice.ui.log_viewer import LogViewerWindow

class PyVoiceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PyVoice AI - Авто-Озвучка дій у відео зі стоп-кадрами")
        self.geometry("780x740")
        self.minsize(720, 650)
        
        # Тема оформлення
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use('clam')
            
        # Змінні
        self.api_key_var = tk.StringVar()
        self.input_video_path = tk.StringVar()
        self.output_video_path = tk.StringVar()
        self.voice_var = tk.StringVar(value="uk-UA-OstapNeural")
        
        # Налаштування стилю та глибини озвучки
        self.video_topic_var = tk.StringVar()
        self.style_var = tk.StringVar(value="Детальний туторіал (з привітанням, поясненням суті та користі дій)")
        self.custom_notes_var = tk.StringVar()
        self.include_intro_var = tk.BooleanVar(value=True)
        self.explain_purpose_var = tk.BooleanVar(value=True)
        self.include_outro_var = tk.BooleanVar(value=True)
        
        # Статус та логування
        self.status_var = tk.StringVar(value="🟢 Готовий до роботи")
        self.log_history = []
        self.log_window = None
        
        self.load_config()
        self.create_widgets()
        
    def load_config(self):
        cfg = load_app_config()
        self.api_key_var.set(cfg.get("gemini_api_key", ""))
        self.voice_var.set(cfg.get("voice", "uk-UA-OstapNeural"))
        self.style_var.set(cfg.get("style", "Детальний туторіал (з привітанням, поясненням суті та користі дій)"))
        self.video_topic_var.set(cfg.get("video_topic", ""))
        self.custom_notes_var.set(cfg.get("custom_notes", ""))
        self.include_intro_var.set(cfg.get("include_intro", True))
        self.explain_purpose_var.set(cfg.get("explain_purpose", True))
        self.include_outro_var.set(cfg.get("include_outro", True))
                
    def save_config(self):
        cfg = {
            "gemini_api_key": self.api_key_var.get().strip(),
            "voice": self.voice_var.get(),
            "style": self.style_var.get(),
            "video_topic": self.video_topic_var.get(),
            "custom_notes": self.custom_notes_var.get(),
            "include_intro": self.include_intro_var.get(),
            "explain_purpose": self.explain_purpose_var.get(),
            "include_outro": self.include_outro_var.get()
        }
        save_app_config(cfg)

    def open_api_key_url(self):
        webbrowser.open("https://aistudio.google.com/app/apikey")

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="12")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # -------------------------------------------------------------
        # СЕКЦІЯ 1: Налаштування ШІ та Стилю озвучки
        # -------------------------------------------------------------
        ai_group = ttk.LabelFrame(main_frame, text=" 1. Налаштування ШІ-Сценариста (Google Gemini Vision) ", padding="10")
        ai_group.pack(fill=tk.X, pady=(0, 8))

        # Рядок 0: API Key
        ttk.Label(ai_group, text="Gemini API Key:").grid(row=0, column=0, sticky="w", pady=2)
        self.api_entry = ttk.Entry(ai_group, textvariable=self.api_key_var, show="*", width=34)
        self.api_entry.grid(row=0, column=1, padx=5, pady=2, sticky="we")

        btn_get_key = ttk.Button(ai_group, text="🔑 Отримати ключ", command=self.open_api_key_url)
        btn_get_key.grid(row=0, column=2, padx=5, pady=2)

        self.show_key_var = tk.BooleanVar(value=False)
        def toggle_key_visibility():
            self.api_entry.config(show="" if self.show_key_var.get() else "*")
        ttk.Checkbutton(ai_group, text="Показати", variable=self.show_key_var, command=toggle_key_visibility).grid(row=0, column=3, padx=2)

        # Рядок 1: Тема / Контекст відео
        ttk.Label(ai_group, text="Про що відео / Контекст:").grid(row=1, column=0, sticky="w", pady=3)
        entry_topic = ttk.Entry(ai_group, textvariable=self.video_topic_var, width=45)
        entry_topic.grid(row=1, column=1, columnspan=3, padx=5, pady=3, sticky="we")

        # Рядок 2: Стиль коментатора
        ttk.Label(ai_group, text="Стиль подачі:").grid(row=2, column=0, sticky="w", pady=3)
        styles = [
            "Детальний туторіал (з привітанням, поясненням суті та користі дій)",
            "Блогерський розмовний стиль (живі емоції, динаміка, звернення до глядачів)",
            "Офіційна презентація продукту (діловий тон, чітка демонстрація)",
            "Лаконічний опис дій (лише факти та кроки)",
            "Власний стиль"
        ]
        style_cb = ttk.Combobox(ai_group, textvariable=self.style_var, values=styles, state="normal", width=42)
        style_cb.grid(row=2, column=1, columnspan=3, padx=5, pady=3, sticky="we")

        # Рядок 3: Додаткові опції (Чекбокси)
        opts_frame = ttk.Frame(ai_group)
        opts_frame.grid(row=3, column=0, columnspan=4, sticky="we", pady=4)
        
        ttk.Checkbutton(opts_frame, text="👋 Привітання на початку (00:00)", variable=self.include_intro_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(opts_frame, text="💡 Пояснювати призначення та користь функцій", variable=self.explain_purpose_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(opts_frame, text="🏁 Підсумок у кінці", variable=self.include_outro_var).pack(side=tk.LEFT)

        # Рядок 4: Додаткові побажання
        ttk.Label(ai_group, text="Додаткові побажання:").grid(row=4, column=0, sticky="w", pady=3)
        entry_notes = ttk.Entry(ai_group, textvariable=self.custom_notes_var, width=45)
        entry_notes.grid(row=4, column=1, columnspan=3, padx=5, pady=3, sticky="we")

        ai_group.columnconfigure(1, weight=1)

        # -------------------------------------------------------------
        # СЕКЦІЯ 2: Відеофайли та Аналіз
        # -------------------------------------------------------------
        video_group = ttk.LabelFrame(main_frame, text=" 2. Вибір відео та запуск ШІ-Аналізу ", padding="10")
        video_group.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(video_group, text="Вхідне відео:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(video_group, textvariable=self.input_video_path, width=45).grid(row=0, column=1, padx=5, pady=2, sticky="we")
        ttk.Button(video_group, text="Огляд...", command=self.browse_video).grid(row=0, column=2, pady=2)

        self.btn_analyze = ttk.Button(
            video_group, 
            text="👁️ Проаналізувати дії у відео через ШІ (Скласти розгорнутий сценарій)", 
            command=self.start_ai_analysis
        )
        self.btn_analyze.grid(row=1, column=0, columnspan=3, pady=(6, 2), sticky="we")

        video_group.columnconfigure(1, weight=1)

        # -------------------------------------------------------------
        # СЕКЦІЯ 3: Редактор сценарію / таймкодів
        # -------------------------------------------------------------
        script_group = ttk.LabelFrame(main_frame, text=" 3. Сценарій озвучки з таймкодами (можна редагувати перед монтажем) ", padding="10")
        script_group.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        btn_toolbar = ttk.Frame(script_group)
        btn_toolbar.pack(fill=tk.X, pady=(0, 4))
        
        ttk.Button(btn_toolbar, text="📂 Відкрити JSON", command=self.load_json_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_toolbar, text="💾 Зберегти JSON", command=self.save_json_file).pack(side=tk.LEFT)
        ttk.Label(btn_toolbar, text="Формат: [{\"start\": \"00:00\", \"text\": \"...\"}]", font=("Segoe UI", 8, "italic")).pack(side=tk.RIGHT)

        self.script_text = tk.Text(script_group, height=8, wrap=tk.WORD, font=("Consolas", 10))
        self.script_text.pack(fill=tk.BOTH, expand=True)

        # -------------------------------------------------------------
        # СЕКЦІЯ 4: Озвучка та Фінальний рендер
        # -------------------------------------------------------------
        render_group = ttk.LabelFrame(main_frame, text=" 4. Озвучення та Синхронізація стоп-кадрів ", padding="10")
        render_group.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(render_group, text="Голос диктора:").grid(row=0, column=0, sticky="w", pady=2)
        voices = ["uk-UA-OstapNeural (Чоловічий)", "uk-UA-PolinaNeural (Жіночий)"]
        self.voice_display_var = tk.StringVar(value=voices[0] if "Ostap" in self.voice_var.get() else voices[1])
        
        def on_voice_change(e=None):
            if "Ostap" in self.voice_display_var.get():
                self.voice_var.set("uk-UA-OstapNeural")
            else:
                self.voice_var.set("uk-UA-PolinaNeural")
        
        voice_cb = ttk.Combobox(render_group, textvariable=self.voice_display_var, values=voices, state="readonly", width=30)
        voice_cb.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        voice_cb.bind("<<ComboboxSelected>>", on_voice_change)

        ttk.Label(render_group, text="Куди зберегти відео:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(render_group, textvariable=self.output_video_path, width=45).grid(row=1, column=1, padx=5, pady=2, sticky="we")
        ttk.Button(render_group, text="Огляд...", command=self.browse_output).grid(row=1, column=2, pady=2)

        self.btn_render = ttk.Button(
            render_group, 
            text="🎬 Створити фінальне відео зі стоп-кадрами та озвучкою", 
            command=self.start_rendering
        )
        self.btn_render.grid(row=2, column=0, columnspan=3, pady=(8, 2), sticky="we")

        render_group.columnconfigure(1, weight=1)

        # -------------------------------------------------------------
        # СЕКЦІЯ 5: Інтерактивний Status Bar (UX/UI Friendly)
        # -------------------------------------------------------------
        status_bar = ttk.Frame(main_frame, padding="6", relief="groove")
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Подвійний клік на статус відкриває вікно логів
        status_bar.bind("<Double-Button-1>", lambda e: self.open_log_window())

        # Індикатор прогресу
        self.progress_bar = ttk.Progressbar(status_bar, mode='indeterminate', length=120)
        self.progress_bar.pack(side=tk.RIGHT, padx=(10, 0))

        # Кнопка відкриття логів
        btn_open_logs = ttk.Button(status_bar, text="📜 Журнал логів", command=self.open_log_window)
        btn_open_logs.pack(side=tk.RIGHT, padx=(5, 0))

        # Текст статусу
        self.status_label = ttk.Label(
            status_bar, 
            textvariable=self.status_var, 
            font=("Segoe UI", 9, "bold"),
            anchor="w",
            cursor="hand2"
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.status_label.bind("<Double-Button-1>", lambda e: self.open_log_window())
        
        # Підказка
        hint_label = ttk.Label(
            status_bar, 
            text=" (двічі клікніть для деталей)", 
            font=("Segoe UI", 8, "italic"),
            foreground="#888888"
        )
        hint_label.pack(side=tk.LEFT)
        hint_label.bind("<Double-Button-1>", lambda e: self.open_log_window())

    def open_log_window(self):
        """Відкриває або активує модальне/окреме вікно логів"""
        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.lift()
            self.log_window.focus_force()
        else:
            self.log_window = LogViewerWindow(self, self.log_history)

    def log_message(self, message: str):
        """Оновлює рядок статусу в головному вікні та надсилає повідомлення у вікно логів"""
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        full_entry = f"[{now_str}] {message}"
        self.log_history.append(full_entry)
        
        def _update():
            # Оновлюємо рядок статусу (беремо чистий текст без зайвих переносів)
            clean_status = message.replace("\n", " ")
            if len(clean_status) > 70:
                clean_status = clean_status[:67] + "..."
            self.status_var.set(clean_status)
            
            # Якщо вікно логів відкрито — додаємо запис туди
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
            state = tk.DISABLED if busy else tk.NORMAL
            self.btn_analyze.config(state=state)
            self.btn_render.config(state=state)
            if busy:
                self.progress_bar.start(10)
            else:
                self.progress_bar.stop()
        self.after(0, _set)

    def start_ai_analysis(self):
        api_key = self.api_key_var.get().strip()
        video_path = self.input_video_path.get().strip()
        style_preset = self.style_var.get().strip()
        video_topic = self.video_topic_var.get().strip()
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

        self.save_config()
        self.set_ui_busy(True)
        self.log_message("🚀 Початок Vision AI аналізу відео...")

        thread = threading.Thread(
            target=self.run_ai_analysis_thread, 
            args=(api_key, video_path, style_preset, video_topic, include_intro, explain_purpose, include_outro, custom_notes),
            daemon=True
        )
        thread.start()

    def run_ai_analysis_thread(self, api_key, video_path, style_preset, video_topic, include_intro, explain_purpose, include_outro, custom_notes):
        try:
            items = analyze_video(
                api_key=api_key,
                video_path=video_path,
                style_preset=style_preset,
                video_topic=video_topic,
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
                messagebox.showinfo("Успіх", f"ШІ успішно проаналізував відео та склав {len(items)} розгорнутих реплік!\nПерегляньте сценарій у Секції 3.")

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

        self.save_config()
        self.set_ui_busy(True)
        self.log_message("🎬 Запуск озвучення та монтажу стоп-кадрів...")

        thread = threading.Thread(
            target=self.run_rendering_thread, 
            args=(input_vid, items, out_vid, voice),
            daemon=True
        )
        thread.start()

    def run_rendering_thread(self, input_vid, items, out_vid, voice):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(
                run_voiceover_pipeline(
                    input_vid, 
                    items, 
                    out_vid, 
                    voice, 
                    self.log_message
                )
            )
            
            self.after(0, lambda: messagebox.showinfo("Успіх", f"Відео успішно створено та збережено:\n{out_vid}"))
        except Exception as e:
            error_str = str(e)
            self.log_message(f"❌ ПОМИЛКА МОНТАЖУ: {error_str}")
            self.after(0, lambda: messagebox.showerror("Помилка монтажу", error_str))
        finally:
            self.set_ui_busy(False)
