import threading
import ctypes
import time
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DLL_PATH = os.path.join(BASE_DIR, "client_core.dll")

try:
    core = ctypes.CDLL(DLL_PATH)
    core.connect_to_server.restype = ctypes.c_int
    core.receive_data.restype = ctypes.c_int
except OSError:
    messagebox.showerror("Lỗi Chí Mạng", "Không tìm thấy file client_core.dll! Hãy biên dịch C++ trước.")
    exit()


class ChatApp:
    def __init__(self):
        self.bad_words = []
        self.server_ip = b"192.168.1.4"
        self.server_port = 9999
        self.connected = False

        self.root = tk.Tk()
        self.root.title("HUST Chat - Đăng nhập")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.setup_login_ui()
        self.root.mainloop()

    def setup_login_ui(self):
        self.f = tk.Frame(self.root, padx=20, pady=20)
        self.f.pack()

        tk.Label(self.f, text="Tài khoản:").grid(row=0, column=0)
        self.u = tk.Entry(self.f)
        self.u.grid(row=0, column=1, pady=5)

        tk.Label(self.f, text="Mật khẩu:").grid(row=1, column=0)
        self.p = tk.Entry(self.f, show="*")
        self.p.grid(row=1, column=1, pady=5)

        tk.Button(self.f, text="Đăng nhập", command=self.login).grid(row=2, column=0, pady=10)
        tk.Button(self.f, text="Đăng ký", command=self.register).grid(row=2, column=1, pady=10)

    # ----------------------------------------------------------------
    # GIAO DIỆN CHAT CHÍNH — gồm 2 tab: "Chat" và "Thông tin nhóm"
    # ----------------------------------------------------------------
    def setup_chat_ui(self):
        self.root.title(f"HUST Chat - {self.username}")
        self.root.geometry("450x400")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Chat (y nguyên giao diện/logic cũ)
        self.tab_chat = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_chat, text="Chat")
        self.setup_chat_tab()

        # Tab 2: Thông tin nhóm chat (mới)
        self.tab_info = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_info, text="Thông tin nhóm")
        self.setup_info_tab()

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        threading.Thread(target=self.recv_loop, daemon=True).start()

    def setup_chat_tab(self):
        chat_frame = tk.Frame(self.tab_chat)
        chat_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.scrollbar = tk.Scrollbar(chat_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.t = tk.Text(chat_frame, height=15, width=40, yscrollcommand=self.scrollbar.set,
                          state='disabled', font=("Arial", 11))
        self.t.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.t.yview)

        # Căn phải và in màu xanh cho tin nhắn của bản thân
        self.t.tag_config("me", foreground="blue", justify="right")
        # Căn trái và in màu đen cho tin nhắn của người khác
        self.t.tag_config("other", foreground="black", justify="left")

        input_frame = tk.Frame(self.tab_chat)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.i = tk.Entry(input_frame, font=("Arial", 11))
        self.i.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.i.bind("<Return>", lambda e: self.send())

        tk.Button(input_frame, text="Gửi", bg="lightblue", command=self.send).pack(side=tk.RIGHT)

    def setup_info_tab(self):
        self.lbl_total_members = tk.Label(
            self.tab_info, text="Tổng số thành viên: --",
            font=("Arial", 11, "bold"), fg="blue"
        )
        self.lbl_total_members.pack(anchor="w", padx=10, pady=(10, 5))

        self.list_members = tk.Listbox(self.tab_info, font=("Arial", 11))
        self.list_members.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def on_tab_changed(self, event):
        # Khi người dùng chuyển sang tab "Thông tin nhóm" (index 1) -> xin lại danh sách mới nhất
        if self.notebook.index(self.notebook.select()) == 1:
            self.request_member_list()

    def request_member_list(self):
        try:
            core.send_data(b"LIST\n")
        except Exception:
            pass

    def update_member_list(self, payload):
        # payload dạng: "user1:1,user2:0,user3:1" (1 = online, 0 = offline)
        self.list_members.delete(0, tk.END)
        entries = [e for e in payload.split(",") if e]
        online_count = 0
        for entry in entries:
            if ":" not in entry:
                continue
            name, status = entry.rsplit(":", 1)
            if status == "1":
                self.list_members.insert(tk.END, f"🟢 {name}")
                online_count += 1
            else:
                self.list_members.insert(tk.END, f"⚪ {name}")
        self.lbl_total_members.config(
            text=f"Tổng số thành viên: {len(entries)}   (Online: {online_count})"
        )

    # ----------------------------------------------------------------
    # KẾT NỐI & GIAO TIẾP VỚI SERVER (không đổi so với bản gốc)
    # ----------------------------------------------------------------
    def ensure_connection(self):
        if not self.connected:
            status = core.connect_to_server(self.server_ip, self.server_port)
            if status == 1:
                self.connected = True
            else:
                raise Exception("Server đang đóng hoặc sai IP!")

    def _wait_for_response(self):
        buffer = ctypes.create_string_buffer(1024)
        recv_buffer = ""
        while self.connected:
            bytes_read = core.receive_data(buffer, 1024)
            if bytes_read > 0:
                recv_buffer += buffer.value.decode('utf-8', errors='ignore')
                if "\n" in recv_buffer:
                    return recv_buffer.split("\n")[0]
            else:
                return ""

    def login(self):
        try:
            self.ensure_connection()
            msg = f"LOGIN|{self.u.get()}|{self.p.get()}\n".encode('utf-8')
            core.send_data(msg)

            res = self._wait_for_response()
            if res.startswith("AUTH_OK"):
                parts = res.split("|")
                if len(parts) > 1:
                    self.bad_words = parts[1].split(",")
                self.username = self.u.get()
                self.f.destroy()
                self.setup_chat_ui()
            elif res == "AUTH_PENDING":
                messagebox.showwarning("Chờ duyệt", "Tài khoản đã đăng ký nhưng Admin chưa duyệt!")
            else:
                messagebox.showerror("Lỗi", "Sai thông tin đăng nhập!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không kết nối được Server C++!\n{e}")

    def register(self):
        try:
            self.ensure_connection()
            msg = f"REG|{self.u.get()}|{self.p.get()}\n".encode('utf-8')
            core.send_data(msg)

            res = self._wait_for_response()
            if res == "REG_OK":
                messagebox.showinfo("Thành công", "Đã gửi yêu cầu đăng ký. Chờ Admin duyệt!")
            else:
                messagebox.showerror("Lỗi", "Tên tài khoản đã tồn tại!")
        except Exception as e:
            messagebox.showerror("Lỗi", "Không kết nối được Server!")

    def send(self):
        msg = self.i.get()
        if msg:
            msg_hien_thi = msg
            for word in self.bad_words:
                if word:
                    stars = "*" * len(word)
                    msg_hien_thi = msg_hien_thi.replace(word, stars)

            self.send_time = time.time()
            self.last_sent_msg = msg_hien_thi

            final_msg = f"CHAT|{msg_hien_thi}\n".encode('utf-8')
            core.send_data(final_msg)

            now = datetime.now().strftime("%H:%M:%S")
            self.show(f"[{now}] {msg_hien_thi}", "me")
            self.i.delete(0, tk.END)

    def recv_loop(self):
        buffer = ctypes.create_string_buffer(2048)
        recv_buffer = ""
        while self.connected:
            bytes_read = core.receive_data(buffer, 2048)
            if bytes_read > 0:
                data = buffer.value.decode('utf-8', errors='ignore')
                recv_buffer += data

                while "\n" in recv_buffer:
                    msg, recv_buffer = recv_buffer.split("\n", 1)
                    if msg:
                        # Tín hiệu báo nhận (RTT) từ Server
                        if msg == "ACK":
                            if hasattr(self, 'send_time'):
                                rtt = (time.time() - self.send_time) * 1000
                                print(f"[METRIC] Độ trễ (RTT): {rtt:.2f} ms")
                        # Phản hồi danh sách thành viên nhóm
                        elif msg.startswith("LIST|"):
                            self.update_member_list(msg[5:])
                        # Tin nhắn bình thường của người khác
                        else:
                            self.show(msg, "other")
            elif bytes_read == -1:
                self.connected = False
                self.show("[Hệ thống] Mất kết nối tới Server!", "other")
                break

    def show(self, msg, tag):
        self.t.config(state='normal')
        self.t.insert(tk.END, msg + "\n", tag)
        self.t.config(state='disabled')
        self.t.see(tk.END)

    def on_closing(self):
        if self.connected:
            core.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    ChatApp()