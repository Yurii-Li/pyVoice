import tkinter as tk
from tkinter import ttk, filedialog
import json

class ScriptEditorWindow(tk.Toplevel):
    """
    Просторе вікно для зручного редагування, перевірки та форматування сценарію озвучки
    зі світлою темою та вбудованим рядком сповіщень без настирливих попапів.
    """
    def __init__(self, parent, initial_content: str, on_save_callback):
        super().__init__(parent)
        self.title("✏️ Редактор сценарію озвучки - PyVoice AI")
        self.geometry("880x650")
        self.minsize(650, 450)
        
        self.parent = parent
        self.on_save_callback = on_save_callback
        
        # Центруємо вікно відносно батьківського
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 440
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 325
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self.create_widgets(initial_content)
        self.update_stats()

    def create_widgets(self, initial_content: str):
        # 1. Верхня панель інструментів
        top_bar = ttk.Frame(self, padding="8")
        top_bar.pack(fill=tk.X)

        ttk.Label(
            top_bar, 
            text="✏️ Редактор сценарію (JSON)", 
            font=("Segoe UI", 11, "bold")
        ).pack(side=tk.LEFT)

        btn_apply = ttk.Button(
            top_bar, 
            text="💾 Застосувати зміни", 
            command=self.apply_changes
        )
        btn_apply.pack(side=tk.RIGHT, padx=(6, 0))

        btn_format = ttk.Button(
            top_bar, 
            text="✨ Авто-форматування", 
            command=self.format_json
        )
        btn_format.pack(side=tk.RIGHT, padx=(6, 0))

        btn_validate = ttk.Button(
            top_bar, 
            text="🔍 Перевірити JSON", 
            command=self.validate_json
        )
        btn_validate.pack(side=tk.RIGHT, padx=(6, 0))

        btn_open = ttk.Button(
            top_bar, 
            text="📂 Відкрити файл", 
            command=self.open_file
        )
        btn_open.pack(side=tk.RIGHT, padx=(6, 0))

        btn_save_file = ttk.Button(
            top_bar, 
            text="💾 Зберегти у файл", 
            command=self.save_to_file
        )
        btn_save_file.pack(side=tk.RIGHT, padx=(6, 0))

        # 2. Вбудована панель сповіщень (Status Banner замість спливаючих вікон)
        self.banner_frame = tk.Frame(self, bg="#f1f2f6", padx=10, pady=4)
        self.banner_frame.pack(fill=tk.X)

        self.banner_label = tk.Label(
            self.banner_frame, 
            text="ℹ️ Редагуйте сценарій, додавайте або змінюйте репліки диктора.", 
            font=("Segoe UI", 9),
            bg="#f1f2f6",
            fg="#2f3542",
            anchor="w"
        )
        self.banner_label.pack(fill=tk.X)

        # 3. Текстовий редактор (Світла тема: білий фон, чорний текст)
        edit_frame = ttk.Frame(self, padding="8")
        edit_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(edit_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_widget = tk.Text(
            edit_frame, 
            wrap=tk.WORD, 
            undo=True,
            font=("Consolas", 11),
            bg="#ffffff",
            fg="#111111",
            insertbackground="#000000",
            selectbackground="#3399ff",
            selectforeground="#ffffff",
            yscrollcommand=scrollbar.set,
            padx=12,
            pady=10,
            relief="solid",
            bd=1
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text_widget.yview)

        # Вставляємо початковий текст
        self.text_widget.insert("1.0", initial_content)
        self.text_widget.bind("<KeyRelease>", lambda e: self.on_text_change())

        # 4. Нижня інформаційна панель
        bottom_bar = ttk.Frame(self, padding="6", relief="groove")
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.stats_label = ttk.Label(
            bottom_bar, 
            text="📊 Реплік: 0 | Символів: 0", 
            font=("Segoe UI", 9)
        )
        self.stats_label.pack(side=tk.LEFT)

        hint = ttk.Label(
            bottom_bar, 
            text="Ctrl+Z — відмінити | Ctrl+Y — повторити", 
            font=("Segoe UI", 8, "italic"),
            foreground="#666666"
        )
        hint.pack(side=tk.RIGHT)

    def show_banner(self, text: str, status: str = "info"):
        """Показує сповіщення у вбудованому банері з кольоровим акцентом"""
        colors = {
            "success": ("#e8f8f0", "#27ae60"), # світло-зелений фон, темно-зелений текст
            "error": ("#fde8e8", "#c0392b"),   # світло-червоний фон, червоний текст
            "warning": ("#fef9e7", "#d35400"), # світло-жовтий фон, помаранчевий текст
            "info": ("#f1f2f6", "#2f3542")     # сірий фон, темний текст
        }
        bg, fg = colors.get(status, colors["info"])
        self.banner_frame.config(bg=bg)
        self.banner_label.config(text=text, bg=bg, fg=fg)

    def on_text_change(self):
        self.update_stats()

    def update_stats(self):
        """Підраховує кількість реплік та символів у реальному часі"""
        content = self.text_widget.get("1.0", tk.END).strip()
        char_count = len(content)
        replicas_count = 0
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                replicas_count = len(parsed)
            elif isinstance(parsed, dict):
                for val in parsed.values():
                    if isinstance(val, list):
                        replicas_count = len(val)
                        break
        except Exception:
            pass
        self.stats_label.config(text=f"📊 Реплік: {replicas_count} | Символів: {char_count}")

    def format_json(self):
        """Красиво форматує JSON з правильними відступами без спливаючих попапів"""
        content = self.text_widget.get("1.0", tk.END).strip()
        if not content:
            self.show_banner("⚠️ Текстове поле порожнє — нічого форматувати.", "warning")
            return
        try:
            parsed = json.loads(content)
            formatted = json.dumps(parsed, ensure_ascii=False, indent=2)
            self.text_widget.delete("1.0", tk.END)
            self.text_widget.insert("1.0", formatted)
            self.update_stats()
            
            count = len(parsed) if isinstance(parsed, list) else 1
            self.show_banner(f"✨ JSON успішно відформатовано! Сформовано {count} реплік.", "success")
        except Exception as e:
            self.show_banner(f"❌ Помилка синтаксису JSON: {str(e)}", "error")

    def validate_json(self):
        """Перевіряє коректність структури сценарію без спливаючих вікон"""
        content = self.text_widget.get("1.0", tk.END).strip()
        if not content:
            self.show_banner("⚠️ Сценарій порожній.", "warning")
            return
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, list):
                raise ValueError("JSON має бути списком реплік: [ {\"start\": \"00:00\", \"text\": \"...\"} ]")
            for idx, item in enumerate(parsed):
                if not isinstance(item, dict) or "start" not in item or "text" not in item:
                    raise ValueError(f"Репліка #{idx+1} не має обов'язкових полів 'start' або 'text'.")
            self.show_banner(f"✅ Перевірка пройдена успішно! Сценарій валідний (всього {len(parsed)} реплік).", "success")
        except Exception as e:
            self.show_banner(f"❌ Помилка структури JSON: {str(e)}", "error")

    def apply_changes(self):
        """Зберігає відредагований текст назад у головне вікно"""
        content = self.text_widget.get("1.0", tk.END).strip()
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, list):
                raise ValueError("JSON має бути списком реплік: [ {\"start\": \"...\", \"text\": \"...\"} ]")
        except Exception as e:
            self.show_banner(f"❌ Не вдалося застосувати: виправте помилку JSON ({str(e)})", "error")
            return
        
        self.on_save_callback(content)
        self.destroy()

    def open_file(self):
        filename = filedialog.askopenfilename(filetypes=[("JSON сценарії", "*.json"), ("Усі файли", "*.*")])
        if filename:
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = f.read()
                self.text_widget.delete("1.0", tk.END)
                self.text_widget.insert("1.0", data)
                self.update_stats()
                self.show_banner(f"📂 Завантажено файл: {filename}", "info")
            except Exception as e:
                self.show_banner(f"❌ Не вдалося відкрити файл: {str(e)}", "error")

    def save_to_file(self):
        content = self.text_widget.get("1.0", tk.END).strip()
        if not content:
            self.show_banner("⚠️ Немає тексту для збереження.", "warning")
            return
        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON файли", "*.json")])
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                self.show_banner(f"💾 Сценарій успішно збережено у: {filename}", "success")
            except Exception as e:
                self.show_banner(f"❌ Не вдалося зберегти файл: {str(e)}", "error")
