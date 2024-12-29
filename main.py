import webview
import subprocess
import os

class API:
    asking = False
        
    def save_path(self):
        if(self.asking == True):
            return None
        self.asking = True
        # Print log to confirm the method is being called
        print("open_file function was triggered")
        
        # Define the path to the file you want to open
        file_path = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG)[0]

        with open("file_paths.txt", "a") as f:
            f.write(f"{file_path}\n")
        
    def open_file(self):
        if(self.asking == True):
            return None
        self.asking = True
        # Print log to confirm the method is being called
        print("open_file function was triggered")
        
        # Define the path to the file you want to open
        file_path = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG)[0]

        print(f"File path: {file_path}")
        
        # Check if the file exists
        if os.path.exists(file_path):
            try:
                # Log to confirm file exists
                print(f"File found: {file_path}")
                
                # Open the file using the default program (Windows example)
                subprocess.run(f"start {file_path}", shell=True, check=True)
                print(f"Opened file: {file_path}")
                # Update the status in the browser
                window.evaluate_js(f"document.getElementById('file-status').innerText = 'File opened: {file_path}'")
            except subprocess.CalledProcessError as e:
                print(f"Error opening file: {e}")
                window.evaluate_js(f"document.getElementById('file-status').innerText = 'Error opening file: {e}'")
        else:
            print("File does not exist!")
            window.evaluate_js(f"document.getElementById('file-status').innerText = 'File not found!'")

# Create an instance of the API class
api = API()

# Create a webview window and expose the API object
window = webview.create_window(
    title='My Webview',
    url='src/index.html',
    width=1500,
    height=1000,
    js_api=api  # Pass the API instance here
)

# Start the webview
webview.start()
