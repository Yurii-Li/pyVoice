import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import json
from typing import List, Dict, Optional

from pyvoice.utils.time_parser import parse_time_to_seconds, format_seconds_to_time
from pyvoice.ui.shortcuts import enable_universal_shortcuts, bring_to_front

class ScriptEditorWindow(ctk.CTkToplevel):
    """
    Сучасний редактор сценарію озвучки на базі CustomTkinter:
    1. 🗂️ Зручні візуальні картки (без ризику зламати JSON-код).
    2. 💻 Чистий JSON для розробників.
    """
    def __init__(self, parent, initial_content: str, on_save_callback):
        super().__init__(parent)
        self.title("✏️ Редактор сценарію озвучки - PyVoice AI")
        self.geometry("980x740")
        self.minsize(740, 520)
        self.resizable(True, True)
        
        self.parent = parent
        self.on_save_callback = on_save_callback
        
        # Центруємо вікно відносно батьківського
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 490
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 370
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        enable_universal_shortcuts(self)

        # Стан даних
        self.cards_data: List[Dict[str, str]] = []
        self.card_widgets: List[Dict] = []
        self.current_mode = "cards"

        self.create_widgets(initial_content)
        self.init_data_and_mode(initial_content)
        
        bring_to_front(self, parent)

    def create_widgets(self, initial_content: str):
        self.configure(fg_color=("#f8fafc", "#090d16"))
        main_box = ctk.CTkFrame(
            self, 
            corner_radius=14,
            fg_color=("#ffffff", "#0e1424"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        main_box.pack(fill="both", expand=True, padx=14, pady=14)

        # -------------------------------------------------------------
        # 1. Верхня панель інструментів (Toolbar)
        # -------------------------------------------------------------
        top_bar = ctk.CTkFrame(main_box, fg_color="transparent")
        top_bar.pack(fill="x", padx=16, pady=(14, 10))

        title_badge = ctk.CTkFrame(top_bar, width=34, height=34, corner_radius=9, fg_color=("#ede9fe", "#2e1065"))
        title_badge.pack(side="left", padx=(0, 10))
        title_badge.pack_propagate(False)
        ctk.CTkLabel(title_badge, text="✏️", font=ctk.CTkFont(size=16)).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            top_bar, 
            text="Редактор сценарію озвучки", 
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=("gray10", "white")
        ).pack(side="left")

        # Сегментований перемикач режимів у стилі iOS / Win11
        self.mode_segmented = ctk.CTkSegmentedButton(
            top_bar,
            values=["🗂️ Зручні картки", "💻 Код JSON"],
            command=self.on_mode_segment_clicked,
            selected_color="#4f46e5",
            selected_hover_color="#4338ca",
            width=240,
            height=32,
            corner_radius=8
        )
        self.mode_segmented.pack(side="left", padx=(24, 0))
        self.mode_segmented.set("🗂️ Зручні картки")

        # Кнопки дій праворуч
        self.btn_apply = ctk.CTkButton(
            top_bar, 
            text="💾 Застосувати зміни", 
            width=155,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(weight="bold"),
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            command=self.apply_changes
        )
        self.btn_apply.pack(side="right", padx=(6, 0))

        self.btn_format = ctk.CTkButton(
            top_bar, 
            text="✨ Авто-формат", 
            width=115,
            height=32,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.format_json
        )
        self.btn_format.pack(side="right", padx=(4, 0))

        self.btn_validate = ctk.CTkButton(
            top_bar, 
            text="🔍 Перевірити", 
            width=100,
            height=32,
            corner_radius=8,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=self.validate_data
        )
        self.btn_validate.pack(side="right", padx=(4, 0))

        self.btn_save_file = ctk.CTkButton(
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
        self.btn_save_file.pack(side="right", padx=(4, 0))

        self.btn_open = ctk.CTkButton(
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
        self.btn_open.pack(side="right")

        # -------------------------------------------------------------
        # 2. Вбудована панель сповіщень (Status Banner)
        # -------------------------------------------------------------
        self.banner_frame = ctk.CTkFrame(main_box, corner_radius=8, fg_color=("#f1f5f9", "#111827"), border_color=("#e2e8f0", "#1e293b"), border_width=1)
        self.banner_frame.pack(fill="x", padx=16, pady=(0, 10))

        self.banner_label = ctk.CTkLabel(
            self.banner_frame, 
            text="ℹ️ Редагуйте репліки диктора зручними картками. Таймкоди задають час початку фрази та стоп-кадру.", 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#475569", "#94a3b8"),
            anchor="w"
        )
        self.banner_label.pack(fill="x", padx=14, pady=7)

        # -------------------------------------------------------------
        # 3. Головний робочий контейнер
        # -------------------------------------------------------------
        self.content_container = ctk.CTkFrame(main_box, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # --- А: Візуальний режим карток ---
        self.cards_view_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")

        # Панель дій для карток
        cards_toolbar = ctk.CTkFrame(self.cards_view_frame, corner_radius=8, height=40)
        cards_toolbar.pack(fill="x", side="top", pady=(0, 8))

        ctk.CTkButton(
            cards_toolbar, 
            text="➕ Додати нову репліку в кінець", 
            height=28,
            font=ctk.CTkFont(weight="bold"),
            fg_color=("#2563eb", "#3b82f6"),
            hover_color=("#1d4ed8", "#2563eb"),
            command=self.add_card_at_end
        ).pack(side="left", padx=8, pady=6)

        ctk.CTkButton(
            cards_toolbar, 
            text="⏱️ Сортувати за хронологією", 
            height=28,
            fg_color=("gray75", "#27272a"),
            hover_color=("gray65", "#3f3f46"),
            command=self.sort_cards_by_time
        ).pack(side="left", padx=(0, 6), pady=6)

        ctk.CTkButton(
            cards_toolbar, 
            text="🧹 Очистити все", 
            height=28,
            fg_color=("#ef4444", "#dc2626"),
            hover_color=("#dc2626", "#b91c1c"),
            command=self.clear_all_cards
        ).pack(side="right", padx=8, pady=6)

        # Сучасний скролер для карток
        self.cards_scroll = ctk.CTkScrollableFrame(self.cards_view_frame, corner_radius=10)
        self.cards_scroll.pack(fill="both", expand=True)

        # --- Б: Режим сирого JSON-коду ---
        self.json_view_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")

        self.text_widget = ctk.CTkTextbox(
            self.json_view_frame, 
            font=("Consolas", 11),
            corner_radius=10,
            activate_scrollbars=True
        )
        self.text_widget.pack(fill="both", expand=True)
        self.text_widget.insert("1.0", initial_content)
        self.text_widget.bind("<KeyRelease>", lambda e: self.update_stats())

        # -------------------------------------------------------------
        # 4. Нижня панель статистики
        # -------------------------------------------------------------
        bottom_bar = ctk.CTkFrame(main_box, fg_color="transparent")
        bottom_bar.pack(fill="x", side="bottom", padx=14, pady=(0, 10))

        self.stats_label = ctk.CTkLabel(
            bottom_bar, 
            text="Реплік: 0 | Слів: 0 | Символів: 0", 
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        self.stats_label.pack(side="left")

        self.duration_est_label = ctk.CTkLabel(
            bottom_bar, 
            text="", 
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#2563eb", "#60a5fa")
        )
        self.duration_est_label.pack(side="left", padx=(18, 0))

        hint_label = ctk.CTkLabel(
            bottom_bar, 
            text="Ctrl+Z / Ctrl+Y / Ctrl+A підтримуються", 
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=("gray50", "gray60")
        )
        hint_label.pack(side="right")

    def init_data_and_mode(self, initial_content: str):
        initial_content = initial_content.strip()
        parsed_ok = False
        if initial_content:
            try:
                parsed = json.loads(initial_content)
                if isinstance(parsed, list):
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
            self.mode_segmented.set("🗂️ Зручні картки")
            self.switch_to_mode("cards")
            self.render_cards()
            self.show_banner("🗂️ Завантажено картковий режим. Змінюйте репліки без ризику помилок синтаксису.", "info")
        else:
            self.mode_segmented.set("💻 Код JSON")
            self.switch_to_mode("json")
            if initial_content:
                self.show_banner("⚠️ Сценарій містить синтаксичну помилку JSON. Відкрито режим коду для виправлення.", "warning")
            else:
                self.show_banner("ℹ️ Сценарій порожній.", "info")

    def switch_to_mode(self, target_mode: str):
        self.current_mode = target_mode
        if target_mode == "cards":
            self.json_view_frame.pack_forget()
            self.cards_view_frame.pack(fill="both", expand=True)
            self.btn_format.configure(state="disabled")
        else:
            self.cards_view_frame.pack_forget()
            self.json_view_frame.pack(fill="both", expand=True)
            self.btn_format.configure(state="normal")
        self.update_stats()

    def on_mode_segment_clicked(self, value: str):
        target = "cards" if "картки" in value.lower() else "json"
        if target == self.current_mode:
            return

        if target == "json":
            self.sync_cards_to_json()
            self.switch_to_mode("json")
            self.show_banner("💻 Увімкнено режим прямого редагування коду JSON.", "info")
        else:
            success = self.sync_json_to_cards()
            if success:
                self.switch_to_mode("cards")
                self.render_cards()
                self.show_banner("🗂️ Сценарій успішно перетворено у зручні картки!", "success")
            else:
                self.mode_segmented.set("💻 Код JSON")

    def sync_cards_to_json(self):
        data = self.get_data_from_cards()
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", formatted)
        self.cards_data = data

    def sync_json_to_cards(self) -> bool:
        content = self.text_widget.get("1.0", "end").strip()
        if not content:
            self.cards_data = []
            return True

        try:
            parsed = json.loads(content)
            if not isinstance(parsed, list):
                raise ValueError("JSON має бути списком об'єктів реплік.")

            new_cards = []
            for idx, item in enumerate(parsed):
                if not isinstance(item, dict) or "start" not in item or "text" not in item:
                    raise ValueError(f"Репліка #{idx+1} не містить полів 'start' або 'text'.")
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
        data = []
        for card in self.card_widgets:
            t = card["time_entry"].get().strip() or "00:00"
            txt = card["text_widget"].get("1.0", "end").strip()
            data.append({"start": t, "text": txt})
        return data

    def render_cards(self):
        for child in self.cards_scroll.winfo_children():
            child.destroy()
        self.card_widgets.clear()

        if not self.cards_data:
            empty_box = ctk.CTkFrame(self.cards_scroll, corner_radius=10, fg_color="transparent")
            empty_box.pack(fill="both", expand=True, pady=40)

            ctk.CTkLabel(
                empty_box, 
                text="📭 Сценарій наразі порожній.", 
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=("gray50", "gray60")
            ).pack(pady=6)

            ctk.CTkButton(
                empty_box, 
                text="➕ Додати першу репліку", 
                font=ctk.CTkFont(weight="bold"),
                command=self.add_card_at_end
            ).pack(pady=10)
            self.update_stats()
            return

        total = len(self.cards_data)
        for idx, item in enumerate(self.cards_data):
            self._create_single_card(idx, total, item)

        self.update_stats()

    def _create_single_card(self, idx: int, total: int, item: Dict[str, str]):
        card_frame = ctk.CTkFrame(
            self.cards_scroll, 
            corner_radius=10,
            fg_color=("#ffffff", "#111827"),
            border_color=("#e2e8f0", "#1e293b"),
            border_width=1
        )
        card_frame.pack(fill="x", pady=6, padx=4)

        # 1. Шапка картки
        header = ctk.CTkFrame(card_frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 6))

        # Номер репліки (бейдж)
        lbl_num = ctk.CTkLabel(
            header, 
            text=f" #{idx+1} ", 
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=("#e0e7ff", "#1e1b4b"),
            text_color=("#4338ca", "#818cf8"),
            corner_radius=6,
            width=38,
            height=24
        )
        lbl_num.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            header, 
            text="⏱️ Таймкод:", 
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        ).pack(side="left", padx=(0, 6))

        time_entry = ctk.CTkEntry(
            header, 
            width=80, 
            height=26,
            font=("Consolas", 12, "bold"),
            justify="center",
            corner_radius=6,
            fg_color=("#f8fafc", "#090d16"),
            border_color=("#cbd5e1", "#1e293b"),
            border_width=1
        )
        time_entry.insert(0, str(item.get("start", "00:00")))
        time_entry.pack(side="left", padx=(0, 8))
        time_entry.bind("<KeyRelease>", lambda e: self.update_stats())

        est_label = ctk.CTkLabel(
            header, 
            text="", 
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=("gray50", "gray60")
        )
        est_label.pack(side="left", padx=4)

        # Кнопки управління
        btn_del = ctk.CTkButton(
            header, 
            text="🗑️", 
            width=32, 
            height=26,
            corner_radius=6,
            fg_color=("#ef4444", "#dc2626"),
            hover_color=("#dc2626", "#b91c1c"),
            command=lambda i=idx: self.delete_card(i)
        )
        btn_del.pack(side="right", padx=2)

        btn_add_after = ctk.CTkButton(
            header, 
            text="➕ Після цієї", 
            width=95, 
            height=26,
            corner_radius=6,
            fg_color=("#f1f5f9", "#1e293b"),
            hover_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f1f5f9"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            command=lambda i=idx: self.insert_card_after(i)
        )
        btn_add_after.pack(side="right", padx=4)

        if idx < total - 1:
            btn_down = ctk.CTkButton(
                header, 
                text="▼", 
                width=30, 
                height=26,
                corner_radius=6,
                fg_color=("#f1f5f9", "#1e293b"),
                hover_color=("#e2e8f0", "#334155"),
                text_color=("#0f172a", "#f1f5f9"),
                border_width=1,
                border_color=("#cbd5e1", "#334155"),
                command=lambda i=idx: self.move_card(i, 1)
            )
            btn_down.pack(side="right", padx=2)

        if idx > 0:
            btn_up = ctk.CTkButton(
                header, 
                text="▲", 
                width=30, 
                height=26,
                corner_radius=6,
                fg_color=("#f1f5f9", "#1e293b"),
                hover_color=("#e2e8f0", "#334155"),
                text_color=("#0f172a", "#f1f5f9"),
                border_width=1,
                border_color=("#cbd5e1", "#334155"),
                command=lambda i=idx: self.move_card(i, -1)
            )
            btn_up.pack(side="right", padx=2)

        # 2. Текстове поле репліки
        text_widget = ctk.CTkTextbox(
            card_frame, 
            height=68, 
            font=("Segoe UI", 11),
            corner_radius=8,
            fg_color=("#f8fafc", "#090d16"),
            border_color=("#cbd5e1", "#1e293b"),
            border_width=1
        )
        text_widget.pack(fill="x", padx=10, pady=(0, 8))
        text_widget.insert("1.0", str(item.get("text", "")))

        def _update_est(e=None, tw=text_widget, el=est_label):
            content = tw.get("1.0", "end").strip()
            words = [w for w in content.split() if w]
            w_count = len(words)
            est_sec = (w_count / 2.3) if w_count > 0 else 0.0
            el.configure(text=f"Слів: {w_count} (~{est_sec:.1f}с)")
            self.update_stats()

        text_widget.bind("<KeyRelease>", _update_est)
        _update_est()

        self.card_widgets.append({
            "frame": card_frame,
            "time_entry": time_entry,
            "text_widget": text_widget
        })

    def add_card_at_end(self):
        self.cards_data = self.get_data_from_cards()
        next_time = "00:01"
        if self.cards_data:
            last_time = self.cards_data[-1].get("start", "00:00")
            sec = parse_time_to_seconds(last_time)
            next_time = format_seconds_to_time(sec + 5.0)

        self.cards_data.append({"start": next_time, "text": ""})
        self.render_cards()
        self.show_banner(f"➕ Додано нову репліку #{len(self.cards_data)}.", "info")
        if self.card_widgets:
            self.card_widgets[-1]["text_widget"].focus_set()

    def insert_card_after(self, index: int):
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
        self.cards_data = self.get_data_from_cards()
        if 0 <= index < len(self.cards_data):
            del self.cards_data[index]
            self.render_cards()
            self.show_banner(f"🗑️ Репліку #{index + 1} видалено.", "warning")

    def move_card(self, index: int, direction: int):
        self.cards_data = self.get_data_from_cards()
        target_idx = index + direction
        if 0 <= target_idx < len(self.cards_data):
            self.cards_data[index], self.cards_data[target_idx] = self.cards_data[target_idx], self.cards_data[index]
            self.render_cards()
            self.show_banner("↕️ Порядок реплік оновлено.", "info")

    def sort_cards_by_time(self):
        self.cards_data = self.get_data_from_cards()
        if not self.cards_data:
            return
        self.cards_data.sort(key=lambda item: parse_time_to_seconds(item.get("start", "00:00")))
        self.render_cards()
        self.show_banner("⏱️ Усі репліки відсортовано за хронологією таймкодів.", "success")

    def clear_all_cards(self):
        if messagebox.askyesno("Очищення", "Ви дійсно бажаєте видалити всі репліки?", parent=self):
            self.cards_data = []
            self.render_cards()
            self.show_banner("🧹 Сценарій повністю очищено.", "info")

    def show_banner(self, message: str, msg_type: str = "info"):
        colors = {
            "info": ("gray90", "#18181b"),
            "success": ("#dcfce7", "#064e3b"),
            "warning": ("#fef9c3", "#713f12"),
            "error": ("#fee2e2", "#7f1d1d")
        }
        bg = colors.get(msg_type, ("gray90", "#18181b"))
        self.banner_frame.configure(fg_color=bg)
        self.banner_label.configure(text=message)

    def update_stats(self):
        total_replicas = 0
        total_chars = 0
        total_words = 0

        if self.current_mode == "cards":
            for card in self.card_widgets:
                total_replicas += 1
                txt = card["text_widget"].get("1.0", "end").strip()
                total_chars += len(txt)
                total_words += len([w for w in txt.split() if w])
        else:
            content = self.text_widget.get("1.0", "end").strip()
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

        self.stats_label.configure(text=f"Реплік: {total_replicas} | Слів: {total_words} | Символів: {total_chars}")
        if total_words > 0:
            self.duration_est_label.configure(text=f"🎙️ Орієнтовна тривалість озвучки: ~{dur_str}")
        else:
            self.duration_est_label.configure(text="")

    def format_json(self):
        content = self.text_widget.get("1.0", "end").strip()
        if not content:
            self.show_banner("⚠️ Сценарій порожній, нічого форматувати.", "warning")
            return
        try:
            parsed = json.loads(content)
            formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
            self.text_widget.delete("1.0", "end")
            self.text_widget.insert("1.0", formatted)
            self.update_stats()
            self.show_banner("✨ JSON успішно відформатовано!", "success")
        except Exception as e:
            self.show_banner(f"❌ Помилка синтаксису JSON: {str(e)}", "error")

    def validate_data(self):
        if self.current_mode == "cards":
            data = self.get_data_from_cards()
            if not data:
                self.show_banner("⚠️ Сценарій порожній.", "warning")
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
            content = self.text_widget.get("1.0", "end").strip()
            if not content:
                self.show_banner("⚠️ Сценарій порожній.", "warning")
                return
            try:
                parsed = json.loads(content)
                if not isinstance(parsed, list):
                    raise ValueError("JSON має бути списком.")
                self.show_banner(f"✅ Перевірка пройдена! JSON валідний ({len(parsed)} реплік).", "success")
            except Exception as e:
                self.show_banner(f"❌ Помилка структури JSON: {str(e)}", "error")

    def apply_changes(self):
        if self.current_mode == "cards":
            data = self.get_data_from_cards()
            formatted_json = json.dumps(data, indent=2, ensure_ascii=False)
            self.on_save_callback(formatted_json)
            self.destroy()
        else:
            content = self.text_widget.get("1.0", "end").strip()
            try:
                parsed = json.loads(content)
                if not isinstance(parsed, list):
                    raise ValueError("JSON має бути списком реплік.")
            except Exception as e:
                self.show_banner(f"❌ Помилка JSON: {str(e)}", "error")
                return
            self.on_save_callback(content)
            self.destroy()

    def open_file(self):
        filename = filedialog.askopenfilename(
            parent=self, 
            filetypes=[("JSON сценарії", "*.json"), ("Усі файли", "*.*")]
        )
        if filename:
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    content = f.read()
                self.text_widget.delete("1.0", "end")
                self.text_widget.insert("1.0", content)
                if self.current_mode == "cards":
                    ok = self.sync_json_to_cards()
                    if ok:
                        self.render_cards()
                    else:
                        self.mode_segmented.set("💻 Код JSON")
                        self.switch_to_mode("json")
                else:
                    self.update_stats()
                self.show_banner(f"📂 Завантажено файл: {filename}", "info")
            except Exception as e:
                self.show_banner(f"❌ Не вдалося відкрити файл: {str(e)}", "error")

    def save_to_file(self):
        if self.current_mode == "cards":
            data = self.get_data_from_cards()
            content = json.dumps(data, indent=2, ensure_ascii=False)
        else:
            content = self.text_widget.get("1.0", "end").strip()

        if not content:
            self.show_banner("⚠️ Немає даних для збереження.", "warning")
            return

        filename = filedialog.asksaveasfilename(
            parent=self, 
            defaultextension=".json", 
            filetypes=[("JSON файли", "*.json")]
        )
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                self.show_banner(f"💾 Сценарій збережено: {filename}", "success")
            except Exception as e:
                self.show_banner(f"❌ Не вдалося зберегти файл: {str(e)}", "error")
