import tkinter as tk
from tkinter import ttk, filedialog
import os

TEMPLATE_TASK_SPEC = """- [x] #### Назва задачі / Фічі (наприклад, Переміщення між складами)
  Короткий опис: що робить функціонал, які додано поля, колонки або чекбокси.
  (Технічні деталі, логіка розрахунку, назви таблиць або умови відбору)

- [x] #### Інша задача з беклогу
  Опис поведінки та вимог...
"""

class TaskSpecDialog(tk.Toplevel):
    """
    Зручне вікно для введення, завантаження з файлу та редагування
    Технічного Завдання (ТЗ), списків завдань, Jira-тікетів, PR-описів або чеклістів.
    """
    def __init__(self, parent, initial_text: str, on_save_callback):
        super().__init__(parent)
        self.title("📋 Технічне завдання / Опис задачі (ТЗ) - PyVoice AI")
        self.geometry("820x600")
        self.minsize(620, 420)
        
        self.parent = parent
        self.on_save_callback = on_save_callback
        self.resizable(True, True)
        
        # Центруємо вікно відносно батьківського
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 410
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 300
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self.create_widgets(initial_text)
        self.update_stats()
        
        self.lift()
        self.focus_force()

    def create_widgets(self, initial_text: str):
        # 1. Верхня панель інструментів (Toolbar)
        top_bar = ttk.Frame(self, padding="8")
        top_bar.pack(fill=tk.X)

        ttk.Label(
            top_bar, 
            text="📋 Технічне завдання / Контекст задачі", 
            font=("Segoe UI", 11, "bold")
        ).pack(side=tk.LEFT)

        btn_apply = ttk.Button(
            top_bar, 
            text="💾 Застосувати", 
            command=self.apply_changes
        )
        btn_apply.pack(side=tk.RIGHT, padx=(6, 0))

        btn_clear = ttk.Button(
            top_bar, 
            text="🧹 Очистити", 
            command=self.clear_text
        )
        btn_clear.pack(side=tk.RIGHT, padx=(6, 0))

        btn_template = ttk.Button(
            top_bar, 
            text="📝 Шаблон ТЗ", 
            command=self.insert_template
        )
        btn_template.pack(side=tk.RIGHT, padx=(6, 0))

        btn_save = ttk.Button(
            top_bar, 
            text="💾 Зберегти у файл", 
            command=self.save_to_file
        )
        btn_save.pack(side=tk.RIGHT, padx=(6, 0))

        btn_open = ttk.Button(
            top_bar, 
            text="📂 Відкрити файл", 
            command=self.open_file
        )
        btn_open.pack(side=tk.RIGHT, padx=(6, 0))

        # 2. Інформаційний банер підказок
        self.banner_frame = tk.Frame(self, bg="#eef2f7", padx=10, pady=5)
        self.banner_frame.pack(fill=tk.X)

        self.banner_label = tk.Label(
            self.banner_frame, 
            text="💡 Сюди можна просто скопіювати список задач, чекліст із беклогу чи короткі технічні нотатки. ШІ сам визначить, яка саме задача показана у відео, та використає її терміни й логіку для точної озвучки.", 
            font=("Segoe UI", 9),
            bg="#eef2f7",
            fg="#2c3e50",
            anchor="w",
            wraplength=780,
            justify=tk.LEFT
        )
        self.banner_label.pack(fill=tk.X)

        # 3. Текстове поле
        edit_frame = ttk.Frame(self, padding="8")
        edit_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(edit_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_widget = tk.Text(
            edit_frame, 
            wrap=tk.WORD, 
            undo=True,
            font=("Segoe UI", 10),
            bg="#ffffff",
            fg="#111111",
            insertbackground="#000000",
            selectbackground="#cce8ff",
            selectforeground="#000000",
            relief="solid",
            borderwidth=1,
            padx=10,
            pady=10,
            yscrollcommand=scrollbar.set
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text_widget.yview)

        # Вставляємо початковий текст
        if initial_text:
            self.text_widget.insert("1.0", initial_text)

        # 4. Нижня панель статистики
        bottom_bar = ttk.Frame(self, padding="8")
        bottom_bar.pack(fill=tk.X)

        self.stats_label = ttk.Label(
            bottom_bar, 
            text="Символів: 0 | Слів: 0 | Рядків: 0", 
            font=("Segoe UI", 9, "bold")
        )
        self.stats_label.pack(side=tk.LEFT)

        hint_label = ttk.Label(
            bottom_bar, 
            text="Ctrl+Z: Відмінити  •  Ctrl+A: Виділити все", 
            font=("Segoe UI", 8),
            foreground="#666666"
        )
        hint_label.pack(side=tk.RIGHT)

        # Події для оновлення статистики
        self.text_widget.bind("<<Modified>>", self.on_text_modified)
        self.text_widget.bind("<KeyRelease>", lambda e: self.update_stats())

    def on_text_modified(self, event=None):
        if self.text_widget.edit_modified():
            self.update_stats()
            self.text_widget.edit_modified(False)

    def show_banner(self, message: str, msg_type: str = "info"):
        colors = {
            "info": ("#eef2f7", "#2c3e50"),
            "success": ("#d4edda", "#155724"),
            "warning": ("#fff3cd", "#856404"),
            "error": ("#f8d7da", "#721c24")
        }
        bg, fg = colors.get(msg_type, ("#eef2f7", "#2c3e50"))
        self.banner_frame.config(bg=bg)
        self.banner_label.config(text=message, bg=bg, fg=fg)

    def update_stats(self):
        content = self.text_widget.get("1.0", tk.END).strip()
        char_count = len(content)
        word_count = len(content.split()) if content else 0
        line_count = len(content.splitlines()) if content else 0

        self.stats_label.config(
            text=f"Символів: {char_count:,} | Слів: {word_count:,} | Рядків: {line_count:,}"
        )

    def insert_template(self):
        content = self.text_widget.get("1.0", tk.END).strip()
        if content:
            self.text_widget.insert(tk.END, "\n\n" + TEMPLATE_TASK_SPEC)
        else:
            self.text_widget.insert("1.0", TEMPLATE_TASK_SPEC)
        self.update_stats()
        self.show_banner("📝 Шаблон структури ТЗ вставлено.", "info")

    def clear_text(self):
        self.text_widget.delete("1.0", tk.END)
        self.update_stats()
        self.show_banner("🧹 Поле ТЗ очищено.", "info")

    def open_file(self):
        filename = filedialog.askopenfilename(
            parent=self, 
            filetypes=[
                ("Текстові та Markdown файли", "*.txt *.md *.markdown *.json *.yaml *.yml *.log *.docx"),
                ("Усі файли", "*.*")
            ]
        )
        self.lift()
        self.focus_force()
        if filename:
            try:
                with open(filename, "r", encoding="utf-8", errors="replace") as f:
                    data = f.read()
                self.text_widget.delete("1.0", tk.END)
                self.text_widget.insert("1.0", data)
                self.update_stats()
                self.show_banner(f"📂 Завантажено файл: {os.path.basename(filename)}", "success")
            except Exception as e:
                self.show_banner(f"❌ Помилка відкриття файлу: {str(e)}", "error")

    def save_to_file(self):
        content = self.text_widget.get("1.0", tk.END).strip()
        if not content:
            self.show_banner("⚠️ Немає тексту для збереження.", "warning")
            return
        filename = filedialog.asksaveasfilename(
            parent=self, 
            defaultextension=".md", 
            filetypes=[("Markdown файл", "*.md"), ("Текстовий файл", "*.txt"), ("Усі файли", "*.*")]
        )
        self.lift()
        self.focus_force()
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                self.show_banner(f"💾 ТЗ збережено у: {os.path.basename(filename)}", "success")
            except Exception as e:
                self.show_banner(f"❌ Не вдалося зберегти файл: {str(e)}", "error")

    def apply_changes(self):
        content = self.text_widget.get("1.0", tk.END).strip()
        self.on_save_callback(content)
        self.destroy()
