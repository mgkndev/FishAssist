# FishAssist

FishAssist is an automated fishing tool designed for high efficiency and reliability. Unlike many macro tools that rely on fixed-time clicking, this project utilizes real-time image recognition to monitor the game state.

## Why FishAssist?

FishAssist is built on the philosophy of transparency and safety. It differs from standard market solutions in three key ways:

- **Non-Invasive Architecture:** FishAssist does not touch the game's memory, inject DLLs, or modify game files. Because it interacts purely with visual output, it is classified as an external automation tool rather than a game hack.
- **Full Transparency:** The project is 100% open source. You can inspect every line of code to verify its security. There are no hidden backdoors—just readable, trusted Python code.
- **Anti-Cheat Resilience:** Unlike standard fixed-interval macros, FishAssist mimics human reaction times and input patterns. This natural, unpredictable behavior significantly reduces the risk of detection by anti-cheat systems.

## What Does FishAssist Do?

FishAssist automates the entire fishing process in Pixel Worlds using advanced Computer Vision (OpenCV) techniques.

- **Intelligent Vision:** Instead of relying on unreliable static timers, the script sees the game screen in real time and reacts to visual feedback.
- **Full Automation:** From casting the line to reeling in the catch, the script manages the entire fishing loop uninterrupted.
- **Tireless Performance:** The only difference between FishAssist and a human player is that the bot does not need to sleep, eat, or rest. It provides consistent, high-efficiency fishing 24/7.

## Setup Guide

To ensure consistent performance, the bot requires a standardized environment.

### 1. Environment Standardization

- **Visual Consistency:** Keep your zoom level, game position, and screen resolution fixed.
- **Disconnect Protection:** For automated disconnect protection to function, your character must reach the fishing spot within 5–10 seconds of spawning. Use fan/portal configurations to ensure proper positioning immediately after entering the world.

### 2. Assets & Screenshots

The bot relies on template matching. You must capture screenshots of your own game screen to create the required assets.

- **Quality:** Assets must be captured in full-screen mode and cropped precisely to match the sample files provided.
- **Transparency:** Ensure your `fish_green` file is saved with a transparent background. Without transparency, the detection algorithm may fail.

### 3. ROI Configuration

ROI stands for **Region of Interest**. These are the specific coordinates the bot monitors. Use the `selector.py` script to identify and save these coordinates to your `main.py` configuration.

#### ROI Selection Guide

| ROI Name | Description |
|----------|-------------|
| `roi_strike` | Area containing the "Strike" text. Keep it tight to avoid color conflicts. A dark background is recommended. |
| `roi_kutu` | The thin box area shown in the reference image (`2.png`). |
| `roi_balik` | The main fishing area. **Critical:** Select this area carefully (`7.png`). |
| `roi_land` | The landing zone for the catch (`4.png`). |
| `roi_net` | The net capture zone. Define this area as concisely as possible (`1.png`). |
| `roi_take` | The interaction/collect area (`3.png`). |
| `roi_world` | The navigation area. Capture this widely (`5.png`). |

> **Warning:** Ensure all assets are smaller than their designated ROI areas. If an asset is larger than its assigned ROI, detection may fail.

## Recovery Mode Configuration

Recovery Mode is a fail-safe mechanism that triggers if the bot detects a disconnection or prolonged inactivity. It searches for the `world.png` asset to initiate the automated reconnection process.

### Configuration Steps

1. **Set World Name:** Open `main.py`, locate line 143, and replace `"YOUR WORLD"` with your actual world name.

2. **Update Coordinates:** Use your coordinate finder script to determine the correct values:

   - **Location #1:** Replace `guvenli_tikla(956, 529)` with the coordinates for the first recovery point.
   - **Location #2:** Replace `guvenli_tikla(848, 658)` with the coordinates for the second recovery point.
   - **Location #3:** Replace `guvenli_tikla(1041, 865)` with the coordinates for the third recovery point.

   **Note:** Your inventory must be visible as shown in the reference image.

## How to Use

Once your setup is correctly configured:

1. Move your character to the standardized fishing position.
2. Run the script.
3. Select your desired bait in-game.
4. Press the **Y** key to define the exact location where the bait should be cast.

## Troubleshooting

- **Color Detection Issues:** If the bot fails to track the blue fish, update the color constants within the source code to match your screen output.
- **Internet Connectivity:** Recovery Mode can handle game disconnections and minor stutters, but it cannot recover from a complete internet outage.

## License

This project is licensed under the **GNU General Public License v3.0**.
