import tkinter as tk
import customtkinter as ctk
import datetime
from pyvoice.ui.shortcuts import bring_to_front

class LogViewerWindow(ctk.CTkToplevel):
    """Окреме сучасне модальне / плаваюче вікно для зручного перегляду логів у реальному часі"""
    def __init__(self, parent, log_history=None):
        super().__init__(parent)
        self.title("📜 Журнал виконання (Логи) - PyVoice AI")
        self.geometry("760x520")
        self.minsize(540, 340)
        
        # Центруємо відносно батьківського вікна
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 380
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 260
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self.parent = parent
        self.create_widgets()
        
        # Завантажуємо історію, якщо є
        if log_history:
            for item in log_history:
                self.append_log(item, is_history=True)

        bring_to_front(self, parent)

    def create_widgets(self):
        self.configure(fg_color=("#f8fafc", "#090d16"))
        main_box = ctk.CTkFrame(
            self, 
            corner_radius=14,
            fg_color=("#ffffff", "#0e1424"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        main_box.pack(fill="both", expand=True, padx=14, pady=14)

        # Верхня панель дій
        top_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        top_frame.pack(fill="x", padx=16, pady=(14, 10))

        title_badge = ctk.CTkFrame(top_frame, width=32, height=32, corner_radius=8, fg_color=("#e0f2fe", "#082f49"))
        title_badge.pack(side="left", padx=(0, 10))
        title_badge.pack_propagate(False)
        ctk.CTkLabel(title_badge, text="📜", font=ctk.CTkFont(size=16)).place(relx=0.5, rely=0.5, anchor="center")

        title_lbl = ctk.CTkLabel(
            top_frame, 
            text="Журнал виконання та логів у реальному часі", 
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=("gray10", "white")
        )
        title_lbl.pack(side="left")

        btn_close = ctk.CTkButton(
            top_frame, 
            text="Закрити", 
            width=85, 
            height=30,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.destroy
        )
        btn_close.pack(side="right", padx=(6, 0))

        btn_copy = ctk.CTkButton(
            top_frame, 
            text="📋 Скопіювати все", 
            width=135, 
            height=30,
            corner_radius=8,
            fg_color=("#4f46e5", "#4338ca"),
            hover_color=("#4338ca", "#3730a3"),
            font=ctk.CTkFont(weight="bold"),
            command=self.copy_all
        )
        btn_copy.pack(side="right", padx=(6, 0))

        btn_clear = ctk.CTkButton(
            top_frame, 
            text="🧹 Очистити", 
            width=100, 
            height=30,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.clear_logs
        )
        btn_clear.pack(side="right")

        # Текстове поле з логами (глибокий термінальний стиль)
        self.text_widget = ctk.CTkTextbox(
            main_box, 
            font=("Consolas", 11),
            corner_radius=10,
            fg_color=("#f8fafc", "#020617"),
            border_color=("#cbd5e1", "#1e293b"),
            border_width=1,
            activate_scrollbars=True
        )
        self.text_widget.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Теги для кольорового форматування
        self.text_widget.tag_config("time", foreground="#888888")
        self.text_widget.tag_config("error", foreground="#f87171")
        self.text_widget.tag_config("success", foreground="#4ade80")
        self.text_widget.tag_config("info", foreground="#60a5fa")
        self.text_widget.tag_config("warning", foreground="#fbbf24")

    def append_log(self, message: str, is_history: bool = False):
        """Додає новий запис у журнал з міткою часу та відповідним кольором"""
        self.text_widget.configure(state="normal")
        
        # Якщо повідомлення вже містить таймштамп, не додаємо новий
        if message.startswith("["):
            formatted_msg = message
            tag = "normal"
            if "❌" in message or "ПОМИЛКА" in message.upper():
                tag = "error"
            elif "✅" in message or "🎉" in message:
                tag = "success"
            elif "🚀" in message or "👁️" in message or "🎙" in message:
                tag = "info"
            elif "⚠️" in message:
                tag = "warning"
                
            self.text_widget.insert("end", formatted_msg + "\n", tag)
        else:
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            tag = "normal"
            if "❌" in message or "ПОМИЛКА" in message.upper():
                tag = "error"
            elif "✅" in message or "🎉" in message:
                tag = "success"
            elif "🚀" in message or "👁️" in message or "🎙" in message or "🎬" in message:
                tag = "info"
            elif "⚠️" in message:
                tag = "warning"
                
            self.text_widget.insert("end", f"[{now_str}] ", "time")
            self.text_widget.insert("end", message + "\n", tag)
            
        self.text_widget.see("end")

    def copy_all(self):
        """Копіює весь вміст логів у буфер обміну"""
        content = self.text_widget.get("1.0", "end").strip()
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)

    def clear_logs(self):
        """Очищує вікно логів"""
        self.text_widget.delete("1.0", "end")
