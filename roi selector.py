import tkinter as tk
import json
import os

class ROISelector:
    def __init__(self, target_key):
        self.target_key = target_key
        self.root = tk.Tk()
        self.root.attributes('-alpha', 0.4)
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        
        self.canvas = tk.Canvas(self.root, cursor="cross", bg="grey")
        self.canvas.pack(fill="both", expand=True)
        
        # UI Labels
        self.label = tk.Label(self.root, text=f"SELECT: {self.target_key.upper()} | Y: Retake | ESC: Exit", 
                             font=("Arial", 20), bg="black", fg="white")
        self.label.pack()
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.root.bind("y", lambda e: self.reset_selector())
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def on_button_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='red', width=3)

    def on_move_press(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_button_release(self, event):
        roi_data = {
            "top": min(self.start_y, event.y),
            "left": min(self.start_x, event.x),
            "width": abs(event.x - self.start_x),
            "height": abs(event.y - self.start_y)
        }
        
        # Display the result to the user
        result_text = f'"{self.target_key}": {roi_data}'
        self.label.config(text=f"COPIED TO CONSOLE:\n{result_text}\n(Y: Retake | ESC: Exit)")
        print(f"\n{result_text}")

    def reset_selector(self):
        self.canvas.delete("all")
        self.label.config(text=f"SELECT: {self.target_key.upper()} | Y: Retake | ESC: Exit")

# Run the selector for a specific region
if __name__ == "__main__":
    # Change 'strike' to whatever region you are currently selecting
    app = ROISelector(target_key="selected area") 
    app.root.mainloop()