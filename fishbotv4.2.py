import cv2
import numpy as np
import pyautogui
import time
import random
import os
import subprocess
import traceback
from mss import mss
from pynput import keyboard

yem_atma_noktasi = None

roi_strike = {"top": 319, "left": 850, "width": 302, "height": 139}
roi_kutu   = {"top": 265, "left": 643, "width": 620, "height": 18}
roi_balik  = {"top": 285, "left": 647, "width": 621, "height": 30} 
roi_land   = {"top": 211, "left": 675, "width": 562, "height": 56} 
roi_net    = {"top": 332, "left": 1172, "width": 50, "height": 40} 
roi_take   = {"top": 713, "left": 841, "width": 231, "height": 75}
roi_world  = {"top": 806, "left": 832, "width": 249, "height": 105}   

morph_kernel = np.ones((3, 3), np.uint8)
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

def find_image(img, template, threshold=0.65):
    if template is None or img is None: return None
    img_h, img_w = img.shape[:2]
    tpl_h, tpl_w = template.shape[:2]
    if tpl_h > img_h or tpl_w > img_w: return None
        
    res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val >= threshold: return max_loc
    return None

def get_initial_box_dimensions(hsv_img, lower_color, upper_color):
    mask = cv2.inRange(hsv_img, lower_color, upper_color)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, morph_kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w > 30: return w
    return 80

def get_fixed_box_center(hsv_img, lower_color, upper_color, fixed_w):
    mask = cv2.inRange(hsv_img, lower_color, upper_color)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, morph_kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w > 30: return x + (fixed_w // 2)
    return None

def get_fish_center(hsv_img, last_x):
    # Dark blue mask
    dark_lower = np.array([95, 100, 20])
    dark_upper = np.array([125, 255, 130])
    mask_lacivert = cv2.inRange(hsv_img, dark_lower, dark_upper)

    # Red mask (both ends of HSV spectrum - between #820B14 and #9C0203)
    kirmizi_lower1 = np.array([0,   220, 110])
    kirmizi_upper1 = np.array([5,   255, 170])
    kirmizi_lower2 = np.array([174, 220, 110])
    kirmizi_upper2 = np.array([180, 255, 170])
    mask_kirmizi = cv2.bitwise_or(
        cv2.inRange(hsv_img, kirmizi_lower1, kirmizi_upper1),
        cv2.inRange(hsv_img, kirmizi_lower2, kirmizi_upper2)
    )

    # Combine both masks
    mask = cv2.bitwise_or(mask_lacivert, mask_kirmizi)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, morph_kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    center_x = None
    if contours:
        valid_c = [c for c in contours if cv2.contourArea(c) > 5]
        if valid_c:
            valid_c = sorted(valid_c, key=cv2.contourArea, reverse=True)
            x, _, w, _ = cv2.boundingRect(valid_c[0])
            current_x = x + (w // 2)
            
            if last_x is None: center_x = current_x
            else: center_x = int(last_x * 0.25 + current_x * 0.75)
    return center_x, mask

def get_green_fish_center_edges(bgr_img, edges_R, edges_L, last_x, threshold=0.22): 
    if edges_R is None or edges_L is None or bgr_img is None: return None
    
    MERKEZ_KAYDIRMA = 0 
    
    img_h, img_w = bgr_img.shape[:2]
    tpl_h, tpl_w = edges_R.shape[:2]
    
    if tpl_h > img_h or tpl_w > img_w: return None
        
    gray_img = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    edges_img = cv2.Canny(gray_img, 30, 100)
    
    edges_img = cv2.dilate(edges_img, dilate_kernel, iterations=1)
    
    res_R = cv2.matchTemplate(edges_img, edges_R, cv2.TM_CCOEFF_NORMED)
    _, max_val_R, _, max_loc_R = cv2.minMaxLoc(res_R)
    
    res_L = cv2.matchTemplate(edges_img, edges_L, cv2.TM_CCOEFF_NORMED)
    _, max_val_L, _, max_loc_L = cv2.minMaxLoc(res_L)
    
    current_x = None
    if max_val_R > max_val_L and max_val_R >= threshold:
        current_x = max_loc_R[0] + (tpl_w // 2) + MERKEZ_KAYDIRMA
    elif max_val_L >= max_val_R and max_val_L >= threshold:
        current_x = max_loc_L[0] + (tpl_w // 2) - MERKEZ_KAYDIRMA
        
    if current_x is not None:
        if last_x is None: return current_x
        else: return int(last_x * 0.25 + current_x * 0.75) 
            
    return None

WORLD_NAME = "YOUR WORLD"  # <-- Change your world name here

def insansi_yaz(metin):
    for harf in metin:
        pyautogui.keyDown(harf)
        time.sleep(random.uniform(0.04, 0.10))
        pyautogui.keyUp(harf)
        time.sleep(random.uniform(0.07, 0.18))

def recovery_modu(sct):
    print("[RECOVERY] World screen detected, starting login sequence...")
    
    guvenli_tikla(956, 529)
    time.sleep(random.uniform(0.4, 0.7))
    guvenli_tikla(956, 529)
    time.sleep(random.uniform(0.5, 0.9))

    insansi_yaz(WORLD_NAME)
    time.sleep(random.uniform(5.0, 6.0))

    guvenli_tikla(848, 658)
    print(f"[RECOVERY] '{WORLD_NAME}' typed, waiting 5 seconds...")
    time.sleep(5.0)

    bekleme = random.uniform(10.0, 12.0)
    print(f"[RECOVERY] World entered, waiting {bekleme:.1f} seconds...")
    time.sleep(bekleme)

    print("[RECOVERY] Clicking final position...")
    guvenli_tikla(1041, 865)
    time.sleep(random.uniform(0.3, 0.8))

    print("[RECOVERY] Recovery complete, casting bait...")

def play_minigame(sct, fixed_box_w):
    box_lower = np.array([40, 100, 100])
    box_upper = np.array([80, 255, 255])
    
    aktif_tus = None
    tus_basma_zamani = 0 
    son_balik_local = None
    balik_gecmisi = []
    kayip_sayaci = 0
    fish_kayip_frame = 0 
    istenen_yon = None
    
    net_ilk_gorulme_zamani = None
    w_basma_zamani = None 

    while True:
        img_net_raw = np.array(sct.grab(roi_net))
        img_net = cv2.cvtColor(img_net_raw, cv2.COLOR_BGRA2BGR)
        
        if find_image(img_net, templates.get("net"), threshold=0.55):
            if net_ilk_gorulme_zamani is None:
                net_ilk_gorulme_zamani = time.time()
                hedef_tepki_suresi = random.uniform(0.15, 0.28) 
            elif w_basma_zamani is None and (time.time() - net_ilk_gorulme_zamani >= hedef_tepki_suresi): 
                if aktif_tus: pyautogui.keyUp(aktif_tus)
                pyautogui.keyDown('w')
                time.sleep(random.uniform(0.04, 0.10))
                pyautogui.keyUp('w')
                w_basma_zamani = time.time()
        else:
            net_ilk_gorulme_zamani = None 

        if w_basma_zamani is not None:
            img_take_raw = np.array(sct.grab(roi_take))
            img_take = cv2.cvtColor(img_take_raw, cv2.COLOR_BGRA2BGR)
            
            if find_image(img_take, templates.get("take"), threshold=0.60):
                if aktif_tus: pyautogui.keyUp(aktif_tus)
                return "landed"
                
            if time.time() - w_basma_zamani > 3.0:
                w_basma_zamani = None 
                net_ilk_gorulme_zamani = None

        img_land_raw = np.array(sct.grab(roi_land))
        img_land = cv2.cvtColor(img_land_raw, cv2.COLOR_BGRA2BGR)
        
        if find_image(img_land, templates.get("fish_lost"), threshold=0.70):
            if aktif_tus: pyautogui.keyUp(aktif_tus)
            return "lost"

        img_kutu_raw = np.array(sct.grab(roi_kutu))
        bgr_kutu = cv2.cvtColor(img_kutu_raw, cv2.COLOR_BGRA2BGR)
        hsv_kutu = cv2.cvtColor(bgr_kutu, cv2.COLOR_BGR2HSV)
        
        img_balik_raw = np.array(sct.grab(roi_balik))
        bgr_balik = cv2.cvtColor(img_balik_raw, cv2.COLOR_BGRA2BGR)
        hsv_balik = cv2.cvtColor(bgr_balik, cv2.COLOR_BGR2HSV)

        box_center_local = get_fixed_box_center(hsv_kutu, box_lower, box_upper, fixed_box_w)
        fish_center_local, _ = get_fish_center(hsv_balik, son_balik_local)
        yesil_devrede = False

        if fish_center_local is None:
            fish_center_local = get_green_fish_center_edges(bgr_balik, templates.get('fish_green_edges_R'), templates.get('fish_green_edges_L'), son_balik_local)
            yesil_devrede = True

        if box_center_local is None:
            kayip_sayaci += 1
            limit = 150 if w_basma_zamani is not None else 60
            if kayip_sayaci > limit:
                break
        else:
            kayip_sayaci = 0

        box_global = box_center_local + roi_kutu["left"] if box_center_local is not None else None
        fish_global = fish_center_local + roi_balik["left"] if fish_center_local is not None else None

        if fish_center_local is not None:
            fish_kayip_frame = 0 
            son_balik_local = fish_center_local 
            balik_gecmisi.append(fish_global)
            
            if len(balik_gecmisi) > 4: balik_gecmisi.pop(0)
                
            balik_hiz = balik_gecmisi[-1] - balik_gecmisi[-2] if len(balik_gecmisi) >= 2 else 0
            balik_hiz = max(min(balik_hiz, 25), -25)
            hedef_x = fish_global + int(balik_hiz * 2) 
            
            if box_global is not None:
                hata = hedef_x - box_global
                hata_payi = 24 if yesil_devrede else 14 
                
                if hata < -hata_payi: istenen_yon = 'a'
                elif hata > hata_payi: istenen_yon = 'd'
                else: istenen_yon = None
            else:
                istenen_yon = None
        else:
            fish_kayip_frame += 1
            if fish_kayip_frame > 4:
                istenen_yon = None
                balik_gecmisi.clear()

        if istenen_yon:
            if aktif_tus != istenen_yon:
                if aktif_tus:
                    pyautogui.keyUp(aktif_tus)
                    time.sleep(random.uniform(0.03, 0.09)) 
                pyautogui.keyDown(istenen_yon)
                aktif_tus = istenen_yon
                tus_basma_zamani = time.time()
            else:
                basili_limit = random.uniform(0.4, 0.65) if yesil_devrede else random.uniform(0.8, 1.3)
                if time.time() - tus_basma_zamani > basili_limit:
                    pyautogui.keyUp(aktif_tus)
                    bekleme = random.uniform(0.03, 0.08) if yesil_devrede else random.uniform(0.01, 0.05)
                    time.sleep(bekleme)
                    pyautogui.keyDown(aktif_tus)
                    tus_basma_zamani = time.time()
        else:
            if aktif_tus:
                pyautogui.keyUp(aktif_tus)
                aktif_tus = None

    if aktif_tus: pyautogui.keyUp(aktif_tus)
    return False

def main():
    resimler = {"strike": 'strike.png', "take": 'take.png', "stolen": 'stolen.png', "net": 'net.png', "fish_lost": 'fish_lost.png', "world": 'world.png'}
    global templates
    
    for k, v in resimler.items():
        if os.path.exists(v):
            templates[k] = cv2.imread(v)

    if os.path.exists('fish_green.png'):
        img_R = cv2.imread('fish_green.png')
        gray_R = cv2.cvtColor(img_R, cv2.COLOR_BGR2GRAY)
        edges_R = cv2.Canny(gray_R, 30, 100)
        edges_R = cv2.dilate(edges_R, dilate_kernel, iterations=1) 
        templates['fish_green_edges_R'] = edges_R
        
        img_L = cv2.flip(img_R, 1)
        gray_L = cv2.cvtColor(img_L, cv2.COLOR_BGR2GRAY)
        edges_L = cv2.Canny(gray_L, 30, 100)
        edges_L = cv2.dilate(edges_L, dilate_kernel, iterations=1) 
        templates['fish_green_edges_L'] = edges_L
    else:
        print("WARNING: fish_green.png not found in the same folder!")

    print("Move your cursor to the fishing spot and press Y...")
    with keyboard.Listener(on_press=set_target_key) as listener:
        listener.join()
        
    print("System Active (V4.2 - Red Fish Tracking & Sleep Protocol).")
    time.sleep(1)
    
    box_lower = np.array([40, 100, 100])
    box_upper = np.array([80, 255, 255])

    s_tutulan   = 0  
    s_fish_lost = 0  
    s_stolen    = 0  
    
    recovery_sayaci = 0 # Total recovery attempt counter

    with mss() as sct:
        while True:
            pyautogui.keyUp('a')
            pyautogui.keyUp('d')
            
            guvenli_tikla(yem_atma_noktasi[0], yem_atma_noktasi[1])
            
            strike_found = False
            son_strike_zamani = time.time()  

            while True:
                bek_bas = time.time()
                tikla_1_yapildi = False
                tikla_2_yapildi = False
                tikla_3_yapildi = False
                esik_1 = random.uniform(2.5, 3.8)
                esik_2 = random.uniform(5.0, 6.5)
                esik_3 = random.uniform(9.0, 11.0)

                while time.time() - bek_bas < 25:
                    gecen_sure = time.time() - bek_bas

                    if gecen_sure >= esik_1 and not tikla_1_yapildi:
                        guvenli_tikla(yem_atma_noktasi[0], yem_atma_noktasi[1])
                        tikla_1_yapildi = True
                        
                    if gecen_sure >= esik_2 and not tikla_2_yapildi:
                        guvenli_tikla(yem_atma_noktasi[0], yem_atma_noktasi[1])
                        tikla_2_yapildi = True

                    if gecen_sure >= esik_3 and not tikla_3_yapildi:
                        guvenli_tikla(yem_atma_noktasi[0], yem_atma_noktasi[1])
                        tikla_3_yapildi = True

                    img_strike_raw = np.array(sct.grab(roi_strike))
                    img_strike = cv2.cvtColor(img_strike_raw, cv2.COLOR_BGRA2BGR)
                    
                    if find_image(img_strike, templates.get("strike"), threshold=0.65):
                        time.sleep(random.uniform(0.2, 0.3))
                        pyautogui.keyDown('w')
                        time.sleep(random.uniform(0.04, 0.10))
                        pyautogui.keyUp('w')
                        strike_found = True
                        break
                    time.sleep(random.uniform(0.04, 0.07))

                if strike_found:
                    break

                if time.time() - son_strike_zamani >= 150: 
                    print("\n[RECOVERY] 2.5 min passed, scanning for world screen (30s)...")
                    tara_bas = time.time()
                    disconnect_bulundu = False
                    
                    while time.time() - tara_bas < 30.0:
                        img_w_raw = np.array(sct.grab(roi_world))
                        img_w = cv2.cvtColor(img_w_raw, cv2.COLOR_BGRA2BGR)

                        if find_image(img_w, templates.get("world"), threshold=0.60):
                            disconnect_bulundu = True
                            break
                        time.sleep(0.5)

                    if disconnect_bulundu:
                        recovery_sayaci += 1
                        print(f"[RECOVERY] World screen found. (Recovery {recovery_sayaci}/3)")
                        
                        if recovery_sayaci > 4:
                            print("\n[CRITICAL] Recovery triggered 5 times!")
                            print("[CRITICAL] Closing Pixel Worlds...")
                            os.system("taskkill /f /im PixelWorlds.exe")
                            print("[CRITICAL] Waiting 30 seconds, then entering sleep mode...")
                            time.sleep(30)
                            subprocess.run(['powershell', '-Command', "Add-Type -Assembly System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"])
                            raise SystemExit("System put to sleep.")
                            
                        recovery_modu(sct)
                    else:
                        print("[RECOVERY] Scan complete, screen looks normal, continuing...")

                    son_strike_zamani = time.time()
                    guvenli_tikla(yem_atma_noktasi[0], yem_atma_noktasi[1])
                else:
                    guvenli_tikla(yem_atma_noktasi[0], yem_atma_noktasi[1])
            
            if not strike_found: continue

            minigame_basladi = False
            take_bekle = False
            fish_kacti = False
            lure_stolen = False
            
            dur_bas = time.time()
            while time.time() - dur_bas < 6:
                if "stolen" in templates:
                    img_stolen_raw = np.array(sct.grab(roi_strike))
                    img_stolen = cv2.cvtColor(img_stolen_raw, cv2.COLOR_BGRA2BGR)
                    if find_image(img_stolen, templates["stolen"], threshold=0.65):
                        s_stolen += 1
                        toplam_yem = s_tutulan + s_fish_lost + s_stolen
                        print(f"\r[Bait: {toplam_yem}] Caught: {s_tutulan} | Fish Lost: {s_fish_lost} | Lure Stolen: {s_stolen}   ", end='', flush=True)
                        lure_stolen = True
                        break 
                
                img_kutu_raw = np.array(sct.grab(roi_kutu))
                hsv_kutu = cv2.cvtColor(cv2.cvtColor(img_kutu_raw, cv2.COLOR_BGRA2BGR), cv2.COLOR_BGR2HSV)
                
                w = get_initial_box_dimensions(hsv_kutu, box_lower, box_upper)
                if w > 30: 
                    minigame_sonuc = play_minigame(sct, w)
                    minigame_basladi = True
                    
                    if minigame_sonuc == "landed":
                        take_bekle = True
                    elif minigame_sonuc == "lost":
                        fish_kacti = True
                        
                    break
                time.sleep(0.05)

            if lure_stolen:
                time.sleep(1)
                continue
                
            if fish_kacti:
                s_fish_lost += 1
                toplam_yem = s_tutulan + s_fish_lost + s_stolen
                print(f"\r[Bait: {toplam_yem}] Caught: {s_tutulan} | Fish Lost: {s_fish_lost} | Lure Stolen: {s_stolen}   ", end='', flush=True)
                time.sleep(2.5)
                continue

            take_bulundu = False
            take_bas = time.time()
            take_ilk_gorulme = None 
            
            while time.time() - take_bas < 8: 
                if fish_kacti: break 
                
                img_take_raw = np.array(sct.grab(roi_take))
                img_take = cv2.cvtColor(img_take_raw, cv2.COLOR_BGRA2BGR)
                
                if find_image(img_take, templates.get("take"), threshold=0.60):
                    if take_ilk_gorulme is None:
                        take_ilk_gorulme = time.time()
                    elif time.time() - take_ilk_gorulme >= 0.7:
                        s_tutulan += 1
                        toplam_yem = s_tutulan + s_fish_lost + s_stolen
                        print(f"\r[Bait: {toplam_yem}] Caught: {s_tutulan} | Fish Lost: {s_fish_lost} | Lure Stolen: {s_stolen}   ", end='', flush=True)
                        time.sleep(random.uniform(0.1, 0.3))
                        pyautogui.keyDown('esc')
                        time.sleep(random.uniform(0.04, 0.10))
                        pyautogui.keyUp('esc')
                        time.sleep(1) 
                        take_bulundu = True
                        break
                else:
                    take_ilk_gorulme = None 
                    
                time.sleep(0.05) 

            time.sleep(random.uniform(1.5, 2.4))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pyautogui.keyUp('a')
        pyautogui.keyUp('d')
        print("\nSystem stopped.")
    except Exception as e:
        pyautogui.keyUp('a')
        pyautogui.keyUp('d')
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        input("\nPress ENTER to close the window...")