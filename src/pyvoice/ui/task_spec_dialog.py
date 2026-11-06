import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from pyvoice.ui.shortcuts import bring_to_front
import os

TEMPLATE_TASK_SPEC = """- [x] #### Назва задачі / Фічі (наприклад, Переміщення між складами)
  Короткий опис: що робить функціонал, які додано поля, колонки або чекбокси.
  (Технічні деталі, логіка розрахунку, назви таблиць або умови відбору)

- [x] #### Інша задача з беклогу
  Опис поведінки та вимог...
"""

class TaskSpecDialog(ctk.CTkToplevel):
    """
    Сучасне вікно на базі CustomTkinter для введення, завантаження з файлу
    та редагування Технічного Завдання (ТЗ), чеклістів або Jira-тікетів.
    """
    def __init__(self, parent, initial_text: str, on_save_callback):
        super().__init__(parent)
        self.title("📋 Технічне завдання / Опис задачі (ТЗ) - PyVoice AI")
        self.geometry("860x640")
        self.minsize(640, 440)
        
        self.parent = parent
        self.on_save_callback = on_save_callback
        self.resizable(True, True)
        
        # Центруємо вікно відносно батьківського
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 430
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 320
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self.create_widgets(initial_text)
        self.update_stats()
        
        bring_to_front(self, parent)

    def create_widgets(self, initial_text: str):
        self.configure(fg_color=("#f8fafc", "#090d16"))
        main_box = ctk.CTkFrame(
            self, 
            corner_radius=14,
            fg_color=("#ffffff", "#0e1424"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        main_box.pack(fill="both", expand=True, padx=14, pady=14)

        # 1. Верхня панель інструментів (Toolbar)
        top_bar = ctk.CTkFrame(main_box, fg_color="transparent")
        top_bar.pack(fill="x", padx=16, pady=(14, 10))

        title_badge = ctk.CTkFrame(top_bar, width=34, height=34, corner_radius=9, fg_color=("#e0f2fe", "#082f49"))
        title_badge.pack(side="left", padx=(0, 10))
        title_badge.pack_propagate(False)
        ctk.CTkLabel(title_badge, text="📋", font=ctk.CTkFont(size=16)).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            top_bar, 
            text="Технічне завдання / Опис контексту", 
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=("gray10", "white")
        ).pack(side="left")

        btn_apply = ctk.CTkButton(
            top_bar, 
            text="💾 Застосувати", 
            width=120,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(weight="bold"),
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            command=self.apply_changes
        )
        btn_apply.pack(side="right", padx=(6, 0))

        btn_clear = ctk.CTkButton(
            top_bar, 
            text="🧹 Очистити", 
            width=90,
            height=32,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.clear_text
        )
        btn_clear.pack(side="right", padx=(6, 0))

        btn_template = ctk.CTkButton(
            top_bar, 
            text="📝 Шаблон ТЗ", 
            width=110,
            height=32,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.insert_template
        )
        btn_template.pack(side="right", padx=(6, 0))

        btn_save = ctk.CTkButton(
            top_bar, 
            text="💾 Зберегти", 
            width=90,
            height=32,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.save_to_file
        )
        btn_save.pack(side="right", padx=(6, 0))

        btn_open = ctk.CTkButton(
            top_bar, 
            text="📂 Відкрити", 
            width=90,
            height=32,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.open_file
        )
        btn_open.pack(side="right")

        # 2. Інформаційний банер підказок
        banner_frame = ctk.CTkFrame(
            main_box, 
            corner_radius=8, 
            fg_color=("#f1f5f9", "#111827"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        banner_frame.pack(fill="x", padx=16, pady=(0, 10))

        banner_label = ctk.CTkLabel(
            banner_frame, 
            text="💡 Сюди можна просто скопіювати список задач, чекліст із беклогу чи короткі технічні нотатки. ШІ сам визначить, яка саме задача показана у відео, та використає її терміни й логіку для точної озвучки.", 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#475569", "#94a3b8"),
            wraplength=800,
            justify="left"
        )
        banner_label.pack(fill="x", padx=14, pady=8)

        # 3. Текстове поле ТЗ
        self.text_widget = ctk.CTkTextbox(
            main_box, 
            wrap="word", 
            undo=True,
            font=("Segoe UI", 11),
            corner_radius=10,
            fg_color=("#f8fafc", "#090d16"),
            border_color=("#cbd5e1", "#1e293b"),
            border_width=1
        )
        self.text_widget.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self.text_widget.insert("1.0", initial_text)

        # 4. Нижня панель статистики
        bottom_bar = ctk.CTkFrame(main_box, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=14, pady=(0, 10))

        self.stats_label = ctk.CTkLabel(
            bottom_bar, 
            text="Символів: 0 | Слів: 0", 
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        self.stats_label.pack(side="left")

        hint_lbl = ctk.CTkLabel(
            bottom_bar, 
            text="Ctrl+A: Виділити все • Ctrl+C / Ctrl+V: Копіювати / Вставити", 
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=("gray50", "gray60")
        )
        hint_lbl.pack(side="right")

        self.text_widget.bind("<KeyRelease>", lambda e: self.update_stats())

    def update_stats(self):
        content = self.text_widget.get("1.0", "end").strip()
        chars = len(content)
        words = len(content.split())
        self.stats_label.configure(text=f"Символів: {chars:,} | Слів: {words:,}")

    def apply_changes(self):
        content = self.text_widget.get("1.0", "end").strip()
        self.on_save_callback(content)
        self.destroy()

    def clear_text(self):
        if messagebox.askyesno("Очищення", "Ви дійсно бажаєте очистити текст ТЗ?", parent=self):
            self.text_widget.delete("1.0", "end")
            self.update_stats()

    def insert_template(self):
        content = self.text_widget.get("1.0", "end").strip()
        if content:
            if not messagebox.askyesno("Шаблон ТЗ", "Замінити поточний текст шаблоном?", parent=self):
                return
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", TEMPLATE_TASK_SPEC)
        self.update_stats()

    def open_file(self):
        filename = filedialog.askopenfilename(
            parent=self, 
            filetypes=[
                ("Текстові та Markdown файли", "*.txt *.md *.markdown *.json *.yaml *.yml *.log *.docx"),
                ("Усі файли", "*.*")
            ]
        )
        if filename:
            try:
                with open(filename, "r", encoding="utf-8", errors="replace") as f:
                    data = f.read()
                self.text_widget.delete("1.0", "end")
                self.text_widget.insert("1.0", data)
                self.update_stats()
            except Exception as e:
                messagebox.showerror("Помилка", f"Не вдалося відкрити файл:\n{str(e)}")

    def save_to_file(self):
        content = self.text_widget.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("Увага", "Текстове поле порожнє!", parent=self)
            return
        filename = filedialog.asksaveasfilename(
            parent=self, 
            defaultextension=".txt", 
            filetypes=[("Текстовий файл (*.txt)", "*.txt"), ("Markdown (*.md)", "*.md")]
        )
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                messagebox.showerror("Помилка", f"Не вдалося зберегти файл:\n{str(e)}")
