from playwright.sync_api import sync_playwright
import time

import subprocess

from flask_logging_server import app
import threading

# Run the app in a separate thread
thread = threading.Thread(target=lambda: app.app.run(debug=True, use_reloader=False), daemon=True)
thread.start()

# Run lichtblick server in docker container
""" docker run -p 8080:8080 lichtblick """

# Run lichtblick app via xvfb with remote debugging
""" export ELECTRON_ENABLE_LOGGING=true """
""" xvfb-run --auto-servernum --server-args='-screen 0 1920x1080x24' lichtblick mcaps/disappearing_vehicle.mcap --disable-gpu --remote-debugging-port=9222 """

""" subprocess.Popen([
    "C:/Users/tsedlmayer/AppData/Local/Programs/lichtblick/Lichtblick.exe",
    "C:/Users/tsedlmayer/Documents/dev/osi3test/examples/osiData/disappearing_vehicle.mcap",
    "--remote-debugging-port=9222"
]) """

# Give the app a few seconds to fully launch
seconds = 3
for i in range(seconds):
    print(f"Waiting for Lichtblick to start... {i+1}/{seconds}")
    time.sleep(1)
print("Lichtblick started, connecting to it...")

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    context = browser.contexts[0]
    print(context.pages)
    page = context.pages[0]
    #page.wait_for_selector("button[title='Seek backward']", state="attached")
    #page.wait_for_selector("button[title='Play']", state="attached")
    #print("wait for selector")
    #page.wait_for_selector("button[title='Seek backward']", state="visible")
    #page.wait_for_selector("button[title='Play']", state="visible")
    #print("Seek backward")
    #page.click("button[title='Seek backward']", force=True)
    #page.click('canvas[data-engine="three.js r156"]', force=True)
    #time.sleep(2)
    #page.click('span[title="Toggle visibility"] input[type="checkbox"]')
    print("Play")
    page.click("button[title='Play']", force=True)
    print("Play clicked")
    browser.close()

    # Keep the main thread alive to prevent the app thread from stopping
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
