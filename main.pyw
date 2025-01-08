import webview
import subprocess
import atexit

def run_script(script, debug):
    """Run a Python script with or without output."""
    if debug:
        process = subprocess.Popen(["python", script])
    else:
        process = subprocess.Popen(["python", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return process

def cleanup():
    """Ensure the cleanup of subprocesses."""
    if controller_process:
        controller_process.terminate()
        controller_process.wait()  # Wait for the process to terminate
        print("controller.pyw process terminated.")

    if server_process:
        server_process.terminate()
        server_process.wait()  # Wait for the process to terminate
        print("server.pyw process terminated.")

if __name__ == "__main__":
    debug = False
    controller_process = None
    server_process = None
    window = None

    try:
        # Run the controller and server scripts
        controller_process = run_script("controller.pyw", debug)
        server_process = run_script("server.pyw", debug)

        atexit.register(cleanup)

        # Create the webview window
        window = webview.create_window('My Webview App', './src/index.html', width=1500, height=1000)
        
        # Start the webview event loop
        webview.start(debug=debug)
    except Exception as e:
        print(f"An error occurred: {e}")