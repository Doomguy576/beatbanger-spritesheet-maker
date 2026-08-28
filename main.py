import tkinter as tk
from config import PRESETS_DIR
from ui import SpriteEditorUI

def main():
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    SpriteEditorUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()