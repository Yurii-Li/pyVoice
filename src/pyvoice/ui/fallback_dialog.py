import tkinter as tk
from tkinter import ttk

class VoiceFallbackDialog(tk.Toplevel):
    """
    Інтерактивне діалогове вікно, яке з'являється при вичерпанні лімітів або збої ШІ-голосу.
    Гарантовано відображає вибір альтернативного голосу та кнопки дій завдяки фіксованому розташуванню.
    """
    def __init__(self, parent, error_message: str, current_voice: str):
        super().__init__(parent)
        self.title("⚠️ Помилка синтезу голосу ШІ - PyVoice AI")
        self.geometry("600x470")
        self.minsize(540, 420)
        self.resizable(True, True)
        
        # Робимо вікно модальним
        self.transient(parent)
        self.grab_set()
        
        # Центрування вікна відносно батьківського
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 300
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 235
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self.chosen_voice = None
        self.cancelled = True
        
        self.create_widgets(error_message, current_voice)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def create_widgets(self, error_message: str, current_voice: str):
        main_frame = ttk.Frame(self, padding="14")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Заголовок та іконка
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 8))

        lbl_icon = ttk.Label(header_frame, text="⚠️", font=("Segoe UI", 26))
        lbl_icon.pack(side=tk.LEFT, padx=(0, 12))

        title_box = ttk.Frame(header_frame)
        title_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(
            title_box, 
            text="Виникла помилка під час синтезу ШІ-голосу", 
            font=("Segoe UI", 11, "bold"),
            foreground="#c0392b"
        ).pack(anchor="w")
        
        ttk.Label(
            title_box, 
            text=f"Поточний голос: {current_voice}", 
            font=("Segoe UI", 9, "italic"),
            foreground="#555555"
        ).pack(anchor="w")

        # 2. Пояснення для користувача
        summary_frame = tk.Frame(main_frame, bg="#fdf2e9", padx=8, pady=6, relief="groove", bd=1)
        summary_frame.pack(fill=tk.X, pady=(0, 8))
        
        ttk.Label(
            summary_frame,
            text="💡 Сервер Google повернув ліміт запитів. Щоб завершити створення відео без зупинки, оберіть надійний безлімітний голос нижче:",
            font=("Segoe UI", 9),
            background="#fdf2e9",
            wraplength=520,
            justify="left"
        ).pack(fill=tk.X)

        # 3. Деталі помилки (Компактне прокручуване поле)
        err_group = ttk.LabelFrame(main_frame, text=" Технічні деталі відповіді сервера ", padding="6")
        err_group.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        err_scroll = ttk.Scrollbar(err_group)
        err_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        err_text = tk.Text(
            err_group, 
            wrap=tk.WORD, 
            height=5, 
            font=("Consolas", 9),
            bg="#f9f9f9",
            fg="#2c3e50",
            yscrollcommand=err_scroll.set,
            bd=1,
            relief="solid"
        )
        err_text.pack(fill=tk.BOTH, expand=True)
        err_scroll.config(command=err_text.yview)

        err_text.insert("1.0", error_message)
        err_text.config(state="disabled")

        # 4. Вибір альтернативного голосу
        choice_box = ttk.LabelFrame(main_frame, text=" Оберіть голос для завершення монтажу (без лімітів) ", padding="8")
        choice_box.pack(fill=tk.X, pady=(0, 12))
        
        fallback_voices = [
            "Edge-TTS: Остап (🔥 Живий / Динамічний)",
            "Edge-TTS: Поліна (🔥 Жива / Динамічна)",
            "Edge-TTS: Остап (Базовий / Швидкий)",
            "Edge-TTS: Поліна (Базова / Швидка)"
        ]
        
        self.voice_var = tk.StringVar(value=fallback_voices[0])
        self.combo_voices = ttk.Combobox(
            choice_box, 
            textvariable=self.voice_var, 
            values=fallback_voices, 
            state="readonly", 
            width=48,
            font=("Segoe UI", 9)
        )
        self.combo_voices.pack(fill=tk.X, pady=2)

        # 5. Нижні кнопки дій (Завжди видимі)
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 0))

        btn_cancel = ttk.Button(btn_frame, text="🛑 Скасувати монтаж", command=self.on_cancel)
        btn_cancel.pack(side=tk.LEFT)

        btn_continue = ttk.Button(
            btn_frame, 
            text="🔄 Продовжити з обраним голосом", 
            command=self.on_continue
        )
        btn_continue.pack(side=tk.RIGHT)

    def on_continue(self):
        self.chosen_voice = self.voice_var.get()
        self.cancelled = False
        self.destroy()

    def on_cancel(self):
        self.chosen_voice = None
        self.cancelled = True
        self.destroy()
