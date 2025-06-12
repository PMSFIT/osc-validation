import os
import time
import subprocess
import signal
from osc_validation.tools.osivisualizationtool import OSIVisualizationTool
from playwright.sync_api import sync_playwright

# xvfb-run --auto-servernum --server-args='-screen 0 1024x768x24' lichtblick --disable-gpu --remote-debugging-port=9222

class Lichtblick(OSIVisualizationTool):
    """
    This class serves as a tool for interacting with the lichtblick visualization.
    """

    def __init__(self, tool_path=None):
        if not tool_path:
            tool_path = "lichtblick"
        if not os.path.exists(tool_path):
            raise FileNotFoundError(f"esmini not found at path: {tool_path}")
        super().__init__(tool_path)

    def run(self, osi_mcap_path):
        log_dir = os.path.dirname(osi_mcap_path)
        log_path = os.path.join(log_dir, "log.jsonl")
        server_proc = self.start_logging_server(log_path)
        time.sleep(2)
        try:
            os.system(
                f"xvfb-run --auto-servernum --server-args='-screen 0 1920x1080x24' lichtblick {osi_mcap_path} --disable-gpu --remote-debugging-port=9222"
            )
            seconds = 10
            for i in range(seconds):
                print(f"Waiting for Lichtblick to start... {i+1}/{seconds}")
            time.sleep(1)
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp("http://localhost:9222")
                context = browser.contexts[0]
                page = context.pages[0]
                page.click("button[title='Play']", force=True)
                browser.close()
        finally:
            self.stop_logging_server(server_proc)
        return log_path

    def start_logging_server(log_path):
        return subprocess.Popen(f"poetry run python flask_logging_server/app.py --log-path {log_path} --port 8080")

    def stop_logging_server(proc):
        proc.send_signal(signal.SIGINT)
        proc.wait()
