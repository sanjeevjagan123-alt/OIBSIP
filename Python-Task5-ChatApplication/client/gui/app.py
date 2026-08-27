"""CustomTkinter-based GUI application for the chat client."""

from __future__ import annotations

import queue
import threading
import logging
import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime

from plyer import notification

from client.core.client import ChatClient
from common.config_loader import load_config

# Simple emoji shortcode map – converts short textual codes to Unicode emojis
EMOJI_MAP = {
    ":smile:": "😊",
    ":laughing:": "😆",
    ":heart:": "❤️",
    ":thumbsup:": "👍",
    ":thumbsdown:": "👎",
    ":sad:": "😢",
    ":wink:": "😉",
    ":fire:": "🔥",
    ":clap:": "👏",
    ":thinking:": "🤔",
}


def replace_emoji_shortcodes(text: str) -> str:
    """Replace known shortcodes in *text* with their emoji equivalents.

    The function iterates over :data:`EMOJI_MAP` and performs a simple
    ``str.replace`` for each shortcode. It returns the transformed string.
    """
    for shortcode, emoji in EMOJI_MAP.items():
        text = text.replace(shortcode, emoji)
    return text

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ChatApp:
    """High-level GUI application managing views and client network."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("chat_app")
        self.config = load_config()
        self.root = ctk.CTk()
        self.root.title("Oasis")
        self.root.geometry("1000x650")
        self.root.minsize(800, 550)

        self.client = ChatClient(self.config.host, self.config.port)
        self.event_queue: "queue.Queue[dict]" = queue.Queue()
        self.listener_started = False

        # ---- Application state ----
        self.current_user = None
        self.current_target_type = "room"
        self.current_target_name = "general"

        self.rooms = []
        self.online_users = set()

        self.typing_users = set()

        self.message_cache = {}
        self.search_results = []

        self.ui_ready = False


        # Container frames
        self.login_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.chat_frame = ctk.CTkFrame(self.root, fg_color="transparent")

        self._build_login()
        self.login_frame.pack(fill="both", expand=True)

        self.root.after(100, self._process_events)

    # ---- Login / Register Screen ----

    def _build_login(self) -> None:
        frm = self.login_frame

        # Center card
        card = ctk.CTkFrame(frm, width=380, corner_radius=16, fg_color="#111a2e")
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            card, text="Oasis",
            font=ctk.CTkFont(size=28, weight="bold"),
        ).pack(pady=(40, 10), padx=60)

        ctk.CTkLabel(
            card, text="Sign in to continue",
            font=ctk.CTkFont(size=13), text_color="#8a94a6",
        ).pack(pady=(0, 30))

        ctk.CTkLabel(
            card, text="Mail ID",
            font=ctk.CTkFont(size=12), text_color="#8a94a6", anchor="w",
        ).pack(pady=(8, 2), padx=50, fill="x")

        self.username_var = ctk.StringVar()
        self.username_entry = ctk.CTkEntry(
            card, textvariable=self.username_var,
            width=280, height=42, corner_radius=10,
        )
        self.username_entry.pack(pady=(0, 8), padx=50)

        ctk.CTkLabel(
            card, text="Password",
            font=ctk.CTkFont(size=12), text_color="#8a94a6", anchor="w",
        ).pack(pady=(8, 2), padx=50, fill="x")

        self.password_var = ctk.StringVar()
        self.password_entry = ctk.CTkEntry(
            card, textvariable=self.password_var,
            show="*", width=280, height=42, corner_radius=10,
        )
        self.password_entry.pack(pady=(0, 8), padx=50)
        self.password_entry.bind("<Return>", lambda e: self._on_login())

        self.login_btn = ctk.CTkButton(
            card, text="Login", command=self._on_login,
            width=280, height=42, corner_radius=10,
        )
        self.login_btn.pack(pady=(20, 10), padx=50)

        self.register_btn = ctk.CTkButton(
            card, text="Create Account", command=self._on_register,
            width=280, height=42, corner_radius=10,
            fg_color="transparent", border_width=1, border_color="#3a4a63",
            hover_color="#1a2740",
        )
        self.register_btn.pack(pady=(0, 40), padx=50)

    # ---- GUI Actions ----

    def _on_register(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        if not username or not password:
            messagebox.showwarning("Missing info", "Enter both username and password.")
            return
        try:
            self.client.connect()
            resp = self.client.register(username, password)
            if resp.get("status") == "success":
                messagebox.showinfo("Registered", "Account created. Please login.")
            else:
                messagebox.showerror("Register failed", resp.get("message", str(resp)))
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_login(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        if not username or not password:
            messagebox.showwarning("Missing info", "Enter both username and password.")
            return
        try:
            self.client.connect()
            if not self.listener_started:
                self.client.start_listener()
                self.client.add_event_callback(self._on_event)
                self.listener_started = True
            resp = self.client.login(username, password)
            if resp.get("status") == "success":
                self.login_frame.pack_forget()
                self._build_chat_placeholder()
                self.chat_frame.pack(fill="both", expand=True)
            else:
                messagebox.showerror("Login failed", resp.get("message", str(resp)))
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _build_chat_placeholder(self) -> None:
        for widget in self.chat_frame.winfo_children():
            widget.destroy()

        self.chat_frame.grid_columnconfigure(1, weight=1)
        self.chat_frame.grid_rowconfigure(0, weight=1)

        # ---- Sidebar (rooms) ----
        sidebar = ctk.CTkFrame(self.chat_frame, width=220, corner_radius=0, fg_color="#0d1526")
        sidebar.grid(row=0, column=0, sticky="nswe")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar, text="Rooms",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(20, 10), padx=15, anchor="w")

        self.rooms_listbox_frame = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.rooms_listbox_frame.pack(fill="both", expand=True, padx=10)

        ctk.CTkButton(
            sidebar, text="Logout", command=self._on_logout,
            fg_color="transparent", border_width=1, border_color="#3a4a63",
            hover_color="#1a2740", height=36,
        ).pack(side="bottom", pady=15, padx=15, fill="x")

        # ---- Main chat area ----
        main = ctk.CTkFrame(self.chat_frame, corner_radius=0, fg_color="#161f36")
        main.grid(row=0, column=1, sticky="nswe")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        top_bar = ctk.CTkFrame(main, height=60, corner_radius=0, fg_color="#111a2e")
        top_bar.grid(row=0, column=0, sticky="we")
        self.current_room_label = ctk.CTkLabel(
            top_bar, text="general",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.current_room_label.pack(side="left", padx=20, pady=15)

        self.chat_display = ctk.CTkTextbox(main, fg_color="#161f36", wrap="word", font=ctk.CTkFont(size=13))
        self.chat_display.grid(row=1, column=0, sticky="nswe", padx=15, pady=10)
        self.chat_display.configure(state="disabled")

        bottom_bar = ctk.CTkFrame(main, height=60, corner_radius=0, fg_color="#111a2e")
        bottom_bar.grid(row=2, column=0, sticky="we")
        bottom_bar.grid_columnconfigure(0, weight=1)

        self.msg_var = ctk.StringVar()
        self.msg_entry = ctk.CTkEntry(
            bottom_bar, textvariable=self.msg_var,
            placeholder_text="Type a message...", height=42, corner_radius=10,
        )
        self.msg_entry.grid(row=0, column=0, sticky="we", padx=(15, 8), pady=10)
        self.msg_entry.bind("<Return>", lambda e: self._send_room_message())

        ctk.CTkButton(
            bottom_bar, text="Send", command=self._send_room_message,
            width=80, height=42, corner_radius=10,
        ).grid(row=0, column=1, padx=(0, 15), pady=10)

        self.current_room = "general"
        self._load_rooms()
        self._load_history()

    def _load_rooms(self) -> None:
        for widget in self.rooms_listbox_frame.winfo_children():
            widget.destroy()
        resp = self.client.get_rooms()
        if resp.get("status") != "success":
            return
        rooms = resp.get("payload", {}).get("rooms", [])
        for room in rooms:
            name = room.get("name", "")
            btn = ctk.CTkButton(
                self.rooms_listbox_frame, text=f"# {name}",
                anchor="w", fg_color="transparent", hover_color="#1a2740",
                command=lambda n=name: self._switch_room(n),
            )
            btn.pack(fill="x", pady=2)

    def _switch_room(self, room_name: str) -> None:
        try:
            self.client.join_room(room_name)
        except Exception:
            pass
        self.current_room = room_name
        self.current_room_label.configure(text=room_name)
        self._load_history()

    def _load_history(self) -> None:
        print(
            "DEBUG LOAD HISTORY:",
            "current_room=", self.current_room,
            "socket=", self.client._socket is not None,
            "listener_active=", self.client._listener_active,
            "listener_thread_alive=",
            self.client._listener_thread.is_alive()
            if self.client._listener_thread is not None
            else None,
        )
        resp = self.client.get_history("room", self.current_room, limit=50)
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        if resp.get("status") == "success":
            messages = resp.get("payload", {}).get("messages", [])
            for m in messages:
                sender = m.get("sender_username", "")
                # Replace any emoji shortcodes in the message content before display
                content = replace_emoji_shortcodes(m.get("content", ""))
                timestamp_str = m.get("timestamp", "")
                try:
                    ts = datetime.fromisoformat(timestamp_str)
                except Exception:
                    try:
                        ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        ts = datetime.now()
                time_prefix = ts.strftime("[%H:%M]")
                self.chat_display.insert("end", f"{time_prefix} {sender}: {content}\n")
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def _send_room_message(self) -> None:
        raw_content = self.msg_var.get().strip()
        if not raw_content:
            return
        content = replace_emoji_shortcodes(raw_content)
        resp = self.client.send_chat_message("room", self.current_room, content)
        if resp.get("status") == "success":
            self.msg_var.set("")
            self.chat_display.configure(state="normal")
            time_prefix = datetime.now().strftime("[%H:%M]")
            self.chat_display.insert("end", f"{time_prefix} You: {content}\n")
            self.chat_display.configure(state="disabled")
            self.chat_display.see("end")
        else:
            messagebox.showerror("Send failed", resp.get("message", str(resp)))

    def _on_logout(self) -> None:
        try:
            self.client.disconnect()
        finally:
            self.chat_frame.pack_forget()
            self.listener_started = False
            self.login_frame.pack(fill="both", expand=True)

        # ---- Event handling ----

    def _on_event(self, frame: dict) -> None:
        try:
            self.event_queue.put(frame)
        except Exception:
            pass

    def _process_events(self) -> None:
        try:
            while True:
                frame = self.event_queue.get_nowait()
                self._handle_server_event(frame)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._process_events)

    def _handle_server_event(self, frame: dict) -> None:
        """Handle asynchronous events received from the server."""

        event = frame.get("event")

        if event == "new_message":
            self._handle_new_message_event(frame)

    def _handle_new_message_event(self, frame: dict) -> None:
        payload = frame.get("payload", {})

        target_type = payload.get("target_type")
        target_name = payload.get("target_name")

        sender = payload.get("sender_username", "")
        content = replace_emoji_shortcodes(payload.get("content", ""))

        # Show a desktop notification if the window is not focused,
        # regardless of which room/target is currently open.
        try:
            if self.root.focus_displayof() is None:
                notification.notify(
                    title=f"New message in {target_name}",
                    message=f"{sender}: {content}",
                    app_name="Oasis",
                    timeout=5,
                )
        except Exception:
            pass

        if target_type != self.current_target_type:
            return

        if target_name != self.current_target_name:
            return

        timestamp_str = payload.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(timestamp_str)
            time_prefix = ts.strftime("[%H:%M]")
        except Exception:
            time_prefix = datetime.now().strftime("[%H:%M]")

        self.chat_display.configure(state="normal")
        self.chat_display.insert(
            "end",
            f"{time_prefix} {sender}: {content}\n",
        )
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        self.root.mainloop()

    def shutdown(self) -> None:
        try:
            self.client.disconnect()
        finally:
            try:
                self.root.destroy()
            except Exception:
                pass