import webview
import subprocess
import sys
import logging

def run_script(script, debug):
    """Run a Python script with or without output."""
    if debug:
        process = subprocess.Popen(["python", script])
    else:
        process = subprocess.Popen(["python", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return process

if __name__ == "__main__":
    debug = False
    controller_process = None
    server_process = None
    window = None

    try:
        # Run the controller and server scripts
        controller_process = run_script("controller.pyw", debug)
        server_process = run_script("server.pyw", debug)

        # Create the webview window
        if(debug):
            window = webview.create_window('My Webview App', './src/index.html', width=1500, height=1000)
        else:
            window = webview.create_window('My Webview App', './src/index.html', fullscreen=True)
        
        # Start the webview event loop
        webview.start(debug=debug)
    except Exception as e:
        print(f"An error occurred: {e}")