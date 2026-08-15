import tkinter as tk
from tkinter import ttk, messagebox
import datetime

class LogViewerWindow(tk.Toplevel):
    """Окреме модальне / плаваюче вікно для зручного перегляду логів у реальному часі"""
    def __init__(self, parent, log_history=None):
        super().__init__(parent)
        self.title("📜 Журнал виконання (Логи) - PyVoice AI")
        self.geometry("720x480")
        self.minsize(500, 300)
        
        # Центруємо відносно батьківського вікна
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 360
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 240
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self.parent = parent
        self.create_widgets()
        
        # Завантажуємо історію, якщо є
        if log_history:
            for item in log_history:
                self.append_log(item, is_history=True)

    def create_widgets(self):
        # Верхня панель дій
        top_frame = ttk.Frame(self, padding="8")
        top_frame.pack(fill=tk.X)

        title_lbl = ttk.Label(
            top_frame, 
            text=" Журнал подій та процесів у реальному часі", 
            font=("Segoe UI", 10, "bold")
        )
        title_lbl.pack(side=tk.LEFT)

        btn_close = ttk.Button(top_frame, text="Закрити", command=self.destroy)
        btn_close.pack(side=tk.RIGHT, padx=(5, 0))

        btn_copy = ttk.Button(top_frame, text="📋 Скопіювати все", command=self.copy_all)
        btn_copy.pack(side=tk.RIGHT, padx=(5, 0))

        btn_clear = ttk.Button(top_frame, text="🧹 Очистити", command=self.clear_logs)
        btn_clear.pack(side=tk.RIGHT, padx=(5, 0))

        # Текстове поле з логами (темна тема для читабельності)
        text_frame = ttk.Frame(self, padding="8")
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.text_widget = tk.Text(
            text_frame, 
            wrap=tk.WORD, 
            bg="#181818", 
            fg="#e0e0e0", 
            insertbackground="white",
            font=("Consolas", 10),
            padx=10, 
            pady=10
        )
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_widget.config(yscrollcommand=scrollbar.set)

        # Теги для кольорового форматування
        self.text_widget.tag_config("time", foreground="#888888")
        self.text_widget.tag_config("error", foreground="#ff6b6b", font=("Consolas", 10, "bold"))
        self.text_widget.tag_config("success", foreground="#51cf66")
        self.text_widget.tag_config("info", foreground="#339af0")
        self.text_widget.tag_config("warning", foreground="#fcc419")

    def append_log(self, message: str, is_history: bool = False):
        """Додає новий запис у журнал з міткою часу та відповідним кольором"""
        self.text_widget.config(state=tk.NORMAL)
        
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
                
            self.text_widget.insert(tk.END, formatted_msg + "\n", tag)
        else:
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            tag = "normal"
            if "❌" in message or "ПОМИЛКА" in message.upper():
                tag = "error"
            elif "✅" in message or "🎉" in message:
                tag = "success"
            elif "🚀" in message or "👁️" in message or "🎙" in message or "🎬" in message:
                tag = "info"

            self.text_widget.insert(tk.END, f"[{now_str}] ", "time")
            self.text_widget.insert(tk.END, f"{message}\n", tag)

        self.text_widget.see(tk.END)
        self.text_widget.config(state=tk.DISABLED)

    def copy_all(self):
        content = self.text_widget.get("1.0", tk.END).strip()
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
            messagebox.showinfo("Скопійовано", "Усі логи успішно скопійовано в буфер обміну!")

    def clear_logs(self):
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.config(state=tk.DISABLED)
        if hasattr(self.parent, "log_history"):
            self.parent.log_history.clear()
