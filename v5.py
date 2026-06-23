import cv2
import numpy as np
import pyautogui
import time
import random
import os
import json
import traceback
import subprocess
from mss import mss
from pynput import keyboard

# ─── Load config ────────────────────────────────────────────────────────────
_cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(_cfg_path, "r", encoding="utf-8") as _f:
    _cfg = json.load(_f)

WORLD_NAME = _cfg["world_name"]

_roi_cfg = _cfg["roi"]
roi_strike = _roi_cfg["strike"]
roi_kutu   = _roi_cfg["box"]
roi_balik  = _roi_cfg["fish"]
roi_land   = _roi_cfg["land"]
roi_net    = _roi_cfg["net"]
roi_take   = _roi_cfg["take"]
roi_world  = _roi_cfg["world"]

_rec = _cfg["recovery"]
NO_STRIKE_TIMEOUT   = _rec["no_strike_timeout_seconds"]
ENTER_WORLD_CLICK   = (_rec["enter_world_click"]["x"],   _rec["enter_world_click"]["y"])
WORLD_CONFIRM_CLICK = (_rec["world_confirm_click"]["x"], _rec["world_confirm_click"]["y"])
EMPTY_AREA_CLICK    = (_rec["empty_area_click"]["x"],    _rec["empty_area_click"]["y"])

_err = _cfg["error_margin"]
ERROR_MARGIN_NORMAL = _err["normal_fish"]
ERROR_MARGIN_GREEN  = _err["green_fish"]

_off = _cfg["offsets"]
BOX_CENTER_OFFSET  = _off["box_center"]
FISH_CENTER_OFFSET = _off["fish_center"]
# ────────────────────────────────────────────────────────────────────────────

yem_atma_noktasi = None

morph_kernel  = np.ones((3, 3), np.uint8)
dilate_kernel = np.ones((2, 2), np.uint8)
templates = {}


def set_target_key(key):
    global yem_atma_noktasi
    try:
        if key.char == 'y':
            x, y = pyautogui.position()
            yem_atma_noktasi = (int(x), int(y))
            return False
    except AttributeError:
        pass


def guvenli_tikla(x, y):
    sapma_x = x + random.randint(-8, 8)
    sapma_y = y + random.randint(-6, 6)
    pyautogui.moveTo(sapma_x, sapma_y, duration=random.uniform(0.08, 0.14))
    pyautogui.mouseDown()
    time.sleep(random.uniform(0.08, 0.15))
    pyautogui.mouseUp()


def insansi_tus(key):
    """Human-like key press with random delays between keydown and keyup."""
    pyautogui.keyDown(key)
    time.sleep(random.uniform(0.06, 0.14))
    pyautogui.keyUp(key)
    time.sleep(random.uniform(0.05, 0.12))


def insansi_yaz(text):
    for char in text:
        pyautogui.keyDown(char)
        time.sleep(random.uniform(0.04, 0.10))
        pyautogui.keyUp(char)
        time.sleep(random.uniform(0.07, 0.18))


def find_image(img, template, threshold=0.65):
    if template is None or img is None:
        return None
    img_h, img_w = img.shape[:2]
    tpl_h, tpl_w = template.shape[:2]
    if tpl_h > img_h or tpl_w > img_w:
        return None
    res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val >= threshold:
        return max_loc
    return None


def get_initial_box_dimensions(hsv_img, lower_color, upper_color):
    mask = cv2.inRange(hsv_img, lower_color, upper_color)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, morph_kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w > 30:
                return w
    return 80


def get_fixed_box_center(hsv_img, lower_color, upper_color, fixed_w):
    mask = cv2.inRange(hsv_img, lower_color, upper_color)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, morph_kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w > 30:
                return x + (fixed_w // 2) + BOX_CENTER_OFFSET
    return None


def get_fish_center(hsv_img, last_x):
    dark_lower = np.array([95, 100, 20])
    dark_upper = np.array([125, 255, 130])
    mask_navy  = cv2.inRange(hsv_img, dark_lower, dark_upper)

    red_lower1 = np.array([0,   220, 110])
    red_upper1 = np.array([5,   255, 170])
    red_lower2 = np.array([174, 220, 110])
    red_upper2 = np.array([180, 255, 170])
    mask_red   = cv2.bitwise_or(
        cv2.inRange(hsv_img, red_lower1, red_upper1),
        cv2.inRange(hsv_img, red_lower2, red_upper2)
    )

    mask = cv2.bitwise_or(mask_navy, mask_red)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, morph_kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    center_x = None
    if contours:
        valid_c = [c for c in contours if cv2.contourArea(c) > 5]
        if valid_c:
            valid_c = sorted(valid_c, key=cv2.contourArea, reverse=True)
            x, _, w, _ = cv2.boundingRect(valid_c[0])
            current_x  = x + (w // 2)
            if last_x is None:
                center_x = current_x
            else:
                center_x = int(last_x * 0.25 + current_x * 0.75)
    return center_x, mask


def get_green_fish_center_edges(bgr_img, edges_R, edges_L, last_x, threshold=0.22):
    if edges_R is None or edges_L is None or bgr_img is None:
        return None
    CENTER_OFFSET = FISH_CENTER_OFFSET
    img_h, img_w  = bgr_img.shape[:2]
    tpl_h, tpl_w  = edges_R.shape[:2]
    if tpl_h > img_h or tpl_w > img_w:
        return None

    gray_img  = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    edges_img = cv2.Canny(gray_img, 30, 100)
    edges_img = cv2.dilate(edges_img, dilate_kernel, iterations=1)

    res_R = cv2.matchTemplate(edges_img, edges_R, cv2.TM_CCOEFF_NORMED)
    _, max_val_R, _, max_loc_R = cv2.minMaxLoc(res_R)
    res_L = cv2.matchTemplate(edges_img, edges_L, cv2.TM_CCOEFF_NORMED)
    _, max_val_L, _, max_loc_L = cv2.minMaxLoc(res_L)

    current_x = None
    if max_val_R > max_val_L and max_val_R >= threshold:
        current_x = max_loc_R[0] + (tpl_w // 2) + CENTER_OFFSET
    elif max_val_L >= max_val_R and max_val_L >= threshold:
        current_x = max_loc_L[0] + (tpl_w // 2) - CENTER_OFFSET

    if current_x is not None:
        if last_x is None:
            return current_x
        else:
            return int(last_x * 0.25 + current_x * 0.75)
    return None


def recovery_mode(sct):
    print("[RECOVERY] World screen detected, starting recovery sequence...")
    time.sleep(random.uniform(0.8, 1.2))

    guvenli_tikla(*ENTER_WORLD_CLICK)
    time.sleep(random.uniform(0.8, 1.2))
    guvenli_tikla(*ENTER_WORLD_CLICK)
    time.sleep(random.uniform(0.5, 0.9))

    insansi_yaz(WORLD_NAME)
    time.sleep(random.uniform(3.0, 4.0))

    guvenli_tikla(*WORLD_CONFIRM_CLICK)
    print(f"[RECOVERY] World name '{WORLD_NAME}' typed, waiting 5 seconds...")
    time.sleep(5.0)

    wait_time = random.uniform(10.0, 12.0)
    print(f"[RECOVERY] Entered world, waiting {wait_time:.1f} seconds...")
    time.sleep(wait_time)

    print("[RECOVERY] Pressing C for last position...")
    insansi_tus('c')
    time.sleep(random.uniform(0.3, 0.8))

    print("[RECOVERY] Recovery complete.")


def launch_and_recover():
    print("\n[SYSTEM] Launching Pixel Worlds via Steam...")
    try:
        os.startfile("steam://rungameid/636040")
    except FileNotFoundError:
        print("[ERROR] Steam protocol could not be launched!")
        raise SystemExit("Steam launch error.")
    except AttributeError:
        subprocess.Popen(["steam://rungameid/636040"])

    print("[SYSTEM] Waiting 20 seconds for the game to open...")
    time.sleep(20.0)

    print("[RECOVERY] Clearing overlays with ESC presses...")
    for _ in range(6):
        pyautogui.keyDown('esc')
        time.sleep(random.uniform(0.04, 0.10))
        pyautogui.keyUp('esc')
        time.sleep(random.uniform(0.40, 0.50))

    guvenli_tikla(*EMPTY_AREA_CLICK)
    time.sleep(random.uniform(0.8, 1.2))
    guvenli_tikla(*EMPTY_AREA_CLICK)
    time.sleep(random.uniform(0.8, 1.2))

    print("[RECOVERY] Waiting 10 seconds for scan simulation...")
    time.sleep(10.0)

    recovery_mode(None)


def play_minigame(sct, fixed_box_w):
    box_lower = np.array([40, 100, 100])
    box_upper = np.array([80, 255, 255])

    active_key      = None
    key_press_time  = 0
    last_fish_local = None
    fish_history    = []
    loss_counter    = 0
    fish_lost_frame = 0
    target_dir      = None
    net_pending     = False
    w_press_time    = None
    box_lost_start = None

    while True:
        img_net_raw = np.array(sct.grab(roi_net))
        img_net     = cv2.cvtColor(img_net_raw, cv2.COLOR_BGRA2BGR)

        if find_image(img_net, templates.get("net"), threshold=0.55):
            net_pending = True
        else:
            net_pending = False

        if w_press_time is not None:
            img_take_raw = np.array(sct.grab(roi_take))
            img_take     = cv2.cvtColor(img_take_raw, cv2.COLOR_BGRA2BGR)
            if find_image(img_take, templates.get("take"), threshold=0.60):
                if active_key:
                    pyautogui.keyUp(active_key)
                return "landed"
            if time.time() - w_press_time > 3.0:
                w_press_time = None

        img_land_raw = np.array(sct.grab(roi_land))
        img_land     = cv2.cvtColor(img_land_raw, cv2.COLOR_BGRA2BGR)
        if find_image(img_land, templates.get("fish_lost"), threshold=0.70):
            if active_key:
                pyautogui.keyUp(active_key)
            return "lost"

        img_kutu_raw = np.array(sct.grab(roi_kutu))
        bgr_kutu     = cv2.cvtColor(img_kutu_raw, cv2.COLOR_BGRA2BGR)
        hsv_kutu     = cv2.cvtColor(bgr_kutu, cv2.COLOR_BGR2HSV)

        img_balik_raw = np.array(sct.grab(roi_balik))
        bgr_balik     = cv2.cvtColor(img_balik_raw, cv2.COLOR_BGRA2BGR)
        hsv_balik     = cv2.cvtColor(bgr_balik, cv2.COLOR_BGR2HSV)

        box_center_local  = get_fixed_box_center(hsv_kutu, box_lower, box_upper, fixed_box_w)
        fish_center_local, _ = get_fish_center(hsv_balik, last_fish_local)
        green_active      = False

        if fish_center_local is None:
            fish_center_local = get_green_fish_center_edges(
                bgr_balik,
                templates.get('fish_green_edges_R'),
                templates.get('fish_green_edges_L'),
                last_fish_local
            )
            green_active = True

        if box_center_local is None:
            if box_lost_start is None:
                box_lost_start = time.time()
            limit = 6 if w_press_time is not None else 6
            if time.time() - box_lost_start > limit:
                break
        else:
            box_lost_start = None
            loss_counter = 0

        box_global  = box_center_local  + roi_kutu["left"]  if box_center_local  is not None else None
        fish_global = fish_center_local + roi_balik["left"] if fish_center_local is not None else None

        if fish_center_local is not None:
            fish_lost_frame  = 0
            last_fish_local  = fish_center_local
            fish_history.append(fish_global)

            if len(fish_history) > 4:
                fish_history.pop(0)

            fish_velocity = fish_history[-1] - fish_history[-2] if len(fish_history) >= 2 else 0
            fish_velocity = max(min(fish_velocity, 25), -25)
            target_x      = fish_global + int(fish_velocity * 2)

            if box_global is not None:
                error      = target_x - box_global
                error_margin = ERROR_MARGIN_GREEN if green_active else ERROR_MARGIN_NORMAL

                if error < -error_margin:
                    target_dir = 'a'
                elif error > error_margin:
                    target_dir = 'd'
                else:
                    target_dir = None
            else:
                target_dir = None
        else:
            fish_lost_frame += 1
            if fish_lost_frame > 4:
                target_dir = None
                fish_history.clear()

        # Net + hata payı kontrolü: net görünüyor ve balık kutunun içindeyse w bas
        if net_pending and w_press_time is None and box_global is not None and fish_global is not None:
            error_for_net = fish_global - box_global
            if abs(error_for_net) <= ERROR_MARGIN_GREEN:
                if active_key:
                    pyautogui.keyUp(active_key)
                    active_key = None
                time.sleep(random.uniform(0.05, 0.10))
                pyautogui.keyDown('w')
                time.sleep(random.uniform(0.04, 0.10))
                pyautogui.keyUp('w')
                w_press_time = time.time()

        if target_dir:
            if active_key != target_dir:
                if active_key:
                    pyautogui.keyUp(active_key)
                    time.sleep(random.uniform(0.03, 0.09))
                pyautogui.keyDown(target_dir)
                active_key     = target_dir
                key_press_time = time.time()
            else:
                hold_limit = random.uniform(0.4, 0.65) if green_active else random.uniform(1.8, 2.5)
                if time.time() - key_press_time > hold_limit:
                    pyautogui.keyUp(active_key)
                    wait = random.uniform(0.03, 0.08) if green_active else random.uniform(0.01, 0.05)
                    time.sleep(wait)
                    pyautogui.keyDown(active_key)
                    key_press_time = time.time()
        else:
            if active_key:
                pyautogui.keyUp(active_key)
                active_key = None

    if active_key:
        pyautogui.keyUp(active_key)
    return False


def save_stats(duration_seconds, lures_used, fish_caught):
    try:
        duration_min = int(duration_seconds // 60)
        duration_sec = int(duration_seconds % 60)
        timestamp    = time.strftime("%Y-%m-%d %H:%M:%S")
        filename     = time.strftime("fishbot_stats_%Y%m%d_%H%M%S.txt")
        script_dir   = os.path.dirname(os.path.abspath(__file__))
        filepath     = os.path.join(script_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("=== FishBot V5 Statistics Report ===\n")
            f.write(f"Date/Time     : {timestamp}\n")
            f.write(f"Runtime       : {duration_min} min {duration_sec} sec\n")
            f.write(f"Lures Used    : {lures_used}\n")
            f.write(f"Fish Caught   : {fish_caught}\n")
        print(f"\n[STATS] Saved: {filename}")
    except Exception as e:
        print(f"\n[ERROR] Could not save stats: {e}")


def main():
    global s_yem, s_tutulan

    image_files = {
        "strike":    'strike.png',
        "take":      'take.png',
        "stolen":    'stolen.png',
        "net":       'net.png',
        "fish_lost": 'fish_lost.png',
        "world":     'world.png'
    }
    global templates

    for key, fname in image_files.items():
        if os.path.exists(fname):
            templates[key] = cv2.imread(fname)

    if os.path.exists('fish_green.png'):
        img_R   = cv2.imread('fish_green.png')
        gray_R  = cv2.cvtColor(img_R, cv2.COLOR_BGR2GRAY)
        edges_R = cv2.Canny(gray_R, 30, 100)
        edges_R = cv2.dilate(edges_R, dilate_kernel, iterations=1)
        templates['fish_green_edges_R'] = edges_R

        img_L   = cv2.flip(img_R, 1)
        gray_L  = cv2.cvtColor(img_L, cv2.COLOR_BGR2GRAY)
        edges_L = cv2.Canny(gray_L, 30, 100)
        edges_L = cv2.dilate(edges_L, dilate_kernel, iterations=1)
        templates['fish_green_edges_L'] = edges_L
    else:
        print("WARNING: fish_green.png not found in the same folder!")

    while True:
        try:
            lure_limit = int(input("How many lures do you want to use? "))
            if lure_limit > 0:
                break
            print("Please enter a number greater than 0.")
        except ValueError:
            print("Please enter a valid number.")

    print("\nMove your mouse to the lure casting point and press Y...")
    with keyboard.Listener(on_press=set_target_key) as listener:
        listener.join()

    print("\nSystem Active (V5 - Auto-recovery enabled).")
    time.sleep(1)

    box_lower = np.array([40, 100, 100])
    box_upper = np.array([80, 255, 255])

    s_yem     = 0
    s_tutulan = 0
    world_miss_counter = 0

    with mss() as sct:
        print(f"System running. Target: {lure_limit} lures.")
        while True:
            pyautogui.keyUp('a')
            pyautogui.keyUp('d')

            guvenli_tikla(yem_atma_noktasi[0], yem_atma_noktasi[1])

            strike_found      = False
            last_strike_time  = time.time()

            while True:
                loop_start    = time.time()
                click1_done   = False
                click2_done   = False
                click3_done   = False
                threshold1    = random.uniform(2.5, 3.8)
                threshold2    = random.uniform(5.0, 6.5)
                threshold3    = random.uniform(9.0, 11.0)

                while time.time() - loop_start < 25:
                    elapsed = time.time() - loop_start

                    if elapsed >= threshold1 and not click1_done:
                        guvenli_tikla(yem_atma_noktasi[0], yem_atma_noktasi[1])
                        click1_done = True

                    if elapsed >= threshold2 and not click2_done:
                        guvenli_tikla(yem_atma_noktasi[0], yem_atma_noktasi[1])
                        click2_done = True

                    if elapsed >= threshold3 and not click3_done:
                        guvenli_tikla(yem_atma_noktasi[0], yem_atma_noktasi[1])
                        click3_done = True

                    img_strike_raw = np.array(sct.grab(roi_strike))
                    img_strike     = cv2.cvtColor(img_strike_raw, cv2.COLOR_BGRA2BGR)

                    if find_image(img_strike, templates.get("strike"), threshold=0.65):
                        s_yem += 1
                        world_miss_counter = 0
                        time.sleep(random.uniform(0.2, 0.3))
                        pyautogui.keyDown('w')
                        time.sleep(random.uniform(0.04, 0.10))
                        pyautogui.keyUp('w')
                        strike_found = True
                        break
                    time.sleep(random.uniform(0.04, 0.07))

                if strike_found:
                    break

                if time.time() - last_strike_time >= NO_STRIKE_TIMEOUT:
                    print("\n[RECOVERY] No strike for timeout period, scanning for world screen...")
                    guvenli_tikla(*EMPTY_AREA_CLICK)
                    time.sleep(1.0)
                    guvenli_tikla(*EMPTY_AREA_CLICK)
                    time.sleep(0.5)

                    scan_start         = time.time()
                    disconnect_found   = False

                    while time.time() - scan_start < 10.0:
                        img_w_raw = np.array(sct.grab(roi_world))
                        img_w     = cv2.cvtColor(img_w_raw, cv2.COLOR_BGRA2BGR)

                        if find_image(img_w, templates.get("world"), threshold=0.60):
                            disconnect_found = True
                            break
                        time.sleep(0.5)

                    if disconnect_found:
                        world_miss_counter = 0
                        print("[RECOVERY] World screen detected, starting recovery...")
                        recovery_mode(sct)
                    else:
                        world_miss_counter += 1
                        print(f"[RECOVERY] World screen not found. ({world_miss_counter}/3)")
                        if world_miss_counter >= 3:
                            print("\n[CRITICAL] World screen not found 3 times in a row!")
                            print("[CRITICAL] Closing Pixel Worlds...")
                            os.system("taskkill /f /im PixelWorlds.exe")
                            print("[CRITICAL] Waiting 10 seconds before relaunch...")
                            time.sleep(10.0)

                            launch_and_recover()

                            world_miss_counter = 0
                            last_strike_time   = time.time()

                    last_strike_time = time.time()
                    guvenli_tikla(yem_atma_noktasi[0], yem_atma_noktasi[1])
                else:
                    guvenli_tikla(yem_atma_noktasi[0], yem_atma_noktasi[1])

            if not strike_found:
                continue

            minigame_started = False
            wait_for_take    = False
            fish_escaped     = False
            lure_stolen      = False

            wait_start = time.time()
            while time.time() - wait_start < 12:
                if "stolen" in templates:
                    img_stolen_raw = np.array(sct.grab(roi_strike))
                    img_stolen     = cv2.cvtColor(img_stolen_raw, cv2.COLOR_BGRA2BGR)
                    if find_image(img_stolen, templates["stolen"], threshold=0.65):
                        print(f"\r[Lures: {s_yem}] Caught: {s_tutulan} | Lure Stolen   ", end='', flush=True)
                        lure_stolen = True
                        break

                img_kutu_raw = np.array(sct.grab(roi_kutu))
                hsv_kutu     = cv2.cvtColor(cv2.cvtColor(img_kutu_raw, cv2.COLOR_BGRA2BGR), cv2.COLOR_BGR2HSV)

                w = get_initial_box_dimensions(hsv_kutu, box_lower, box_upper)
                if w > 30:
                    minigame_result  = play_minigame(sct, w)
                    minigame_started = True

                    if minigame_result == "landed":
                        wait_for_take = True
                    elif minigame_result == "lost":
                        fish_escaped  = True
                    break
                time.sleep(0.05)

            if lure_stolen:
                time.sleep(1)
                continue

            if fish_escaped:
                print(f"\r[Lures: {s_yem}] Caught: {s_tutulan}   ", end='', flush=True)
                time.sleep(2.5)
                continue

            take_found       = False
            take_start       = time.time()
            take_first_seen  = None

            while time.time() - take_start < 8:
                if fish_escaped:
                    break

                img_take_raw = np.array(sct.grab(roi_take))
                img_take     = cv2.cvtColor(img_take_raw, cv2.COLOR_BGRA2BGR)

                if find_image(img_take, templates.get("take"), threshold=0.60):
                    if take_first_seen is None:
                        take_first_seen = time.time()
                    elif time.time() - take_first_seen >= 0.7:
                        s_tutulan += 1
                        print(f"\r[Lures: {s_yem}] Caught: {s_tutulan}   ", end='', flush=True)
                        time.sleep(random.uniform(0.1, 0.3))
                        pyautogui.keyDown('esc')
                        time.sleep(random.uniform(0.04, 0.10))
                        pyautogui.keyUp('esc')
                        time.sleep(1)
                        take_found = True
                        break
                else:
                    take_first_seen = None

                time.sleep(0.05)

            time.sleep(random.uniform(1.5, 2.4))

            if s_yem >= lure_limit:
                print(f"\n[DONE] Reached {lure_limit} lure limit. Closing game...")
                os.system("taskkill /f /im PixelWorlds.exe")
                print("Computer will sleep in 30 seconds...")
                time.sleep(30)
                subprocess.run([
                    'powershell', '-Command',
                    "Add-Type -Assembly System.Windows.Forms; "
                    "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"
                ])
                raise SystemExit(f"Reached {lure_limit} lure limit. Computer put to sleep.")


s_yem     = 0
s_tutulan = 0
_program_start = 0

if __name__ == "__main__":
    _program_start = time.time()
    try:
        main()
    except KeyboardInterrupt:
        pyautogui.keyUp('a')
        pyautogui.keyUp('d')
        save_stats(time.time() - _program_start, s_yem, s_tutulan)
        print("\nSystem stopped.")
    except SystemExit as e:
        pyautogui.keyUp('a')
        pyautogui.keyUp('d')
        save_stats(time.time() - _program_start, s_yem, s_tutulan)
        print(f"\n{e}")
    except Exception as e:
        pyautogui.keyUp('a')
        pyautogui.keyUp('d')
        save_stats(time.time() - _program_start, s_yem, s_tutulan)
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        input("\nPress ENTER to close...")
