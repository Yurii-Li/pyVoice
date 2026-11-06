import tkinter as tk
import customtkinter as ctk
from pyvoice.ui.shortcuts import bring_to_front

class VoiceFallbackDialog(ctk.CTkToplevel):
    """
    Сучасне інтерактивне діалогове вікно CustomTkinter, яке з'являється
    при вичерпанні лімітів або збої ШІ-голосу Gemini.
    """
    def __init__(self, parent, error_message: str, current_voice: str):
        super().__init__(parent)
        self.title("⚠️ Помилка синтезу голосу ШІ - PyVoice AI")
        self.geometry("620x500")
        self.minsize(540, 420)
        self.resizable(True, True)
        
        # Модальне вікно
        self.transient(parent)
        self.grab_set()
        
        # Центрування вікна відносно батьківського
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 310
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 250
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self.chosen_voice = None
        self.cancelled = True
        
        self.create_widgets(error_message, current_voice)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        bring_to_front(self, parent)

    def create_widgets(self, error_message: str, current_voice: str):
        self.configure(fg_color=("#f8fafc", "#090d16"))
        main_box = ctk.CTkFrame(
            self, 
            corner_radius=14,
            fg_color=("#ffffff", "#0e1424"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        main_box.pack(fill="both", expand=True, padx=14, pady=14)

        # 1. Заголовок та іконка
        header_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        header_frame.pack(fill="x", padx=16, pady=(16, 10))

        icon_frame = ctk.CTkFrame(header_frame, width=44, height=44, corner_radius=12, fg_color=("#fee2e2", "#450a0a"))
        icon_frame.pack(side="left", padx=(0, 14))
        icon_frame.pack_propagate(False)
        ctk.CTkLabel(icon_frame, text="⚠️", font=ctk.CTkFont(size=22)).place(relx=0.5, rely=0.5, anchor="center")

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            title_box, 
            text="Виникла помилка під час синтезу ШІ-голосу", 
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=("#ef4444", "#f87171")
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            title_box, 
            text=f"Поточний голос: {current_voice}", 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#64748b", "#94a3b8")
        ).pack(anchor="w")

        # 2. Пояснення для користувача
        summary_frame = ctk.CTkFrame(main_box, corner_radius=8, fg_color=("#f1f5f9", "#111827"), border_color=("#e2e8f0", "#1e293b"), border_width=1)
        summary_frame.pack(fill="x", padx=16, pady=(0, 10))
        
        ctk.CTkLabel(
            summary_frame,
            text="💡 Сервер Google повернув тимчасовий ліміт запитів. Щоб завершити створення відео без зупинки, оберіть надійний безлімітний голос нижче:",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#475569", "#94a3b8"),
            wraplength=550,
            justify="left"
        ).pack(fill="x", padx=14, pady=8)

        # 3. Деталі помилки
        err_box = ctk.CTkFrame(main_box, corner_radius=8, fg_color=("#f8fafc", "#020617"), border_color=("#cbd5e1", "#1e293b"), border_width=1)
        err_box.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        ctk.CTkLabel(
            err_box, 
            text="Технічні деталі відповіді сервера:", 
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        ).pack(anchor="w", padx=12, pady=(6, 2))

        self.err_text = ctk.CTkTextbox(
            err_box, 
            height=90, 
            font=("Consolas", 10),
            corner_radius=6,
            fg_color=("#f8fafc", "#020617"),
            border_width=0
        )
        self.err_text.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.err_text.insert("1.0", error_message)
        self.err_text.configure(state="disabled")

        # 4. Вибір альтернативного голосу
        choice_box = ctk.CTkFrame(main_box, corner_radius=8, fg_color=("#f1f5f9", "#111827"), border_color=("#e2e8f0", "#1e293b"), border_width=1)
        choice_box.pack(fill="x", padx=16, pady=(0, 14))
        
        ctk.CTkLabel(
            choice_box, 
            text="Оберіть голос для завершення монтажу (без лімітів):", 
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        ).pack(anchor="w", padx=12, pady=(8, 4))

        fallback_voices = [
            "Edge-TTS: Остап (🔥 Живий / Динамічний)",
            "Edge-TTS: Поліна (🔥 Жива / Динамічна)",
            "Edge-TTS: Остап (Базовий / Швидкий)",
            "Edge-TTS: Поліна (Базова / Швидка)"
        ]
        
        self.voice_var = tk.StringVar(value=fallback_voices[0])
        self.combo_voices = ctk.CTkOptionMenu(
            choice_box, 
            values=fallback_voices,
            variable=self.voice_var,
            height=34,
            corner_radius=8,
            fg_color=("#ffffff", "#1e293b"),
            button_color=("#059669", "#047857"),
            button_hover_color=("#047857", "#065f46"),
            dropdown_fg_color=("#ffffff", "#111827"),
            dropdown_hover_color=("#f1f5f9", "#1e293b"),
            text_color=("#0f172a", "#f8fafc"),
            dynamic_resizing=False
        )
        self.combo_voices.pack(fill="x", padx=12, pady=(0, 12))

        # 5. Нижні кнопки дій
        btn_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 16), side="bottom")

        btn_cancel = ctk.CTkButton(
            btn_frame, 
            text="🛑 Скасувати монтаж", 
            height=34,
            corner_radius=8,
            fg_color=("#ef4444", "#dc2626"),
            hover_color=("#dc2626", "#b91c1c"),
            command=self.on_cancel
        )
        btn_cancel.pack(side="left")

        btn_continue = ctk.CTkButton(
            btn_frame, 
            text="🔄 Продовжити з обраним голосом", 
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(weight="bold"),
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            command=self.on_continue
        )
        btn_continue.pack(side="right")

    def on_continue(self):
        self.chosen_voice = self.voice_var.get()
        self.cancelled = False
        self.destroy()

    def on_cancel(self):
        self.chosen_voice = None
        self.cancelled = True
        self.destroy()
