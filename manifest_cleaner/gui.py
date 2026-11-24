"""Vietnamese desktop UI. All widget access stays on the Tk main thread."""
from __future__ import annotations

import copy
import json
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__
from .common import parse_weight, text_value
from .engine import CARRIERS, EDITABLE_FIELDS, FIELD_LABELS, ReviewSourceError, load_review, load_settings, process_manifest, validate_carrier_settings
from .exporter import export_port_bundle, preview_record_for_export

NAVY = "#13334C"
BG = "#F2F5F8"
TEXT = "#20364A"
MUTED = "#596D7C"
NUMBER_LABELS = {"legacy": "Theo quy tắc hãng", "decimal_comma": "Dấu phẩy thập phân", "decimal_dot": "Dấu chấm thập phân"}
WEIGHT_LABELS = {"unknown": "Chưa xác nhận ý nghĩa", "gross": "Tổng trọng lượng (gross)", "cargo": "Trọng lượng hàng"}
SOURCE_REASON_LABELS = {
    "table_header": "Tiêu đề bảng", "identical_table_header": "Tiêu đề lặp lại, giữ cùng cấu trúc và đơn vị",
    "header_schema_or_unit_changed": "Tiêu đề thay đổi cột hoặc đơn vị", "after_changed_header": "Chưa đọc tiếp sau tiêu đề thay đổi",
    "known_total_footer": "Dòng tổng cộng", "party_or_bill_context": "Thông tin người gửi, người nhận hoặc B/L",
    "non_container_note": "Ghi chú không phải dòng container", "container_record": "Dòng container đã đọc",
    "missing_or_invalid_container": "Thiếu mã container hoặc mã cần kiểm tra",
    "weight_first_tons": "Trọng lượng đứng trước mô tả, đơn vị tấn", "description_first_kg": "Trọng lượng đứng sau mô tả, đơn vị kg",
    "ambiguous": "Có nhiều cách đọc trọng lượng và mô tả", "unparsed": "Chưa đọc đủ cấu trúc dòng",
    "marks_empty": "Container rỗng trong cột MARKS", "marks_incomplete": "Cột MARKS chưa đủ thông tin container",
    "explicit_empty_detail": "Dòng ghi rõ container rỗng",
    "container_record_requires_review": "Dòng container còn thiếu dữ liệu khi đọc nguồn",
    "description_metadata_port": "Dòng địa điểm/cảng, không gán thành tên hàng",
    "description_metadata_total": "Dòng tổng trong mô tả, không gán thành tên hàng",
    "description_metadata_attachment": "Dòng dẫn tới danh sách đính kèm, không gán thành tên hàng",
    "description_metadata_quantity": "Thông tin số lượng/kích cỡ được dùng để đối chiếu",
}


def _source_field(record, field):
    """Human-readable source evidence; never replace missing evidence with output."""
    raw = record.get("raw") or {}
    names = {
        "BL_No": ("BL_No", "bill_no"), "Container_No": ("container_no", "container_line", "container_cell"),
        "Seal_No": ("seal", "seal_no", "container_line"), "Size_Type": ("size_type", "Size_Type", "type"),
        "Weight_Value": ("weight", "gw", "weight_line", "weight_cell_value", "weight_cell"),
        "Description": ("description", "comm", "matched_description", "description_cell"),
        "Cleaned_Consignee_Name_For_Output": ("consignee",),
    }
    if field == "BL_No" and raw.get("bl_evidence"):
        return " | ".join(f"{item.get('position', '')}: {item.get('value', '')}" for item in raw["bl_evidence"] if item.get("value"))
    if field == "Cleaned_Consignee_Name_For_Output":
        party = raw.get("party_values") or {}
        return text_value(raw.get("consignee") or party.get("Consignee") or record.get("Consignee")) or "Xem khối người nhận trong nguồn"
    if field == "FE_Status":
        evidence = [f"Tiêu đề: {raw['context_status']}"] if raw.get("context_status") else []
        if raw.get("row_status"):
            evidence.append(f"Dòng: {raw['row_status']}")
        return " | ".join(evidence) or text_value(raw.get("comm") or raw.get("matched_description") or raw.get("description")) or "Xem mô tả và quy tắc suy luận"
    if field == "Operator":
        return "SOC" if raw.get("is_soc") is True else "Xem dấu SOC/COC trong nguồn"
    for name in names.get(field, ()):
        if raw.get(name) is not None and text_value(raw[name]) != "":
            value = text_value(raw[name])
            if field == "Weight_Value" and raw.get("weight_source_unit"):
                value += " " + text_value(raw["weight_source_unit"])
            return value
    return "—"


def _runtime_description(session):
    settings = session.metadata.get("effective_settings") or session.settings
    metadata = session.metadata
    sheets = metadata.get("selected_sheet") or metadata.get("source_sheet") or metadata.get("sheets_used") or "Chưa xác định"
    if isinstance(sheets, (list, tuple)):
        sheets = ", ".join(str(x) for x in sheets)
    profile = metadata.get("profile_version") or metadata.get("profile") or metadata.get("adapter") or session.carrier
    if isinstance(profile, dict):
        profile = profile.get("name") or profile.get("version") or session.carrier
    number = NUMBER_LABELS.get(settings.get("number_format", "legacy"), settings.get("number_format"))
    weight = WEIGHT_LABELS.get(settings.get("weight_kind", metadata.get("weight_kind", "unknown")), "Chưa xác nhận ý nghĩa")
    return f"Đang dùng: {number}  |  Trọng lượng: {weight}  |  Sheet: {sheets}  |  Bộ quy tắc: {profile}"


class ManifestApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Manifest Cleaner {__version__} — Nhập hệ thống Cảng")
        self.root.geometry("1240x800")
        self.root.minsize(1020, 650)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.session = None
        self.busy = False
        self.events = queue.Queue()
        self.dirty = False
        self.selected_path = None
        self.sort_field = None
        self.sort_reverse = False
        self.carrier = tk.StringVar(value="VOSCO")
        self.search = tk.StringVar()
        self.only_issues = tk.BooleanVar(value=False)
        self.show_excluded = tk.BooleanVar(value=False)
        self.include_review = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Chọn hãng tàu và mở một file manifest để bắt đầu.")
        self.file_label = tk.StringVar(value="Chưa chọn manifest")
        self.summary = tk.StringVar(value="Mỗi lần xử lý một manifest của một hãng tàu.")
        self.configuration = tk.StringVar(value="Quy ước số, ý nghĩa trọng lượng và sheet sẽ hiện tại đây sau khi mở manifest.")
        self.config_path = (Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]) / "settings.json"
        try:
            self.settings = load_settings(self.config_path if self.config_path.is_file() else None)
        except Exception as exc:
            self.settings = load_settings()
            messagebox.showwarning("Cấu hình", f"Không đọc được cấu hình: {exc}\nĐang dùng quy tắc mặc định từ các repo.", parent=root)
        self._style()
        self._build()
        self.search.trace_add("write", lambda *_: self.refresh())
        self.root.bind("<Control-o>", lambda _: self.choose_file())
        self.root.bind("<Control-s>", lambda _: self.export())
        self.root.bind("<F1>", lambda _: self.help())
        self.root.after(100, self._poll)

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Issue.TLabel", foreground="#A52B25", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("Primary.TButton", background=NAVY, foreground="white", borderwidth=0)
        style.map("Primary.TButton", background=[("active", "#245675"), ("disabled", "#BAC6D0")], foreground=[("disabled", "#EEF2F5")])
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=30, background="white", fieldbackground="white", foreground=TEXT)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=(8, 10))
        style.map("Treeview", background=[("selected", "#245675")], foreground=[("selected", "white")])
        style.configure("TNotebook.Tab", font=("Segoe UI", 10), padding=(18, 9))
        style.configure("TCheckbutton", background=BG, foreground=TEXT, font=("Segoe UI", 10))

    def _build(self):
        header = tk.Frame(self.root, bg=NAVY)
        header.pack(fill="x")
        tk.Label(header, text="MANIFEST CLEANER", font=("Segoe UI", 22, "bold"), fg="white", bg=NAVY).pack(anchor="w", padx=24, pady=(17, 2))
        tk.Label(header, text="VOSCO  ·  VIMC  ·  VINAFCO     |     Chuẩn hóa dữ liệu để nhập hệ thống Cảng", font=("Segoe UI", 11), fg="#D6E5EF", bg=NAVY).pack(anchor="w", padx=25, pady=(0, 18))
        toolbar = ttk.Frame(self.root, padding=(20, 16))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Hãng tàu", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 10))
        self.carrier_box = ttk.Combobox(toolbar, textvariable=self.carrier, values=CARRIERS, state="readonly", width=14, font=("Segoe UI", 11))
        self.carrier_box.pack(side="left")
        self.carrier_box.bind("<<ComboboxSelected>>", self.carrier_changed)
        self.open_button = ttk.Button(toolbar, text="Mở manifest…", style="Primary.TButton", command=self.choose_file)
        self.open_button.pack(side="left", padx=12)
        self.resume_button = ttk.Button(toolbar, text="Mở phiên đã lưu…", command=self.choose_review)
        self.resume_button.pack(side="left", padx=(0, 8))
        self.reload_button = ttk.Button(toolbar, text="Xử lý lại", command=self.reprocess, state="disabled")
        self.reload_button.pack(side="left")
        ttk.Button(toolbar, text="Cấu hình đọc…", command=self.number_settings).pack(side="right", padx=(8, 0))
        ttk.Button(toolbar, text="Hướng dẫn", command=self.help).pack(side="right")
        info = ttk.Frame(self.root, padding=(22, 0, 22, 12))
        info.pack(fill="x")
        ttk.Label(info, textvariable=self.file_label, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(info, textvariable=self.summary, style="Muted.TLabel", wraplength=950).pack(anchor="w", pady=(5, 0))
        ttk.Label(info, textvariable=self.configuration, style="Muted.TLabel", wraplength=950).pack(anchor="w", pady=(5, 0))
        filters = ttk.Frame(self.root, padding=(20, 5, 20, 10))
        filters.pack(fill="x")
        ttk.Label(filters, text="Tìm container / B/L / hàng hóa:").pack(side="left", padx=(0, 8))
        ttk.Entry(filters, textvariable=self.search, width=31, font=("Segoe UI", 10)).pack(side="left")
        ttk.Checkbutton(filters, text="Chỉ mục cần kiểm tra", variable=self.only_issues, command=self.refresh).pack(side="left", padx=16)
        ttk.Checkbutton(filters, text="Hiện dòng đã loại", variable=self.show_excluded, command=self.refresh).pack(side="left")
        ttk.Button(filters, text="Tra nguồn…", command=self.show_source_coverage).pack(side="right")
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        data_tab = ttk.Frame(self.tabs)
        issues_tab = ttk.Frame(self.tabs)
        self.tabs.add(data_tab, text="Container")
        self.tabs.add(issues_tab, text="Cần kiểm tra")
        self.tabs.bind("<<NotebookTabChanged>>", self._update_row_actions)
        fields = ("status", "Container_No", "BL_No", "VTOS_Size", "Operator", "FE_Status", "Weight_Value", "Cleaned_Consignee_Name_For_Output", "Description")
        self.tree = ttk.Treeview(data_tab, columns=fields, show="headings", selectmode="browse")
        widths = {"status": 115, "Container_No": 140, "BL_No": 155, "VTOS_Size": 105, "Operator": 95,
                  "FE_Status": 55, "Weight_Value": 125, "Cleaned_Consignee_Name_For_Output": 220, "Description": 300}
        for name in fields:
            label = "Trạng thái" if name == "status" else FIELD_LABELS.get(name, name)
            self.tree.heading(name, text=label, command=lambda key=name: self.sort_by(key))
            self.tree.column(name, width=widths[name], minwidth=45, stretch=False)
        self._scrollbars(data_tab, self.tree)
        self.tree.tag_configure("error", background="#FDE9E7")
        self.tree.tag_configure("warning", background="#FFF6DD")
        self.tree.tag_configure("excluded", foreground="#87939C", background="#EDF0F3")
        self.tree.bind("<Double-1>", lambda _: self.edit_selected())
        self.tree.bind("<<TreeviewSelect>>", self._update_row_actions)
        issue_fields = ("severity", "container", "field", "message", "source")
        self.issue_tree = ttk.Treeview(issues_tab, columns=issue_fields, show="headings", selectmode="browse")
        for name, label, width in [("severity", "Mức", 100), ("container", "Container", 140), ("field", "Thông tin", 140),
                                  ("message", "Nội dung cần kiểm tra", 650), ("source", "Nguồn", 160)]:
            self.issue_tree.heading(name, text=label)
            self.issue_tree.column(name, width=width, minwidth=70, stretch=name == "message")
        self._scrollbars(issues_tab, self.issue_tree)
        self.issue_tree.bind("<Double-1>", self.open_issue)
        self.issue_tree.bind("<<TreeviewSelect>>", self._update_row_actions)
        self.issue_tree.tag_configure("error", background="#FDE9E7")
        self.issue_tree.tag_configure("warning", background="#FFF6DD")
        self.issue_records = {}
        self.issue_keys = {}
        actionbar = ttk.Frame(self.root, padding=(20, 0, 20, 10))
        actionbar.pack(fill="x")
        self.edit_button = ttk.Button(actionbar, text="Xem / sửa dòng", command=self.edit_selected, state="disabled")
        self.edit_button.pack(side="left")
        self.ack_button = ttk.Button(actionbar, text="Đã đối chiếu…", command=self.acknowledge, state="disabled")
        self.ack_button.pack(side="left", padx=8)
        self.exclude_button = ttk.Button(actionbar, text="Loại / khôi phục dòng…", command=self.exclude, state="disabled")
        self.exclude_button.pack(side="left")
        self.review_button = ttk.Button(actionbar, text="Lưu đối chiếu…", command=self.save_review, state="disabled")
        self.review_button.pack(side="right", padx=(8, 0))
        self.export_button = ttk.Button(actionbar, text="Xuất file nhập Cảng…", style="Primary.TButton", command=self.export, state="disabled")
        self.export_button.pack(side="right")
        footer = ttk.Frame(self.root, padding=(22, 5, 22, 16))
        footer.pack(fill="x")
        ttk.Checkbutton(footer, text="Xuất kèm đối chiếu JSON để mở lại phiên", variable=self.include_review).pack(anchor="w", pady=(0, 8))
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=125)
        self.progress.pack(side="right")
        ttk.Label(footer, textvariable=self.status, style="Muted.TLabel", wraplength=850).pack(side="left")

    @staticmethod
    def _scrollbars(parent, tree):
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky="nsew")
        y = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        y.grid(row=0, column=1, sticky="ns")
        x = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        x.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)

    def carrier_changed(self, _=None):
        if self.session and self.carrier.get() != self.session.carrier:
            self.export_button.configure(state="disabled")
            self.status.set("Hãng đã đổi. Bấm Xử lý lại hoặc mở manifest mới để dùng quy tắc của hãng vừa chọn.")
        elif self.session:
            self.refresh()

    def _confirm_discard(self):
        return not self.dirty or messagebox.askyesno("Chỉnh sửa chưa lưu", "Phiên hiện tại có chỉnh sửa chưa lưu đối chiếu. Tiếp tục rời phiên này và bỏ các chỉnh sửa chưa lưu?", parent=self.root)

    def choose_file(self):
        if self.busy or not self._confirm_discard():
            return
        path = filedialog.askopenfilename(title="Chọn một manifest", filetypes=[("Excel manifest", "*.xlsx *.xls *.xlsm"), ("Tất cả", "*.*")], parent=self.root)
        if path:
            self._start(Path(path))

    def choose_review(self):
        """Resume saved edits only after the original workbook hash is verified."""
        if self.busy or not self._confirm_discard():
            return
        path = filedialog.askopenfilename(title="Mở phiên đối chiếu đã lưu", filetypes=[("Đối chiếu JSON", "*.json")], parent=self.root)
        if not path:
            return
        try:
            try:
                session = load_review(path)
            except ReviewSourceError as exc:
                prompt = (f"{exc}\n\nBạn muốn chọn lại đúng file manifest gốc? "
                          "Chỉ mở phiên khi nội dung file trùng với nguồn đã lưu; các chỉnh sửa không bị xử lý lại.")
                if not messagebox.askyesno("Tìm lại manifest gốc", prompt, parent=self.root):
                    return
                source = filedialog.askopenfilename(title="Chọn đúng manifest gốc của phiên", filetypes=[("Excel manifest", "*.xlsx *.xls *.xlsm")], parent=self.root)
                if not source:
                    return
                session = load_review(path, source_path=source)
        except Exception as exc:
            messagebox.showerror("Không mở được phiên", str(exc), parent=self.root)
            return
        self.session = session
        self.selected_path = Path(session.metadata["source_path"])
        self.carrier.set(session.carrier)
        self.settings[session.carrier] = copy.deepcopy(session.settings)
        self.dirty = False
        self.search.set("")
        self.only_issues.set(False)
        self.file_label.set(f"{self.selected_path.name}  |  Đã mở phiên: {Path(path).name}")
        self.reload_button.configure(state="normal")
        self.refresh()
        self.status.set("Đã khôi phục chỉnh sửa, xác nhận và dòng đã loại. Đang dùng cấu hình lưu trong phiên; chưa ghi đè settings.json.")

    def reprocess(self):
        if self.selected_path and not self.busy and self._confirm_discard():
            self._start(self.selected_path)

    def _start(self, path: Path):
        self.busy = True
        self.session = None
        self.dirty = False
        self.selected_path = path
        self.file_label.set(path.name)
        self.summary.set("Đang đọc dữ liệu và áp dụng quy tắc hãng tàu…")
        self.configuration.set("Đang xác định cấu hình hiệu lực và các sheet trong file…")
        self.status.set("Đang xử lý. Cửa sổ vẫn có thể di chuyển và xem trạng thái.")
        self.tree.delete(*self.tree.get_children())
        self.issue_tree.delete(*self.issue_tree.get_children())
        self.open_button.configure(state="disabled")
        self.resume_button.configure(state="disabled")
        self.reload_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.review_button.configure(state="disabled")
        self.carrier_box.configure(state="disabled")
        self._update_row_actions()
        self.progress.start(15)
        carrier = self.carrier.get()
        settings = dict(self.settings[carrier])
        def work():
            try:
                result = process_manifest(path, carrier, settings=settings,
                                          progress=lambda *args: self.events.put(("progress", args)))
                self.events.put(("done", result))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    messages = [x for x in value if isinstance(x, str)]
                    if messages:
                        self.status.set(messages[-1])
                else:
                    self.busy = False
                    self.progress.stop()
                    self.progress["value"] = 0
                    self.open_button.configure(state="normal")
                    self.resume_button.configure(state="normal")
                    self.reload_button.configure(state="normal")
                    self.carrier_box.configure(state="readonly")
                    if kind == "done":
                        self.session = value
                        self.refresh()
                    else:
                        self.summary.set("Chưa xử lý được manifest. File gốc được giữ nguyên.")
                        self.status.set(value)
                        messagebox.showerror("Không xử lý được manifest", value, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def refresh(self):
        if not self.session:
            return
        session = self.session
        issues = session.validate()
        stats = session.statistics()
        by_id = {r["record_id"]: r for r in session.records}
        error_containers = {text_value(by_id.get(str(i.get("record_id")), {}).get("Container_No")) or str(i.get("record_id"))
                            for i in issues if i.get("severity") == "error" and i.get("record_id") is not None}
        file_errors = sum(i.get("severity") == "error" and i.get("record_id") is None for i in issues)
        error_summary = f"{stats['errors'] - file_errors} lỗi dòng trên {len(error_containers)} container"
        if file_errors:
            error_summary += f" + {file_errors} lỗi toàn file"
        self.summary.set(f"{session.carrier}  |  {stats['bills']} B/L · {stats['containers']} container / {stats['active_records']} dòng  |  F: {stats['full']} · E: {stats['empty']} · Chưa rõ: {stats['unknown']}  |  {error_summary} · {stats['warnings']} cảnh báo · {stats['excluded']} dòng đã loại")
        self.configuration.set(_runtime_description(session))
        self.tabs.tab(1, text=f"Cần kiểm tra ({len(issues)})")
        current = self.tree.selection()
        selected_issue = self.issue_tree.selection()
        prior_issue_key = self.issue_keys.get(selected_issue[0]) if selected_issue else None
        self.tree.delete(*self.tree.get_children())
        self.issue_tree.delete(*self.issue_tree.get_children())
        per_record = {}
        for item in issues:
            per_record.setdefault(str(item.get("record_id")), []).append(item)
        rows = list(session.records)
        if self.sort_field and self.sort_field != "status":
            key = self.sort_field
            def sort_value(record):
                if key != "Weight_Value":
                    return text_value(record.get(key)).casefold()
                try:
                    return float(record.get(key) or 0)
                except (TypeError, ValueError):
                    return float("inf")
            rows.sort(key=sort_value, reverse=self.sort_reverse)
        query = self.search.get().casefold().strip()
        for record in rows:
            rid = record["record_id"]
            row_issues = per_record.get(rid, [])
            excluded = record.get("_excluded", False)
            if excluded and not self.show_excluded.get():
                continue
            if self.only_issues.get() and not row_issues:
                continue
            if query and query not in " ".join(text_value(v) for k, v in record.items() if k not in {"raw", "rules"}).casefold():
                continue
            error = any(i.get("severity") == "error" for i in row_issues)
            label = "Đã loại" if excluded else "Cần sửa" if error else "Cần kiểm tra" if row_issues else "Đã đối chiếu" if record.get("_manual_review_reason") else "Đủ dữ liệu"
            tag = "excluded" if excluded else "error" if error else "warning" if row_issues else ""
            weight = record.get("Weight_Value")
            values = (label, record.get("Container_No", ""), record.get("BL_No", ""), record.get("VTOS_Size", ""),
                      record.get("Operator", ""), record.get("FE_Status", ""), text_value(weight),
                      record.get("Cleaned_Consignee_Name_For_Output", ""), record.get("Description", ""))
            self.tree.insert("", "end", iid=rid, values=values, tags=(tag,))
        if current and self.tree.exists(current[0]):
            self.tree.selection_set(current[0])
        self.issue_records = {}
        self.issue_keys = {}
        records_by_id = {r["record_id"]: r for r in session.records}
        for index, item in enumerate(issues):
            rid = item.get("record_id")
            record = records_by_id.get(str(rid), {}) if rid else {}
            source = f"{item.get('source_sheet') or record.get('source_sheet') or ''}:{item.get('source_row') or record.get('source_row') or ''}"
            iid = f"issue-{index}"
            self.issue_records[iid] = str(rid) if rid else None
            self.issue_keys[iid] = (str(rid), item.get("code"), item.get("message"))
            self.issue_tree.insert("", "end", iid=iid, values=("Lỗi" if item.get("severity") == "error" else "Cảnh báo" if item.get("severity") == "warning" else "Thông tin",
                                  record.get("Container_No", "Toàn file"), FIELD_LABELS.get(item.get("field"), item.get("field") or ""), item.get("message", ""), source), tags=(item.get("severity", ""),))
            if self.issue_keys[iid] == prior_issue_key:
                self.issue_tree.selection_set(iid)
        can_export = (stats["errors"] == 0 and session.carrier == self.carrier.get() and not self.busy
                      and not session.metadata.get("settings_changed") and session.settings == self.settings[self.carrier.get()])
        self.export_button.configure(state="normal" if can_export else "disabled")
        self.review_button.configure(state="normal")
        self._update_row_actions()
        self.status.set(f"Đã đọc {stats['detected_records']} bản ghi; đang giữ {stats['active_records']}. " +
                        ("Xử lý các lỗi trong mục Cần kiểm tra trước khi xuất." if stats["errors"] else "Sẵn sàng xuất. Có thể mở từng dòng để đối chiếu nguồn."))

    def sort_by(self, field):
        self.sort_reverse = not self.sort_reverse if self.sort_field == field else False
        self.sort_field = field
        self.refresh()

    def selected_record_id(self, *, notify=True):
        rid = None
        if self.session and not self.busy:
            if self.tabs.index(self.tabs.select()) == 1:
                selected = self.issue_tree.selection()
                rid = self.issue_records.get(selected[0]) if selected else None
            else:
                selected = self.tree.selection()
                rid = selected[0] if selected else None
        if rid and not any(r["record_id"] == rid for r in self.session.records):
            rid = None
        if not rid and notify:
            messagebox.showinfo("Chọn dòng", "Chọn một container hoặc một lỗi của container trong tab đang mở. Lỗi toàn file không áp dụng thao tác theo dòng.", parent=self.root)
        return rid

    def _update_row_actions(self, _=None):
        if not hasattr(self, "exclude_button"):
            return
        state = "normal" if self.selected_record_id(notify=False) else "disabled"
        for button in (self.edit_button, self.ack_button, self.exclude_button):
            button.configure(state=state)

    def _record_context(self, rid):
        record = self.session.get_record(rid)
        return f"Container: {record.get('Container_No') or '(chưa có số)'}\nB/L: {record.get('BL_No') or '(chưa có số)'}"

    def show_source_coverage(self):
        if not self.session or self.busy:
            return
        fragments = self.session.metadata.get("source_fragments") or []
        dialog = tk.Toplevel(self.root)
        dialog.title("Tra cứu các đoạn nguồn đã được ghi nhận")
        dialog.geometry("1050x650")
        dialog.minsize(840, 520)
        dialog.transient(self.root)
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Đây là tình trạng tại lần đọc nguồn, không phải số lỗi còn lại sau chỉnh sửa. Tab Cần kiểm tra phản ánh lỗi hiện tại.", wraplength=970, style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
        if not fragments:
            ttk.Label(body, text="Bộ đọc của phiên này chưa ghi danh sách đoạn nguồn. Vị trí và dữ liệu gốc của từng container vẫn có trong cửa sổ sửa.", wraplength=970).pack(anchor="w")
            return
        labels = {"parsed": "Đã nhận diện", "unresolved": "Cần đối chiếu lúc đọc", "ignored": "Bỏ qua có lý do", "corroborating": "Bằng chứng đối chiếu"}
        counts = {key: sum(isinstance(item, dict) and item.get("status") == key for item in fragments) for key in labels}
        ttk.Label(body, text="  ·  ".join(f"{label}: {counts[key]}" for key, label in labels.items()), wraplength=970).pack(anchor="w", pady=(0, 10))
        table_frame = ttk.Frame(body)
        table_frame.pack(fill="both", expand=True)
        table = ttk.Treeview(table_frame, columns=("source", "status", "reason", "text"), show="headings", selectmode="browse")
        for name, label, width in (("source", "Vị trí nguồn", 140), ("status", "Tình trạng lúc đọc", 175), ("reason", "Lý do", 220), ("text", "Nguyên văn", 500)):
            table.heading(name, text=label)
            table.column(name, width=width, minwidth=80, stretch=False)
        self._scrollbars(table_frame, table)
        table.tag_configure("unresolved", background="#FFF6DD")
        detail = tk.Text(body, height=6, wrap="word", font=("Segoe UI", 10), bg="white", relief="flat", padx=8, pady=8)
        detail.pack(fill="x", pady=(10, 0))
        detail.insert("1.0", "Chọn một đoạn nguồn để xem đầy đủ nội dung.")
        detail.configure(state="disabled")
        indexed = {}
        for index, item in enumerate(fragments):
            if not isinstance(item, dict):
                continue
            position = f"{item.get('source_sheet', '')}:{item.get('source_row', '')}"
            if item.get("source_column"):
                position += f" · cột {item['source_column']}"
            iid = f"source-{index}"
            indexed[iid] = item
            reason = SOURCE_REASON_LABELS.get(item.get("reason"), item.get("reason", ""))
            table.insert("", "end", iid=iid, values=(position, labels.get(item.get("status"), item.get("status", "")), reason, item.get("text", "")), tags=(item.get("status", ""),))
        def show_fragment(_=None):
            selected = table.selection()
            if not selected:
                return
            item = indexed[selected[0]]
            detail.configure(state="normal")
            detail.delete("1.0", "end")
            reason = SOURCE_REASON_LABELS.get(item.get("reason"), item.get("reason", ""))
            detail.insert("1.0", f"Nguồn: {item.get('source_sheet', '')}, dòng {item.get('source_row', '')}\nLý do: {reason}\n\n{item.get('text', '')}")
            detail.configure(state="disabled")
        table.bind("<<TreeviewSelect>>", show_fragment)

    def open_issue(self, _=None):
        selected = self.issue_tree.selection()
        if selected:
            rid = self.issue_records.get(selected[0])
            if rid:
                self.edit_record(rid)
            else:
                messagebox.showinfo("Thông tin toàn file", self.issue_tree.item(selected[0], "values")[3], parent=self.root)

    def edit_selected(self):
        rid = self.selected_record_id()
        if rid:
            self.edit_record(rid)

    def edit_record(self, rid):
        record = self.session.get_record(rid)
        original = {name: text_value(record.get(name)) for name in EDITABLE_FIELDS}
        record_issues = [item for item in self.session.validate() if item.get("record_id") == rid]
        affected = {field for item in record_issues for field in (item.get("resolution_fields") or [item.get("field")]) if field}
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Đối chiếu container — {record.get('Container_No') or 'chưa có số'}")
        dialog.geometry("1000x760")
        dialog.minsize(880, 670)
        dialog.transient(self.root)
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"B/L: {record.get('BL_No') or '(chưa có số)'}  |  Nguồn: {Path(record.get('source_file') or '').name}  |  Sheet {record.get('source_sheet','')} · dòng {record.get('source_row','')}", font=("Segoe UI", 10, "bold"), wraplength=940).pack(anchor="w", pady=(0, 10))
        notebook = ttk.Notebook(body)
        notebook.pack(fill="both", expand=True, pady=(0, 8))
        edit_tab = ttk.Frame(notebook, padding=10)
        source_tab = ttk.Frame(notebook, padding=10)
        notebook.add(edit_tab, text="Chỉnh sửa / xác nhận")
        notebook.add(source_tab, text="Nguồn và giá trị sẽ xuất")
        if record_issues:
            issue_text = tk.Text(edit_tab, height=3, wrap="word", font=("Segoe UI", 10), bg="#FFF5E7", relief="flat", padx=8, pady=6)
            issue_text.pack(fill="x", pady=(0, 8))
            issue_text.insert("1.0", "\n".join(("LỖI: " if i.get("severity") == "error" else "Lưu ý: ") + i.get("message", "") for i in record_issues))
            issue_text.configure(state="disabled")
        ttk.Label(edit_tab, text="Chỉ trường đã sửa hoặc được tích xác nhận mới được ghi nhận là đã đối chiếu. Dấu * chỉ trường liên quan lỗi/cảnh báo.", wraplength=900, style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        form = ttk.Frame(edit_tab)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        variables = {}
        verified = {}
        for index, name in enumerate(EDITABLE_FIELDS):
            label = FIELD_LABELS[name] + (" *" if name in affected else "")
            ttk.Label(form, text=label, style="Issue.TLabel" if name in affected else "TLabel").grid(row=index, column=0, sticky="w", padx=(0, 10), pady=4)
            variable = tk.StringVar(value=original[name])
            variables[name] = variable
            if name == "FE_Status":
                widget = ttk.Combobox(form, textvariable=variable, values=("F", "E", ""), state="readonly", width=38)
            else:
                widget = ttk.Entry(form, textvariable=variable, width=38)
            widget.grid(row=index, column=1, sticky="ew", padx=(0, 14), pady=4)
            verified[name] = tk.BooleanVar(value=False)
            ttk.Checkbutton(form, text="Đã đối chiếu trường này", variable=verified[name]).grid(row=index, column=2, sticky="w", pady=4)
        ttk.Label(edit_tab, text="Nhập trọng lượng bằng TẤN; dùng dấu phẩy hoặc dấu chấm thập phân. F = có hàng, E = rỗng.", style="Muted.TLabel", wraplength=900).pack(anchor="w", pady=(8, 4))

        candidates = record.get("raw", {}).get("ambiguous_candidates", [])
        if candidates:
            picker = ttk.Frame(edit_tab)
            picker.pack(fill="x", pady=(8, 0))
            descriptions = []
            for index, candidate in enumerate(candidates, 1):
                descriptions.append(f"{index}. {candidate.get('weight_raw', '')} {candidate.get('source_unit', '')}; hàng: {candidate.get('description', '')}")
            choice = tk.StringVar(value="")
            ttk.Label(picker, text="Cách đọc đã đối chiếu từ nguồn:").pack(anchor="w")
            ttk.Combobox(picker, textvariable=choice, values=descriptions, state="readonly").pack(side="left", fill="x", expand=True, pady=(5, 0))
            def use_candidate():
                if choice.get() not in descriptions:
                    messagebox.showinfo("Chọn cách đọc", "Đối chiếu dòng gốc rồi chọn một cách đọc. Ứng dụng không tự chọn thay bạn.", parent=dialog)
                    return
                candidate = candidates[descriptions.index(choice.get())]
                weight = parse_weight(candidate.get("weight_raw"), default_unit=candidate.get("source_unit") or "TONS", number_format=self.session.settings.get("number_format", "legacy"))
                if weight is None:
                    messagebox.showerror("Chưa đọc được số", "Cách đọc này không phù hợp quy ước số hiện tại. Kiểm tra nguồn và cấu hình đọc.", parent=dialog)
                    return
                variables["Weight_Value"].set(text_value(weight["value"]))
                variables["Description"].set(candidate.get("description", ""))
                verified["Weight_Value"].set(True)
                verified["Description"].set(True)
                update_preview()
            ttk.Button(picker, text="Điền và xác nhận 2 trường", command=use_candidate).pack(side="right", padx=(8, 0), pady=(5, 0))

        ttk.Label(source_tab, text="Xem trước đúng giá trị ghi vào mẫu 16 cột của hãng. Các lỗi chưa xử lý vẫn chặn xuất file.", wraplength=900, style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        source_raw = record.get("raw", {})
        original_text = source_raw.get("source_cell") or source_raw.get("container_cell") or source_raw.get("text")
        if original_text:
            source_text = tk.Text(source_tab, height=3, wrap="word", font=("Segoe UI", 10), bg="white", relief="solid", borderwidth=1, padx=8, pady=5)
            source_text.pack(fill="x", pady=(0, 8))
            source_text.insert("1.0", "Nguyên văn nguồn: " + text_value(original_text))
            source_text.configure(state="disabled")
        comparison_frame = ttk.Frame(source_tab)
        comparison_frame.pack(fill="both", expand=True)
        comparison = ttk.Treeview(comparison_frame, columns=("field", "source", "output"), show="headings", height=12)
        for name, label, width in (("field", "Cột trong file nhập Cảng", 175), ("source", "Bằng chứng từ nguồn", 340), ("output", "Giá trị sẽ xuất", 330)):
            comparison.heading(name, text=label)
            comparison.column(name, width=width, minwidth=100, stretch=True)
        self._scrollbars(comparison_frame, comparison)
        comparison.tag_configure("review", background="#FFF6DD")
        source_fields = {"Số BL": "BL_No", "Số Vận Đơn": "BL_No", "Số Container": "Container_No", "Số niêm chì": "Seal_No", "Số niêm chì 1": "Seal_No", "Chủ hàng": "Cleaned_Consignee_Name_For_Output", "Kích cỡ": "Size_Type", "Kích cỡ VTOS": "Size_Type", "Loại Container": "Size_Type", "Hãng khai thác": "Operator", "F/E": "FE_Status", "TL hàng": "Weight_Value", "Trọng lượng (Tấn)": "Weight_Value", "Hàng hóa": "Description"}
        def update_preview():
            # Only this record is copied. Engine validation and exporter rules
            # are shared with the real save/export path; no preview is persisted.
            projected = copy.copy(self.session)
            projected.records = [copy.deepcopy(item) if item["record_id"] == rid else item for item in self.session.records]
            projected.corrections = []
            changes = {name: variable.get() for name, variable in variables.items() if variable.get() != original[name]}
            verified_fields = [name for name, variable in verified.items() if variable.get()]
            comparison.delete(*comparison.get_children())
            try:
                if changes or verified_fields:
                    projected.update_record(rid, changes, "Chỉ xem trước, chưa lưu", verified_fields=verified_fields)
                preview = preview_record_for_export(projected, projected.get_record(rid))
            except (ValueError, TypeError) as exc:
                comparison.insert("", "end", values=("Chưa xem trước được", "Kiểm tra các ô đang sửa", str(exc)), tags=("review",))
                return
            for column, value in preview.items():
                field = source_fields.get(column)
                comparison.insert("", "end", values=(column, _source_field(record, field) if field else "Theo quy tắc xuất", text_value(value)), tags=("review",) if field in affected else ())
        notebook.bind("<<NotebookTabChanged>>", lambda _: update_preview())
        ttk.Button(source_tab, text="Cập nhật xem trước theo các ô đang sửa", command=update_preview).pack(anchor="e", pady=6)
        advanced = ttk.Frame(source_tab)
        advanced_visible = False
        details = tk.Text(advanced, height=7, wrap="word", font=("Consolas", 9), bg="white", relief="flat", padx=8, pady=6)
        details.pack(fill="both", expand=True)
        details.insert("1.0", json.dumps({"Nguồn": source_raw, "Quy tắc": record.get("rules", []), "Vấn đề": record_issues}, ensure_ascii=False, indent=2, default=str))
        details.configure(state="disabled")
        def toggle_details():
            nonlocal advanced_visible
            advanced_visible = not advanced_visible
            if advanced_visible:
                advanced.pack(fill="both", expand=True)
            else:
                advanced.pack_forget()
            advanced_button.configure(text="Ẩn dữ liệu kỹ thuật (JSON)" if advanced_visible else "Hiện dữ liệu kỹ thuật (JSON)")
        advanced_button = ttk.Button(source_tab, text="Hiện dữ liệu kỹ thuật (JSON)", command=toggle_details)
        advanced_button.pack(anchor="w", pady=(0, 4))
        update_preview()
        ttk.Label(body, text="Lý do chỉnh sửa / căn cứ xác nhận (bắt buộc)").pack(anchor="w")
        reason = tk.StringVar()
        ttk.Entry(body, textvariable=reason).pack(fill="x", pady=(5, 8))
        buttons = ttk.Frame(body)
        buttons.pack(fill="x")
        def save():
            changes = {name: variable.get() for name, variable in variables.items() if variable.get() != original[name]}
            verified_fields = [name for name, variable in verified.items() if variable.get()]
            if not changes and not verified_fields:
                messagebox.showinfo("Chưa có thay đổi", "Sửa trường cần thiết hoặc tích xác nhận đúng trường đã đối chiếu. Mở rồi đóng form không tự xác nhận dữ liệu.", parent=dialog)
                return
            try:
                self.session.update_record(rid, changes, reason.get(), verified_fields=verified_fields)
                self.dirty = True
                self.refresh()
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Chưa lưu được", str(exc), parent=dialog)
        ttk.Button(buttons, text="Lưu chỉnh sửa / xác nhận", style="Primary.TButton", command=save).pack(side="right")
        ttk.Button(buttons, text="Đóng", command=dialog.destroy).pack(side="right", padx=8)

    def acknowledge(self):
        rid = self.selected_record_id()
        if rid:
            reason = simpledialog.askstring("Đã đối chiếu", self._record_context(rid) + "\n\nGhi căn cứ xác nhận cảnh báo. Lỗi dữ liệu vẫn phải sửa hoặc xác nhận đúng trường trong form:", parent=self.root)
            if reason:
                self.session.acknowledge_record(rid, reason)
                self.dirty = True
                self.refresh()

    def exclude(self):
        rid = self.selected_record_id()
        if rid:
            excluded = not self.session.get_record(rid).get("_excluded", False)
            reason = simpledialog.askstring("Loại dòng" if excluded else "Khôi phục dòng", self._record_context(rid) + "\n\n" + ("Dòng này sẽ không được xuất vào hệ thống Cảng." if excluded else "Dòng này sẽ trở lại danh sách cần xuất.") + "\nGhi lý do (ví dụ: dòng lặp đã đối chiếu):", parent=self.root)
            if reason:
                self.session.set_excluded(rid, excluded, reason)
                self.dirty = True
                self.refresh()

    def export(self):
        if not self.session or self.busy:
            return
        if self.session.carrier != self.carrier.get():
            messagebox.showinfo("Hãng tàu đã đổi", "Xử lý lại manifest theo hãng vừa chọn trước khi xuất.", parent=self.root)
            return
        if self.session.metadata.get("settings_changed") or self.session.settings != self.settings[self.carrier.get()]:
            messagebox.showinfo("Quy ước đã đổi", "Xử lý lại manifest để áp dụng quy ước mới trước khi xuất.", parent=self.root)
            return
        stats = self.session.statistics()
        if stats["errors"]:
            messagebox.showwarning("Cần xử lý lỗi", f"Còn {stats['errors']} lỗi. Mở mục Cần kiểm tra để xử lý.", parent=self.root)
            return
        if stats["warnings"] and not messagebox.askyesno("Xác nhận xuất", f"Còn {stats['warnings']} cảnh báo. Bạn đã kiểm tra và muốn xuất file?", parent=self.root):
            return
        path = filedialog.asksaveasfilename(title="Xuất file nhập hệ thống Cảng", defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
                                          initialfile=f"{self.selected_path.stem}_{self.session.carrier}_CLEAN.xlsx", confirmoverwrite=False, parent=self.root)
        if path:
            try:
                include_review = self.include_review.get()
                try:
                    result = export_port_bundle(self.session, path, include_review=include_review)
                except FileExistsError:
                    output = Path(path)
                    destinations = [str(output)] + ([str(output.with_suffix(".review.json"))] if include_review else [])
                    if not messagebox.askyesno("Xác nhận ghi đè", "Bộ file sau đã có file cùng tên:\n\n" + "\n".join(destinations) + "\n\nGhi đè bộ file này?", parent=self.root):
                        return
                    result = export_port_bundle(self.session, path, overwrite=True, include_review=include_review)
                review_path = result.get("review")
                if review_path:
                    self.dirty = False
                self.status.set(f"Đã xuất: {Path(path).name}  |  {stats['active_records']} dòng, {stats['containers']} container.")
                review_message = f"\nĐối chiếu để mở lại phiên: {review_path}" if review_path else "\nChưa lưu đối chiếu trong lần xuất này; dùng Lưu đối chiếu để giữ phiên làm việc."
                messagebox.showinfo("Đã xuất file", f"Excel nhập Cảng: {result['excel']}{review_message}\n\nGiữ đúng mẫu 16 cột của {self.session.carrier}.", parent=self.root)
            except Exception as exc:
                messagebox.showerror("Không xuất được", str(exc), parent=self.root)

    def save_review(self):
        if not self.session:
            return
        path = filedialog.asksaveasfilename(title="Lưu bản đối chiếu", defaultextension=".json", filetypes=[("Đối chiếu JSON", "*.json")],
                                          initialfile=f"{self.selected_path.stem}_DOI_CHIEU.json", parent=self.root)
        if path:
            try:
                self.session.save_review(path)
                self.dirty = False
                self.status.set("Đã lưu dữ liệu gốc, kết quả, các mục cần kiểm tra và lịch sử chỉnh sửa.")
            except Exception as exc:
                messagebox.showerror("Không lưu được", str(exc), parent=self.root)

    def number_settings(self):
        if self.busy:
            return
        carrier = self.carrier.get()
        existing = copy.deepcopy(self.settings[carrier])
        dialog = tk.Toplevel(self.root)
        dialog.title("Cấu hình đọc manifest")
        dialog.geometry("660x520")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=20)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"Hãng: {carrier}", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        choices = {"Theo mẫu hiện tại (mặc định)": "legacy", "Dấu phẩy thập phân: 25.000,50": "decimal_comma", "Dấu chấm thập phân: 25,000.50": "decimal_dot"}
        current = existing.get("number_format", "legacy")
        choice = tk.StringVar(value=next(k for k, v in choices.items() if v == current))
        ttk.Label(body, text="Quy ước số của dữ liệu dạng chữ").pack(anchor="w", pady=(14, 4))
        ttk.Combobox(body, textvariable=choice, values=list(choices), state="readonly", width=48).pack(fill="x")
        ttk.Label(body, text="Ý nghĩa trọng lượng trong nguồn").pack(anchor="w", pady=(14, 4))
        weight_choices = {value: key for key, value in WEIGHT_LABELS.items()}
        default_weight_kind = "gross" if carrier == "VINAFCO" else "unknown"
        weight_choice = tk.StringVar(value=WEIGHT_LABELS[existing.get("weight_kind", default_weight_kind)])
        ttk.Combobox(body, textvariable=weight_choice, values=list(weight_choices), state="readonly").pack(fill="x")
        ttk.Label(body, text="Sheet cần xử lý (có thể nhập đúng tên sheet)").pack(anchor="w", pady=(14, 4))
        automatic = "Theo quy tắc nhận diện của hãng"
        available = self.session.metadata.get("available_sheets", []) if self.session else []
        sheet_choice = tk.StringVar(value=existing.get("selected_sheet") or automatic)
        ttk.Combobox(body, textvariable=sheet_choice, values=[automatic, *available], state="normal").pack(fill="x")
        ttk.Label(body, text="Chỉ đổi ý nghĩa trọng lượng khi đã đối chiếu với hãng tàu. Số numeric trong Excel giữ nguyên. Cấu hình mới chỉ có hiệu lực sau khi bấm Xử lý lại; các chỉnh sửa của phiên cũ không tự chuyển sang kết quả mới.", wraplength=590, style="Muted.TLabel").pack(anchor="w", pady=(16, 6))
        def save():
            updated = copy.deepcopy(existing)
            updated["number_format"] = choices[choice.get()]
            updated["weight_kind"] = weight_choices[weight_choice.get()]
            selected_sheet = sheet_choice.get().strip()
            if selected_sheet and selected_sheet != automatic:
                updated["selected_sheet"] = selected_sheet
            else:
                updated.pop("selected_sheet", None)
            try:
                updated = validate_carrier_settings(carrier, updated)
            except ValueError as exc:
                messagebox.showerror("Cấu hình chưa hợp lệ", str(exc), parent=dialog)
                return
            if updated == existing:
                dialog.destroy()
                return
            self.settings[carrier] = updated
            try:
                self.config_path.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                messagebox.showwarning("Cấu hình", "Đã áp dụng trong phiên này; thư mục ứng dụng không cho lưu cấu hình lâu dài.", parent=dialog)
            if self.session and self.session.carrier == carrier:
                self.export_button.configure(state="disabled")
                self.status.set("Quy ước số đã đổi. Bấm Xử lý lại để áp dụng trước khi xuất.")
                self.session.metadata["settings_changed"] = True
                self.dirty = True
                self.refresh()
                self.status.set("Cấu hình đọc đã đổi. Lưu đối chiếu nếu cần giữ các sửa đổi, rồi bấm Xử lý lại để áp dụng trước khi xuất.")
            dialog.destroy()
        ttk.Button(body, text="Lưu cấu hình", style="Primary.TButton", command=save).pack(anchor="e", pady=(12, 0))

    def help(self):
        messagebox.showinfo("Hướng dẫn nhanh", "1. Chọn hãng tàu, mở một manifest và xem cấu hình đọc đang dùng.\n2. Mở tab Cần kiểm tra; nhấp đúp lỗi để sửa đúng container.\n3. Chỉ tích Đã đối chiếu trường này khi đã kiểm tra chính trường đó. Sửa seal không tự xác nhận F/E hoặc trọng lượng.\n4. Trong cửa sổ sửa, tab Nguồn và giá trị sẽ xuất cho thấy giá trị gốc và mẫu 16 cột. Dữ liệu JSON được thu gọn ở phần kỹ thuật.\n5. Xuất Excel; mặc định lưu kèm .review.json để giữ nguồn, sửa đổi và lịch sử.\n6. Mở phiên đã lưu để tiếp tục công việc; phải cung cấp đúng manifest gốc, nội dung không thay đổi.\n\nLỗi chặn xuất; cảnh báo cần đối chiếu. Loại dòng luôn hiển thị container/B/L và cần lý do. Cột Độ chính xác (%) là điểm quy tắc, không phải xác suất đã đo.\n\nCtrl+O: mở manifest · Ctrl+S: xuất · F1: hướng dẫn", parent=self.root)

    def close(self):
        if self.busy and not messagebox.askyesno("Đang xử lý", "Đóng ứng dụng và dừng phiên đang xử lý?", parent=self.root):
            return
        if self._confirm_discard():
            self.root.destroy()


def main():
    root = tk.Tk()
    ManifestApp(root)
    root.mainloop()
