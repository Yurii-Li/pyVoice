import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
from typing import List, Dict, Optional

from pyvoice.utils.time_parser import parse_time_to_seconds, format_seconds_to_time
from pyvoice.ui.shortcuts import enable_universal_shortcuts

class ScriptEditorWindow(tk.Toplevel):
    """
    Повнофункціональний редактор сценарію озвучки з двома режимами:
    1. 🗂️ Зручний візуальний режим карток (редагування таймкодів і тексту без ризику зламати JSON).
    2. 💻 Режим чистого JSON коду (для розробників).
    """
    def __init__(self, parent, initial_content: str, on_save_callback):
        super().__init__(parent)
        self.title("✏️ Редактор сценарію озвучки - PyVoice AI")
        self.geometry("940x700")
        self.minsize(720, 500)
        self.resizable(True, True)
        
        self.parent = parent
        self.on_save_callback = on_save_callback
        
        # Центруємо вікно відносно батьківського
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 470
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 350
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        # Увімкнення гарячих клавіш Ctrl+C, Ctrl+V, Ctrl+A для української розкладки
        enable_universal_shortcuts(self)

        # Стан даних
        self.cards_data: List[Dict[str, str]] = []
        self.card_widgets: List[Dict] = []
        self.current_mode = "cards"  # "cards" або "json"

        # Створення компонентів інтерфейсу
        self.create_widgets(initial_content)
        
        # Визначаємо початковий режим відповідно до валідності JSON
        self.init_data_and_mode(initial_content)
        
        self.lift()
        self.focus_force()

    def create_widgets(self, initial_content: str):
        # -------------------------------------------------------------
        # 1. Верхня панель інструментів (Toolbar)
        # -------------------------------------------------------------
        top_bar = ttk.Frame(self, padding="8")
        top_bar.pack(fill=tk.X)

        ttk.Label(
            top_bar, 
            text="✏️ Редактор сценарію", 
            font=("Segoe UI", 11, "bold")
        ).pack(side=tk.LEFT)

        # Перемикач режимів: Картки / JSON
        mode_box = ttk.Frame(top_bar, padding="2")
        mode_box.pack(side=tk.LEFT, padx=(18, 0))

        ttk.Label(mode_box, text="Режим:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        
        self.mode_var = tk.StringVar(value="cards")
        self.rb_cards = ttk.Radiobutton(
            mode_box, 
            text="🗂️ Зручні картки", 
            value="cards", 
            variable=self.mode_var, 
            command=self.on_mode_switched
        )
        self.rb_cards.pack(side=tk.LEFT, padx=3)

        self.rb_json = ttk.Radiobutton(
            mode_box, 
            text="💻 Код JSON (для розробників)", 
            value="json", 
            variable=self.mode_var, 
            command=self.on_mode_switched
        )
        self.rb_json.pack(side=tk.LEFT, padx=3)

        # Кнопки дій праворуч
        self.btn_apply = ttk.Button(
            top_bar, 
            text="💾 Застосувати зміни", 
            command=self.apply_changes
        )
        self.btn_apply.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_format = ttk.Button(
            top_bar, 
            text="✨ Авто-формат", 
            command=self.format_json
        )
        self.btn_format.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_validate = ttk.Button(
            top_bar, 
            text="🔍 Перевірити", 
            command=self.validate_data
        )
        self.btn_validate.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_save_file = ttk.Button(
            top_bar, 
            text="💾 Зберегти файл", 
            command=self.save_to_file
        )
        self.btn_save_file.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_open = ttk.Button(
            top_bar, 
            text="📂 Відкрити файл", 
            command=self.open_file
        )
        self.btn_open.pack(side=tk.RIGHT, padx=(4, 0))

        # -------------------------------------------------------------
        # 2. Вбудована панель сповіщень (Status Banner)
        # -------------------------------------------------------------
        self.banner_frame = tk.Frame(self, bg="#f1f2f6", padx=10, pady=5)
        self.banner_frame.pack(fill=tk.X)

        self.banner_label = tk.Label(
            self.banner_frame, 
            text="ℹ️ Редагуйте репліки диктора зручними картками.", 
            font=("Segoe UI", 9),
            bg="#f1f2f6",
            fg="#2f3542",
            anchor="w"
        )
        self.banner_label.pack(fill=tk.X)

        # -------------------------------------------------------------
        # 3. Головний робочий контейнер
        # -------------------------------------------------------------
        self.content_container = ttk.Frame(self)
        self.content_container.pack(fill=tk.BOTH, expand=True)

        # --- А: Візуальний режим карток ---
        self.cards_view_frame = ttk.Frame(self.content_container)

        # Панель швидких дій для карток (додати в кінець, сортувати)
        cards_toolbar = tk.Frame(self.cards_view_frame, bg="#ecf0f1", padx=8, pady=6, relief="groove", bd=1)
        cards_toolbar.pack(fill=tk.X, side=tk.TOP)

        btn_add_end = ttk.Button(
            cards_toolbar, 
            text="➕ Додати нову репліку в кінець", 
            command=self.add_card_at_end
        )
        btn_add_end.pack(side=tk.LEFT, padx=(0, 6))

        btn_sort = ttk.Button(
            cards_toolbar, 
            text="⏱️ Сортувати за хронологією", 
            command=self.sort_cards_by_time
        )
        btn_sort.pack(side=tk.LEFT, padx=(0, 6))

        btn_clear = ttk.Button(
            cards_toolbar, 
            text="🧹 Очистити все", 
            command=self.clear_all_cards
        )
        btn_clear.pack(side=tk.RIGHT, padx=(6, 0))

        # Скролований Canvas для карток
        canvas_box = ttk.Frame(self.cards_view_frame)
        canvas_box.pack(fill=tk.BOTH, expand=True)

        self.cards_canvas = tk.Canvas(canvas_box, bg="#f5f6fa", highlightthickness=0, borderwidth=0)
        self.cards_scrollbar = ttk.Scrollbar(canvas_box, orient=tk.VERTICAL, command=self.cards_canvas.yview)
        self.cards_canvas.configure(yscrollcommand=self.cards_scrollbar.set)

        self.cards_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.cards_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.cards_inner_frame = tk.Frame(self.cards_canvas, bg="#f5f6fa", padx=8, pady=8)
        self.cards_window = self.cards_canvas.create_window((0, 0), window=self.cards_inner_frame, anchor="nw")

        self.cards_inner_frame.bind("<Configure>", self._on_cards_frame_configure)
        self.cards_canvas.bind("<Configure>", self._on_cards_canvas_configure)

        # Прокрутка мишкою
        self.bind_mouse_wheel(self.cards_canvas)
        self.bind_mouse_wheel(self.cards_inner_frame)

        # --- Б: Режим сирого JSON-коду ---
        self.json_view_frame = ttk.Frame(self.content_container, padding="6")

        json_scroll = ttk.Scrollbar(self.json_view_frame)
        json_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_widget = tk.Text(
            self.json_view_frame, 
            wrap=tk.WORD, 
            undo=True,
            font=("Consolas", 11),
            bg="#ffffff",
            fg="#111111",
            insertbackground="#000000",
            selectbackground="#cce8ff",
            selectforeground="#000000",
            relief="solid",
            borderwidth=1,
            padx=10,
            pady=10,
            yscrollcommand=json_scroll.set
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)
        json_scroll.config(command=self.text_widget.yview)

        self.text_widget.insert("1.0", initial_content)
        self.text_widget.bind("<<Modified>>", self.on_json_text_modified)
        self.text_widget.bind("<KeyRelease>", lambda e: self.update_stats())

        # -------------------------------------------------------------
        # 4. Нижня панель статистики
        # -------------------------------------------------------------
        bottom_bar = ttk.Frame(self, padding="8")
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.stats_label = ttk.Label(
            bottom_bar, 
            text="Реплік: 0 | Символів: 0", 
            font=("Segoe UI", 9, "bold")
        )
        self.stats_label.pack(side=tk.LEFT)

        self.duration_est_label = ttk.Label(
            bottom_bar, 
            text="", 
            font=("Segoe UI", 9),
            foreground="#2980b9"
        )
        self.duration_est_label.pack(side=tk.LEFT, padx=(15, 0))

        hint_label = ttk.Label(
            bottom_bar, 
            text="Ctrl+Z: Відмінити  •  Ctrl+Y: Повторити  •  Ctrl+A: Виділити все", 
            font=("Segoe UI", 8),
            foreground="#7f8c8d"
        )
        hint_label.pack(side=tk.RIGHT)

    def bind_mouse_wheel(self, widget):
        """Рекурсивно прив'язує прокрутку коліщатком миші для плавного скролу карток"""
        def _on_wheel(event):
            if self.current_mode == "cards" and self.cards_canvas.winfo_exists():
                if self.cards_canvas.yview() != (0.0, 1.0):
                    self.cards_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        widget.bind("<MouseWheel>", _on_wheel, add="+")

    def _on_cards_frame_configure(self, event=None):
        self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all"))

    def _on_cards_canvas_configure(self, event):
        self.cards_canvas.itemconfig(self.cards_window, width=event.width)

    def init_data_and_mode(self, initial_content: str):
        """Парсить початковий вміст. Якщо валідний JSON-список — показує картки, інакше JSON"""
        initial_content = initial_content.strip()
        parsed_ok = False
        if initial_content:
            try:
                parsed = json.loads(initial_content)
                if isinstance(parsed, list):
                    # Приводимо до стандартного формату
                    valid_items = []
                    for item in parsed:
                        if isinstance(item, dict) and "start" in item and "text" in item:
                            valid_items.append({
                                "start": str(item["start"]).strip(),
                                "text": str(item["text"]).strip()
                            })
                    self.cards_data = valid_items
                    parsed_ok = True
            except Exception:
                pass

        if parsed_ok:
            self.mode_var.set("cards")
            self.switch_to_mode("cards")
            self.render_cards()
            self.show_banner("🗂️ Завантажено візуальний картковий режим. Змінюйте таймкоди та репліки без помилок синтаксису.", "info")
        else:
            self.mode_var.set("json")
            self.switch_to_mode("json")
            if initial_content:
                self.show_banner("⚠️ Сценарій має помилку синтаксису JSON. Відкрито режим коду для виправлення.", "warning")
            else:
                self.show_banner("ℹ️ Сценарій порожній. Введіть JSON або перемкніться на картковий режим.", "info")

    def switch_to_mode(self, target_mode: str):
        """Перемикає відображення між картками та редактором коду JSON"""
        self.current_mode = target_mode
        if target_mode == "cards":
            self.json_view_frame.pack_forget()
            self.cards_view_frame.pack(fill=tk.BOTH, expand=True)
            self.btn_format.config(state="disabled")
        else:
            self.cards_view_frame.pack_forget()
            self.json_view_frame.pack(fill=tk.BOTH, expand=True)
            self.btn_format.config(state="normal")
        self.update_stats()

    def on_mode_switched(self):
        """Обробник перемикання радіокнопок Картки / JSON"""
        target = self.mode_var.get()
        if target == self.current_mode:
            return

        if target == "json":
            # Перехід з карток у JSON: вичитуємо актуальні дані з віджетів карток
            self.sync_cards_to_json()
            self.switch_to_mode("json")
            self.show_banner("💻 Увімкнено режим коду JSON для розробників.", "info")
        else:
            # Перехід з JSON у картки: перевіряємо валідність коду
            success = self.sync_json_to_cards()
            if success:
                self.switch_to_mode("cards")
                self.render_cards()
                self.show_banner("🗂️ Сценарій успішно розпізнано та відкрито у зручних картках!", "success")
            else:
                # Повертаємо радіокнопку на JSON
                self.mode_var.set("json")

    def sync_cards_to_json(self):
        """Збирає всі дані з карток і записує відформатований JSON у текстове поле"""
        data = self.get_data_from_cards()
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert("1.0", formatted)
        self.cards_data = data

    def sync_json_to_cards(self) -> bool:
        """Перевіряє JSON у текстовому полі та оновлює список `self.cards_data`"""
        content = self.text_widget.get("1.0", tk.END).strip()
        if not content:
            self.cards_data = []
            return True

        try:
            parsed = json.loads(content)
            if not isinstance(parsed, list):
                raise ValueError("JSON має бути списком реплік: [ {\"start\": \"00:01\", \"text\": \"...\"} ]")

            new_cards = []
            for idx, item in enumerate(parsed):
                if not isinstance(item, dict):
                    raise ValueError(f"Елемент #{idx+1} має бути об'єктом із полями 'start' та 'text'.")
                if "start" not in item or "text" not in item:
                    raise ValueError(f"Репліка #{idx+1} не містить обов'язкових полів 'start' або 'text'.")
                new_cards.append({
                    "start": str(item["start"]).strip(),
                    "text": str(item["text"]).strip()
                })
            self.cards_data = new_cards
            return True
        except Exception as e:
            self.show_banner(f"❌ Неможливо перемкнутися на картки: {str(e)}", "error")
            return False

    def get_data_from_cards(self) -> List[Dict[str, str]]:
        """Вичитує актуальні значення з усіх полів введення відкритих карток"""
        data = []
        for card in self.card_widgets:
            t = card["time_var"].get().strip() or "00:00"
            txt = card["text_widget"].get("1.0", tk.END).strip()
            data.append({"start": t, "text": txt})
        return data

    def render_cards(self):
        """Повністю перемальовує картки на канвасі"""
        for child in self.cards_inner_frame.winfo_children():
            child.destroy()
        self.card_widgets.clear()

        if not self.cards_data:
            empty_box = tk.Frame(self.cards_inner_frame, bg="#f5f6fa", pady=40)
            empty_box.pack(fill=tk.BOTH, expand=True)

            tk.Label(
                empty_box, 
                text="📭 Сценарій наразі порожній.", 
                font=("Segoe UI", 12), 
                fg="#7f8c8d", 
                bg="#f5f6fa"
            ).pack(pady=4)

            btn_first = tk.Button(
                empty_box, 
                text="➕ Додати першу репліку", 
                font=("Segoe UI", 10, "bold"), 
                bg="#3498db", 
                fg="white", 
                activebackground="#2980b9",
                activeforeground="white",
                padx=12, 
                pady=6, 
                bd=0, 
                relief="flat", 
                cursor="hand2", 
                command=self.add_card_at_end
            )
            btn_first.pack(pady=10)
            self.update_stats()
            return

        total = len(self.cards_data)
        for idx, item in enumerate(self.cards_data):
            self._create_single_card(idx, total, item)

        self.update_stats()
        self._on_cards_frame_configure()

    def _create_single_card(self, idx: int, total: int, item: Dict[str, str]):
        """Створює окрему стильну картку для однієї репліки"""
        card_frame = tk.Frame(
            self.cards_inner_frame, 
            bg="#ffffff", 
            bd=1, 
            relief="solid", 
            highlightbackground="#dcdde1",
            highlightthickness=1
        )
        card_frame.pack(fill=tk.X, pady=5, padx=4)

        self.bind_mouse_wheel(card_frame)

        # 1. Шапка картки (номер, таймкод, кнопки дій)
        header = tk.Frame(card_frame, bg="#f8f9fa", padx=8, pady=5)
        header.pack(fill=tk.X)
        self.bind_mouse_wheel(header)

        # Номер репліки
        lbl_num = tk.Label(
            header, 
            text=f" #{idx+1} ", 
            font=("Segoe UI", 9, "bold"), 
            bg="#2f3542", 
            fg="#ffffff", 
            padx=5, 
            pady=1
        )
        lbl_num.pack(side=tk.LEFT, padx=(0, 8))

        # Поле таймкоду
        tk.Label(
            header, 
            text="⏱️ Таймкод:", 
            font=("Segoe UI", 9, "bold"), 
            bg="#f8f9fa", 
            fg="#2f3542"
        ).pack(side=tk.LEFT, padx=(0, 4))

        time_var = tk.StringVar(value=str(item.get("start", "00:00")))
        time_entry = ttk.Entry(
            header, 
            textvariable=time_var, 
            width=8, 
            font=("Consolas", 10, "bold"), 
            justify="center"
        )
        time_entry.pack(side=tk.LEFT, padx=(0, 10))
        time_entry.bind("<KeyRelease>", lambda e: self.update_stats())

        # Індикатор оцінки тривалості
        est_label = tk.Label(header, text="", font=("Segoe UI", 8), bg="#f8f9fa", fg="#747d8c")
        est_label.pack(side=tk.LEFT, padx=6)
        self.bind_mouse_wheel(est_label)

        # Кнопки дій справа: Видалити, Додати після цієї, Вгору/Вниз
        btn_del = tk.Button(
            header, 
            text="🗑️ Видалити", 
            font=("Segoe UI", 8),
            bg="#ffeaa7", 
            fg="#d63031", 
            activebackground="#ff7675", 
            activeforeground="white",
            bd=0, 
            relief="flat", 
            cursor="hand2", 
            padx=7, 
            pady=2,
            command=lambda i=idx: self.delete_card(i)
        )
        btn_del.pack(side=tk.RIGHT, padx=2)

        btn_add_after = tk.Button(
            header, 
            text="➕ Після цієї", 
            font=("Segoe UI", 8),
            bg="#dfe4ea", 
            fg="#2f3542", 
            activebackground="#ced6e0",
            bd=0, 
            relief="flat", 
            cursor="hand2", 
            padx=7, 
            pady=2,
            command=lambda i=idx: self.insert_card_after(i)
        )
        btn_add_after.pack(side=tk.RIGHT, padx=4)

        if idx < total - 1:
            btn_down = tk.Button(
                header, 
                text="▼ Вниз", 
                font=("Segoe UI", 8),
                bg="#dfe4ea", 
                fg="#2f3542", 
                bd=0, 
                relief="flat", 
                cursor="hand2", 
                padx=5, 
                pady=2,
                command=lambda i=idx: self.move_card(i, 1)
            )
            btn_down.pack(side=tk.RIGHT, padx=2)

        if idx > 0:
            btn_up = tk.Button(
                header, 
                text="▲ Вгору", 
                font=("Segoe UI", 8),
                bg="#dfe4ea", 
                fg="#2f3542", 
                bd=0, 
                relief="flat", 
                cursor="hand2", 
                padx=5, 
                pady=2,
                command=lambda i=idx: self.move_card(i, -1)
            )
            btn_up.pack(side=tk.RIGHT, padx=2)

        # 2. Текстова частина репліки
        body_frame = tk.Frame(card_frame, bg="#ffffff", padx=8, pady=6)
        body_frame.pack(fill=tk.BOTH, expand=True)
        self.bind_mouse_wheel(body_frame)

        text_widget = tk.Text(
            body_frame,
            wrap=tk.WORD,
            undo=True,
            height=3,
            font=("Segoe UI", 10),
            bg="#ffffff",
            fg="#2d3436",
            relief="solid",
            bd=1,
            padx=8,
            pady=6,
            insertbackground="#000000"
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert("1.0", str(item.get("text", "")))
        self.bind_mouse_wheel(text_widget)

        def _update_est(e=None, tw=text_widget, el=est_label):
            content = tw.get("1.0", tk.END).strip()
            words = [w for w in content.split() if w]
            w_count = len(words)
            # Середня швидкість українського диктора: ~2.3 - 2.5 слова на секунду
            est_sec = (w_count / 2.3) if w_count > 0 else 0.0
            el.config(text=f"Слів: {w_count} (~{est_sec:.1f} сек)")
            self.update_stats()

        text_widget.bind("<KeyRelease>", _update_est)
        _update_est()

        self.card_widgets.append({
            "frame": card_frame,
            "time_var": time_var,
            "text_widget": text_widget
        })

    def add_card_at_end(self):
        """Додає нову репліку в кінець списку карток"""
        self.cards_data = self.get_data_from_cards()
        next_time = "00:01"
        if self.cards_data:
            last_time = self.cards_data[-1].get("start", "00:00")
            sec = parse_time_to_seconds(last_time)
            next_time = format_seconds_to_time(sec + 5.0)

        self.cards_data.append({"start": next_time, "text": ""})
        self.render_cards()
        self.show_banner(f"➕ Додано нову репліку #{len(self.cards_data)}.", "info")
        
        # Прокрутка донизу
        self.cards_canvas.yview_moveto(1.0)
        # Фокус на останньому полі вводу
        if self.card_widgets:
            self.card_widgets[-1]["text_widget"].focus_set()

    def insert_card_after(self, index: int):
        """Вставляє нову репліку безпосередньо після обраної"""
        self.cards_data = self.get_data_from_cards()
        curr_time = self.cards_data[index].get("start", "00:00")
        sec = parse_time_to_seconds(curr_time)
        new_time = format_seconds_to_time(sec + 2.0)

        self.cards_data.insert(index + 1, {"start": new_time, "text": ""})
        self.render_cards()
        self.show_banner(f"➕ Вставлено репліку #{index + 2}.", "info")

        if index + 1 < len(self.card_widgets):
            self.card_widgets[index + 1]["text_widget"].focus_set()

    def delete_card(self, index: int):
        """Видаляє обрану репліку зі списку карток"""
        self.cards_data = self.get_data_from_cards()
        if 0 <= index < len(self.cards_data):
            del self.cards_data[index]
            self.render_cards()
            self.show_banner(f"🗑️ Репліку #{index + 1} видалено.", "warning")

    def move_card(self, index: int, direction: int):
        """Зміщує репліку вгору (-1) або вниз (+1) у черзі"""
        self.cards_data = self.get_data_from_cards()
        target_idx = index + direction
        if 0 <= target_idx < len(self.cards_data):
            self.cards_data[index], self.cards_data[target_idx] = self.cards_data[target_idx], self.cards_data[index]
            self.render_cards()
            self.show_banner(f"↕️ Порядок реплік оновлено.", "info")

    def sort_cards_by_time(self):
        """Сортує репліки за зростанням таймкодів"""
        self.cards_data = self.get_data_from_cards()
        if not self.cards_data:
            return
        self.cards_data.sort(key=lambda item: parse_time_to_seconds(item.get("start", "00:00")))
        self.render_cards()
        self.show_banner("⏱️ Усі репліки відсортовано за хронологією таймкодів.", "success")

    def clear_all_cards(self):
        """Очищує всі репліки після підтвердження"""
        if messagebox.askyesno("Очищення сценарію", "Ви дійсно бажаєте видалити всі репліки зі сценарію?", parent=self):
            self.cards_data = []
            self.render_cards()
            self.show_banner("🧹 Сценарій повністю очищено.", "info")

    def on_json_text_modified(self, event=None):
        if self.text_widget.edit_modified():
            self.update_stats()
            self.text_widget.edit_modified(False)

    def show_banner(self, message: str, msg_type: str = "info"):
        """Показує інформаційні повідомлення у верхньому банері без модальних вікон"""
        colors = {
            "info": ("#f1f2f6", "#2f3542"),
            "success": ("#d4edda", "#155724"),
            "warning": ("#fff3cd", "#856404"),
            "error": ("#f8d7da", "#721c24")
        }
        bg, fg = colors.get(msg_type, ("#f1f2f6", "#2f3542"))
        self.banner_frame.config(bg=bg)
        self.banner_label.config(text=message, bg=bg, fg=fg)

    def update_stats(self):
        """Оновлює статистику реплік, кількості символів та орієнтовної тривалості озвучки"""
        total_replicas = 0
        total_chars = 0
        total_words = 0

        if self.current_mode == "cards":
            for card in self.card_widgets:
                total_replicas += 1
                txt = card["text_widget"].get("1.0", tk.END).strip()
                total_chars += len(txt)
                total_words += len([w for w in txt.split() if w])
        else:
            content = self.text_widget.get("1.0", tk.END).strip()
            total_chars = len(content)
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    total_replicas = len(parsed)
                    for item in parsed:
                        if isinstance(item, dict):
                            t = str(item.get("text", "")).strip()
                            total_words += len([w for w in t.split() if w])
            except Exception:
                total_replicas = content.count('"text"')

        est_total_sec = (total_words / 2.3) if total_words > 0 else 0.0
        mins = int(est_total_sec // 60)
        secs = int(est_total_sec % 60)
        dur_str = f"{mins}хв {secs}с" if mins > 0 else f"{secs}с"

        self.stats_label.config(text=f"Реплік: {total_replicas} | Слів: {total_words} | Символів: {total_chars}")
        if total_words > 0:
            self.duration_est_label.config(text=f"🎙️ Орієнтовна тривалість озвучки: ~{dur_str}")
        else:
            self.duration_est_label.config(text="")

    def format_json(self):
        """Автоматично форматує JSON з відступами у режимі коду"""
        content = self.text_widget.get("1.0", tk.END).strip()
        if not content:
            self.show_banner("⚠️ Сценарій порожній, нічого форматувати.", "warning")
            return
        try:
            parsed = json.loads(content)
            formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
            self.text_widget.delete("1.0", tk.END)
            self.text_widget.insert("1.0", formatted)
            self.update_stats()
            self.show_banner("✨ JSON успішно відформатовано!", "success")
        except Exception as e:
            self.show_banner(f"❌ Помилка синтаксису JSON: {str(e)}", "error")

    def validate_data(self):
        """Перевіряє коректність структури сценарію у поточному режимі"""
        if self.current_mode == "cards":
            data = self.get_data_from_cards()
            if not data:
                self.show_banner("⚠️ Сценарій порожній. Додайте хоча б одну репліку.", "warning")
                return
            for idx, item in enumerate(data):
                if not item["start"].strip():
                    self.show_banner(f"⚠️ У репліці #{idx+1} не вказано таймкод.", "warning")
                    return
                if not item["text"].strip():
                    self.show_banner(f"⚠️ Репліка #{idx+1} містить порожній текст.", "warning")
                    return
            self.show_banner(f"✅ Усі {len(data)} реплік заповнені коректно!", "success")
        else:
            content = self.text_widget.get("1.0", tk.END).strip()
            if not content:
                self.show_banner("⚠️ Сценарій порожній.", "warning")
                return
            try:
                parsed = json.loads(content)
                if not isinstance(parsed, list):
                    raise ValueError("JSON має бути списком: [ {\"start\": \"00:00\", \"text\": \"...\"} ]")
                for idx, item in enumerate(parsed):
                    if not isinstance(item, dict) or "start" not in item or "text" not in item:
                        raise ValueError(f"Репліка #{idx+1} не має обов'язкових полів 'start' або 'text'.")
                self.show_banner(f"✅ Перевірка пройдена! JSON валідний ({len(parsed)} реплік).", "success")
            except Exception as e:
                self.show_banner(f"❌ Помилка структури JSON: {str(e)}", "error")

    def apply_changes(self):
        """Зберігає зміни та передає JSON-рядок назад у головне вікно програми"""
        if self.current_mode == "cards":
            data = self.get_data_from_cards()
            formatted_json = json.dumps(data, indent=2, ensure_ascii=False)
            self.on_save_callback(formatted_json)
            self.destroy()
        else:
            content = self.text_widget.get("1.0", tk.END).strip()
            try:
                parsed = json.loads(content)
                if not isinstance(parsed, list):
                    raise ValueError("JSON має бути списком реплік.")
            except Exception as e:
                self.show_banner(f"❌ Не вдалося застосувати: виправте помилку JSON ({str(e)})", "error")
                return
            self.on_save_callback(content)
            self.destroy()

    def open_file(self):
        """Завантажує сценарій із зовнішнього файлу JSON"""
        filename = filedialog.askopenfilename(
            parent=self, 
            filetypes=[("JSON сценарії", "*.json"), ("Усі файли", "*.*")]
        )
        self.lift()
        self.focus_force()
        if filename:
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Оновлюємо текстовий віджет
                self.text_widget.delete("1.0", tk.END)
                self.text_widget.insert("1.0", content)

                if self.current_mode == "cards":
                    ok = self.sync_json_to_cards()
                    if ok:
                        self.render_cards()
                    else:
                        self.mode_var.set("json")
                        self.switch_to_mode("json")
                else:
                    self.update_stats()

                self.show_banner(f"📂 Завантажено файл: {filename}", "info")
            except Exception as e:
                self.show_banner(f"❌ Не вдалося відкрити файл: {str(e)}", "error")

    def save_to_file(self):
        """Зберігає поточний сценарій у JSON файл"""
        if self.current_mode == "cards":
            data = self.get_data_from_cards()
            content = json.dumps(data, indent=2, ensure_ascii=False)
        else:
            content = self.text_widget.get("1.0", tk.END).strip()

        if not content:
            self.show_banner("⚠️ Немає даних для збереження.", "warning")
            return

        filename = filedialog.asksaveasfilename(
            parent=self, 
            defaultextension=".json", 
            filetypes=[("JSON файли", "*.json")]
        )
        self.lift()
        self.focus_force()
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                self.show_banner(f"💾 Сценарій успішно збережено: {filename}", "success")
            except Exception as e:
                self.show_banner(f"❌ Не вдалося зберегти файл: {str(e)}", "error")
