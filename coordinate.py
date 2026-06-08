import time
from pynput import mouse

file_name = "coordinates.txt"

# Reset the file on every launch
with open(file_name, "w", encoding="utf-8") as f:
    f.write("--- SAVED COORDINATES ---\n")

print("Coordinate Logger Active!")
print("Switch to the game screen and RIGHT CLICK on the points you want to record...")
print("Press Ctrl + C in the terminal to exit.\n")

def on_click(x, y, button, pressed):
    # Capture only the right mouse button press
    if button == mouse.Button.right and pressed:
        coord_line = f"X: {int(x)}, Y: {int(y)}"
        print(f"[SAVED] -> {coord_line}")
        
        # Append to file
        with open(file_name, "a", encoding="utf-8") as f:
            f.write(coord_line + "\n")

# Listen to mouse clicks
with mouse.Listener(on_click=on_click) as listener:
    try:
        listener.join()
    except KeyboardInterrupt:
        print("\nRecording process terminated. You can check the 'coordinates.txt' file.")