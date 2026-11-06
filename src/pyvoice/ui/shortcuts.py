import tkinter as tk
from tkinter import ttk

def enable_universal_shortcuts(root: tk.Tk):
    """
    Універсальне вирішення проблеми комбінацій клавіш (Ctrl+V, Ctrl+C, Ctrl+X, Ctrl+A, Ctrl+Z, Ctrl+Y)
    у Tkinter при українській (та будь-якій іншій не-англійській) розкладці клавіатури,
    а також додавання зручного контекстного меню правої кнопки миші для всіх полів.
    """
    
    def on_ctrl_key(event):
        # Перевірка чи затиснуто Control (state біт 2: 0x4)
        if not (event.state & 0x0004):
            return

        widget = event.widget
        if not widget:
            return

        code = event.keycode
        
        # 65 = A (Виділити все)
        if code == 65:
            if isinstance(widget, (tk.Entry, ttk.Entry)):
                widget.select_range(0, tk.END)
                widget.icursor(tk.END)
                return "break"
            elif isinstance(widget, tk.Text):
                widget.tag_add(tk.SEL, "1.0", tk.END)
                widget.mark_set(tk.INSERT, "1.0")
                widget.see(tk.INSERT)
                return "break"

        # 86 = V (Вставити)
        elif code == 86:
            if event.keysym.lower() not in ("v",):
                try:
                    widget.event_generate("<<Paste>>")
                except Exception:
                    try:
                        text = widget.clipboard_get()
                        if isinstance(widget, (tk.Entry, ttk.Entry)):
                            if widget.select_present():
                                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                            widget.insert(tk.INSERT, text)
                        elif isinstance(widget, tk.Text):
                            try:
                                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                            except Exception:
                                pass
                            widget.insert(tk.INSERT, text)
                    except Exception:
                        pass
                return "break"

        # 67 = C (Копіювати)
        elif code == 67:
            if event.keysym.lower() not in ("c",):
                try:
                    widget.event_generate("<<Copy>>")
                except Exception:
                    pass
                return "break"

        # 88 = X (Вирізати)
        elif code == 88:
            if event.keysym.lower() not in ("x",):
                try:
                    widget.event_generate("<<Cut>>")
                except Exception:
                    pass
                return "break"

        # 90 = Z (Відмінити)
        elif code == 90:
            if event.keysym.lower() not in ("z",):
                try:
                    widget.event_generate("<<Undo>>")
                except Exception:
                    pass
                return "break"

        # 89 = Y (Повторити)
        elif code == 89:
            if event.keysym.lower() not in ("y",):
                try:
                    widget.event_generate("<<Redo>>")
                except Exception:
                    pass
                return "break"

    root.bind_all("<Control-KeyPress>", on_ctrl_key, add="+")
    
    # Додавання контекстного меню для правої кнопки миші
    def show_context_menu(event):
        widget = event.widget
        if not isinstance(widget, (tk.Entry, ttk.Entry, tk.Text)):
            return
            
        menu = tk.Menu(widget, tearoff=0)
        
        has_selection = False
        if isinstance(widget, (tk.Entry, ttk.Entry)):
            has_selection = widget.select_present()
        elif isinstance(widget, tk.Text):
            has_selection = bool(widget.tag_ranges(tk.SEL))
            
        def do_cut():
            try:
                widget.event_generate("<<Cut>>")
            except Exception:
                pass

        def do_copy():
            try:
                widget.event_generate("<<Copy>>")
            except Exception:
                pass

        def do_paste():
            try:
                widget.event_generate("<<Paste>>")
            except Exception:
                try:
                    text = widget.clipboard_get()
                    if isinstance(widget, (tk.Entry, ttk.Entry)):
                        if widget.select_present():
                            widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                        widget.insert(tk.INSERT, text)
                    elif isinstance(widget, tk.Text):
                        try:
                            widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                        except Exception:
                            pass
                        widget.insert(tk.INSERT, text)
                except Exception:
                    pass

        def do_select_all():
            if isinstance(widget, (tk.Entry, ttk.Entry)):
                widget.select_range(0, tk.END)
                widget.icursor(tk.END)
            elif isinstance(widget, tk.Text):
                widget.tag_add(tk.SEL, "1.0", tk.END)
                widget.mark_set(tk.INSERT, "1.0")

        menu.add_command(label="✂️ Вирізати", command=do_cut, state=tk.NORMAL if has_selection else tk.DISABLED)
        menu.add_command(label="📄 Копіювати", command=do_copy, state=tk.NORMAL if has_selection else tk.DISABLED)
        menu.add_command(label="📋 Вставити", command=do_paste)
        menu.add_separator()
        menu.add_command(label="🔘 Виділити все", command=do_select_all)
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    root.bind_all("<Button-3>", show_context_menu, add="+")

def bring_to_front(window, parent=None):
    """
    Гарантує, що додаткове вікно (CTkToplevel) надійно з'явиться поверх головного
    вікна та отримає активний фокус у Windows, уникаючи відкриття на задньому плані.
    """
    if parent is not None:
        try:
            window.transient(parent)
        except Exception:
            pass
    try:
        window.lift()
        window.focus_force()
        window.attributes("-topmost", True)
        window.after(120, lambda: window.attributes("-topmost", False))
        window.after(150, window.lift)
        window.after(150, window.focus_force)
    except Exception:
        pass
