import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "Database", "chat.db"))

class AdminConsole:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Server Admin Panel (SQLite)")
        self.root.geometry("500x450")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Lịch sử Chat (Đã trả về thiết kế rộng rãi ban đầu)
        self.tab_history = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_history, text="Lịch sử Chat")
        self.setup_history_tab()

        # Tab 2: Đang Online
        self.tab_online = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_online, text="Đang Online")
        self.setup_online_tab()

        # Tab 3: Duyệt Tài Khoản
        self.tab_pending = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_pending, text="Duyệt Tài Khoản")
        self.setup_pending_tab()

        # Tab 4: Thành viên nhóm (Đổi tên và làm lại giao diện theo ý bạn)
        self.tab_users = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_users, text="Thành viên nhóm")
        self.setup_users_tab()

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        self.root.mainloop()

    def get_db_connection(self):
        if not os.path.exists(DB_PATH):
            messagebox.showerror("Lỗi", "Không tìm thấy Database! Hãy chạy Server C++ trước.")
            return None
        return sqlite3.connect(DB_PATH)

    def setup_history_tab(self):
        self.txt_history = tk.Text(self.tab_history, state='disabled', font=("Arial", 10))
        scrollbar = tk.Scrollbar(self.tab_history, command=self.txt_history.yview)
        self.txt_history.config(yscrollcommand=scrollbar.set)
        self.txt_history.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def setup_online_tab(self):
        self.list_online = tk.Listbox(self.tab_online, font=("Arial", 11))
        self.list_online.pack(fill=tk.BOTH, expand=True, pady=10)

    def setup_pending_tab(self):
        frame_list = tk.Frame(self.tab_pending)
        frame_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.list_pending = tk.Listbox(frame_list, font=("Arial", 11))
        self.list_pending.pack(fill=tk.BOTH, expand=True, pady=10)

        frame_btn = tk.Frame(self.tab_pending)
        frame_btn.pack(side=tk.RIGHT, padx=10)
        tk.Button(frame_btn, text="Duyệt User", bg="lightgreen", width=12, command=self.approve_user).pack(pady=5)
        tk.Button(frame_btn, text="Từ chối/Xóa", bg="salmon", width=12, command=self.reject_user).pack(pady=5)

    def setup_users_tab(self):
        # Khung bên trái chứa Tiêu đề đếm số lượng và Danh sách
        frame_left = tk.Frame(self.tab_users)
        frame_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=10)

        self.lbl_total_members = tk.Label(frame_left, text="Tổng số thành viên: 0", font=("Arial", 11, "bold"), fg="blue")
        self.lbl_total_members.pack(anchor="w", pady=(0, 5))

        self.list_users = tk.Listbox(frame_left, font=("Arial", 11))
        self.list_users.pack(fill=tk.BOTH, expand=True)

        # Khung bên phải chứa nút Xóa thành viên
        frame_btn = tk.Frame(self.tab_users)
        frame_btn.pack(side=tk.RIGHT, padx=10)
        tk.Button(frame_btn, text="Xóa thành viên", bg="red", fg="white", width=12, command=self.delete_user).pack(pady=5)

    def on_tab_changed(self, event):
        self.load_data()

    def load_data(self):
        conn = self.get_db_connection()
        if not conn: return
        cur = conn.cursor()

        # Tải Lịch sử
        self.txt_history.config(state='normal')
        self.txt_history.delete(1.0, tk.END)
        cur.execute("SELECT timestamp, message FROM history")
        for row in cur.fetchall():
            self.txt_history.insert(tk.END, f"[{row[0]}] {row[1]}\n")
        self.txt_history.config(state='disabled')
        self.txt_history.see(tk.END)

        # Tải Online
        self.list_online.delete(0, tk.END)
        cur.execute("SELECT username FROM users WHERE is_online = 1")
        for row in cur.fetchall():
            self.list_online.insert(tk.END, f"🟢 {row[0]}")

        # Tải Pending
        self.list_pending.delete(0, tk.END)
        cur.execute("SELECT username FROM users WHERE status = 0")
        for row in cur.fetchall():
            self.list_pending.insert(tk.END, row[0])

        # Tải Danh sách Thành viên (Tab 4)
        self.list_users.delete(0, tk.END)
        cur.execute("SELECT username FROM users WHERE status = 1")
        approved_users = cur.fetchall()
        
        # Cập nhật con số hiển thị
        self.lbl_total_members.config(text=f"Tổng số thành viên: {len(approved_users)}")
        
        # Đổ danh sách vào listbox
        for row in approved_users:
            self.list_users.insert(tk.END, row[0])

        conn.close()

    def approve_user(self):
        sel = self.list_pending.curselection()
        if not sel: return
        user = self.list_pending.get(sel[0])
        
        conn = self.get_db_connection()
        conn.execute("UPDATE users SET status = 1 WHERE username = ?", (user,))
        conn.commit()
        conn.close()
        messagebox.showinfo("Thành công", f"Đã duyệt tài khoản: {user}")
        self.load_data()

    def reject_user(self):
        sel = self.list_pending.curselection()
        if not sel: return
        user = self.list_pending.get(sel[0])
        
        conn = self.get_db_connection()
        conn.execute("DELETE FROM users WHERE username = ?", (user,))
        conn.commit()
        conn.close()
        self.load_data()

    def delete_user(self):
        sel = self.list_users.curselection()
        if not sel: return
        user = self.list_users.get(sel[0]) # Lấy chính xác tên username
        
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn xóa vĩnh viễn thành viên '{user}'?"):
            conn = self.get_db_connection()
            # Xóa tài khoản khỏi DB
            conn.execute("DELETE FROM users WHERE username = ?", (user,))
            conn.commit()
            conn.close()
            self.load_data()

if __name__ == "__main__":
    AdminConsole()