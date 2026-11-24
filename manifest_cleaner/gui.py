"""Vietnamese desktop UI. All widget access stays on the Tk main thread."""
from __future__ import annotations

import copy
import csv
import io
import json
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, simpledialog, ttk

from xlsxwriter.utility import xl_col_to_name

from . import __version__
from .common import parse_weight, seal_text, text_value
from .engine import CARRIERS, EDITABLE_FIELDS, FIELD_LABELS, ReviewSourceError, load_review, load_settings, process_manifest, validate_carrier_settings
from .exporter import export_port_bundle, preview_record_for_export
from .issue_display import issue_field, issue_location, issue_raw_value, issue_title

# Light operational palette, Segoe UI hierarchy and shared spacing in pixels at 96 DPI.
PAGE = "#F3F6F9"
SURFACE = "#FFFFFF"
BORDER = "#8193A5"
TEXT = "#182A3D"
MUTED = "#46596C"
ACCENT = "#124C72"
ACCENT_HOVER = "#0C3C5C"
ACCENT_SOFT = "#E6EFF7"
SUCCESS = "#166146"
WARNING = "#745000"
WARNING_BG = "#FFF4D8"
DANGER = "#9C2E28"
DANGER_HOVER = "#F8E2DF"
DANGER_BG = "#FCECEB"
EXCLUDED_BG = "#E8EDF2"
DISABLED_BG = "#E4EAF0"
FOCUS = "#14669A"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 15, "bold")
FONT_NUMBER = ("Segoe UI", 17, "bold")
FONT_MONO = ("Consolas", 9)
IDENTIFIER_COLUMNS = ("Container_No", "Seal_No", "BL_No", "VTOS_Size", "Operator")
# Figure spaces keep right-aligned weights apart from the left-aligned consignee text.
WEIGHT_PAD = "\u2007\u2007"
GAP = 8
PAD = 16
WINDOW_PREFERRED = (1440, 820)
WINDOW_MINIMUM = (940, 620)
STAT_ITEMS = (
    ("containers", "Container", "Count"), ("full", "F · Có hàng", "Success"),
    ("empty", "E · Rỗng", "Count"), ("errors", "Lỗi chặn", "Error"),
    ("warnings", "Cảnh báo", "Warning"), ("excluded", "Đã loại", "Muted"),
)
NUMBER_LABELS = {"legacy": "Theo quy tắc hãng", "decimal_comma": "Dấu phẩy thập phân", "decimal_dot": "Dấu chấm thập phân"}
WEIGHT_LABELS = {"unknown": "Chưa xác nhận (phiên cũ)", "gross": "Tổng vỏ và hàng", "cargo": "Trọng lượng hàng (phiên cũ)"}
SOURCE_REASON_LABELS = {
    "table_header": "Tiêu đề bảng", "identical_table_header": "Tiêu đề lặp lại, giữ cùng cấu trúc và đơn vị",
    "header_schema_or_unit_changed": "Tiêu đề thay đổi cột hoặc đơn vị", "after_changed_header": "Chưa đọc tiếp sau tiêu đề thay đổi",
    "known_total_footer": "Dòng tổng cộng", "party_or_bill_context": "Thông tin người gửi, người nhận hoặc B/L",
    "non_container_note": "Ghi chú không phải dòng container", "container_record": "Dòng container đã đọc",
    "missing_or_invalid_container": "Thiếu mã container hoặc mã cần kiểm tra",
    "weight_first_tons": "Trọng lượng đứng trước mô tả, đơn vị tấn", "description_first_kg": "Trọng lượng đứng sau mô tả, đơn vị kg",
    "ambiguous": "Có nhiều cách đọc trọng lượng và mô tả", "unparsed": "Chưa đọc đủ cấu trúc dòng",
    "seal_type_ambiguous": "Có nhiều cách tách seal, kích cỡ, trọng lượng hoặc mô tả",
    "marks_empty": "Container rỗng trong cột MARKS", "marks_incomplete": "Cột MARKS chưa đủ thông tin container",
    "explicit_empty_detail": "Dòng ghi rõ container rỗng",
    "container_record_requires_review": "Dòng container còn thiếu dữ liệu khi đọc nguồn",
    "description_metadata_port": "Dòng địa điểm/cảng, không gán thành tên hàng",
    "description_metadata_total": "Dòng tổng trong mô tả, không gán thành tên hàng",
    "description_metadata_attachment": "Dòng dẫn tới danh sách đính kèm, không gán thành tên hàng",
    "description_metadata_quantity": "Thông tin số lượng/kích cỡ được dùng để đối chiếu",
    "delivery_mode_annotation": "Ký hiệu phương thức giao nhận trong cột container",
    "weight_continuation_matched": "Trọng lượng ở ô nối tiếp, đã khớp số lượng và tổng",
    "weight_continuation_ambiguous": "Ô trọng lượng nối tiếp chưa đủ căn cứ để ghép",
    "legacy_compact_identifier_corroborated_in_marks": "Mã container ngắn trùng trong dòng chi tiết và MARKS",
    "container_summary_header": "Tiêu đề bảng tổng hợp container", "container_summary_size": "Số lượng theo kích cỡ",
    "container_summary_total": "Tổng số container khai báo", "container_summary_other_metric": "Chỉ số khác trong bảng tổng hợp",
    "container_summary_unlabeled_metric": "Giá trị tổng hợp thiếu nhãn",
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
    if field == "Weight_Value":
        row = raw.get("weight_source_row")
        column = raw.get("weight_source_column")
        line = raw.get("weight_source_line")
        value = text_value(raw.get("weight_line"))
        if value and all(isinstance(number, int) and number > 0 for number in (row, column, line)):
            cell = f"{xl_col_to_name(column - 1)}{row}"
            sheet = text_value(record.get("source_sheet"))
            address = f"{sheet}!{cell}" if sheet else cell
            return f"{address} · dòng {line} trong ô · {value}"
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
        owner_total = raw.get("ownership_total") or {}
        if owner_total.get("text"):
            return f"Dòng {owner_total.get('source_row', '')} · {owner_total['text']}"
        return "SOC" if raw.get("is_soc") is True else "Xem dấu SOC/COC trong nguồn"
    value_text = seal_text if field == "Seal_No" else text_value
    for name in names.get(field, ()):
        if raw.get(name) is not None and text_value(raw[name]) != "":
            value = value_text(raw[name])
            if field == "Weight_Value" and raw.get("weight_source_unit"):
                value += " " + text_value(raw["weight_source_unit"])
            return value
    return "—"


def _present_text(value):
    return bool(text_value(value))


def _sheet_description(session):
    metadata = session.metadata
    sheets = metadata.get("selected_sheet") or metadata.get("source_sheet") or metadata.get("sheets_used") or "Chưa xác định"
    if isinstance(sheets, (list, tuple)):
        sheets = ", ".join(str(x) for x in sheets)
    return sheets


def _runtime_exceptions(session):
    """Name reading settings only when they differ from the carrier default, such as an older saved session."""
    settings = session.metadata.get("effective_settings") or session.settings
    notes = []
    number_format = settings.get("number_format", "legacy")
    if number_format != "legacy":
        notes.append("Số: " + NUMBER_LABELS.get(number_format, number_format))
    weight_kind = settings.get("weight_kind", session.metadata.get("weight_kind", "unknown"))
    if weight_kind != "gross":
        notes.append("Trọng lượng: " + WEIGHT_LABELS.get(weight_kind, "Chưa xác nhận ý nghĩa"))
    return notes


def _reconciliation_description(session):
    result = session.metadata.get("reconciliation")
    if not result:
        return ""
    source = result.get("source_total")
    parsed = result.get("parsed_total")
    difference = result.get("total_difference")
    if source is None or difference is None:
        reason = result.get("reason") or "Chưa xác định được tổng số container từ nguồn."
        text = f"Đối soát lúc đọc chưa hoàn tất. Đọc được {parsed} mã container duy nhất. {reason}"
    else:
        delta = f"{difference:+d}" if difference else "0"
        text = f"Đối soát lúc đọc: nguồn khai {source} · đọc được {parsed} · chênh lệch {delta}"
        if result.get("reason"):
            text += f" · {result['reason']}"
    if result.get("size_differences"):
        text += " · Có kích cỡ lệch. Xem mục Cần kiểm tra."
    return text


def _monitor_work_area(parent):
    """Get the Windows work area of the parent monitor, excluding the taskbar."""
    parent.update_idletasks()
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class MonitorInfo(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        monitor_from_window = user32.MonitorFromWindow
        monitor_from_window.argtypes = [wintypes.HWND, wintypes.DWORD]
        monitor_from_window.restype = wintypes.HANDLE
        get_monitor_info = user32.GetMonitorInfoW
        get_monitor_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        get_monitor_info.restype = wintypes.BOOL
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(info)
        handle = monitor_from_window(parent.winfo_id(), 2)
        if handle and get_monitor_info(handle, ctypes.byref(info)):
            return info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom
    return 0, 0, parent.winfo_screenwidth(), parent.winfo_screenheight()


def _enable_dpi_awareness():
    """Opt in before Tk creates an HWND, falling back on older Windows."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) in (0, -2147024891):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def _pixels(widget, value):
    """Scale fixed dimensions with Tk's measured display density."""
    return round(value * widget.winfo_fpixels("1i") / 96)


def _fit_window(window, parent, preferred, minimum):
    left, top, right, bottom = _monitor_work_area(parent)
    max_width = max(1, right - left - _pixels(window, 24))
    max_height = max(1, bottom - top - _pixels(window, 60))
    width, height = min(_pixels(window, preferred[0]), max_width), min(_pixels(window, preferred[1]), max_height)
    x = left + (right - left - width) // 2
    y = top + max(0, (bottom - top - height - _pixels(window, 30)) // 2)
    # The leading plus makes negative coordinates absolute on a monitor left of the primary.
    window.geometry(f"{width}x{height}+{x}+{y}")
    window.minsize(min(_pixels(window, minimum[0]), width), min(_pixels(window, minimum[1]), height))


def _fit_dialog(dialog, parent, preferred=(940, 690), minimum=(475, 330)):
    _fit_window(dialog, parent, preferred, minimum)


def _scroll_area(parent):
    canvas = tk.Canvas(parent, background=PAGE, borderwidth=0, highlightthickness=0, width=1, height=1)
    scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    scroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.configure(yscrollcommand=scroll.set)
    content = ttk.Frame(canvas, padding=8)
    window = canvas.create_window((0, 0), window=content, anchor="nw")
    canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
    content.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
    return canvas, content


def _bind_dialog_scroll(dialog, panes):
    def pane_for(widget):
        for canvas, content in panes:
            if widget is canvas or widget is content or str(widget).startswith(f"{content}."):
                return canvas, content
        return None

    def wheel(event):
        pane = pane_for(event.widget)
        if pane and not isinstance(event.widget, (tk.Text, ttk.Treeview)):
            direction = -1 if event.num == 4 or event.delta > 0 else 1
            pane[0].yview_scroll(direction * 3, "units")
            return "break"

    def page(event):
        pane = pane_for(event.widget)
        if pane and not isinstance(event.widget, (tk.Text, ttk.Treeview)):
            pane[0].yview_scroll(-1 if event.keysym == "Prior" else 1, "pages")
            return "break"

    def reveal(event):
        pane = pane_for(event.widget)
        if not pane:
            return
        canvas, content = pane
        height = content.winfo_height()
        viewport = canvas.winfo_height()
        if height <= viewport:
            return
        y = event.widget.winfo_rooty() - content.winfo_rooty()
        start = canvas.canvasy(0)
        end = y + event.widget.winfo_height()
        if y < start:
            canvas.yview_moveto(y / height)
        elif end > start + viewport:
            canvas.yview_moveto((end - viewport) / height)

    for binding in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        dialog.bind(binding, wheel, add="+")
    for binding in ("<Prior>", "<Next>"):
        dialog.bind(binding, page, add="+")
    dialog.bind("<FocusIn>", reveal, add="+")


def _wrapped_label(parent, **options):
    label = ttk.Label(parent, wraplength=420, **options)

    def resize(event):
        if event.widget is parent and label.winfo_exists():
            label.configure(wraplength=max(100, event.width - _pixels(parent, 2 * PAD)))

    parent.bind("<Configure>", resize, add="+")
    return label


class ManifestApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Manifest Cleaner {__version__} — Nhập hệ thống Cảng")
        self.root.withdraw()
        self.root.configure(bg=PAGE)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.session = None
        self.busy = False
        self.events = queue.Queue()
        self.dirty = False
        self.export_directory = None
        self.selected_path = None
        self.read_override = None
        self.sort_field = None
        self.sort_reverse = False
        self.severity_filter = None
        self.count_labels = {}
        self.table_counts = (0, 0)
        self.issue_count = 0
        self.carrier = tk.StringVar(value=CARRIERS[0])
        self.search = tk.StringVar()
        self.only_issues = tk.BooleanVar(value=False)
        self.show_excluded = tk.BooleanVar(value=False)
        self.include_review = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Chọn hãng tàu và mở một file manifest để bắt đầu.")
        self.file_label = tk.StringVar(value="Chưa chọn manifest")
        self.summary = tk.StringVar()
        self.filter_status = tk.StringVar()
        self.export_hint = tk.StringVar(value="Mở manifest để xuất.")
        self.configuration = tk.StringVar(value="")
        self.config_path = (Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]) / "settings.json"
        try:
            self.settings = load_settings(self.config_path if self.config_path.is_file() else None)
        except Exception as exc:
            self.settings = load_settings()
            messagebox.showwarning("Cấu hình", f"Không đọc được cấu hình: {exc}\nĐang dùng quy tắc mặc định từ các repo.", parent=root)
        self._style()
        self._build()
        _fit_window(self.root, self.root, WINDOW_PREFERRED, WINDOW_MINIMUM)
        self.root.deiconify()
        self.root.bind_class("TButton", "<Return>", lambda event: (event.widget.invoke(), "break")[1])
        self.search.trace_add("write", lambda *_: self.refresh())
        self.root.bind("<Control-o>", lambda _: self.choose_file())
        self.root.bind("<Control-s>", lambda _: self.export())
        self.root.bind("<F1>", lambda _: self.help())
        self.root.after(100, self._poll)

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        pixels = lambda value: _pixels(self.root, value)
        style.configure(".", background=PAGE, foreground=TEXT, font=FONT,
                        focuscolor=FOCUS, bordercolor=BORDER)
        style.configure("TFrame", background=PAGE)
        style.configure("TLabel", background=PAGE, foreground=TEXT, font=FONT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Issue.TLabel", foreground=DANGER, font=FONT_BOLD)
        style.configure("Toolbar.TFrame", background=SURFACE)
        style.configure("Toolbar.TLabel", background=SURFACE)
        style.configure("Title.Toolbar.TLabel", font=FONT_TITLE)

        style.configure("TButton", background=SURFACE, foreground=TEXT, font=FONT,
                        padding=(pixels(10), pixels(5)), borderwidth=1, relief="solid",
                        lightcolor=BORDER, darkcolor=BORDER)
        style.map("TButton",
                  background=[("disabled", PAGE), ("pressed", ACCENT_SOFT), ("active", ACCENT_SOFT)],
                  foreground=[("disabled", MUTED)], bordercolor=[("focus", FOCUS), ("!focus", BORDER)],
                  lightcolor=[("focus", FOCUS)], darkcolor=[("focus", FOCUS)])
        style.configure("Primary.TButton", background=ACCENT, foreground=SURFACE,
                        bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT, focuscolor=SURFACE)
        style.map("Primary.TButton",
                  background=[("disabled", DISABLED_BG), ("pressed", ACCENT_HOVER), ("active", ACCENT_HOVER)],
                  foreground=[("disabled", MUTED), ("!disabled", SURFACE)],
                  bordercolor=[("disabled", BORDER), ("focus", FOCUS)],
                  lightcolor=[("disabled", DISABLED_BG), ("!disabled", ACCENT)],
                  darkcolor=[("disabled", DISABLED_BG), ("!disabled", ACCENT)])
        style.configure("Danger.TButton", foreground=DANGER)
        style.map("Danger.TButton", foreground=[("disabled", MUTED), ("!disabled", DANGER)],
                  background=[("disabled", PAGE), ("active", DANGER_HOVER), ("pressed", DANGER_HOVER)])
        for variant, color in (("Count", ACCENT), ("Success", SUCCESS), ("Error", DANGER),
                               ("Warning", WARNING), ("Muted", MUTED)):
            style.configure(f"{variant}.Number.TLabel", background=SURFACE, foreground=color, font=FONT_NUMBER)
            style.configure(f"{variant}.Count.TButton", font=FONT_BOLD, foreground=color,
                            padding=(pixels(6), pixels(1)))
            style.map(f"{variant}.Count.TButton", foreground=[("disabled", MUTED), ("!disabled", color)],
                      background=[("disabled", PAGE), ("active", ACCENT_SOFT)])

        style.configure("Treeview", font=FONT, rowheight=pixels(29),
                        background=SURFACE, fieldbackground=SURFACE, foreground=TEXT)
        style.configure("Treeview.Heading", font=FONT_BOLD, padding=(pixels(8), pixels(6)),
                        background=PAGE, foreground=TEXT, relief="flat")
        style.map("Treeview",
                  background=[("selected", ACCENT)], foreground=[("selected", SURFACE)],
                  bordercolor=[("focus", FOCUS)])
        style.map("Treeview.Heading", background=[("active", ACCENT_SOFT)])
        style.configure("TNotebook", background=PAGE, tabmargins=0, padding=0)
        style.configure("TNotebook.Tab", font=FONT, padding=(pixels(13), pixels(6)),
                        background=PAGE, foreground=MUTED)
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT_SOFT), ("active", SURFACE)],
                  foreground=[("selected", ACCENT)], font=[("selected", FONT_BOLD)],
                  padding=[("selected", (pixels(13), pixels(9))), ("!selected", (pixels(13), pixels(6)))],
                  expand=[("selected", (0, pixels(2), 0, 0))], bordercolor=[("focus", FOCUS)])
        style.configure("TCheckbutton", background=PAGE, foreground=TEXT, font=FONT)
        style.map("TCheckbutton", bordercolor=[("focus", FOCUS)])
        for control in ("TEntry", "TCombobox"):
            style.configure(control, padding=(pixels(5), pixels(3)), fieldbackground=SURFACE)
            style.map(control, fieldbackground=[("disabled", DISABLED_BG), ("readonly", SURFACE)],
                      foreground=[("disabled", MUTED)], bordercolor=[("focus", FOCUS)],
                      lightcolor=[("focus", FOCUS)], darkcolor=[("focus", FOCUS)])
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=DISABLED_BG)

    def _build(self):
        gap = _pixels(self.root, GAP)
        pad = _pixels(self.root, PAD)
        toolbar = ttk.Frame(self.root, style="Toolbar.TFrame", padding=(pad, gap))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Manifest Cleaner", style="Title.Toolbar.TLabel").pack(side="left", padx=(0, pad))
        ttk.Label(toolbar, text="Hãng tàu", style="Toolbar.TLabel", font=FONT_BOLD).pack(side="left", padx=(0, gap))
        self.carrier_box = ttk.Combobox(toolbar, textvariable=self.carrier, values=CARRIERS,
                                       state="readonly", width=8, font=FONT)
        self.carrier_box.pack(side="left", padx=(0, gap))
        self.carrier_box.bind("<<ComboboxSelected>>", self.carrier_changed)
        self.open_button = ttk.Button(toolbar, text="Mở manifest…", style="Primary.TButton", command=self.choose_file)
        self.open_button.pack(side="left", padx=(0, gap))
        self.resume_button = ttk.Button(toolbar, text="Mở phiên đã lưu…", command=self.choose_review)
        self.resume_button.pack(side="left", padx=(0, gap))
        self.reload_button = ttk.Button(toolbar, text="Xử lý lại", command=self.reprocess, state="disabled")
        self.reload_button.pack(side="left")
        extras = ttk.Frame(toolbar, style="Toolbar.TFrame")
        extras.pack(side="right")
        ttk.Button(extras, text="Hướng dẫn", command=self.help).pack(side="left")
        ttk.Button(extras, text="Cấu hình đọc…", command=self.number_settings).pack(side="left", padx=(gap, 0))

        # Reserve the lower controls before giving the remaining space to the table.
        footer = ttk.Frame(self.root, padding=(pad, gap // 2, pad, gap))
        footer.pack(side="bottom", fill="x")
        footer.columnconfigure(0, weight=1)
        self.json_check = ttk.Checkbutton(footer, text="Xuất kèm đối chiếu JSON để mở lại phiên",
                                          variable=self.include_review)
        self.json_check.grid(row=0, column=0, sticky="w", pady=(0, gap // 2))
        self.progress = ttk.Progressbar(footer, mode="determinate", length=_pixels(self.root, 110))
        self.progress.grid(row=1, column=1, sticky="e", padx=(gap, 0))
        self.status_label = _wrapped_label(footer, textvariable=self.status, style="Muted.TLabel")
        self.status_label.grid(row=1, column=0, sticky="w")
        footer.bind("<Configure>", lambda event: self.status_label.configure(
            wraplength=max(100, event.width - self.progress.winfo_reqwidth() - 3 * pad)), add="+")

        self.actionbar = ttk.Frame(self.root, padding=(pad, gap, pad, 0))
        self.actionbar.pack(side="bottom", fill="x")
        edits = ttk.Frame(self.actionbar)
        edits.grid(row=0, column=0, sticky="w")
        self.actionbar.columnconfigure(1, weight=1)
        self.edit_button = ttk.Button(edits, text="Xem / sửa dòng", command=self.edit_selected, state="disabled")
        self.edit_button.pack(side="left", padx=(0, gap))
        self.ack_button = ttk.Button(edits, text="Đã đối chiếu…", command=self.acknowledge, state="disabled")
        self.ack_button.pack(side="left", padx=(0, gap))
        self.exclude_button = ttk.Button(edits, text="Loại / khôi phục dòng…", command=self.exclude, state="disabled")
        self.exclude_button.pack(side="left")
        outputs = ttk.Frame(self.actionbar)
        outputs.grid(row=0, column=2, sticky="e")
        self.review_button = ttk.Button(outputs, text="Lưu đối chiếu…", command=self.save_review, state="disabled")
        self.review_button.pack(side="left", padx=(0, gap))
        self.export_button = ttk.Button(outputs, text="Xuất file nhập Cảng…", style="Primary.TButton", command=self.export, state="disabled")
        self.export_button.pack(side="left")
        self.export_hint_label = _wrapped_label(self.actionbar, textvariable=self.export_hint, style="Muted.TLabel")
        self.export_hint_label.grid(row=1, column=0, columnspan=3, sticky="e", pady=(gap // 2, 0))
        self.export_folder_button = ttk.Button(self.actionbar, text="Mở thư mục kết quả", command=self.open_export_folder)
        self.export_folder_button.grid(row=2, column=2, sticky="e", pady=(gap // 2, 0))
        self.export_folder_button.grid_remove()

        info = ttk.Frame(self.root, padding=(pad, gap, pad, 0))
        info.pack(fill="x")
        _wrapped_label(info, textvariable=self.file_label, font=FONT_BOLD).pack(anchor="w")
        counts = ttk.Frame(info)
        counts.pack(fill="x", pady=(gap, gap // 2))
        for index, (key, label, variant) in enumerate(STAT_ITEMS):
            counts.columnconfigure(index, weight=1, uniform="stats")
            value = tk.StringVar(value="—")
            self.count_labels[key] = value
            card = ttk.Frame(counts, style="Toolbar.TFrame", padding=(gap, gap // 2))
            card.grid(row=0, column=index, sticky="nsew", padx=(0, gap if index < len(STAT_ITEMS) - 1 else 0))
            card.rowconfigure(0, minsize=_pixels(self.root, 26))
            number = ttk.Label(card, textvariable=value, style=f"{variant}.Number.TLabel")
            if key in {"errors", "warnings"}:
                severity = "error" if key == "errors" else "warning"
                button = ttk.Button(card, style=f"{variant}.Count.TButton", text=label,
                                    command=lambda kind=severity: self._filter_severity(kind))
                button.grid(row=0, column=0, sticky="w")
                number.bind("<Button-1>", lambda _, choice=button: choice.invoke())
            else:
                ttk.Label(card, text=label, style="Toolbar.TLabel").grid(row=0, column=0, sticky="w")
            number.grid(row=1, column=0, sticky="w")
        self.summary_label = _wrapped_label(info, textvariable=self.summary, style="Muted.TLabel")
        self.summary_label.pack(anchor="w")
        # Shown only while it has text, so an empty line never leaves a gap.
        self.configuration_label = _wrapped_label(info, textvariable=self.configuration, style="Muted.TLabel")

        filters = ttk.Frame(self.root, padding=(pad, gap, pad, gap))
        filters.pack(fill="x")
        ttk.Label(filters, text="Tìm container / B/L / hàng hóa:").pack(side="left", padx=(0, gap))
        self.search_entry = ttk.Entry(filters, textvariable=self.search, width=17)
        self.search_entry.pack(side="left", padx=(0, gap))
        ttk.Checkbutton(filters, text="Chỉ mục cần kiểm tra", variable=self.only_issues, command=self.refresh).pack(side="left", padx=(0, gap))
        ttk.Checkbutton(filters, text="Hiện dòng đã loại", variable=self.show_excluded, command=self.refresh).pack(side="left")
        filter_actions = ttk.Frame(filters)
        filter_actions.pack(side="right")
        ttk.Button(filter_actions, text="Xóa bộ lọc", command=self._clear_filters).pack(side="left", padx=(gap, gap))
        ttk.Button(filter_actions, text="Tra nguồn…", command=self.show_source_coverage).pack(side="left")
        filter_feedback = ttk.Frame(self.root)
        filter_feedback.pack(fill="x", padx=pad, pady=(0, gap // 2))
        _wrapped_label(filter_feedback, textvariable=self.filter_status, style="Muted.TLabel").pack(anchor="w")

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=pad)
        self.tabs.enable_traversal()
        data_tab = ttk.Frame(self.tabs)
        issues_tab = ttk.Frame(self.tabs)
        self.tabs.add(data_tab, text="Container")
        self.tabs.add(issues_tab, text="Cần kiểm tra")
        self.tabs.bind("<<NotebookTabChanged>>", self._tab_changed)
        fields = (
            ("status", "Trạng thái", 103), ("Container_No", FIELD_LABELS["Container_No"], 120),
            ("Seal_No", FIELD_LABELS["Seal_No"], 95), ("BL_No", FIELD_LABELS["BL_No"], 108),
            ("VTOS_Size", FIELD_LABELS["VTOS_Size"], 83), ("Operator", FIELD_LABELS["Operator"], 90),
            ("FE_Status", FIELD_LABELS["FE_Status"], 42), ("Weight_Value", FIELD_LABELS["Weight_Value"], 111),
            ("Cleaned_Consignee_Name_For_Output", FIELD_LABELS["Cleaned_Consignee_Name_For_Output"], 200),
            ("Description", FIELD_LABELS["Description"], 180),
        )
        self.tree = ttk.Treeview(data_tab, columns=tuple(name for name, _, _ in fields),
                                 show="headings", selectmode="browse", height=6)
        self.data_headings = {name: label for name, label, _ in fields}
        self._columns(self.tree, fields, stretchy={"Cleaned_Consignee_Name_For_Output", "Description"},
                      numeric={"Weight_Value"}, sortable=True)
        self._scrollbars(data_tab, self.tree)
        self.tree.tag_configure("error", background=DANGER_BG)
        self.tree.tag_configure("warning", background=WARNING_BG)
        self.tree.tag_configure("excluded", foreground=MUTED, background=EXCLUDED_BG)
        self.tree.bind("<Double-1>", lambda _: self.edit_selected())
        self.tree.bind("<Return>", lambda _: self.edit_selected())
        self.tree.bind("<<TreeviewSelect>>", self._update_row_actions)

        self._build_issues(issues_tab, gap)
        self.tree.bind("<Control-c>", lambda _: self._copy_table_row(self.tree))
        self.empty_labels = [tk.Label(tab, bg=SURFACE, fg=MUTED, font=FONT, takefocus=False)
                             for tab in (data_tab, self.issue_list)]
        # Tk traverses siblings in stacking order. Match the visible layout.
        self.actionbar.lift()
        footer.lift()
        self._update_table_states()

    def _build_issues(self, tab, gap):
        toolbar = ttk.Frame(tab, padding=(0, gap // 2))
        toolbar.pack(fill="x")
        self.issue_detail_open = True
        self.issue_detail_toggle = ttk.Button(toolbar, text="Ẩn chi tiết", command=self._toggle_issue_detail)
        self.issue_detail_toggle.pack(side="right")
        body = ttk.Frame(tab)
        body.pack(fill="both", expand=True)
        self.issue_panel = ttk.Frame(body, width=_pixels(self.root, 335), padding=(gap, 0, 0, 0))
        self.issue_panel.pack(side="right", fill="y")
        self.issue_panel.pack_propagate(False)
        self.issue_list = ttk.Frame(body)
        self.issue_list.pack(fill="both", expand=True)
        issue_fields = (("#0", "Loại vấn đề / Container", 200), ("severity", "Mức", 82),
                        ("field", "Trường", 134), ("source", "Nguồn", 122))
        self.issue_tree = ttk.Treeview(self.issue_list, columns=("severity", "field", "source"),
                                      show="tree headings", selectmode="browse", height=6)
        self._columns(self.issue_tree, issue_fields, stretchy={"#0", "field"})
        self._scrollbars(self.issue_list, self.issue_tree)
        self.issue_tree.bind("<Double-1>", self.open_issue)
        self.issue_tree.bind("<Return>", self.open_issue)
        self.issue_tree.bind("<Control-c>", lambda _: self._copy_table_row(self.issue_tree, hierarchical=True))
        self.issue_tree.bind("<<TreeviewSelect>>", self._issue_selected)
        self.issue_tree.tag_configure("group", background=ACCENT_SOFT, font=FONT_BOLD)
        self.issue_tree.tag_configure("error", background=DANGER_BG)
        self.issue_tree.tag_configure("warning", background=WARNING_BG)
        self.issue_records = {}
        self.issue_items = {}
        self.issue_groups = {}
        self.issue_locations = {}
        self.issue_keys = {}
        buttons = ttk.Frame(self.issue_panel)
        buttons.pack(side="bottom", fill="x", pady=(gap // 2, 0))
        self.issue_edit_button = ttk.Button(buttons, text="Sửa dòng", command=self.edit_selected, state="disabled")
        self.issue_ack_button = ttk.Button(buttons, text="Đã đối chiếu", command=self.acknowledge, state="disabled")
        self.issue_source_button = ttk.Button(buttons, text="Xem nguồn", command=self._show_issue_source, state="disabled")
        for button in (self.issue_edit_button, self.issue_ack_button, self.issue_source_button):
            button.pack(side="left", expand=True, fill="x")
        self.issue_detail_title = _wrapped_label(self.issue_panel, text="Chi tiết đối chiếu", font=FONT_BOLD)
        self.issue_detail_title.pack(anchor="w", pady=(gap // 2, gap // 2))
        self.issue_detail_text = self._read_only_text(self.issue_panel)
        buttons.lift()
        self.issue_panel.lift()
        self._set_issue_panel("Chi tiết đối chiếu", "Chọn một vấn đề để xem thông báo và nguồn.")

    @staticmethod
    def _read_only_text(parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        detail = tk.Text(frame, width=1, height=1, wrap="word", font=FONT, bg=SURFACE, fg=TEXT,
                         highlightbackground=BORDER, highlightcolor=FOCUS, padx=GAP, pady=GAP,
                         exportselection=False)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=detail.yview)
        scroll.pack(side="right", fill="y")
        detail.pack(side="left", fill="both", expand=True)
        detail.configure(yscrollcommand=scroll.set)
        # Read-only text is focusable for copy and scrolling, and Tab leaves it.
        detail.bind("<Tab>", lambda _: (detail.tk_focusNext().focus_set(), "break")[1])
        detail.bind("<Shift-Tab>", lambda _: (detail.tk_focusPrev().focus_set(), "break")[1])
        return detail

    def _set_issue_panel(self, title, body):
        self.issue_detail_title.configure(text=title)
        self.issue_detail_text.configure(state="normal")
        self.issue_detail_text.delete("1.0", "end")
        self.issue_detail_text.insert("1.0", body)
        self.issue_detail_text.configure(state="disabled")
        self.issue_detail_text.yview_moveto(0)

    def _copy_table_row(self, tree, *, hierarchical=False):
        selection = tree.selection()
        if selection:
            row = selection[0]
            # The full item dictionary coerces numeric-looking strings such as seal IDs.
            values = tuple(str(value).removesuffix(WEIGHT_PAD) for value in tree.item(row, "values"))
            if hierarchical:
                values = (tree.item(row, "text"), *values)
            output = io.StringIO(newline="")
            csv.writer(output, dialect="excel-tab").writerow(values)
            self.root.clipboard_clear()
            self.root.clipboard_append(output.getvalue().removesuffix("\r\n"))
        return "break"

    def _toggle_issue_detail(self):
        self.issue_detail_open = not self.issue_detail_open
        self._update_issue_panel_visibility()

    def _update_issue_panel_visibility(self):
        visible = self.issue_detail_open and self.issue_count
        if visible:
            self.issue_panel.pack(side="right", fill="y", before=self.issue_list)
        else:
            if self.root.focus_get() in (self.issue_detail_text, self.issue_edit_button,
                                        self.issue_ack_button, self.issue_source_button):
                self.issue_tree.focus_set()
            self.issue_panel.pack_forget()
        self.issue_detail_toggle.configure(text="Ẩn chi tiết" if visible else "Hiện chi tiết",
                                           state="normal" if self.issue_count else "disabled")

    def _issue_selected(self, _=None):
        self._update_row_actions()
        selected = self.issue_tree.selection()
        key = selected[0] if selected and self.session and not self.busy else None
        item = self.issue_items.get(key)
        group = self.issue_groups.get(key)
        rid = self.issue_records.get(key)
        available = "normal" if rid else "disabled"
        self.issue_edit_button.configure(state=available)
        self.issue_ack_button.configure(state=available)
        self.issue_source_button.configure(state="normal" if item else "disabled")
        if item:
            record = self.session.get_record(rid) if rid else {}
            context = "Toàn file" if not rid else (
                f"Container {record.get('Container_No') or 'chưa có số'} · B/L {record.get('BL_No') or 'chưa có số'}")
            value = issue_raw_value(item, record)
            body = (f"{context}\n{issue_field(item)} · {self.issue_locations[key]}\n\n{item['message']}")
            if value:
                body += f"\n\nGiá trị nguồn\n{value}"
            self._set_issue_panel(issue_title(item), body)
        elif group:
            title, count = group
            self._set_issue_panel(title, f"{count} vấn đề trong nhóm. Mở nhóm và chọn từng dòng để xem nguồn "
                                         "và cách xử lý. Với lỗi toàn file, kiểm tra nguồn hoặc cấu hình đọc.")
        else:
            self._set_issue_panel("Chi tiết đối chiếu", "Chọn một vấn đề để xem thông báo và nguồn.")

    def _show_issue_source(self):
        selected = self.issue_tree.selection()
        key = selected[0] if selected and self.session and not self.busy else None
        item = self.issue_items.get(key)
        if not item:
            return
        rid = self.issue_records[key]
        record = self.session.get_record(rid) if rid else {}
        dialog = tk.Toplevel(self.root)
        dialog.title("Nguồn vấn đề")
        dialog.transient(self.root)
        _fit_dialog(dialog, self.root, (740, 460), (425, 280))
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=PAD)
        frame.pack(fill="both", expand=True)
        ttk.Button(frame, text="Đóng", command=dialog.destroy).pack(side="bottom", anchor="e", pady=(GAP, 0))
        name = self.selected_path.name if self.selected_path else ""
        _wrapped_label(frame, text=f"{name} · {self.issue_locations[key]}", font=FONT_BOLD).pack(anchor="w", pady=(0, GAP))
        text = self._read_only_text(frame)
        value = issue_raw_value(item, record)
        text.insert("1.0", value or "Chưa lưu nguyên văn cho vấn đề này. Đối chiếu vị trí trên manifest gốc.\n\n" + item["message"])
        text.configure(state="disabled")
        text.focus_set()
        dialog.bind("<Escape>", lambda _: dialog.destroy())

    def _set_configuration(self, text):
        self.configuration.set(text)
        label = getattr(self, "configuration_label", None)
        if label is None:
            return
        if text:
            label.pack(anchor="w", after=self.summary_label)
        else:
            label.pack_forget()

    def _fit_identifier_columns(self, records):
        """Widen identifier columns to the longest value so B/L and seal numbers are never cut off."""
        if not isinstance(self.tree, ttk.Treeview):
            return  # Display-free regression doubles have no font metrics.
        font = tkfont.Font(root=self.root, font=FONT)
        padding, cap = _pixels(self.root, 20), _pixels(self.root, 320)
        floors = self.__dict__.get("column_floor", {})
        for key in IDENTIFIER_COLUMNS:
            texts = {seal_text(record.get(key)) if key == "Seal_No" else text_value(record.get(key)) for record in records}
            widest = max((font.measure(text) for text in texts if text), default=0)
            width = min(cap, max(floors.get((str(self.tree), key), 0), widest + padding))
            self.tree.column(key, width=width, minwidth=width)

    def _columns(self, table, fields, *, stretchy=(), numeric=(), sortable=False):
        font = tkfont.Font(root=self.root, font=FONT_BOLD)
        heading_padding = _pixels(self.root, 20)
        for key, name, base in fields:
            width = max(_pixels(self.root, base), font.measure(name + (" ↓" if sortable else "")) + heading_padding)
            self.__dict__.setdefault("column_floor", {})[(str(table), key)] = width
            # Long free-text columns shrink before the table needs a horizontal scrollbar.
            minimum = min(width, _pixels(self.root, 120)) if key in stretchy else width
            table.column(key, width=width, minwidth=minimum, stretch=key in stretchy,
                         anchor="e" if key in numeric else "w")
            table.heading(key, text=name, anchor="w")
            if sortable:
                table.heading(key, command=lambda field=key: self.sort_by(field))

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
            self._update_export_state()
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
        self.read_override = (session.carrier, self.selected_path, copy.deepcopy(session.settings))
        self.dirty = False
        self.search.set("")
        self.only_issues.set(False)
        self.file_label.set(f"{self.selected_path.name}  |  Đã mở phiên: {Path(path).name}")
        self.reload_button.configure(state="normal")
        self.refresh()
        self.status.set("Đã khôi phục chỉnh sửa, xác nhận và dòng đã loại. Đang dùng cấu hình lưu trong phiên; chưa ghi đè settings.json.")

    def reprocess(self):
        if self.selected_path and not self.busy and self._confirm_discard():
            self._start(self.selected_path, read_settings=self._read_settings())

    def _read_settings(self):
        carrier = self.carrier.get()
        override = getattr(self, "read_override", None)
        if override and override[:2] == (carrier, self.selected_path):
            return dict(override[2])
        return dict(self.settings[carrier])

    def _start(self, path: Path, *, sheet=None, read_settings=None):
        self.busy = True
        self.session = None
        self.dirty = False
        self.selected_path = path
        carrier = self.carrier.get()
        self.read_override = None
        if read_settings is not None or sheet:
            settings = dict(read_settings if read_settings is not None else self.settings[carrier])
            if sheet:
                settings["selected_sheet"] = sheet
            self.read_override = (carrier, path, settings)
        self.file_label.set(path.name)
        self.summary.set("Đang đọc dữ liệu và áp dụng quy tắc hãng tàu…")
        self._set_configuration("")
        self.status.set("Đang xử lý. Cửa sổ vẫn có thể di chuyển và xem trạng thái.")
        for value in self.count_labels.values():
            value.set("—")
        self.table_counts = (0, 0)
        self.issue_count = 0
        self.tabs.tab(1, text="Cần kiểm tra")
        self.tree.delete(*self.tree.get_children())
        self.issue_tree.delete(*self.issue_tree.get_children())
        self.open_button.configure(state="disabled")
        self.resume_button.configure(state="disabled")
        self.reload_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.review_button.configure(state="disabled")
        self.carrier_box.configure(state="disabled")
        self._update_row_actions()
        self._update_table_states()
        self._issue_selected()
        self._update_export_state()
        self.progress.configure(mode="indeterminate")
        self.progress.start(15)
        settings = self._read_settings()
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
                    self.progress.configure(mode="determinate", value=0)
                    self.open_button.configure(state="normal")
                    self.resume_button.configure(state="normal")
                    self.reload_button.configure(state="normal")
                    self.carrier_box.configure(state="readonly")
                    if kind == "done":
                        self._complete_read(value)
                    else:
                        self.summary.set("Chưa xử lý được manifest. File gốc được giữ nguyên.")
                        self.status.set("Không đọc được manifest. Kiểm tra file và hãng đã chọn rồi bấm Xử lý lại.")
                        self._update_table_states()
                        self._update_export_state()
                        messagebox.showerror("Không xử lý được manifest",
                                             f"{value}\n\nKiểm tra file và hãng đã chọn, rồi bấm Xử lý lại.",
                                             parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _complete_read(self, session):
        self.session = session
        if getattr(self, "read_override", None):
            self.read_override = (session.carrier, self.selected_path, dict(session.settings))
        self.refresh()
        candidates = session.metadata.get("table_candidates") or []
        if not candidates:
            return
        sheet = self._choose_sheet(candidates)
        if sheet:
            self._start(self.selected_path, sheet=sheet, read_settings=self._read_settings())
        else:
            self.status.set("Chưa chọn sheet. Bấm Xử lý lại để chọn bảng của manifest này.")

    def _choose_sheet(self, candidates):
        by_name = {candidate["source_sheet"]: candidate for candidate in candidates}
        dialog = tk.Toplevel(self.root)
        dialog.title("Chọn sheet manifest")
        dialog.transient(self.root)
        _fit_dialog(dialog, self.root, (740, 390), (420, 260))
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=PAD)
        body.pack(fill="both", expand=True)
        actions = ttk.Frame(body)
        actions.pack(side="bottom", fill="x", pady=(GAP, 0))
        _wrapped_label(body, text="Tìm thấy nhiều bảng. Chọn sheet cần xử lý.").pack(anchor="w")
        selected = tk.StringVar(dialog)
        choice = ttk.Combobox(body, textvariable=selected, values=tuple(by_name), state="readonly")
        choice.pack(fill="x", pady=8)
        header = tk.StringVar(dialog, value="Chọn tên sheet để xem dòng tiêu đề và mẫu dữ liệu.")
        _wrapped_label(body, textvariable=header).pack(anchor="w")
        preview = tk.Text(body, height=6, wrap="word", state="disabled", padx=6, pady=6)
        preview.pack(fill="both", expand=True, pady=(6, 0))
        picked = None

        def confirm():
            nonlocal picked
            if selected.get() in by_name:
                picked = selected.get()
                dialog.destroy()

        use = ttk.Button(actions, text="Dùng sheet này", command=confirm, state="disabled", style="Primary.TButton")
        use.pack(side="right")
        ttk.Button(actions, text="Hủy", command=dialog.destroy).pack(side="right", padx=(0, 8))

        def show_preview(_=None):
            candidate = by_name[selected.get()]
            header.set(f"Dòng tiêu đề: {candidate['header_row']}")
            preview.configure(state="normal")
            preview.delete("1.0", "end")
            for row in candidate.get("preview_rows", []):
                preview.insert("end", f"Dòng {row['source_row']}: {row['text']}\n")
            preview.configure(state="disabled")
            use.configure(state="normal")

        choice.bind("<<ComboboxSelected>>", show_preview)
        dialog.bind("<Return>", lambda _: confirm())
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        choice.focus_set()
        self.root.wait_window(dialog)
        return picked

    def _filter_severity(self, severity):
        if not self.session or self.busy:
            return
        self.severity_filter = severity
        self.tabs.select(1)
        self.refresh()
        self.issue_tree.focus_set()

    def _clear_filters(self):
        self.severity_filter = None
        self.only_issues.set(False)
        self.show_excluded.set(False)
        if self.search.get():
            self.search.set("")  # Its trace refreshes both tables.
        else:
            self.refresh()

    def _tab_changed(self, _=None):
        self._issue_selected()
        self._update_table_states()

    def _update_table_states(self):
        if self.busy:
            messages = ["Đang đọc manifest…"] * 2
        elif not self.session:
            message = "Kiểm tra file rồi bấm Xử lý lại." if self.selected_path else "Chọn hãng rồi bấm Mở manifest."
            messages = [message] * 2
        else:
            data_empty = ("Không có kết quả. Bấm Xóa bộ lọc để xem lại."
                          if self.session.records else "Chưa có dòng container. Xem tab Cần kiểm tra.")
            issue_empty = ("Không có cảnh báo hoặc lỗi." if not self.table_counts[1]
                           else "Không có kết quả. Bấm Xóa bộ lọc để xem lại.")
            messages = [data_empty, issue_empty]
        tables = (self.tree, self.issue_tree)
        for table, label, message in zip(tables, self.empty_labels, messages):
            if not table.get_children():
                label.configure(text=message)
                label.place(relx=.5, rely=.44, anchor="center", relwidth=.85)
            else:
                label.place_forget()
        self._update_issue_panel_visibility()
        if not self.session:
            self.filter_status.set("")
            return
        active = self.tabs.index(self.tabs.select())
        count = self.issue_count if active else len(self.tree.get_children())
        level = {"error": "Lỗi chặn", "warning": "Cảnh báo"}.get(self.severity_filter)
        self.filter_status.set(f"{count} / {self.table_counts[active]} kết quả" + (f" · Mức: {level}" if level else ""))

    def _update_export_state(self, stats=None):
        if self.busy:
            hint = "Đang đọc manifest. Chờ xử lý xong."
        elif self.session is None:
            hint = "Đọc lại manifest để xuất." if self.selected_path else "Mở manifest để xuất."
        elif self.session.carrier != self.carrier.get():
            hint = "Hãng đã đổi. Bấm Xử lý lại trước khi xuất."
        elif self.session.metadata.get("settings_changed") or self.session.settings != self._read_settings():
            hint = "Cấu hình đã đổi. Bấm Xử lý lại trước khi xuất."
        elif stats["errors"]:
            hint = f"Còn {stats['errors']} lỗi chặn xuất. Xem tab Cần kiểm tra."
        else:
            hint = ""
        self.export_hint.set(hint)
        self.export_button.configure(state="disabled" if hint else "normal")
        self.open_button.configure(style="Primary.TButton" if hint else "TButton")

    @staticmethod
    def _selection_snapshot(table):
        selection = table.selection()
        children = table.get_children()
        old_focus = selection[0] if selection and selection[0] in children else None
        return old_focus, children.index(old_focus) if old_focus else 0

    @staticmethod
    def _restore_selection(table, key, position):
        children = table.get_children()
        if not children:
            return
        target = key if key in children else children[min(position, len(children) - 1)]
        table.selection_set(target)
        table.focus(target)
        table.see(target)

    def refresh(self):
        if not self.session:
            self._update_table_states()
            self._update_export_state()
            return
        session = self.session
        issues = [item for item in session.validate() if item.get("severity") in {"error", "warning"}]
        stats = session.statistics()
        for key, value in self.count_labels.items():
            value.set(str(stats[key]))
        self.table_counts = (len(session.records), len(issues))
        self.summary.set(f"{session.carrier} · {stats['bills']} B/L · {stats['active_records']} dòng"
                         + (f" · {stats['unknown']} chưa rõ F/E" if stats["unknown"] else "")
                         + (f" · Sheet {_sheet_description(session)}"
                            if len(session.metadata.get("available_sheets") or ()) > 1 else "")
                         + "".join(" · " + note for note in _runtime_exceptions(session)))
        # Reading settings stay in the settings dialog and the JSON; only reconciliation is shown here.
        self._set_configuration(_reconciliation_description(session))
        self.tabs.tab(1, text=f"Cần kiểm tra ({len(issues)})")
        current, position = self._selection_snapshot(self.tree)
        self.tree.delete(*self.tree.get_children())
        active_issues = [item for item in issues if self.severity_filter in (None, item["severity"])]
        per_record = {}
        for item in issues:
            per_record.setdefault(str(item.get("record_id")), []).append(item)
        filtered_records = {str(item.get("record_id")) for item in active_issues}
        status_by_record = {}
        for row in session.records:
            rid = row["record_id"]
            findings = per_record.get(rid, ())
            if row.get("_excluded"):
                status_by_record[rid] = ("Đã loại", "excluded")
            elif findings:
                errors = sum(item["severity"] == "error" for item in findings)
                status_by_record[rid] = (f"{errors} lỗi", "error") if errors else (f"{len(findings)} cảnh báo", "warning")
            elif row.get("_manual_review_reason"):
                status_by_record[rid] = ("Đã đối chiếu", "")
            else:
                status_by_record[rid] = ("Đủ dữ liệu", "")
        rows = list(session.records)
        if self.sort_field:
            key = self.sort_field

            def sort_value(record):
                if key == "status":
                    return status_by_record[record["record_id"]][0].casefold()
                if key != "Weight_Value":
                    return text_value(record.get(key)).casefold()
                try:
                    return float(record.get(key) or 0)
                except (TypeError, ValueError):
                    return float("inf")

            rows.sort(key=sort_value, reverse=self.sort_reverse)
        query = self.search.get().casefold().strip()
        matches = set()
        for record in rows:
            rid = record["record_id"]
            row_issues = per_record.get(rid, ())
            if query:
                record_text = [text_value(value) for field, value in record.items()
                               if field not in {"raw", "rules", "Warning"}]
                record_text.extend(f"{issue_title(item)} {text_value(item.get('message'))}" for item in row_issues)
                if query not in " ".join(record_text).casefold():
                    continue
            matches.add(rid)
            if record.get("_excluded") and not self.show_excluded.get():
                continue
            if (self.only_issues.get() or self.severity_filter) and rid not in filtered_records:
                continue
            label, tag = status_by_record[rid]
            values = (label, record.get("Container_No", ""), seal_text(record.get("Seal_No")),
                      record.get("BL_No", ""), record.get("VTOS_Size", ""),
                      record.get("Operator", ""), record.get("FE_Status", ""),
                      text_value(record.get("Weight_Value")) + WEIGHT_PAD if _present_text(record.get("Weight_Value")) else "",
                      record.get("Cleaned_Consignee_Name_For_Output", ""), record.get("Description", ""))
            self.tree.insert("", "end", iid=rid, values=values, tags=(tag,))
        self._fit_identifier_columns(session.records)
        self._restore_selection(self.tree, current, position)
        self._refresh_issues(active_issues, query, matches)
        self._update_export_state(stats)
        self.review_button.configure(state="normal")
        self._tab_changed()
        if stats["errors"]:
            next_step = ""  # The reason beside the export button already points to the blocking errors.
        elif stats["warnings"]:
            next_step = "Xem cảnh báo trong mục Cần kiểm tra. Có thể xác nhận để tiếp tục xuất."
        else:
            next_step = "Có thể xuất. Mở từng dòng để xem bằng chứng từ nguồn."
        self.status.set(f"Đã đọc {stats['detected_records']} bản ghi. {next_step}".strip())

    def _refresh_issues(self, findings, query, matches):
        tree = self.issue_tree
        groups_open = {group: tree.item(group, "open") for group in tree.get_children()}
        old_selection = tree.selection()
        current = old_selection[0] if old_selection else None
        old_key = self.issue_keys.get(current)
        old_leaves = list(self.issue_items)
        position = old_leaves.index(current) if current in old_leaves else 0
        tree.delete(*tree.get_children())
        self.issue_records = {}
        self.issue_items = {}
        self.issue_groups = {}
        self.issue_locations = {}
        self.issue_keys = {}
        records = {row["record_id"]: row for row in self.session.records}
        grouped = {}
        for item in findings:
            rid = item.get("record_id")
            record = records.get(str(rid), {}) if rid else {}
            source = issue_location(item, record, self.session.carrier, self.session.metadata)
            label = "Lỗi" if item["severity"] == "error" else "Cảnh báo"
            field = issue_field(item)
            title = issue_title(item)
            message = item["message"]
            if query and str(rid) not in matches and query not in f"{title} {label} {field} {message} {source}".casefold():
                continue
            grouped.setdefault(item["code"], []).append((item, rid, record, label, issue_field(item, compact=True), source))
        next_selection = None
        for code, entries in grouped.items():
            group = f"group-{code}"
            title = issue_title(entries[0][0])
            self.issue_groups[group] = (title, len(entries))
            tree.insert("", "end", iid=group, text=f"{title} ({len(entries)})",
                        open=groups_open.get(group, True), tags=("group",))
            for item, rid, record, label, field, source in entries:
                leaf = f"issue-{len(self.issue_items)}"
                self.issue_records[leaf] = str(rid) if rid else None
                self.issue_items[leaf] = item
                self.issue_locations[leaf] = source
                key = (str(rid), code, item["message"], source)
                self.issue_keys[leaf] = key
                tree.insert(group, "end", iid=leaf, text=record.get("Container_No") or ("Chưa có số" if rid else "Toàn file"),
                            values=(label, field, source), tags=(item["severity"],))
                if old_key == key:
                    next_selection = leaf
        leaves = list(self.issue_items)
        self.issue_count = len(leaves)
        if self.issue_count:
            if current in self.issue_groups:
                next_selection = current
            if next_selection is None:
                next_selection = leaves[min(position, len(leaves) - 1)]
                if not tree.item(tree.parent(next_selection), "open"):
                    next_selection = tree.parent(next_selection)
            tree.selection_set(next_selection)
            tree.focus(next_selection)
            tree.see(next_selection)

    def sort_by(self, field):
        self.sort_reverse = not self.sort_reverse if self.sort_field == field else False
        self.sort_field = field
        for key, label in self.data_headings.items():
            indicator = (" ↓" if self.sort_reverse else " ↑") if key == field else ""
            self.tree.heading(key, text=label + indicator)
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
        rid = self.selected_record_id(notify=False)
        state = "normal" if rid else "disabled"
        for button in (self.edit_button, self.ack_button, self.exclude_button):
            button.configure(state=state)
        will_exclude = rid and not self.session.get_record(rid).get("_excluded")
        self.exclude_button.configure(style="Danger.TButton" if will_exclude else "TButton")

    def _record_context(self, rid):
        record = self.session.get_record(rid)
        return f"Container: {record.get('Container_No') or '(chưa có số)'}\nB/L: {record.get('BL_No') or '(chưa có số)'}"

    def show_source_coverage(self):
        if not self.session or self.busy:
            return
        fragments = self.session.metadata.get("source_fragments") or []
        dialog = tk.Toplevel(self.root)
        dialog.title("Tra cứu các đoạn nguồn đã được ghi nhận")
        dialog.transient(self.root)
        _fit_dialog(dialog, self.root, (980, 630), (510, 355))
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        _wrapped_label(body, text="Đây là tình trạng tại lần đọc nguồn, không phải số lỗi còn lại sau chỉnh sửa. Tab Cần kiểm tra phản ánh lỗi hiện tại.",
                       style="Muted.TLabel").pack(anchor="w", pady=(0, GAP))
        if not fragments:
            _wrapped_label(body, text="Bộ đọc của phiên này chưa ghi danh sách đoạn nguồn. Vị trí và dữ liệu gốc của từng container vẫn có trong cửa sổ sửa.").pack(anchor="w")
            return
        labels = {"parsed": "Đã nhận diện", "unresolved": "Cần đối chiếu lúc đọc", "ignored": "Bỏ qua có lý do", "corroborating": "Bằng chứng đối chiếu"}
        counts = {key: sum(isinstance(item, dict) and item.get("status") == key for item in fragments) for key in labels}
        _wrapped_label(body, text="  ·  ".join(f"{label}: {counts[key]}" for key, label in labels.items()),
                       style="Muted.TLabel").pack(anchor="w", pady=(0, GAP))
        detail_frame = ttk.Frame(body)
        detail_frame.pack(side="bottom", fill="x", pady=(GAP, 0))
        detail = tk.Text(detail_frame, height=4, wrap="word", font=FONT, bg=SURFACE, fg=TEXT,
                         highlightbackground=BORDER, highlightcolor=FOCUS, padx=GAP, pady=GAP)
        scroll = ttk.Scrollbar(detail_frame, orient="vertical", command=detail.yview)
        scroll.pack(side="right", fill="y")
        detail.pack(side="left", expand=True, fill="x")
        detail.configure(yscrollcommand=scroll.set)
        table_frame = ttk.Frame(body)
        table_frame.pack(fill="both", expand=True)
        table = ttk.Treeview(table_frame, columns=("source", "status", "reason", "text"), show="headings", selectmode="browse")
        self._columns(table, (("source", "Vị trí nguồn", 116), ("status", "Tình trạng lúc đọc", 158),
                              ("reason", "Lý do", 168), ("text", "Nguyên văn", 350)), stretchy={"text"})
        self._scrollbars(table_frame, table)
        table.tag_configure("unresolved", background=WARNING_BG)
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
        table.bind("<Return>", lambda _: show_fragment())
        rows = table.get_children()
        if rows:
            table.selection_set(rows[0])
            table.focus(rows[0])
        table.focus_set()

    def open_issue(self, event=None):
        key = self.issue_tree.focus()
        if key in self.issue_groups:
            if event is None or event.type != tk.EventType.ButtonPress:
                self.issue_tree.item(key, open=not self.issue_tree.item(key, "open"))
            return "break"
        if key in self.issue_items:
            rid = self.issue_records[key]
            if rid and event is not None and event.type == tk.EventType.ButtonPress:
                self.edit_record(rid)
                return "break"
            self.issue_detail_open = True
            self._update_issue_panel_visibility()
            self._issue_selected()
        return "break"

    def edit_selected(self):
        rid = self.selected_record_id()
        if rid:
            self.edit_record(rid)

    def edit_record(self, rid):
        record = self.session.get_record(rid)
        original = {name: text_value(record.get(name)) for name in EDITABLE_FIELDS}
        original["Seal_No"] = seal_text(record.get("Seal_No"))
        record_issues = [item for item in self.session.validate() if item.get("record_id") == rid]
        review_issues = [item for item in record_issues if item.get("severity") in {"error", "warning"}]
        affected = {field for item in review_issues for field in (item.get("resolution_fields") or [item.get("field")]) if field}
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Đối chiếu container — {record.get('Container_No') or 'chưa có số'}")
        dialog.transient(self.root)
        _fit_dialog(dialog, self.root)
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=14)
        body.pack(fill="both", expand=True)
        footer = ttk.Frame(body)
        footer.pack(side="bottom", fill="x", pady=(8, 0))
        notebook = ttk.Notebook(body)
        notebook.pack(fill="both", expand=True)
        notebook.enable_traversal()
        edit_page, source_page = ttk.Frame(notebook), ttk.Frame(notebook)
        notebook.add(edit_page, text="Chỉnh sửa / xác nhận")
        notebook.add(source_page, text="Nguồn và giá trị xuất")
        edit_canvas, edit_tab = _scroll_area(edit_page)
        source_canvas, source_tab = _scroll_area(source_page)
        _bind_dialog_scroll(dialog, [(edit_canvas, edit_tab), (source_canvas, source_tab)])
        context = f"B/L: {record.get('BL_No') or '(chưa có số)'}  |  {Path(record.get('source_file') or '').name}  |  Sheet {record.get('source_sheet', '')} · dòng {record.get('source_row', '')}"
        _wrapped_label(edit_tab, text=context, font=FONT_BOLD).pack(anchor="w", pady=(0, 8))
        if record.get("_excluded"):
            reason = next((entry.get("reason", "") for entry in reversed(self.session.corrections)
                           if entry.get("record_id") == rid and entry.get("action") == "exclude"), "")
            if reason:
                _wrapped_label(edit_tab, text=f"Đã loại · {reason}", style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        for finding in review_issues:
            blocking = finding.get("severity") == "error"
            label = "Lỗi chặn xuất" if blocking else "Cảnh báo"
            style = "Issue.TLabel" if blocking else "TLabel"
            _wrapped_label(edit_tab, text=f"{label} · {finding.get('message', '')}", style=style).pack(anchor="w", pady=(0, 4))
        _wrapped_label(edit_tab, text="Dấu * chỉ trường liên quan lỗi hoặc cảnh báo. Tích xác nhận khi đã kiểm tra chính trường đó.", style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        _wrapped_label(edit_tab, text="Nút Lưu áp dụng vào phiên đang mở. Dùng Lưu đối chiếu để giữ sửa đổi và lý do trong file JSON.", style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        form = ttk.Frame(edit_tab)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        variables = {}
        verified = {}
        form_fields = []
        for index, name in enumerate(EDITABLE_FIELDS):
            field_name = FIELD_LABELS[name] + (" *" if name in affected else "")
            label = ttk.Label(form, text=field_name, style="Issue.TLabel" if name in affected else "TLabel")
            label.grid(row=index, column=0, sticky="w", padx=(0, 10), pady=4)
            variable = tk.StringVar(value=original[name])
            variables[name] = variable
            if name == "FE_Status":
                widget = ttk.Combobox(form, textvariable=variable, values=("F", "E", ""), state="readonly", width=12)
            else:
                widget = ttk.Entry(form, textvariable=variable, width=12)
            widget.grid(row=index, column=1, sticky="ew", padx=(0, 8), pady=4)
            verified[name] = tk.BooleanVar(value=False)
            check = ttk.Checkbutton(form, text="Đã đối chiếu", variable=verified[name])
            check.grid(row=index, column=2, sticky="w", pady=4)
            form_fields.append((label, widget, check))

        compact_form = None
        def reflow_form(event):
            nonlocal compact_form
            full_width = sum(max(row[column].winfo_reqwidth() for row in form_fields) for column in range(3)) + 24
            compact = event.width < full_width
            if compact == compact_form:
                return
            compact_form = compact
            form.columnconfigure(0, weight=int(compact))
            form.columnconfigure(1, weight=int(not compact))
            for index, (label, widget, check) in enumerate(form_fields):
                label.grid_configure(row=index * 2 if compact else index, columnspan=2 if compact else 1)
                field_row = index * 2 + 1 if compact else index
                widget.grid_configure(row=field_row, column=0 if compact else 1)
                check.grid_configure(row=field_row, column=1 if compact else 2)

        form.bind("<Configure>", reflow_form)
        _wrapped_label(edit_tab, text="Trọng lượng nhập bằng tấn. F là có hàng. E là rỗng.", style="Muted.TLabel").pack(anchor="w", pady=(8, 4))

        layout_issue = next((item for item in review_issues if item.get("code") in
                             {"VIMC_LAYOUT_AMBIGUOUS", "VIMC_SEAL_TYPE_AMBIGUOUS"}), None)
        candidate_fields = set(layout_issue.get("resolution_fields") or ()) if layout_issue else set()
        candidates = record.get("raw", {}).get("ambiguous_candidates", [])
        if candidates and candidate_fields:
            picker = ttk.Frame(edit_tab)
            picker.pack(fill="x", pady=(8, 0))
            includes_seal_type = {"Seal_No", "Size_Type"} <= candidate_fields
            descriptions = []
            for index, candidate in enumerate(candidates, 1):
                weight_text = f"{candidate.get('weight_raw', '')} {candidate.get('source_unit', '')}"
                seal_type = ""
                if includes_seal_type:
                    seal = seal_text(candidate.get("seal_no")) or "(trống)"
                    seal_type = f"Seal: {seal} · Cỡ: {candidate['size_type']} · "
                descriptions.append(f"{index}. {seal_type}{weight_text} · Hàng: {candidate.get('description', '')}")
            choice = tk.StringVar(value="")
            ttk.Label(picker, text="Cách đọc đã đối chiếu từ nguồn").pack(anchor="w")
            ttk.Combobox(picker, textvariable=choice, values=descriptions, state="readonly").pack(fill="x", pady=(5, 0))
            def use_candidate():
                if choice.get() not in descriptions:
                    messagebox.showinfo("Chọn cách đọc", "Đối chiếu dòng gốc rồi chọn một cách đọc. Ứng dụng không tự chọn thay bạn.", parent=dialog)
                    return
                candidate = candidates[descriptions.index(choice.get())]
                values = {"Description": candidate.get("description", "")}
                if "Weight_Value" in candidate_fields:
                    weight = parse_weight(candidate.get("weight_raw"), default_unit=candidate.get("source_unit") or "TONS", number_format=self.session.settings.get("number_format", "legacy"))
                    if weight is None:
                        messagebox.showerror("Chưa đọc được số", "Cách đọc này không phù hợp quy ước số hiện tại. Kiểm tra nguồn và cấu hình đọc.", parent=dialog)
                        return
                    values["Weight_Value"] = text_value(weight["value"])
                if includes_seal_type:
                    values.update(Seal_No=seal_text(candidate.get("seal_no")), Size_Type=candidate["size_type"])
                for field, value in values.items():
                    if field in candidate_fields:
                        variables[field].set(value)
                        verified[field].set(True)
                update_preview()
            button_text = f"Điền và xác nhận {len(candidate_fields)} trường"
            ttk.Button(picker, text=button_text, command=use_candidate).pack(anchor="e", pady=(5, 0))

        _wrapped_label(source_tab, text=context, font=FONT_BOLD).pack(anchor="w", pady=(0, 8))
        _wrapped_label(source_tab, text="Bảng này xem trước giá trị của các ô đang sửa. Các lỗi chưa xử lý vẫn chặn xuất file.", style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        preview_state = _wrapped_label(source_tab, text="", style="Muted.TLabel")
        preview_state.pack(anchor="w")
        source_raw = record.get("raw", {})
        original_text = source_raw.get("source_cell") or source_raw.get("container_cell") or source_raw.get("text")
        if original_text:
            source_text = tk.Text(source_tab, height=3, wrap="word", font=FONT, bg=SURFACE, fg=TEXT, relief="solid", borderwidth=1, padx=8, pady=5)
            source_text.pack(fill="x", pady=(0, 8))
            source_text.insert("1.0", "Nguyên văn nguồn: " + text_value(original_text))
            source_text.configure(state="disabled")
        comparison_frame = ttk.Frame(source_tab)
        comparison_frame.pack(fill="both", expand=True)
        comparison = ttk.Treeview(comparison_frame, columns=("field", "source", "output"), show="headings", height=12)
        self._columns(comparison, (("field", "Cột trong file nhập Cảng", 175),
                                   ("source", "Bằng chứng từ nguồn", 270),
                                   ("output", "Giá trị sẽ xuất", 260)),
                      stretchy={"source", "output"})
        self._scrollbars(comparison_frame, comparison)
        comparison.tag_configure("review", background=WARNING_BG)
        source_fields = {"Số BL": "BL_No", "Số Vận Đơn": "BL_No", "Số Container": "Container_No", "Số niêm chì": "Seal_No", "Số niêm chì 1": "Seal_No", "Chủ hàng": "Cleaned_Consignee_Name_For_Output", "Kích cỡ": "Size_Type", "Kích cỡ VTOS": "Size_Type", "Loại Container": "Size_Type", "Hãng khai thác": "Operator", "F/E": "FE_Status", "TL hàng": "Weight_Value", "Trọng lượng (Tấn)": "Weight_Value", "Hàng hóa": "Description"}
        def update_preview():
            # Only this record is copied. Engine validation and exporter rules
            # are shared with the real save/export path; no preview is persisted.
            projected = copy.copy(self.session)
            projected.records = [copy.deepcopy(item) if item["record_id"] == rid else item for item in self.session.records]
            projected.corrections = list(self.session.corrections)
            changes = {name: variable.get() for name, variable in variables.items() if variable.get() != original[name]}
            verified_fields = [name for name, variable in verified.items() if variable.get()]
            typed_reason = reason.get().strip()
            preview_state.configure(text="Chưa nhập lý do. Xem trước chưa có ghi chú cho sửa đổi này."
                                    if (changes or verified_fields) and not typed_reason else "")
            comparison.delete(*comparison.get_children())
            try:
                if changes or verified_fields:
                    projected.update_record(rid, changes, typed_reason or "Xem trước", verified_fields=verified_fields)
                    if not typed_reason:
                        projected.corrections = list(self.session.corrections)
                preview = preview_record_for_export(projected, projected.get_record(rid))
            except (ValueError, TypeError) as exc:
                comparison.insert("", "end", values=("Chưa xem trước được", "Kiểm tra các ô đang sửa", str(exc)), tags=("review",))
                return
            for column, value in preview.items():
                field = source_fields.get(column)
                output = seal_text(value) if field == "Seal_No" else text_value(value)
                comparison.insert("", "end", values=(column, _source_field(record, field) if field else "Theo quy tắc xuất", output), tags=("review",) if field in affected else ())
        notebook.bind("<<NotebookTabChanged>>", lambda _: update_preview())
        ttk.Button(source_tab, text="Cập nhật xem trước theo các ô đang sửa", command=update_preview).pack(anchor="e", pady=6)
        advanced = ttk.Frame(source_tab)
        advanced_visible = False
        details = tk.Text(advanced, height=7, wrap="word", font=FONT_MONO, bg=SURFACE, fg=TEXT, relief="flat", padx=8, pady=6)
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
        _wrapped_label(footer, text="Lý do / căn cứ đối chiếu (bắt buộc)").pack(anchor="w")
        reason = tk.StringVar()
        update_preview()
        reason_entry = ttk.Entry(footer, textvariable=reason)
        reason_entry.pack(fill="x", pady=(4, 6))
        buttons = ttk.Frame(footer)
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
                self.status.set("Đã ghi thay đổi vào phiên. Dùng Lưu đối chiếu để giữ thay đổi và lý do trong JSON.")
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Chưa lưu được", str(exc), parent=dialog)
        ttk.Button(buttons, text="Lưu chỉnh sửa / xác nhận", style="Primary.TButton", command=save).pack(side="right")
        ttk.Button(buttons, text="Hủy", command=dialog.destroy).pack(side="right", padx=8)

        def save_key(_):
            save()
            return "break"

        def cancel_key(_):
            dialog.destroy()
            return "break"

        dialog.bind("<Control-s>", save_key)
        dialog.bind("<Control-Return>", save_key)
        reason_entry.bind("<Return>", save_key)
        dialog.bind("<Escape>", cancel_key)
        notebook.focus_set()

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
        if self.session.metadata.get("settings_changed") or self.session.settings != self._read_settings():
            messagebox.showinfo("Quy ước đã đổi", "Xử lý lại manifest để áp dụng quy ước mới trước khi xuất.", parent=self.root)
            return
        stats = self.session.statistics()
        if stats["errors"]:
            messagebox.showwarning("Cần xử lý lỗi", f"Còn {stats['errors']} lỗi. Mở mục Cần kiểm tra để xử lý.", parent=self.root)
            return
        if stats["warnings"] and not messagebox.askyesno(
            "Xuất khi còn cảnh báo",
            f"Phiên còn {stats['warnings']} cảnh báo trong mục Cần kiểm tra. Bạn muốn tiếp tục xuất Excel?",
            parent=self.root,
        ):
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
                self.export_directory = Path(result["excel"]).resolve().parent
                self.export_folder_button.grid()
                self.status.set(f"Đã xuất: {Path(path).name}  |  {stats['active_records']} dòng, {stats['containers']} container.")
                review_message = f"\nĐối chiếu để mở lại phiên: {review_path}" if review_path else "\nChưa lưu đối chiếu trong lần xuất này; dùng Lưu đối chiếu để giữ phiên làm việc."
                messagebox.showinfo("Đã xuất file", f"Excel nhập Cảng: {result['excel']}{review_message}\n\nGiữ đúng mẫu 16 cột của {self.session.carrier}.", parent=self.root)
            except Exception as exc:
                messagebox.showerror("Không xuất được", str(exc), parent=self.root)

    def open_export_folder(self):
        if self.export_directory is None:
            return
        try:
            os.startfile(str(self.export_directory))
        except (AttributeError, OSError) as exc:
            messagebox.showerror("Không mở được thư mục",
                                 f"Mở thủ công thư mục {self.export_directory}.\n\n{exc}", parent=self.root)

    def save_review(self):
        if not self.session:
            return
        path = filedialog.asksaveasfilename(title="Lưu bản đối chiếu", defaultextension=".json", filetypes=[("Đối chiếu JSON", "*.json")],
                                          initialfile=f"{self.selected_path.stem}_DOI_CHIEU.json", parent=self.root)
        if path:
            try:
                self.session.save_review(path)
                self.dirty = False
                self.status.set("Đã lưu phiên đối chiếu và lịch sử chỉnh sửa vào JSON. Khi mở lại, cần đúng file manifest gốc.")
            except Exception as exc:
                messagebox.showerror("Không lưu được", str(exc), parent=self.root)

    def number_settings(self):
        if self.busy:
            return
        carrier = self.carrier.get()
        existing = self._read_settings()
        dialog = tk.Toplevel(self.root)
        dialog.title("Cấu hình đọc manifest")
        dialog.transient(self.root)
        _fit_dialog(dialog, self.root, (660, 400), (420, 290))
        dialog.grab_set()
        outer = ttk.Frame(dialog, padding=PAD)
        outer.pack(fill="both", expand=True)
        actions = ttk.Frame(outer)
        actions.pack(side="bottom", fill="x", pady=(GAP, 0))
        canvas, body = _scroll_area(outer)
        _bind_dialog_scroll(dialog, [(canvas, body)])
        ttk.Label(body, text=f"Hãng: {carrier}", font=FONT_BOLD).pack(anchor="w")
        choices = {"Theo mẫu hiện tại (mặc định)": "legacy", "Dấu phẩy thập phân: 25.000,50": "decimal_comma", "Dấu chấm thập phân: 25,000.50": "decimal_dot"}
        current = existing.get("number_format", "legacy")
        choice = tk.StringVar(value=next(k for k, v in choices.items() if v == current))
        ttk.Label(body, text="Quy ước số của dữ liệu dạng chữ").pack(anchor="w", pady=(14, 4))
        format_box = ttk.Combobox(body, textvariable=choice, values=list(choices), state="readonly", width=32)
        format_box.pack(fill="x")
        _wrapped_label(body, text="Trọng lượng manifest gồm vỏ container và hàng bên trong.").pack(anchor="w", pady=(GAP, 0))
        _wrapped_label(body, text="Sheet cần xử lý (có thể nhập đúng tên sheet)").pack(anchor="w", pady=(GAP, 4))
        automatic = "Theo quy tắc nhận diện của hãng"
        available = self.session.metadata.get("available_sheets", []) if self.session else []
        sheet_choice = tk.StringVar(value=existing.get("selected_sheet") or automatic)
        ttk.Combobox(body, textvariable=sheet_choice, values=[automatic, *available], state="normal").pack(fill="x")
        _wrapped_label(body, text="Quy ước dấu thập phân áp dụng cho các ô dạng chữ. Bấm Xử lý lại để dùng cấu hình mới. Các chỉnh sửa của phiên cũ nằm trong bản đối chiếu đã lưu.", style="Muted.TLabel").pack(anchor="w", pady=(GAP, 0))
        def save():
            updated = copy.deepcopy(existing)
            updated["number_format"] = choices[choice.get()]
            selected_sheet = sheet_choice.get().strip()
            if selected_sheet and selected_sheet != automatic:
                updated["selected_sheet"] = selected_sheet
            else:
                updated.pop("selected_sheet", None)
            try:
                updated = validate_carrier_settings(carrier, updated, preserve_weight_kind=True)
            except ValueError as exc:
                messagebox.showerror("Cấu hình chưa hợp lệ", str(exc), parent=dialog)
                return
            if updated == existing:
                dialog.destroy()
                return
            # Only persist the fields changed here, not settings held by a
            # saved review or the sheet picked for this specific workbook.
            defaults = dict(self.settings[carrier])
            for key in ("number_format", "selected_sheet"):
                if updated.get(key) != existing.get(key):
                    if key in updated:
                        defaults[key] = updated[key]
                    else:
                        defaults.pop(key, None)
            self.settings[carrier] = defaults
            try:
                self.config_path.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                messagebox.showwarning("Cấu hình", "Đã áp dụng trong phiên này; thư mục ứng dụng không cho lưu cấu hình lâu dài.", parent=dialog)
            if self.session and self.session.carrier == carrier:
                self.read_override = (carrier, self.selected_path, updated)
                self.export_button.configure(state="disabled")
                self.status.set("Quy ước số đã đổi. Bấm Xử lý lại để áp dụng trước khi xuất.")
                self.session.metadata["settings_changed"] = True
                self.dirty = True
                self.refresh()
                self.status.set("Cấu hình đọc đã đổi. Lưu đối chiếu nếu cần giữ các sửa đổi, rồi bấm Xử lý lại để áp dụng trước khi xuất.")
            dialog.destroy()
        ttk.Button(actions, text="Lưu cấu hình", style="Primary.TButton", command=save).pack(side="right")
        dialog.bind("<Return>", lambda _: save())
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        format_box.focus_set()

    def help(self):
        messagebox.showinfo("Hướng dẫn nhanh",
            "1. Chọn hãng tàu và mở manifest.\n"
            "2. Xem tab Cần kiểm tra. Nhấp đúp một mục để mở đúng dòng. Lỗi chặn xuất Excel. Cảnh báo vẫn cho phép xuất sau khi xác nhận.\n"
            "3. Trong cửa sổ sửa, chỉ tích Đã đối chiếu với trường vừa kiểm tra. Tab Nguồn và giá trị xuất cho thấy nguồn và giá trị dự kiến.\n"
            "4. Nhập lý do rồi bấm Lưu chỉnh sửa / xác nhận để áp dụng vào phiên. Lưu đối chiếu ghi các sửa đổi và lịch sử vào JSON. "
            "Xuất Excel mặc định lưu kèm JSON. Mở lại JSON cần đúng manifest gốc chưa thay đổi.\n\n"
            "Cửa sổ sửa — Ctrl+S hoặc Ctrl+Enter để lưu, Esc để hủy. Nhấn Enter khi đang nhập lý do cũng lưu.\n"
            "Cửa sổ chính — Ctrl+O mở manifest, Ctrl+S xuất Excel, F1 xem hướng dẫn.", parent=self.root)

    def close(self):
        if self.busy and not messagebox.askyesno("Đang xử lý", "Đóng ứng dụng và dừng phiên đang xử lý?", parent=self.root):
            return
        if self._confirm_discard():
            self.root.destroy()


def main():
    _enable_dpi_awareness()
    root = tk.Tk()
    ManifestApp(root)
    root.mainloop()
