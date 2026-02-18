import tkinter as tk
from tkinter import messagebox
import subprocess
import threading
import os
from io import BytesIO

# Deine Minecraft-Version für Filter
MC_VERSION = "1.21.11"

# Module testen
try:
    import requests
    from PIL import Image, ImageTk
except Exception as e:
    messagebox.showerror(
        "Fehlendes Modul",
        f"Ein benötigtes Modul fehlt:\n\n{e}\n\nBitte installiere:\npython -m pip install requests pillow"
    )
    raise

minecraft_process = None
logging_enabled = False

# Caches
icon_cache = {}      # project_id -> PhotoImage
versions_cache = {}  # project_id -> versions JSON
page_cache = {}      # (category, query, page) -> data JSON

# ---------------------------
#  LOG-FUNKTION MIT FARBEN
# ---------------------------
def log(text):
    if not logging_enabled:
        return

    if "ERROR" in text or "Exception" in text:
        tag = "red"
    elif "WARN" in text:
        tag = "yellow"
    else:
        tag = "lime"

    log_box.insert(tk.END, text + "\n", tag)
    log_box.see(tk.END)

# ---------------------------
#  MOD/WORLD/PACK LISTE
# ---------------------------
def show_content_list():
    log_box.delete("1.0", tk.END)

    base = os.getcwd()
    mc = os.path.join(base, ".minecraft")

    sections = {
        "🧩 Mods": os.path.join(mc, "mods"),
        "📦 Datapacks": os.path.join(mc, "saves"),
        "🌍 Worlds / Saves": os.path.join(mc, "saves"),
        "🎨 Resourcepacks": os.path.join(mc, "resourcepacks")
    }

    for title, path in sections.items():
        log_box.insert(tk.END, f"\n{title}\n", "header")
        log_box.insert(tk.END, "─" * 80 + "\n", "line")

        if not os.path.exists(path):
            log_box.insert(tk.END, "  (Ordner nicht gefunden)\n", "gray")
            continue

        items = os.listdir(path)
        if not items:
            log_box.insert(tk.END, "  (leer)\n", "gray")
            continue

        for item in items:
            log_box.insert(tk.END, f"  • {item}\n", "white")

    log_box.see(tk.END)

# ---------------------------
#  MINECRAFT STARTEN
# ---------------------------
def start_minecraft():
    global minecraft_process

    set_stop_button()

    base = os.getcwd()
    mc_dir = os.path.join(base, ".minecraft")
    mc_version = MC_VERSION

    # Loader suchen
    loader = None
    for root_dir, dirs, files in os.walk(os.path.join(mc_dir, "libraries")):
        for f in files:
            if f.startswith("fabric-loader-") and f.endswith(".jar"):
                loader = os.path.join(root_dir, f)
                break
        if loader:
            break

    if not loader:
        log("❌ Kein Fabric Loader gefunden")
        set_start_button()
        return

    # Minecraft JAR
    mcjar = os.path.join(mc_dir, "versions", mc_version, f"{mc_version}.jar")

    if not os.path.exists(mcjar):
        log(f"❌ Minecraft JAR nicht gefunden: {mcjar}")
        set_start_button()
        return

    # Classpath bauen
    libs = []
    for root_dir, dirs, files in os.walk(os.path.join(mc_dir, "libraries")):
        for f in files:
            if f.endswith(".jar"):
                libs.append(os.path.join(root_dir, f))

    cp = ";".join([loader, mcjar] + libs)

    # Java starten OHNE Host-Konsole
    minecraft_process = subprocess.Popen(
        [
            "java",
            "-Xmx4G",
            "-Xms2G",
            "-cp", cp,
            "net.fabricmc.loader.impl.launch.knot.KnotClient",
            "--gameDir", mc_dir
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    for line in minecraft_process.stdout:
        log(line.rstrip())

    set_start_button()

def start_thread():
    threading.Thread(target=start_minecraft, daemon=True).start()

# ---------------------------
#  STOP-FUNKTION
# ---------------------------
def stop_minecraft():
    global minecraft_process
    if minecraft_process and minecraft_process.poll() is None:
        minecraft_process.terminate()
        log("⛔ Minecraft gestoppt")
    set_start_button()

# ---------------------------
#  BUTTON-STATES
# ---------------------------
def set_start_button():
    start_button.config(
        text="Start",
        bg="#4CAF50",
        activebackground="#449d48",
        command=start_thread
    )

def set_stop_button():
    start_button.config(
        text="Stop",
        bg="#d9534f",
        activebackground="#c9302c",
        command=stop_minecraft
    )

# ---------------------------
#  ORDNER ÖFFNEN
# ---------------------------
def open_folder():
    mc_dir = os.path.join(os.getcwd(), ".minecraft")
    os.startfile(mc_dir)

# ---------------------------
#  LOGGING AN/AUS
# ---------------------------
def toggle_logs():
    global logging_enabled
    logging_enabled = log_var.get()

    if logging_enabled:
        log_box.delete("1.0", tk.END)
        log("✔ Logs aktiviert")
    else:
        show_content_list()

# ---------------------------
#  ICON LADE-FUNKTION (mit Cache + Thread)
# ---------------------------
def load_icon_async(project_id, icon_url, label):
    if project_id in icon_cache:
        # Direkt aus Cache
        img_tk = icon_cache[project_id]
        label.config(image=img_tk)
        label.image = img_tk
        return

    def worker():
        img_tk_local = None
        if icon_url:
            try:
                img_data = requests.get(icon_url, timeout=10).content
                img = Image.open(BytesIO(img_data)).resize((64, 64))
                img_tk_local = ImageTk.PhotoImage(img)
            except:
                img_tk_local = None

        def apply():
            if img_tk_local:
                icon_cache[project_id] = img_tk_local
                label.config(image=img_tk_local)
                label.image = img_tk_local

        root.after(0, apply)

    threading.Thread(target=worker, daemon=True).start()

# ---------------------------
#  MODRINTH-FENSTER
# ---------------------------
def open_modrinth_window():
    mod_window = tk.Toplevel(root)
    mod_window.title("Add Content – Modrinth")
    mod_window.state("zoomed")
    mod_window.configure(bg="#121212")

    # State für Suche / Kategorie / Seite
    state = {
        "category": "mod",   # mod, shader, resourcepack, datapack
        "query": "",
        "page": 0,
        "pages": 1,
        "limit": 20
    }

    CATEGORY_MAP = {
        "Mods": "mod",
        "Shader": "shader",
        "Resourcepacks": "resourcepack",
        "Datapacks": "datapack"
    }

    # Kategorie-Buttons
    cat_frame = tk.Frame(mod_window, bg="#121212")
    cat_frame.pack(pady=10)

    def set_category(cat_key):
        state["category"] = CATEGORY_MAP[cat_key]
        state["page"] = 0
        search_var.set("")  # leeren → Top für Kategorie
        load_modrinth_page(state, scroll_frame, pagination_frame)

    for label in CATEGORY_MAP.keys():
        b = tk.Button(
            cat_frame,
            text=label,
            font=("Segoe UI", 14),
            bg="#333333",
            fg="white",
            activebackground="#555555",
            activeforeground="white",
            bd=0,
            relief="flat",
            padx=15,
            pady=5,
            command=lambda l=label: set_category(l)
        )
        b.pack(side="left", padx=5)

    search_var = tk.StringVar()

    search_entry = tk.Entry(
        mod_window,
        textvariable=search_var,
        font=("Segoe UI", 16),
        width=40
    )
    search_entry.pack(pady=10)

    def on_search():
        state["query"] = search_var.get()
        state["page"] = 0
        load_modrinth_page(state, scroll_frame, pagination_frame)

    search_button = tk.Button(
        mod_window,
        text="Suchen",
        font=("Segoe UI", 16),
        bg="#3a8dde",
        fg="white",
        command=on_search
    )
    search_button.pack()

    result_frame = tk.Frame(mod_window, bg="#121212")
    result_frame.pack(fill="both", expand=True, pady=10)

    canvas = tk.Canvas(result_frame, bg="#121212", highlightthickness=0)
    scrollbar = tk.Scrollbar(result_frame, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg="#121212")

    scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Pagination unten
    pagination_frame = tk.Frame(mod_window, bg="#121212")
    pagination_frame.pack(pady=10)

    # Beim Öffnen: Top-Mods (Kategorie Mods, leere Suche)
    load_modrinth_page(state, scroll_frame, pagination_frame)

def load_modrinth_page(state, parent_frame, pagination_frame):
    # UI leeren
    for widget in parent_frame.winfo_children():
        widget.destroy()

    category = state["category"]
    query = state["query"]
    page = state["page"]
    limit = state["limit"]
    offset = page * limit

    key = (category, query.strip(), page)

    def build_ui_from_data(data):
        hits = data.get("hits", [])
        total_hits = data.get("total_hits", len(hits))
        pages = max(1, (total_hits + limit - 1) // limit)
        state["pages"] = pages

        for hit in hits:
            mod_id = hit["project_id"]
            name = hit["title"]
            desc = hit["description"]
            icon_url = hit.get("icon_url")
            downloads = hit.get("downloads", 0)

            frame = tk.Frame(parent_frame, bg="#1e1e1e", pady=10)
            frame.pack(fill="x", padx=20, pady=10)

            # ICON-Label (wird async befüllt)
            icon_label = tk.Label(frame, bg="#1e1e1e")
            icon_label.pack(side="left", padx=10)

            # Icon async laden
            load_icon_async(mod_id, icon_url, icon_label)

            text_frame = tk.Frame(frame, bg="#1e1e1e")
            text_frame.pack(side="left", fill="x", expand=True)

            tk.Label(
                text_frame,
                text=name,
                font=("Segoe UI", 16, "bold"),
                fg="white",
                bg="#1e1e1e"
            ).pack(anchor="w")

            tk.Label(
                text_frame,
                text=f"Downloads: {downloads:,}",
                font=("Segoe UI", 10),
                fg="#888888",
                bg="#1e1e1e"
            ).pack(anchor="w")

            tk.Label(
                text_frame,
                text=desc,
                font=("Segoe UI", 12),
                fg="#cccccc",
                bg="#1e1e1e",
                wraplength=800,
                justify="left"
            ).pack(anchor="w")

            def install_mod(mod_id=mod_id, name=name):
                try:
                    if mod_id in versions_cache:
                        versions = versions_cache[mod_id]
                    else:
                        versions = requests.get(
                            f"https://api.modrinth.com/v2/project/{mod_id}/version",
                            timeout=10
                        ).json()
                        versions_cache[mod_id] = versions

                    file = None
                    for v in versions:
                        if MC_VERSION in v.get("game_versions", []):
                            if v.get("files"):
                                file = v["files"][0]
                                break

                    if not file:
                        messagebox.showerror("Fehler", "Keine Version für deine Minecraft-Version gefunden.")
                        return

                    file_url = file["url"]
                    file_name = file["filename"]

                    mods_folder = os.path.join(os.getcwd(), ".minecraft", "mods")
                    os.makedirs(mods_folder, exist_ok=True)

                    file_data = requests.get(file_url, timeout=20).content
                    with open(os.path.join(mods_folder, file_name), "wb") as f:
                        f.write(file_data)

                    messagebox.showinfo("Installiert", f"{name} wurde installiert!")
                    if not logging_enabled:
                        show_content_list()
                except Exception as e:
                    messagebox.showerror("Fehler", f"Installation fehlgeschlagen:\n{e}")

            install_button = tk.Button(
                frame,
                text="Installieren",
                font=("Segoe UI", 12),
                bg="#4CAF50",
                fg="white",
                activebackground="#449d48",
                activeforeground="white",
                command=install_mod
            )
            install_button.pack(side="right", padx=20)

        # Pagination-UI neu aufbauen
        for w in pagination_frame.winfo_children():
            w.destroy()

        def go_page(p):
            if 0 <= p < state["pages"]:
                state["page"] = p
                load_modrinth_page(state, parent_frame, pagination_frame)

        prev_btn = tk.Button(
            pagination_frame,
            text="«",
            font=("Segoe UI", 12),
            bg="#333333",
            fg="white",
            bd=0,
            relief="flat",
            command=lambda: go_page(state["page"] - 1)
        )
        prev_btn.pack(side="left", padx=5)

        max_buttons = min(10, pages)
        start_page = max(0, min(state["page"] - 4, pages - max_buttons))
        end_page = start_page + max_buttons

        for p in range(start_page, end_page):
            txt = str(p + 1)
            bg = "#3a8dde" if p == state["page"] else "#333333"
            b = tk.Button(
                pagination_frame,
                text=txt,
                font=("Segoe UI", 12),
                bg=bg,
                fg="white",
                bd=0,
                relief="flat",
                width=3,
                command=lambda pp=p: go_page(pp)
            )
            b.pack(side="left", padx=2)

        next_btn = tk.Button(
            pagination_frame,
            text="»",
            font=("Segoe UI", 12),
            bg="#333333",
            fg="white",
            bd=0,
            relief="flat",
            command=lambda: go_page(state["page"] + 1)
        )
        next_btn.pack(side="left", padx=5)

    # Wenn Seite im Cache → direkt UI bauen
    if key in page_cache:
        build_ui_from_data(page_cache[key])
        return

    # Sonst: im Thread laden
    def worker():
        base_url = "https://api.modrinth.com/v2/search"
        facets = f'[[\"project_type:{category}\"]]'
        if not query.strip():
            url = (
                f"{base_url}?query=&facets={facets}"
                f"&versions=[\"{MC_VERSION}\"]"
                f"&index=downloads&limit={limit}&offset={offset}"
            )
        else:
            url = (
                f"{base_url}?query={query}"
                f"&facets={facets}"
                f"&versions=[\"{MC_VERSION}\"]"
                f"&limit={limit}&offset={offset}"
            )

        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            def err():
                messagebox.showerror("Fehler", f"Modrinth Anfrage fehlgeschlagen:\n{e}")
            root.after(0, err)
            return

        page_cache[key] = data

        def apply():
            build_ui_from_data(data)

        root.after(0, apply)

    threading.Thread(target=worker, daemon=True).start()

# ---------------------------
#  UI
# ---------------------------
root = tk.Tk()
root.title("Fabric Launcher")

root.state("zoomed")
root.configure(bg="#121212")

# Start/Stop Button
start_button = tk.Button(
    root,
    text="Start",
    font=("Segoe UI", 22, "bold"),
    bg="#4CAF50",
    fg="white",
    activebackground="#449d48",
    activeforeground="white",
    width=20,
    height=2,
    bd=0,
    relief="flat",
    command=start_thread
)
start_button.pack(pady=15)

# Logs Checkbox
log_var = tk.BooleanVar()
log_check = tk.Checkbutton(
    root,
    text="Logs anzeigen",
    variable=log_var,
    command=toggle_logs,
    font=("Segoe UI", 16),
    bg="#121212",
    fg="white",
    activebackground="#121212",
    activeforeground="white",
    selectcolor="#121212"
)
log_check.pack()

# Add Content Button (Modrinth)
add_content_button = tk.Button(
    root,
    text="➕ Add Content (Modrinth)",
    font=("Segoe UI", 16),
    bg="#3a8dde",
    fg="white",
    activebackground="#2f6fa8",
    activeforeground="white",
    width=25,
    height=1,
    bd=0,
    relief="flat",
    command=open_modrinth_window
)
add_content_button.pack(pady=10)

# Log / Content Fenster
log_box = tk.Text(
    root,
    bg="#1e1e1e",
    fg="white",
    insertbackground="white",
    font=("Consolas", 14),
    width=120,
    height=25,
    bd=0,
    relief="flat"
)
log_box.tag_config("red", foreground="red")
log_box.tag_config("yellow", foreground="yellow")
log_box.tag_config("lime", foreground="#00ff88")
log_box.tag_config("header", foreground="#00aaff", font=("Consolas", 14, "bold"))
log_box.tag_config("line", foreground="#555555")
log_box.tag_config("gray", foreground="#888888")
log_box.pack(pady=10)

# Folder Button
folder_button = tk.Button(
    root,
    text="📁 Ordner öffnen",
    font=("Segoe UI", 18),
    bg="#333333",
    fg="white",
    activebackground="#222222",
    activeforeground="white",
    width=25,
    height=2,
    bd=0,
    relief="flat",
    command=open_folder
)
folder_button.pack(pady=10)

# Beim Start: Mods/Worlds anzeigen
show_content_list()

try:
    root.mainloop()
except Exception as e:
    messagebox.showerror("Launcher Fehler", str(e))
    raise


