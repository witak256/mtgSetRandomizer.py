import io
import random
import re
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

import cairosvg
import requests
from PIL import Image, ImageTk


HEADERS = {
    "User-Agent": "MTGSetRandomizer/1.0",
    "Accept": "application/json",
}

SVG_HEADERS = {
    "User-Agent": "MTGSetRandomizer/1.0",
    "Accept": "image/svg+xml",
}

MAX_CACHE_SIZE = 25
ICON_CACHE = {}

ALLOWED_DROPDOWN_SET_TYPES = {"expansion", "masters", "core"}

def get_random_set_code_from_input():
    raw_text = set_codes_text.get("1.0", tk.END)

    set_codes = [
        code.strip().lower()
        for code in re.split(r"[\s,]+", raw_text)
        if code.strip()
    ]

    valid_set_codes = [
        code
        for code in set_codes
        if re.fullmatch(r"[a-z0-9]{2,6}", code)
    ]
    if not valid_set_codes:
        messagebox.showwarning(
            "No Valid Set Codes",
            "Please enter at least valid set codes (2-6 lowercase letters or numbers).\n\n"
            "Examples: khm, neo, dmu, 40k"
        )
        return None
    return random.choice(valid_set_codes)

def get_random_set_code():
    response = requests.get(
        "https://api.scryfall.com/sets",
        headers=HEADERS,
        timeout=10
    )
    response.raise_for_status()

    sets_data = response.json().get("data", [])

    if not sets_data:
        raise ValueError("No sets were returned by Scryfall.")

    return random.choice(sets_data)["code"]

def get_available_sets():
    response = requests.get(
        "https://api.scryfall.com/sets",
        headers=HEADERS,
        timeout=10
    )
    response.raise_for_status()

    try:
        sets_data = response.json()
    except requests.JSONDecodeError as error:
        raise ValueError("Scryfall returned an invalid JSON response.") from error

    available_sets = []

    for set_item in sets_data.get("data", []):
        set_type = set_item.get("set_type", "")

        if set_type not in ALLOWED_DROPDOWN_SET_TYPES:
            continue

        name = set_item.get("name", "Unknown set")
        code = set_item.get("code", "").lower()

        if code:
            available_sets.append({
                "name": name,
                "code": code,
                "set_type": set_type,
                "display_name": f"{name} ({code.upper()})",
            })

    return available_sets

def get_set_icon(set_code):
    #Get set data from Scryfall
    url = f"https://api.scryfall.com/sets/{set_code.lower()}"
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=10)
    response.raise_for_status()

    try:
        set_data = response.json()
    except requests.JSONDecodeError as error:
        raise ValueError("Scryfall returned an invalid JSON response.") from error

    icon_url = set_data.get("icon_svg_uri")

    if not icon_url:
        raise ValueError("No icon found for this set.")

    return {
        "name": set_data.get("name", "Unknown set"),
        "code": set_data.get("code", set_code),
        "icon_url": icon_url,
    }

def load_svg_icon_as_tk_image(icon_url, size=100):
    svg_response = requests.get(
        icon_url,
        headers=SVG_HEADERS,
        timeout=10)
    svg_response.raise_for_status()

    png_bytes = cairosvg.svg2png(
        bytestring=svg_response.content,
        output_width=size,
        output_height=size
    )

    image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    return ImageTk.PhotoImage(image)

def store_icon_in_cache(cache_key, set_info, icon_image):
    if len(ICON_CACHE) >= MAX_CACHE_SIZE:
        oldest_cache_key = next(iter(ICON_CACHE))
        del ICON_CACHE[oldest_cache_key]

    ICON_CACHE[cache_key] = {
        "set_info": set_info,
        "icon_image": icon_image,
    }

def load_sets_for_dropdown(root_window):
    try:
        available_sets = get_available_sets()

        root_window.after(
            0,
            lambda: populate_set_dropdown(available_sets)
        )

    except requests.RequestException as error:
        error_message = str(error)
        root_window.after(0, show_dropdown_load_failed)
        root_window.after(
            0,
            lambda: messagebox.showerror(
                "Error",
                f"Failed to load set list:\n{error_message}"
            )
        )
    except Exception as error:
        error_message = str(error)
        root_window.after(0, show_dropdown_load_failed)
        root_window.after(
            0,
            lambda: messagebox.showerror(
                "Error",
                f"Something went wrong while loading sets:\n{error_message}"
            )
        )


def populate_set_dropdown(available_sets):
    global dropdown_sets_by_display_name

    dropdown_sets_by_display_name = {
        set_item["display_name"]: set_item["code"]
        for set_item in available_sets
    }

    set_dropdown["values"] = list(dropdown_sets_by_display_name.keys())

    if available_sets:
        set_dropdown.current(0)
        add_set_button.config(state=tk.NORMAL)
    else:
        add_set_button.config(state=tk.DISABLED)

def show_dropdown_load_failed():
    selected_set_name.set("Failed to load sets")
    set_dropdown["values"] = ["Failed to load sets"]
    add_set_button.config(state=tk.DISABLED)

def add_selected_set_to_input():
    selected_display_name = selected_set_name.get()

    if not selected_display_name:
        return

    selected_code = dropdown_sets_by_display_name.get(selected_display_name)

    if not selected_code:
        return

    current_text = set_codes_text.get("1.0", tk.END)

    current_codes = {
        code.strip().lower()
        for code in re.split(r"[\s,]+", current_text)
        if code.strip()
    }

    if selected_code in current_codes:
        messagebox.showinfo(
            "Set Already Added",
            f"{selected_code.upper()} is already in the list."
        )
        return

    if current_codes:
        set_codes_text.insert(tk.END, f", {selected_code}")
    else:
        set_codes_text.insert("1.0", selected_code)

def clear_set_codes():
    set_codes_text.delete("1.0", tk.END)

def load_random_icon_in_background(root_window: tk.Tk, clicked_button: tk.Button, random_set_code: str):
    try:
        cache_key = random_set_code.lower()

        if cache_key in ICON_CACHE:
            cached_item = ICON_CACHE.pop(cache_key)
            ICON_CACHE[cache_key] = cached_item

            root_window.after(
                0,
                lambda: show_loaded_icon(
                    cached_item["set_info"],
                    cached_item["icon_image"]
                )
            )
            return

        set_info = get_set_icon(cache_key)

        icon_image = load_svg_icon_as_tk_image(set_info["icon_url"], size=100)

        store_icon_in_cache(cache_key, set_info, icon_image)

        root_window.after(
            0,
            lambda: show_loaded_icon(set_info, icon_image)
        )

    except requests.RequestException as error:
        if isinstance(error, requests.HTTPError) and error.response is not None:
            if error.response.status_code == 404:
                error_message = (
                    "Set code not found.\n\n"
                    "Please check the code and try again."
                )
            else:
                error_message = str(error)
        else:
            error_message = str(error)

        root_window.after(
            0,
            lambda: messagebox.showerror(
                "Error",
                f"Failed to fetch set data:\n{error_message}"
            )
        )
    except Exception as error:
        error_message = str(error)
        root_window.after(
            0,
            lambda: messagebox.showerror(
                "Error",
                f"Something went wrong:\n{error_message}"
            )
        )
    finally:
        root_window.after(0, lambda: clicked_button.config(state=tk.NORMAL))

def show_loaded_icon(set_info, icon_image):
    icon_label.config(image=icon_image)
    icon_label.image = icon_image

    info_label.config(
        text=f"{set_info['name']}\n"
             f"Code: {set_info['code'].upper()}"
    )

def on_button_click(root_window, clicked_button):
    clicked_button.config(state=tk.DISABLED)

    random_set_code = get_random_set_code_from_input()

    if random_set_code is None:
        clicked_button.config(state=tk.NORMAL)
        return

    info_label.config(text="Loading...")
    icon_label.config(image="")
    icon_label.image = None

    threading.Thread(
        target=load_random_icon_in_background,
        args=(root_window, clicked_button, random_set_code),
        daemon=True
    ).start()

def main():
    global set_codes_text, icon_label, info_label
    global selected_set_name, set_dropdown, add_set_button
    root = tk.Tk()
    root.title("MTG Set Randomizer")
    root.geometry("400x500")

    title_label = tk.Label(
        root,
        text="MTG Set Randomizer",
        font=("Arial", 16, "bold")
    )
    title_label.pack(pady=(15, 5))

    instructions_label = tk.Label(
        root,
        text="Enter set codes separated by commas, spaces, or new lines:",
        font=("Arial", 10),
        justify="center"
    )
    instructions_label.pack(pady=(0, 5))

    set_codes_text = tk.Text(
        root,
        height=5,
        width=35
    )
    set_codes_text.pack(pady=5)

    set_codes_text.insert("1.0", "khm, neo, dmu")

    selected_set_name = tk.StringVar(value="Loading sets...")

    dropdown_frame = tk.Frame(root)
    dropdown_frame.pack(pady=5)

    set_dropdown = ttk.Combobox(
        dropdown_frame,
        textvariable=selected_set_name,
        values=["Loading sets..."],
        width=32,
        state="readonly"
    )
    set_dropdown.pack(side=tk.LEFT, padx=(0, 5))

    add_set_button = tk.Button(
        dropdown_frame,
        text="Add Set",
        command=add_selected_set_to_input,
        state=tk.DISABLED
    )
    add_set_button.pack(side=tk.LEFT)

    clear_button = tk.Button(
        dropdown_frame,
        text="Clear List",
        command=clear_set_codes
    )
    clear_button.pack(side=tk.LEFT, padx=(5, 0))

    threading.Thread(
        target=load_sets_for_dropdown,
        args=(root,),
        daemon=True
    ).start()

    button = tk.Button(
        root,
        text="Get Random Set Icon",
    )
    button.config(command=lambda: on_button_click(root, button))
    button.pack(pady=20)

    icon_label = tk.Label(root)
    icon_label.pack(pady=10)

    info_label = tk.Label(
        root,
        text="Enter set codes, then click the button",
        font=("Arial", 12),
        justify="center"
    )
    info_label.pack(pady=10)

    root.mainloop()
if __name__ == "__main__":
    main()