import tkinter as tk
from tkinter import ttk

class VoiceFallbackDialog(tk.Toplevel):
    """
    Інтерактивне діалогове вікно, яке з'являється при вичерпанні лімітів або збої ШІ-голосу.
    Дозволяє користувачу обрати інший надійний голос (Edge TTS) або скасувати процес.
    """
    def __init__(self, parent, error_message: str, current_voice: str):
        super().__init__(parent)
        self.title("⚠️ Помилка синтезу голосу ШІ - PyVoice AI")
        self.geometry("540x320")
        self.resizable(False, False)
        
        # Робимо вікно модальним
        self.transient(parent)
        self.grab_set()
        
        # Центрування вікна відносно батьківського
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 270
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 160
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self.chosen_voice = None
        self.cancelled = True
        
        self.create_widgets(error_message, current_voice)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def create_widgets(self, error_message: str, current_voice: str):
        main_frame = ttk.Frame(self, padding="16")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Заголовок та іконка
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        lbl_icon = ttk.Label(header_frame, text="⚠️", font=("Segoe UI", 24))
        lbl_icon.pack(side=tk.LEFT, padx=(0, 10))

        title_box = ttk.Frame(header_frame)
        title_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(
            title_box, 
            text="Виникла помилка під час ШІ-озвучення", 
            font=("Segoe UI", 11, "bold"),
            foreground="#c0392b"
        ).pack(anchor="w")
        
        ttk.Label(
            title_box, 
            text=f"Поточний голос: {current_voice}", 
            font=("Segoe UI", 9, "italic"),
            foreground="#555555"
        ).pack(anchor="w")

        # Опис помилки
        err_box = ttk.LabelFrame(main_frame, text=" Деталі помилки ", padding="8")
        err_box.pack(fill=tk.X, pady=(0, 12))

        lbl_err = ttk.Label(
            err_box, 
            text=error_message, 
            font=("Segoe UI", 9), 
            wraplength=480, 
            justify="left",
            foreground="#2c3e50"
        )
        lbl_err.pack(fill=tk.X)

        # Вибір альтернативного голосу
        choice_box = ttk.Frame(main_frame)
        choice_box.pack(fill=tk.X, pady=(0, 16))

        ttk.Label(choice_box, text="Оберіть голос для продовження (без лімітів):", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        
        fallback_voices = [
            "Edge-TTS: Остап (🔥 Живий / Динамічний)",
            "Edge-TTS: Поліна (🔥 Жива / Динамічна)",
            "Edge-TTS: Остап (Базовий / Швидкий)",
            "Edge-TTS: Поліна (Базова / Швидка)"
        ]
        
        self.voice_var = tk.StringVar(value=fallback_voices[0])
        self.combo_voices = ttk.Combobox(choice_box, textvariable=self.voice_var, values=fallback_voices, state="readonly", width=45)
        self.combo_voices.pack(fill=tk.X)

        # Кнопки дій
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

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
