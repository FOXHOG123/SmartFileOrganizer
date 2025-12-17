# main.py
import os
import shutil
import csv
import json
from datetime import datetime
from pathlib import Path

from kivy.lang import Builder
from kivy.properties import (
    StringProperty,
    BooleanProperty,
    ListProperty,
    NumericProperty,
)
from kivy.utils import platform
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout

from kivymd.app import MDApp
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.dialog import MDDialog


# -----------------------------
# CATEGORY CONFIG
# -----------------------------

CATEGORY_MAP = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg", ".heic"],
    "Videos": [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm"],
    "Audio": [".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"],
    "Documents": [".doc", ".docx", ".txt", ".rtf", ".odt"],
    "PDFs": [".pdf"],
    "Spreadsheets": [".xls", ".xlsx", ".csv", ".ods"],
    "Presentations": [".ppt", ".pptx", ".odp"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Executables": [".exe", ".msi", ".bat", ".sh", ".apk"],
    "Code": [".py", ".java", ".cpp", ".c", ".js", ".php", ".html", ".css", ".ts", ".ipynb"],
}


def get_category(extension: str) -> str:
    extension = extension.lower()
    for category, ext_list in CATEGORY_MAP.items():
        if extension in ext_list:
            return category
    return "Others"


def guess_ai_category(entry: Path, base_category: str) -> str:
    """
    Simple 'AI' heuristic: if file is in Others,
    guess category from filename keywords.
    """
    if base_category != "Others":
        return ""

    name = entry.name.lower()

    if any(k in name for k in ["img", "image", "photo", "camera", "screenshot", "snap"]):
        return "Images"
    if any(k in name for k in ["video", "movie", "clip", "record"]):
        return "Videos"
    if any(k in name for k in ["doc", "report", "assignment", "notes", "letter"]):
        return "Documents"
    if any(k in name for k in ["music", "song", "audio", "track"]):
        return "Audio"

    return ""


def get_file_info(entry: Path, root_folder: Path):
    # ignore our own report files
    if entry.name in ("organized_index.csv", "organized_index.json"):
        return None

    ext = entry.suffix.lower()
    category = get_category(ext)
    ai_hint = guess_ai_category(entry, category)

    stat = entry.stat()
    size_bytes = stat.st_size
    modified_time = datetime.fromtimestamp(stat.st_mtime)
    relative_path = str(entry.relative_to(root_folder))

    return {
        "name": entry.name,
        "relative_path": relative_path,
        "full_path": str(entry.resolve()),
        "extension": ext if ext else "(no extension)",
        "category": category,
        "ai_hint": ai_hint,  # for "AI" suggestions
        "size_bytes": size_bytes,
        "modified_time": modified_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def scan_folder(folder_path: Path, recursive: bool = True):
    files_info = []

    if recursive:
        for dirpath, _, filenames in os.walk(folder_path):
            for filename in filenames:
                entry = Path(dirpath) / filename
                if entry.is_file():
                    info = get_file_info(entry, folder_path)
                    if info:
                        files_info.append(info)
    else:
        for entry in folder_path.iterdir():
            if entry.is_file():
                info = get_file_info(entry, folder_path)
                if info:
                    files_info.append(info)
    return files_info


def organize_files(root_folder: Path, files_info):
    if not files_info:
        return "No files found to organize."

    category_count = {}
    for info in files_info:
        category_count[info["category"]] = category_count.get(info["category"], 0) + 1

    result_lines = ["Summary by category:"]
    for cat, count in category_count.items():
        result_lines.append(f"  {cat}: {count} file(s)")

    for info in files_info:
        src = Path(info["full_path"])
        category_folder = root_folder / info["category"]
        category_folder.mkdir(exist_ok=True)

        dest = category_folder / src.name

        # Skip if already inside target folder
        if src.parent == category_folder:
            continue

        if dest.exists():
            base = dest.stem
            ext = dest.suffix
            counter = 1
            while True:
                new_name = f"{base} ({counter}){ext}"
                new_dest = category_folder / new_name
                if not new_dest.exists():
                    dest = new_dest
                    break
                counter += 1

        shutil.move(str(src), str(dest))

    result_lines.append("\nFiles have been organized into category folders.")
    return "\n".join(result_lines)


def export_reports(folder_path: Path, files_info):
    if not files_info:
        return "No files to export."

    csv_path = folder_path / "organized_index.csv"
    json_path = folder_path / "organized_index.json"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=files_info[0].keys())
        writer.writeheader()
        writer.writerows(files_info)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(files_info, f, indent=4)

    return f"Reports created:\n  CSV : {csv_path}\n  JSON: {json_path}"


def search_files(files_info, search_type: str, query: str):
    query_lower = query.lower()
    results = []
    for info in files_info:
        if search_type == "name":
            if query_lower in info["name"].lower():
                results.append(info)
        elif search_type == "extension":
            # allow with or without dot
            ext_query = query_lower.lstrip(".")
            if ext_query == info["extension"].lower().lstrip("."):
                results.append(info)
        elif search_type == "category":
            if (
                query_lower == info["category"].lower()
                or query_lower == info.get("ai_hint", "").lower()
            ):
                results.append(info)
    return results


# -----------------------------
# KIVY UI
# -----------------------------

class FolderChooser(BoxLayout):
    # will hold the current path to show in the label
    current_path = StringProperty("")


KV = """
<FolderChooser>:
    orientation: "vertical"
    size_hint_y: None
    height: dp(420)

    MDBoxLayout:
        size_hint_y: None
        height: dp(48)
        padding: dp(6)
        spacing: dp(6)

        MDIconButton:
            icon: "arrow-left"
            on_release: app.folder_chooser_go_back()

        MDLabel:
            id: current_path_label
            text: root.current_path
            font_style: "Caption"
            theme_text_color: "Custom"
            text_color: 0, 1, 0.5, 1
            shorten: True
            shorten_from: "left"

        MDRectangleFlatButton:
            text: "Select"
            on_release: app.on_folder_selected()

    MDSeparator:

    FileChooserListView:
        id: file_chooser
        dirselect: True

Screen:
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "Smart File Organizer"
            elevation: 2
            left_action_items: [["folder", lambda x: app.open_folder_picker()]]
            right_action_items: [["theme-light-dark", lambda x: app.toggle_theme()]]

        MDBoxLayout:
            orientation: "vertical"
            padding: dp(10)
            spacing: dp(10)

            MDTextField:
                id: folder_input
                text: app.folder_path
                hint_text: "Folder path (e.g. /storage/emulated/0/Download)"
                size_hint_y: None
                height: self.minimum_height

            MDBoxLayout:
                size_hint_y: None
                height: dp(40)
                spacing: dp(10)

                MDLabel:
                    text: "Scan subfolders"
                    halign: "left"

                MDSwitch:
                    id: recursive_switch
                    active: app.recursive
                    on_active: app.set_recursive(self.active)

            MDBoxLayout:
                size_hint_y: None
                height: dp(50)
                spacing: dp(10)

                MDRectangleFlatIconButton:
                    id: scan_btn
                    text: "Scan"
                    icon: "magnify-scan"
                    on_release: app.on_scan_pressed(self)

                MDRectangleFlatIconButton:
                    id: report_btn
                    text: "Report"
                    icon: "file-document-outline"
                    on_release: app.on_report_pressed(self)

                MDRectangleFlatIconButton:
                    id: organize_btn
                    text: "Organize"
                    icon: "folder-move-outline"
                    on_release: app.on_organize_pressed(self)

            MDSeparator:

            MDBoxLayout:
                size_hint_y: None
                height: dp(50)
                spacing: dp(10)

                MDTextField:
                    id: search_query
                    hint_text: "Search (name, ext, category)"
                    size_hint_x: 0.6

                MDRectangleFlatIconButton:
                    text: "Name"
                    icon: "text-search"
                    on_release: app.on_search_pressed("name", self)

                MDRectangleFlatIconButton:
                    text: "Ext"
                    icon: "file-code-outline"
                    on_release: app.on_search_pressed("extension", self)

                MDRectangleFlatIconButton:
                    text: "Cat"
                    icon: "shape"
                    on_release: app.on_search_pressed("category", self)

            MDSeparator:

            MDProgressBar:
                id: progress_bar
                value: app.progress
                size_hint_y: None
                height: dp(4)

            MDLabel:
                text: "Log Output"
                size_hint_y: None
                height: dp(20)

            ScrollView:
                MDLabel:
                    id: log_label
                    text: app.log_text
                    text_size: self.width, None
                    size_hint_y: None
                    height: self.texture_size[1]
                    padding: dp(10), dp(10)
                    theme_text_color: "Custom"
                    text_color: 0, 1, 0.5, 1
"""


class SmartFileOrganizerApp(MDApp):
    folder_path = StringProperty("")
    recursive = BooleanProperty(True)
    log_text = StringProperty("")
    files_info = ListProperty([])
    progress = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.folder_dialog = None

    def build(self):
        self.title = "Smart File Organizer"
        # techy dark theme
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "LightGreen"

        # Default folder for Android / others
        if platform == "android":
            self.folder_path = "/storage/emulated/0/Download"
        else:
            self.folder_path = str(Path.home() / "Downloads")

        return Builder.load_string(KV)

    # ---------- helpers ----------

    def append_log(self, text, clear=False):
        if clear:
            self.log_text = ""
        self.log_text += text + "\n"

    def show_snackbar(self, text):
        # Fallback: just log message instead of using Snackbar
        self.append_log(f"[INFO] {text}")

    def set_progress(self, value):
        self.progress = value

    def reset_progress(self, *args):
        self.progress = 0

    def animate_button(self, button):
        # simple tap animation: fade quickly
        anim = Animation(opacity=0.5, duration=0.05) + Animation(
            opacity=1.0, duration=0.05
        )
        anim.start(button)

    def get_root_folder(self):
        folder_widget = self.root.ids.get("folder_input")
        if folder_widget:
            path = folder_widget.text.strip()
        else:
            path = self.folder_path.strip()

        if not path:
            self.append_log("[ERROR] Folder path is empty")
            return None

        folder = Path(path)
        if not folder.exists() or not folder.is_dir():
            self.append_log("[ERROR] Invalid folder path")
            return None

        self.folder_path = path
        return folder

    def set_recursive(self, value: bool):
        self.recursive = value

    # ---------- folder picker ----------

    def open_folder_picker(self):
        start_path = (
            self.folder_path
            if self.folder_path
            else ("/storage/emulated/0" if platform == "android" else str(Path.home()))
        )

        if not self.folder_dialog:
            content = FolderChooser()
            self.folder_dialog = MDDialog(
                title="Select Folder",
                type="custom",
                content_cls=content,
                auto_dismiss=False,
            )
            self.folder_dialog.buttons = [
                MDRaisedButton(
                    text="Cancel",
                    on_release=lambda x: self.folder_dialog.dismiss(),
                ),
            ]
            self.folder_dialog.size_hint = (0.9, None)
            self.folder_dialog.height = dp(500)
        else:
            content = self.folder_dialog.content_cls

        content.current_path = start_path
        content.ids.file_chooser.path = start_path

        self.folder_dialog.open()

    def folder_chooser_go_back(self):
        """Go one level up in FileChooser."""
        if not self.folder_dialog:
            return
        content = self.folder_dialog.content_cls
        chooser = content.ids.file_chooser
        current = Path(chooser.path)
        parent = current.parent
        if str(parent) == str(current):
            return
        chooser.path = str(parent)
        content.current_path = chooser.path

    def on_folder_selected(self, *args):
        chooser = self.folder_dialog.content_cls.ids.file_chooser
        if chooser.selection:
            path = chooser.selection[0]
            p = Path(path)
            if p.is_file():
                p = p.parent
            self.folder_path = str(p)
            self.root.ids.folder_input.text = self.folder_path
            self.append_log(f"[INFO] Folder selected: {self.folder_path}")
        else:
            # if nothing selected, use current path
            current_path = chooser.path
            if current_path:
                self.folder_path = current_path
                self.root.ids.folder_input.text = self.folder_path
                self.append_log(f"[INFO] Folder selected: {self.folder_path}")
            else:
                self.append_log("[INFO] No folder selected")
        self.folder_dialog.dismiss()

    # ---------- theme ----------

    def toggle_theme(self):
        self.theme_cls.theme_style = (
            "Dark" if self.theme_cls.theme_style == "Light" else "Light"
        )

    # ---------- actions ----------

    def on_scan_pressed(self, button):
        self.animate_button(button)
        folder = self.get_root_folder()
        if not folder:
            return

        self.set_progress(10)
        self.append_log(f"Scanning: {folder} (recursive={self.recursive})", clear=True)
        try:
            self.files_info = scan_folder(folder, recursive=self.recursive)
        except Exception as e:
            self.append_log(f"[ERROR] Error while scanning: {e}")
            self.show_snackbar("Scan failed")
            self.set_progress(0)
            return

        if not self.files_info:
            self.append_log("No files found.")
            self.show_snackbar("No files")
            self.set_progress(0)
            return

        self.append_log(f"Found {len(self.files_info)} file(s).")

        category_count = {}
        for info in self.files_info:
            category_count[info["category"]] = category_count.get(info["category"], 0) + 1

        self.append_log("\nFiles by category:")
        for cat, count in category_count.items():
            self.append_log(f"  {cat}: {count} file(s)")

        # AI summary for Others
        ai_counts = {}
        for info in self.files_info:
            if info["category"] == "Others" and info.get("ai_hint"):
                ai_counts[info["ai_hint"]] = ai_counts.get(info["ai_hint"], 0) + 1

        if ai_counts:
            self.append_log("\nAI suggestions for 'Others':")
            for cat, count in ai_counts.items():
                self.append_log(f"  Maybe {cat}: {count} file(s)")

        self.show_snackbar("Scan complete")
        self.set_progress(100)
        Clock.schedule_once(self.reset_progress, 0.8)

    def on_report_pressed(self, button):
        self.animate_button(button)

        if not self.files_info:
            self.show_snackbar("Scan first")
            self.append_log("No data to report. Please scan first.")
            return

        folder = self.get_root_folder()
        if not folder:
            return

        self.set_progress(30)
        try:
            msg = export_reports(folder, self.files_info)
        except Exception as e:
            self.append_log(f"[ERROR] Error creating report: {e}")
            self.show_snackbar("Report failed")
            self.set_progress(0)
            return

        self.append_log("\n" + msg)
        self.show_snackbar("Report created")
        self.set_progress(100)
        Clock.schedule_once(self.reset_progress, 0.8)

    def on_organize_pressed(self, button):
        self.animate_button(button)

        if not self.files_info:
            self.show_snackbar("Scan first")
            self.append_log("No data to organize. Please scan first.")
            return

        folder = self.get_root_folder()
        if not folder:
            return

        self.append_log("\nOrganizing files (this may take a moment)...")
        self.set_progress(50)
        try:
            msg = organize_files(folder, self.files_info)
        except Exception as e:
            self.append_log(f"[ERROR] Error organizing: {e}")
            self.show_snackbar("Organize failed")
            self.set_progress(0)
            return

        self.append_log(msg)
        self.show_snackbar("Organize complete")
        self.set_progress(100)
        Clock.schedule_once(self.reset_progress, 0.8)

    def on_search_pressed(self, search_type: str, button):
        self.animate_button(button)

        if not self.files_info:
            self.show_snackbar("Scan first")
            self.append_log("No data for search. Please scan first.")
            return

        query_widget = self.root.ids.get("search_query")
        if not query_widget:
            return

        query = query_widget.text.strip()
        if not query:
            self.show_snackbar("Enter search text")
            return

        results = search_files(self.files_info, search_type, query)
        self.append_log(f"\nSearch ({search_type}) = '{query}'")
        self.append_log(f"Matches found: {len(results)}")

        for info in results[:50]:
            line = f"[{info['category']}] {info['relative_path']} ({info['size_bytes']} bytes)"
            if info.get("ai_hint"):
                line += f"  [AI: {info['ai_hint']}]"
            self.append_log(line)

        if len(results) > 50:
            self.append_log(f"...and {len(results) - 50} more results not shown.")

        self.show_snackbar("Search done")


if __name__ == "__main__":
    SmartFileOrganizerApp().run()