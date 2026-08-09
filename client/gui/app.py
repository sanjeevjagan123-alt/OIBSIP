"""Tkinter-based GUI application for the chat client."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import logging

from client.core.client import ChatClient
from common.config_loader import load_config


class ChatApp:
    """High-level GUI application managing views and client network."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("chat_app")
        self.config = load_config()
        self.root = tk.Tk()
        self.root.title("Oasis Chat")
        self.root.geometry("800x600")

        self.client = ChatClient(self.config.host, self.config.port)
        self.event_queue: "queue.Queue[dict]" = queue.Queue()

        # Simple frames
        self.login_frame = ttk.Frame(self.root)
        self.chat_frame = ttk.Frame(self.root)

        self._build_login()
        self._build_chat()

        self.login_frame.pack(fill=tk.BOTH, expand=True)
        self.listener_started = False

        # Polling loop for events
        self.root.after(100, self._process_events)

    def _build_login(self) -> None:
        frm = self.login_frame
        ttk.Label(frm, text="Username:").pack(pady=6)
        self.username_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.username_var).pack(pady=6)

        ttk.Label(frm, text="Password:").pack(pady=6)
        self.password_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.password_var, show="*").pack(pady=6)

        btn_frame = ttk.Frame(frm)
        btn_frame.pack(pady=12)
        ttk.Button(btn_frame, text="Register", command=self._on_register).grid(row=0, column=0, padx=6)
        ttk.Button(btn_frame, text="Login", command=self._on_login).grid(row=0, column=1, padx=6)

    def _build_chat(self) -> None:
        frm = self.chat_frame
        top = ttk.Frame(frm)
        top.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(top, textvariable=tk.StringVar(value="Logged in as:" )).pack(side=tk.LEFT, padx=6)
        self.current_user_label = ttk.Label(top, text="(not logged in)")
        self.current_user_label.pack(side=tk.LEFT)
        ttk.Button(top, text="Logout", command=self._on_logout).pack(side=tk.RIGHT, padx=6)

        middle = ttk.Frame(frm)
        middle.pack(fill=tk.BOTH, expand=True)

        # Room list
        rooms_frame = ttk.Frame(middle)
        rooms_frame.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)
        ttk.Label(rooms_frame, text="Rooms").pack()
        self.rooms_listbox = tk.Listbox(rooms_frame, height=15)
        self.rooms_listbox.pack()
        ttk.Button(rooms_frame, text="Join", command=self._join_selected_room).pack(pady=6)

        # Chat area
        chat_area = ttk.Frame(middle)
        chat_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.chat_history = scrolledtext.ScrolledText(chat_area, state=tk.DISABLED)
        self.chat_history.pack(fill=tk.BOTH, expand=True)

        bottom = ttk.Frame(frm)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        self.msg_var = tk.StringVar()
        ttk.Entry(bottom, textvariable=self.msg_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6, pady=6)
        ttk.Button(bottom, text="Send to Room", command=self._send_room_message).pack(side=tk.LEFT, padx=6)
        ttk.Button(bottom, text="Send DM", command=self._send_direct_message).pack(side=tk.LEFT, padx=6)

    # ---- GUI Actions ----
    def _on_register(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        try:
            self.client.connect()
            resp = self.client.register(username, password)
            if resp.get("status") == "success":
                messagebox.showinfo("Register", "Registration successful. Please login.")
            else:
                messagebox.showerror("Register failed", resp.get("message", str(resp)))
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_login(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        try:
            self.client.connect()
            if not self.listener_started:
                self.client.start_listener()
                self.client.add_event_callback(self._on_event)
                self.listener_started = True
            resp = self.client.login(username, password)
            if resp.get("status") == "success":
                self.current_user_label.config(text=username)
                self.login_frame.forget()
                self.chat_frame.pack(fill=tk.BOTH, expand=True)
                # Populate rooms list (basic)
                self.rooms_listbox.delete(0, tk.END)
                self.rooms_listbox.insert(tk.END, "general")
                # Auto-join handled by server; request history
                hist = self.client.get_history("room", "general", limit=50)
                self._append_history_messages(hist)
            else:
                messagebox.showerror("Login failed", resp.get("message", str(resp)))
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_logout(self) -> None:
        try:
            self.client.disconnect()
        finally:
            self.chat_frame.forget()
            self.login_frame.pack(fill=tk.BOTH, expand=True)
            self.current_user_label.config(text="(not logged in)")

    def _join_selected_room(self) -> None:
        sel = self.rooms_listbox.curselection()
        if not sel:
            return
        room = self.rooms_listbox.get(sel[0])
        resp = self.client.join_room(room)
        if resp.get("status") == "success":
            messagebox.showinfo("Joined", f"Joined room {room}")
        else:
            messagebox.showerror("Join failed", resp.get("message", str(resp)))

    def _send_room_message(self) -> None:
        content = self.msg_var.get().strip()
        if not content:
            return
        resp = self.client.send_chat_message("room", "general", content)
        if resp.get("status") == "success":
            self.msg_var.set("")
        else:
            messagebox.showerror("Send failed", resp.get("message", str(resp)))

    def _send_direct_message(self) -> None:
        content = self.msg_var.get().strip()
        if not content:
            return
        # For simplicity send to the username in username field
        target = self.username_var.get().strip()
        resp = self.client.send_chat_message("user", target, content)
        if resp.get("status") == "success":
            self.msg_var.set("")
        else:
            messagebox.showerror("Send failed", resp.get("message", str(resp)))

    # ---- Event handling ----
    def _on_event(self, frame: dict) -> None:
        # push to thread-safe queue for GUI thread
        try:
            self.event_queue.put(frame)
        except Exception:
            pass

    def _process_events(self) -> None:
        try:
            while True:
                frame = self.event_queue.get_nowait()
                self._handle_frame(frame)
        except Exception:
            pass
        finally:
            self.root.after(100, self._process_events)

    def _handle_frame(self, frame: dict) -> None:
        event = frame.get("event")
        if event == "new_message":
            payload = frame.get("payload", {})
            sender = payload.get("sender_username") or payload.get("sender") or ""
            content = payload.get("content")
            ts = payload.get("timestamp", "")
            self._append_chat_line(f"[{ts}] {sender}: {content}")
        elif event == "room_update":
            payload = frame.get("payload", {})
            self._append_chat_line(f"[room] {payload}")
        elif event == "response":
            # ignore plain responses in the async loop
            pass
        else:
            self._append_chat_line(f"[event] {frame}")

    def _append_chat_line(self, text: str) -> None:
        self.chat_history.configure(state=tk.NORMAL)
        self.chat_history.insert(tk.END, text + "\n")
        self.chat_history.configure(state=tk.DISABLED)
        self.chat_history.yview(tk.END)

    def _append_history_messages(self, resp: dict) -> None:
        if resp.get("status") != "success":
            return
        msgs = resp.get("payload", {}).get("messages", [])
        for m in msgs:
            line = f"[{m.get('timestamp')}] {m.get('sender_username')}: {m.get('content')}"
            self._append_chat_line(line)

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
