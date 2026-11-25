import json
import os
import random
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk


SESSION_SECONDS = 45 * 60
EMAIL_MINIMUM_WORDS = 90
APP_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROMPTS_PATH = os.path.join(APP_DIRECTORY, "prompts.json")
ATTEMPTS_DIRECTORY = os.path.join(APP_DIRECTORY, "attempts")


class DanskSkrivningApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DU3 Skrivning - Practice")
        self.root.geometry("1920x1080")
        self.root.minsize(700, 600)
        self.root.protocol("WM_DELETE_WINDOW", self.close_window)

        self.active_attempt = False
        self.timer_after_id = None
        self.timer_flash_after_id = None
        self.timer_flash_sequence = []
        self.timer_flash_index = 0
        self.timer_flash_visible = False
        self.timer_permanent_red = False
        self.last_timer_alert = None
        self.deadline = None
        self.current_prompt = None
        self.dark_mode = False
        self.complaint_text = None
        self.email_text = None
        self.timer_label = None
        self.complaint_count_label = None
        self.email_count_label = None

        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Timer.TLabel", font=("Segoe UI", 28, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 13, "bold"))
        self.style = style
        self.toolbar = ttk.Frame(self.root, padding=(12, 8))
        self.toolbar.pack(fill="x")
        self.theme_button = ttk.Button(self.toolbar, command=self.toggle_theme)
        self.theme_button.pack(side="left")

        self.show_menu()

    def clear_window(self):
        for child in self.root.winfo_children():
            if child is not self.toolbar:
                child.destroy()
        self.timer_label = None

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode:
            background, surface, foreground = "#202522", "#2b322e", "#eef2ee"
            muted, input_background = "#c2cbc4", "#171b19"
        else:
            background, surface, foreground = "#f3f5f2", "#ffffff", "#202521"
            muted, input_background = "#5c665f", "#ffffff"

        self.root.configure(background=background)
        self.style.configure(".", background=background, foreground=foreground)
        self.style.configure("TFrame", background=background)
        self.style.configure("TLabel", background=background, foreground=foreground)
        self.style.configure("Title.TLabel", background=background, foreground=foreground)
        self.style.configure("Section.TLabel", background=background, foreground=foreground)
        self.style.configure(
            "Timer.TLabel",
            background=background,
            foreground="#b42318" if self.timer_permanent_red else foreground,
        )
        self.style.configure(
            "TButton", background=surface, foreground=foreground, padding=(8, 4)
        )
        self.style.map(
            "TButton",
            background=[("active", "#d9e0db" if not self.dark_mode else "#414a44")],
        )
        self.style.configure(
            "Finished.TButton", background="#15803d", foreground="#ffffff", padding=(8, 4)
        )
        self.style.map(
            "Finished.TButton",
            background=[("active", "#166534"), ("pressed", "#14532d")],
            foreground=[("disabled", "#ffffff")],
        )
        self.theme_button.configure(text="Light mode" if self.dark_mode else "Dark mode")

        for widget in self.root.winfo_children():
            self.apply_widget_theme(widget, foreground, input_background)

        if self.timer_label is not None and self.timer_label.winfo_exists():
            timer_is_red = self.timer_permanent_red and not self.timer_flash_after_id
            if self.timer_flash_after_id is not None:
                timer_is_red = self.timer_flash_visible
            self.timer_label.configure(
                foreground="#b42318" if timer_is_red else foreground
            )

        if self.complaint_text is not None and self.email_text is not None:
            self.update_word_counts()

    def apply_widget_theme(self, widget, foreground, input_background):
        if isinstance(widget, tk.Text):
            widget.configure(
                background=input_background,
                foreground=foreground,
                insertbackground=foreground,
                selectbackground="#356b52" if self.dark_mode else "#b8d7c3",
            )
        elif isinstance(widget, tk.Listbox):
            widget.configure(
                background=input_background,
                foreground=foreground,
                selectbackground="#356b52" if self.dark_mode else "#b8d7c3",
                selectforeground=foreground,
            )
        elif isinstance(widget, tk.Toplevel):
            widget.configure(background="#202522" if self.dark_mode else "#f3f5f2")

        for child in widget.winfo_children():
            self.apply_widget_theme(child, foreground, input_background)

    def load_prompts(self):
        if not os.path.isfile(PROMPTS_PATH):
            raise ValueError(f"Prompt file not found:\n{PROMPTS_PATH}")

        try:
            with open(PROMPTS_PATH, "r", encoding="utf-8") as prompt_file:
                prompts = json.load(prompt_file)
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Could not read prompts.json:\n{error}") from error

        if not isinstance(prompts, dict):
            raise ValueError('prompts.json must contain an object with "complaints" and "emails" lists.')

        complaints = prompts.get("complaints")
        emails = prompts.get("emails")

        if not isinstance(complaints, list) or not complaints:
            raise ValueError('prompts.json must contain a non-empty "complaints" list.')
        if not isinstance(emails, list) or not emails:
            raise ValueError('prompts.json must contain a non-empty "emails" list.')

        valid_complaints = [
            prompt.strip()
            for prompt in complaints
            if isinstance(prompt, str) and prompt.strip()
        ]
        valid_emails = [
            prompt.strip()
            for prompt in emails
            if isinstance(prompt, str) and prompt.strip()
        ]

        if not valid_complaints:
            raise ValueError('The "complaints" list has no usable non-empty strings.')
        if not valid_emails:
            raise ValueError('The "emails" list has no usable non-empty strings.')

        return {"complaints": valid_complaints, "emails": valid_emails}

    def show_menu(self):
        self.cancel_timer()
        self.active_attempt = False
        self.current_prompt = None
        self.complaint_text = None
        self.email_text = None
        self.clear_window()

        content = ttk.Frame(self.root, padding=36)
        content.pack(fill="both", expand=True)

        ttk.Label(content, text="DU3 Skrivning", style="Title.TLabel").pack(pady=(90, 12))
        ttk.Label(
            content,
            text="DU3 = complaint + email (min. 90 words)",
            font=("Segoe UI", 13),
        ).pack(pady=(0, 30))
        ttk.Button(
            content,
            text="Start new attempt",
            command=self.start_attempt,
            width=28,
        ).pack(pady=8, ipady=5)
        ttk.Button(
            content,
            text="View past attempts",
            command=self.show_past_attempts,
            width=28,
        ).pack(pady=8, ipady=5)
        self.apply_theme()

    def start_attempt(self):
        try:
            prompts = self.load_prompts()
            self.current_prompt = {
                "complaint": random.choice(prompts["complaints"]),
                "email": random.choice(prompts["emails"]),
            }
        except ValueError as error:
            messagebox.showerror("Prompts unavailable", str(error), parent=self.root)
            return

        self.active_attempt = True
        self.deadline = time.monotonic() + SESSION_SECONDS
        self.timer_permanent_red = False
        self.last_timer_alert = None
        self.show_attempt_screen()
        self.update_timer()

    def show_attempt_screen(self):
        self.clear_window()

        content = ttk.Frame(self.root, padding=(24, 18))
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(5, weight=1)
        content.rowconfigure(9, weight=2)

        top_row = ttk.Frame(content)
        top_row.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        top_row.columnconfigure(0, weight=1)
        ttk.Label(top_row, text="Writing attempt", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.timer_label = ttk.Label(top_row, text="45:00", style="Timer.TLabel")
        self.timer_label.grid(row=0, column=1, sticky="e")

        ttk.Label(content, text="Complaint/Review/Application prompt", style="Section.TLabel").grid(
            row=1, column=0, sticky="w", pady=(0, 3)
        )
        ttk.Label(
            content,
            text=self.current_prompt["complaint"],
            wraplength=820,
            justify="left",
        ).grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(content, text="Opgave 1", style="Section.TLabel").grid(
            row=3, column=0, sticky="w", pady=(0, 4)
        )
        self.complaint_text = self.create_text_area(content, height=8, row=4)
        self.complaint_count_label = ttk.Label(content, text="Words: 0")
        self.complaint_count_label.grid(row=5, column=0, sticky="nw", pady=(8, 14))

        ttk.Label(content, text="Email prompt", style="Section.TLabel").grid(
            row=6, column=0, sticky="w", pady=(0, 3)
        )
        ttk.Label(
            content,
            text=self.current_prompt["email"],
            wraplength=820,
            justify="left",
        ).grid(row=7, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(content, text="Opgave 2 (min. 90 ord)", style="Section.TLabel").grid(
            row=8, column=0, sticky="w", pady=(0, 4)
        )
        self.email_text = self.create_text_area(content, height=12, row=9)
        self.email_count_label = ttk.Label(
            content, text="Words: 0 / 90", foreground="#b42318"
        )
        self.email_count_label.grid(row=10, column=0, sticky="w", pady=(4, 10))
        bottom_controls = ttk.Frame(content)
        bottom_controls.grid(row=11, column=0, sticky="ew", pady=(4, 0))
        bottom_controls.columnconfigure(0, weight=1)
        bottom_controls.columnconfigure(1, weight=1)
        ttk.Button(
            bottom_controls,
            text="Back",
            command=self.confirm_back_to_menu,
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            bottom_controls,
            text="Finished",
            command=self.finish_attempt,
            style="Finished.TButton",
        ).grid(row=0, column=1, sticky="e", ipady=4)
        self.apply_theme()

    def create_text_area(self, parent, height, row):
        text_widget = tk.Text(
            parent,
            height=height,
            wrap="word",
            undo=True,
            font=("Segoe UI", 13),
        )
        text_widget.grid(row=row, column=0, sticky="nsew")
        text_widget.bind("<<Modified>>", self.update_word_counts)
        text_widget.bind("<MouseWheel>", self.scroll_text)
        text_widget.bind("<Button-4>", self.scroll_text)
        text_widget.bind("<Button-5>", self.scroll_text)
        return text_widget

    def scroll_text(self, event):
        if event.num == 4:
            event.widget.yview_scroll(-1, "units")
        elif event.num == 5:
            event.widget.yview_scroll(1, "units")
        else:
            event.widget.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def update_word_counts(self, event=None):
        if self.complaint_text is None or self.email_text is None:
            return

        for widget in (self.complaint_text, self.email_text):
            if widget.edit_modified():
                widget.edit_modified(False)

        complaint_count = len(self.complaint_text.get("1.0", "end-1c").split())
        email_count = len(self.email_text.get("1.0", "end-1c").split())
        self.complaint_count_label.configure(text=f"Words: {complaint_count}")
        meets_minimum = email_count >= EMAIL_MINIMUM_WORDS
        self.email_count_label.configure(
            text=f"Words: {email_count} / {EMAIL_MINIMUM_WORDS}",
            foreground=("#45b878" if self.dark_mode else "#067647")
            if meets_minimum
            else ("#ff6b63" if self.dark_mode else "#b42318"),
        )

    def update_timer(self):
        if not self.active_attempt:
            return

        remaining = max(0, int(self.deadline - time.monotonic() + 0.999))
        minutes, seconds = divmod(remaining, 60)
        self.timer_label.configure(text=f"{minutes:02d}:{seconds:02d}")
        if remaining > 0 and remaining % 300 == 0 and remaining != self.last_timer_alert:
            self.last_timer_alert = remaining
            if remaining == 300:
                self.timer_permanent_red = True
                self.flash_timer([True, False, True])
            else:
                self.flash_timer([True, False])
        if remaining == 0:
            self.finish_attempt()
        else:
            self.timer_after_id = self.root.after(250, self.update_timer)

    def flash_timer(self, sequence):
        if self.timer_flash_after_id is not None:
            self.root.after_cancel(self.timer_flash_after_id)
        self.timer_flash_sequence = sequence
        self.timer_flash_index = 0
        self.advance_timer_flash()

    def advance_timer_flash(self):
        if self.timer_label is None or self.timer_flash_index >= len(self.timer_flash_sequence):
            self.timer_flash_after_id = None
            self.timer_flash_visible = False
            return

        self.timer_flash_visible = self.timer_flash_sequence[self.timer_flash_index]
        self.timer_flash_index += 1
        color = "#b42318" if self.timer_flash_visible else (
            "#eef2ee" if self.dark_mode else "#202521"
        )
        self.timer_label.configure(foreground=color)
        if self.timer_flash_index < len(self.timer_flash_sequence):
            self.timer_flash_after_id = self.root.after(180, self.advance_timer_flash)
        else:
            self.timer_flash_after_id = None
            self.timer_flash_visible = False
            self.timer_label.configure(
                foreground="#b42318" if self.timer_permanent_red else (
                    "#eef2ee" if self.dark_mode else "#202521"
                )
            )

    def cancel_timer(self):
        if self.timer_after_id is not None:
            self.root.after_cancel(self.timer_after_id)
            self.timer_after_id = None
        if self.timer_flash_after_id is not None:
            self.root.after_cancel(self.timer_flash_after_id)
            self.timer_flash_after_id = None
        self.timer_flash_sequence = []
        self.timer_flash_index = 0
        self.timer_flash_visible = False

    def finish_attempt(self):
        if not self.active_attempt:
            return

        complaint = self.complaint_text.get("1.0", "end-1c")
        email = self.email_text.get("1.0", "end-1c")
        try:
            saved_path = self.save_attempt(complaint, email)
        except OSError as error:
            messagebox.showerror(
                "Could not save attempt", f"The attempt was not saved:\n{error}", parent=self.root
            )
            return

        self.active_attempt = False
        self.cancel_timer()
        self.show_finished(saved_path)

    def save_attempt(self, complaint, email):
        os.makedirs(ATTEMPTS_DIRECTORY, exist_ok=True)
        finished_at = datetime.now().astimezone()
        timestamp = finished_at.strftime("%Y-%m-%d %H:%M:%S %Z")
        filename_base = finished_at.strftime("attempt_%Y-%m-%d_%H-%M")
        filename = f"{filename_base}.txt"
        suffix = 2
        while os.path.exists(os.path.join(ATTEMPTS_DIRECTORY, filename)):
            filename = f"{filename_base}_{suffix:02d}.txt"
            suffix += 1

        content = (
            f"Timestamp: {timestamp}\n\n"
            "=== COMPLAINT PROMPT ===\n"
            f"{self.current_prompt['complaint']}\n\n"
            "=== COMPLAINT TEXT ===\n"
            f"{complaint}\n\n"
            f"Complaint word count: {len(complaint.split())}\n\n"
            "=== EMAIL PROMPT ===\n"
            f"{self.current_prompt['email']}\n\n"
            "=== EMAIL TEXT ===\n"
            f"{email}\n\n"
            f"Email word count: {len(email.split())}\n\n"
            "=== GRADING PROMPT ===\n"
            "Assess the complaint and email above as a Danish-language teacher preparing a learner "
            "for the DU3 writing test. Comment on task completion, clarity, vocabulary, grammar, "
            "and sentence structure. Check whether the email contains at least 90 words. Give "
            "specific corrections and explain the most important improvements. Do not rewrite the "
            "texts without explaining the changes. Please reply in english.\n"
            "=== END GRADING PROMPT ===\n"
        )
        saved_path = os.path.join(ATTEMPTS_DIRECTORY, filename)
        with open(saved_path, "w", encoding="utf-8") as attempt_file:
            attempt_file.write(content)
        return saved_path

    def show_finished(self, saved_path):
        self.clear_window()
        content = ttk.Frame(self.root, padding=36)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Attempt saved", style="Title.TLabel").pack(pady=(130, 12))
        ttk.Label(
            content,
            text=f"Saved to:\n{os.path.relpath(saved_path, APP_DIRECTORY)}",
            justify="center",
        ).pack(pady=(0, 24))
        ttk.Button(
            content, text="Return to start menu", command=self.show_menu
        ).pack(ipadx=12, ipady=5)
        self.apply_theme()

    def show_past_attempts(self):
        self.clear_window()
        content = ttk.Frame(self.root, padding=24)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        ttk.Label(content, text="Past attempts", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )
        list_frame = ttk.Frame(content)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.attempt_list = tk.Listbox(list_frame, activestyle="dotbox", height=18)
        self.attempt_list.grid(row=0, column=0, sticky="nsew")
        self.attempt_list.bind("<Double-Button-1>", lambda event: self.open_selected_attempt())

        try:
            filenames = sorted(
                (
                    name
                    for name in os.listdir(ATTEMPTS_DIRECTORY)
                    if name.lower().endswith(".txt")
                    and os.path.isfile(os.path.join(ATTEMPTS_DIRECTORY, name))
                ),
                reverse=True,
            )
        except FileNotFoundError:
            filenames = []
        self.attempt_filenames = filenames
        for filename in filenames:
            self.attempt_list.insert("end", filename)

        if not filenames:
            ttk.Label(content, text="No saved attempts yet.").grid(
                row=2, column=0, sticky="w", pady=(8, 0)
            )

        controls = ttk.Frame(content)
        controls.grid(row=3, column=0, sticky="e", pady=(14, 0))
        ttk.Button(controls, text="Open selected", command=self.open_selected_attempt).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(controls, text="Back", command=self.show_menu).pack(side="left")
        self.apply_theme()

    def open_selected_attempt(self):
        selection = self.attempt_list.curselection()
        if not selection:
            messagebox.showinfo("Select an attempt", "Choose an attempt to open.", parent=self.root)
            return

        path = os.path.join(ATTEMPTS_DIRECTORY, self.attempt_filenames[selection[0]])
        try:
            with open(path, "r", encoding="utf-8") as attempt_file:
                content = attempt_file.read()
        except OSError as error:
            messagebox.showerror("Could not open attempt", str(error), parent=self.root)
            return

        viewer = tk.Toplevel(self.root)
        viewer.title(os.path.basename(path))
        viewer.geometry("760x600")
        text = tk.Text(viewer, wrap="word", padx=12, pady=12, font=("Segoe UI", 13))
        text.pack(fill="both", expand=True)
        text.insert("1.0", content)
        text.configure(state="disabled")
        text.bind("<MouseWheel>", self.scroll_text)
        text.bind("<Button-4>", self.scroll_text)
        text.bind("<Button-5>", self.scroll_text)
        self.apply_theme()

    def confirm_back_to_menu(self):
        if not self.active_attempt:
            self.show_menu()
            return

        discard = messagebox.askyesno(
            "Return to menu?",
            "This attempt has not been saved. Return to the menu and discard it?",
            parent=self.root,
        )
        if discard:
            self.show_menu()

    def close_window(self):
        if self.active_attempt:
            discard = messagebox.askyesno(
                "Quit current attempt?",
                "This attempt has not been saved. Close the window and discard it?",
                parent=self.root,
            )
            if not discard:
                return
        self.cancel_timer()
        self.root.destroy()


def main():
    root = tk.Tk()
    DanskSkrivningApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()