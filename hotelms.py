
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import csv
from datetime import datetime
import os

DB_FILE = "hotel.db"

# Try to import fpdf for PDF invoice creation; if not available we'll fallback to text invoice.
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except Exception:
    FPDF_AVAILABLE = False

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_no TEXT UNIQUE NOT NULL,
            room_type TEXT,
            rate REAL DEFAULT 0,
            notes TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guest_name TEXT NOT NULL,
            room_no TEXT NOT NULL,
            phone TEXT,
            check_in TEXT,
            check_out TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            nights INTEGER DEFAULT 0,
            total REAL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

class HotelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hotel Management System — Rooms & Invoices")
        self.root.geometry("1000x650")
        init_db()
        self.create_widgets()
        self.populate_room_tree()
        self.populate_booking_tree()
        self.update_room_dropdown()

    def run_query(self, query, params=(), commit=False):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(query, params)
        result = c.fetchall()
        if commit:
            conn.commit()
            conn.close()
            return None
        conn.close()
        return result

    def create_widgets(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # --- Bookings tab ---
        tab_book = ttk.Frame(nb)
        nb.add(tab_book, text="Bookings")

        # booking form
        frm = ttk.Frame(tab_book, padding=10)
        frm.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(frm, text="Guest Name").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
        self.entry_name = ttk.Entry(frm, width=30); self.entry_name.grid(row=0, column=1, padx=4, pady=4)

        ttk.Label(frm, text="Room No").grid(row=0, column=2, sticky=tk.W, padx=4, pady=4)
        self.room_var = tk.StringVar()
        self.combo_room = ttk.Combobox(frm, width=18, textvariable=self.room_var, state="readonly")
        self.combo_room.grid(row=0, column=3, padx=4, pady=4)

        ttk.Label(frm, text="Phone").grid(row=1, column=0, sticky=tk.W, padx=4, pady=4)
        self.entry_phone = ttk.Entry(frm, width=30); self.entry_phone.grid(row=1, column=1, padx=4, pady=4)

        ttk.Label(frm, text="Check-in (YYYY-MM-DD)").grid(row=1, column=2, sticky=tk.W, padx=4, pady=4)
        self.entry_checkin = ttk.Entry(frm, width=18); self.entry_checkin.grid(row=1, column=3, padx=4, pady=4)

        ttk.Label(frm, text="Check-out (YYYY-MM-DD)").grid(row=2, column=2, sticky=tk.W, padx=4, pady=4)
        self.entry_checkout = ttk.Entry(frm, width=18); self.entry_checkout.grid(row=2, column=3, padx=4, pady=4)

        btn_frame = ttk.Frame(frm); btn_frame.grid(row=3, column=0, columnspan=4, pady=8)
        ttk.Button(btn_frame, text="Add Booking", command=self.add_booking).grid(row=0, column=0, padx=6)
        ttk.Button(btn_frame, text="Update Selected", command=self.update_booking).grid(row=0, column=1, padx=6)
        ttk.Button(btn_frame, text="Check-out (Delete)", command=self.delete_booking).grid(row=0, column=2, padx=6)
        ttk.Button(btn_frame, text="Export CSV", command=self.export_csv).grid(row=0, column=3, padx=6)
        ttk.Button(btn_frame, text="Generate Invoice (selected)", command=self.generate_invoice).grid(row=0, column=4, padx=6)

        # search
        search_frame = ttk.LabelFrame(tab_book, text="Search", padding=8)
        search_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=6)
        ttk.Label(search_frame, text="Query (name or room)").pack(side=tk.LEFT, padx=6)
        self.search_var = tk.StringVar(); ttk.Entry(search_frame, textvariable=self.search_var, width=40).pack(side=tk.LEFT, padx=6)
        ttk.Button(search_frame, text="Search", command=self.search_bookings).pack(side=tk.LEFT, padx=6)
        ttk.Button(search_frame, text="Clear Search", command=self.populate_booking_tree).pack(side=tk.LEFT, padx=6)

        # bookings table
        tree_frame = ttk.Frame(tab_book); tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        columns = ("id", "guest_name", "room_no", "phone", "check_in", "check_out", "nights", "total", "created_at")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col, head, width in [
            ("id","ID",50), ("guest_name","Guest Name",200), ("room_no","Room No",100),
            ("phone","Phone",120), ("check_in","Check-in",100), ("check_out","Check-out",100),
            ("nights","Nights",70), ("total","Total",90), ("created_at","Created At",170)
        ]:
            self.tree.heading(col, text=head)
            self.tree.column(col, width=width, anchor=tk.CENTER if col!="guest_name" else tk.W)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1); tree_frame.grid_columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # availability checker
        avail_frame = ttk.LabelFrame(tab_book, text="Availability Checker", padding=8)
        avail_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=6)
        ttk.Label(avail_frame, text="From (YYYY-MM-DD)").grid(row=0, column=0, padx=6, pady=4)
        self.av_from = ttk.Entry(avail_frame, width=15); self.av_from.grid(row=0, column=1, padx=6)
        ttk.Label(avail_frame, text="To (YYYY-MM-DD)").grid(row=0, column=2, padx=6, pady=4)
        self.av_to = ttk.Entry(avail_frame, width=15); self.av_to.grid(row=0, column=3, padx=6)
        ttk.Button(avail_frame, text="Check Available Rooms", command=self.check_availability).grid(row=0, column=4, padx=8)
        self.av_result = tk.StringVar(); ttk.Label(avail_frame, textvariable=self.av_result).grid(row=1, column=0, columnspan=6, sticky=tk.W, padx=6)

        # --- Rooms tab ---
        tab_rooms = ttk.Frame(nb)
        nb.add(tab_rooms, text="Rooms")

        room_form = ttk.Frame(tab_rooms, padding=10); room_form.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(room_form, text="Room No").grid(row=0, column=0, padx=4, pady=4)
        self.r_room_no = ttk.Entry(room_form, width=15); self.r_room_no.grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(room_form, text="Type").grid(row=0, column=2, padx=4, pady=4)
        self.r_type = ttk.Entry(room_form, width=20); self.r_type.grid(row=0, column=3, padx=4, pady=4)
        ttk.Label(room_form, text="Rate (per night)").grid(row=1, column=0, padx=4, pady=4)
        self.r_rate = ttk.Entry(room_form, width=15); self.r_rate.grid(row=1, column=1, padx=4, pady=4)
        ttk.Label(room_form, text="Notes").grid(row=1, column=2, padx=4, pady=4)
        self.r_notes = ttk.Entry(room_form, width=30); self.r_notes.grid(row=1, column=3, padx=4, pady=4)

        room_btns = ttk.Frame(room_form); room_btns.grid(row=2, column=0, columnspan=4, pady=8)
        ttk.Button(room_btns, text="Add/Save Room", command=self.add_room).grid(row=0, column=0, padx=6)
        ttk.Button(room_btns, text="Update Selected Room", command=self.update_room).grid(row=0, column=1, padx=6)
        ttk.Button(room_btns, text="Delete Selected Room", command=self.delete_room).grid(row=0, column=2, padx=6)
        ttk.Button(room_btns, text="Refresh Rooms", command=self.populate_room_tree).grid(row=0, column=3, padx=6)

        # rooms table
        rframe = ttk.Frame(tab_rooms); rframe.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        rcols = ("id","room_no","room_type","rate","notes")
        self.room_tree = ttk.Treeview(rframe, columns=rcols, show="headings", selectmode="browse")
        for col, head, width in [
            ("id","ID",50), ("room_no","Room No",120), ("room_type","Type",180),
            ("rate","Rate",100), ("notes","Notes",300)
        ]:
            self.room_tree.heading(col, text=head); self.room_tree.column(col, width=width, anchor=tk.CENTER if col!="room_type" else tk.W)
        rvsb = ttk.Scrollbar(rframe, orient="vertical", command=self.room_tree.yview)
        rhsb = ttk.Scrollbar(rframe, orient="horizontal", command=self.room_tree.xview)
        self.room_tree.configure(yscroll=rvsb.set, xscroll=rhsb.set)
        self.room_tree.grid(row=0, column=0, sticky="nsew")
        rvsb.grid(row=0, column=1, sticky="ns"); rhsb.grid(row=1, column=0, sticky="ew")
        rframe.grid_rowconfigure(0, weight=1); rframe.grid_columnconfigure(0, weight=1)
        self.room_tree.bind("<<TreeviewSelect>>", self.on_room_select)

        # status bar
        self.status_var = tk.StringVar(); self.status_var.set("Ready")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X, side=tk.BOTTOM)

    # ---------- ROOM FUNCTIONS ----------
    def add_room(self):
        room_no = self.r_room_no.get().strip()
        room_type = self.r_type.get().strip()
        rate = self.r_rate.get().strip()
        notes = self.r_notes.get().strip()
        if not room_no:
            messagebox.showwarning("Validation", "Room number is required.")
            return
        try:
            rate_f = float(rate) if rate else 0.0
        except ValueError:
            messagebox.showwarning("Validation", "Rate must be a number.")
            return

        try:
            self.run_query("INSERT INTO rooms (room_no, room_type, rate, notes) VALUES (?, ?, ?, ?)", (room_no, room_type, rate_f, notes), commit=True)
            self.status_var.set(f"Added room {room_no}")
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate", "Room number already exists.")
            return
        self.clear_room_form()
        self.populate_room_tree()
        self.update_room_dropdown()

    def populate_room_tree(self):
        rows = self.run_query("SELECT id, room_no, room_type, rate, notes FROM rooms ORDER BY room_no")
        for r in self.room_tree.get_children():
            self.room_tree.delete(r)
        for row in rows:
            self.room_tree.insert("", tk.END, values=row)
        self.status_var.set(f"{len(rows)} rooms loaded")

    def on_room_select(self, event):
        sel = self.room_tree.selection()
        if not sel: return
        vals = self.room_tree.item(sel[0], "values")
        # populate form
        self.r_room_no.delete(0, tk.END); self.r_room_no.insert(0, vals[1])
        self.r_type.delete(0, tk.END); self.r_type.insert(0, vals[2])
        self.r_rate.delete(0, tk.END); self.r_rate.insert(0, vals[3])
        self.r_notes.delete(0, tk.END); self.r_notes.insert(0, vals[4])

    def update_room(self):
        sel = self.room_tree.selection()
        if not sel:
            messagebox.showinfo("Select room", "Please select a room to update.")
            return
        row = self.room_tree.item(sel[0], "values")
        room_id = row[0]
        room_no = self.r_room_no.get().strip()
        room_type = self.r_type.get().strip()
        rate = self.r_rate.get().strip()
        notes = self.r_notes.get().strip()
        try:
            rate_f = float(rate) if rate else 0.0
        except ValueError:
            messagebox.showwarning("Validation", "Rate must be a number.")
            return
        # update unique room_no might conflict - handle exception
        try:
            self.run_query("UPDATE rooms SET room_no=?, room_type=?, rate=?, notes=? WHERE id=?", (room_no, room_type, rate_f, notes, room_id), commit=True)
            self.status_var.set(f"Updated room {room_no}")
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate", "Room number conflicts with existing room.")
            return
        self.populate_room_tree()
        self.update_room_dropdown()

    def delete_room(self):
        sel = self.room_tree.selection()
        if not sel:
            messagebox.showinfo("Select room", "Please select a room to delete.")
            return
        row = self.room_tree.item(sel[0], "values")
        room_id, room_no = row[0], row[1]
        # check if bookings exist for that room
        linked = self.run_query("SELECT id FROM bookings WHERE room_no=?", (room_no,))
        if linked:
            if not messagebox.askyesno("Confirm delete", f"There are {len(linked)} bookings for room {room_no}. Delete anyway?"):
                return
        self.run_query("DELETE FROM rooms WHERE id=?", (room_id,), commit=True)
        self.status_var.set(f"Deleted room {room_no}")
        self.populate_room_tree()
        self.update_room_dropdown()

    def clear_room_form(self):
        self.r_room_no.delete(0, tk.END); self.r_type.delete(0, tk.END); self.r_rate.delete(0, tk.END); self.r_notes.delete(0, tk.END)

    def update_room_dropdown(self):
        rows = self.run_query("SELECT room_no FROM rooms ORDER BY room_no")
        room_list = [r[0] for r in rows]
        self.combo_room['values'] = room_list

    # ---------- BOOKING FUNCTIONS ----------
    def add_booking(self):
        name = self.entry_name.get().strip()
        room = self.room_var.get().strip()
        phone = self.entry_phone.get().strip()
        check_in = self.entry_checkin.get().strip()
        check_out = self.entry_checkout.get().strip()

        if not name or not room:
            messagebox.showwarning("Validation", "Guest name and room number are required.")
            return

        for d in (check_in, check_out):
            if d:
                try:
                    datetime.strptime(d, "%Y-%m-%d")
                except ValueError:
                    messagebox.showwarning("Validation", f"Date format should be YYYY-MM-DD: {d}")
                    return

        # compute nights if both dates present
        nights = 0
        if check_in and check_out:
            dt_in = datetime.strptime(check_in, "%Y-%m-%d")
            dt_out = datetime.strptime(check_out, "%Y-%m-%d")
            nights = (dt_out - dt_in).days
            if nights <= 0:
                messagebox.showwarning("Validation", "Check-out must be after check-in.")
                return

        # check room exists and rate
        r = self.run_query("SELECT rate FROM rooms WHERE room_no=?", (room,))
        rate = float(r[0][0]) if r else 0.0
        total = nights * rate

        # Check overlap bookings
        if check_in and check_out:
            overlapping = self.run_query(
                "SELECT id FROM bookings WHERE room_no = ? AND NOT (check_out <= ? OR check_in >= ?)",
                (room, check_in, check_out)
            )
            if overlapping:
                messagebox.showwarning("Room Occupied", "This room is occupied during the selected dates.")
                return

        self.run_query(
            "INSERT INTO bookings (guest_name, room_no, phone, check_in, check_out, nights, total) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, room, phone, check_in, check_out, nights, total),
            commit=True
        )
        self.status_var.set(f"Added booking for {name} in room {room}")
        self.clear_form()
        self.populate_booking_tree()

    def populate_booking_tree(self, rows=None):
        for r in self.tree.get_children(): self.tree.delete(r)
        if rows is None:
            rows = self.run_query("SELECT id, guest_name, room_no, phone, check_in, check_out, nights, total, created_at FROM bookings ORDER BY created_at DESC")
        for row in rows:
            self.tree.insert("", tk.END, values=row)
        self.status_var.set(f"{len(rows)} bookings loaded")

    def on_tree_select(self, event):
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0], "values")
            self.status_var.set(f"Selected booking ID {vals[0]}")

    def on_tree_double_click(self, event):
        sel = self.tree.selection()
        if not sel: return
        vals = self.tree.item(sel[0], "values")
        # populate fields
        self.entry_name.delete(0, tk.END); self.entry_name.insert(0, vals[1])
        self.room_var.set(vals[2])
        self.entry_phone.delete(0, tk.END); self.entry_phone.insert(0, vals[3])
        self.entry_checkin.delete(0, tk.END); self.entry_checkin.insert(0, vals[4] or "")
        self.entry_checkout.delete(0, tk.END); self.entry_checkout.insert(0, vals[5] or "")

    def get_selected_booking_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select booking", "Please select a booking in the table.")
            return None
        return self.tree.item(sel[0], "values")[0]

    def update_booking(self):
        booking_id = self.get_selected_booking_id()
        if not booking_id: return
        name = self.entry_name.get().strip()
        room = self.room_var.get().strip()
        phone = self.entry_phone.get().strip()
        check_in = self.entry_checkin.get().strip()
        check_out = self.entry_checkout.get().strip()
        if not name or not room:
            messagebox.showwarning("Validation", "Guest name and room number are required.")
            return
        for d in (check_in, check_out):
            if d:
                try:
                    datetime.strptime(d, "%Y-%m-%d")
                except ValueError:
                    messagebox.showwarning("Validation", f"Date format should be YYYY-MM-DD: {d}")
                    return
        nights = 0
        if check_in and check_out:
            dt_in = datetime.strptime(check_in, "%Y-%m-%d")
            dt_out = datetime.strptime(check_out, "%Y-%m-%d")
            nights = (dt_out - dt_in).days
            if nights <= 0:
                messagebox.showwarning("Validation", "Check-out must be after check-in.")
                return
        r = self.run_query("SELECT rate FROM rooms WHERE room_no=?", (room,))
        rate = float(r[0][0]) if r else 0.0
        total = nights * rate

        # avoid overlapping with other bookings (exclude this booking)
        if check_in and check_out:
            overlapping = self.run_query(
                "SELECT id FROM bookings WHERE room_no = ? AND id != ? AND NOT (check_out <= ? OR check_in >= ?)",
                (room, booking_id, check_in, check_out)
            )
            if overlapping:
                messagebox.showwarning("Room Occupied", "This room is occupied during the selected dates.")
                return

        self.run_query(
            "UPDATE bookings SET guest_name=?, room_no=?, phone=?, check_in=?, check_out=?, nights=?, total=? WHERE id=?",
            (name, room, phone, check_in, check_out, nights, total, booking_id),
            commit=True
        )
        self.status_var.set(f"Updated booking {booking_id}")
        self.clear_form()
        self.populate_booking_tree()

    def delete_booking(self):
        booking_id = self.get_selected_booking_id()
        if not booking_id: return
        if not messagebox.askyesno("Confirm", "Are you sure you want to check-out / delete this booking?"):
            return
        self.run_query("DELETE FROM bookings WHERE id=?", (booking_id,), commit=True)
        self.status_var.set(f"Deleted booking {booking_id}")
        self.populate_booking_tree()

    def search_bookings(self):
        q = self.search_var.get().strip()
        if not q:
            self.populate_booking_tree()
            return
        like = f"%{q}%"
        rows = self.run_query("SELECT id, guest_name, room_no, phone, check_in, check_out, nights, total, created_at FROM bookings WHERE guest_name LIKE ? OR room_no LIKE ? ORDER BY created_at DESC",(like,like))
        self.populate_booking_tree(rows)

    def clear_form(self):
        self.entry_name.delete(0, tk.END)
        self.room_var.set("")
        self.entry_phone.delete(0, tk.END)
        self.entry_checkin.delete(0, tk.END)
        self.entry_checkout.delete(0, tk.END)

    def export_csv(self):
        rows = self.run_query("SELECT id, guest_name, room_no, phone, check_in, check_out, nights, total, created_at FROM bookings ORDER BY created_at DESC")
        if not rows:
            messagebox.showinfo("Export CSV", "No bookings to export.")
            return
        fpath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files","*.csv")], title="Save bookings as...")
        if not fpath: return
        try:
            with open(fpath, mode="w", newline='', encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ID","Guest Name","Room No","Phone","Check-in","Check-out","Nights","Total","Created At"])
                for r in rows: writer.writerow(r)
            messagebox.showinfo("Export CSV", f"Bookings exported to {fpath}")
            self.status_var.set(f"Exported {len(rows)} bookings to CSV")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV: {e}")

    # ---------- AVAILABILITY ----------
    def check_availability(self):
        frm = self.av_from.get().strip()
        to = self.av_to.get().strip()
        for d in (frm, to):
            if d:
                try:
                    datetime.strptime(d, "%Y-%m-%d")
                except ValueError:
                    messagebox.showwarning("Validation", f"Date format should be YYYY-MM-DD: {d}")
                    return
        if not frm or not to:
            messagebox.showwarning("Validation", "Please enter both From and To dates.")
            return
        if datetime.strptime(to, "%Y-%m-%d") <= datetime.strptime(frm, "%Y-%m-%d"):
            messagebox.showwarning("Validation", "To date must be after From date.")
            return
        # get all rooms
        rooms = [r[0] for r in self.run_query("SELECT room_no FROM rooms")]
        free_rooms = []
        for room in rooms:
            overlapping = self.run_query("SELECT id FROM bookings WHERE room_no=? AND NOT (check_out <= ? OR check_in >= ?)", (room, frm, to))
            if not overlapping:
                free_rooms.append(room)
        if not rooms:
            self.av_result.set("No rooms configured yet.")
        elif free_rooms:
            self.av_result.set("Available rooms: " + ", ".join(free_rooms))
        else:
            self.av_result.set("No rooms are available in this date range.")
        self.status_var.set("Availability checked")

    # ---------- INVOICE ----------
    def get_selected_booking_row(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select booking", "Please select a booking to generate invoice.")
            return None
        vals = self.tree.item(sel[0], "values")
        return vals

    def generate_invoice(self):
        vals = self.get_selected_booking_row()
        if not vals: return
        # vals mapping: id, guest_name, room_no, phone, check_in, check_out, nights, total, created_at
        booking = {
            "id": vals[0],
            "guest_name": vals[1],
            "room_no": vals[2],
            "phone": vals[3],
            "check_in": vals[4] or "",
            "check_out": vals[5] or "",
            "nights": vals[6] or 0,
            "total": vals[7] or 0.0,
            "created_at": vals[8]
        }
        # get room rate & type
        r = self.run_query("SELECT room_type, rate FROM rooms WHERE room_no=?", (booking["room_no"],))
        room_type = r[0][0] if r else ""
        rate = float(r[0][1]) if r else 0.0

        # ask save path
        default_name = f"invoice_booking_{booking['id']}.pdf" if FPDF_AVAILABLE else f"invoice_booking_{booking['id']}.txt"
        fpath = filedialog.asksaveasfilename(defaultextension=os.path.splitext(default_name)[1], initialfile=default_name, title="Save Invoice As")
        if not fpath:
            return

        try:
            if FPDF_AVAILABLE and fpath.lower().endswith(".pdf"):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "Hotel Invoice", ln=True, align="C")
                pdf.ln(6)
                pdf.set_font("Arial", size=12)
                pdf.cell(40, 8, f"Invoice ID: {booking['id']}", ln=True)
                pdf.cell(40, 8, f"Guest: {booking['guest_name']}", ln=True)
                pdf.cell(40, 8, f"Phone: {booking['phone']}", ln=True)
                pdf.cell(40, 8, f"Room No: {booking['room_no']} ({room_type})", ln=True)
                pdf.cell(40, 8, f"Check-in: {booking['check_in']}", ln=True)
                pdf.cell(40, 8, f"Check-out: {booking['check_out']}", ln=True)
                pdf.cell(40, 8, f"Nights: {booking['nights']}", ln=True)
                pdf.cell(40, 8, f"Rate/night: {rate:.2f}", ln=True)
                pdf.ln(4)
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(40, 8, f"Total: {float(booking['total']):.2f}", ln=True)
                pdf.output(fpath)
            else:
                # text fallback
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("HOTEL INVOICE\n\n")
                    f.write(f"Invoice ID: {booking['id']}\n")
                    f.write(f"Guest: {booking['guest_name']}\n")
                    f.write(f"Phone: {booking['phone']}\n")
                    f.write(f"Room No: {booking['room_no']} ({room_type})\n")
                    f.write(f"Check-in: {booking['check_in']}\n")
                    f.write(f"Check-out: {booking['check_out']}\n")
                    f.write(f"Nights: {booking['nights']}\n")
                    f.write(f"Rate/night: {rate:.2f}\n")
                    f.write(f"\nTotal: {float(booking['total']):.2f}\n")
            messagebox.showinfo("Invoice", f"Invoice saved to {fpath}")
            self.status_var.set(f"Invoice generated for booking {booking['id']}")
        except Exception as e:
            messagebox.showerror("Invoice Error", f"Failed to create invoice: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = HotelApp(root)
    root.mainloop()
