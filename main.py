import webview
import subprocess
import os

class API:
    asking = False
        
    def save_path(self):
        if self.asking:
            return None
        self.asking = True
        
        # Define the path to the file you want to open
        file_path = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG)

        if file_path is None:
            return None
        
        file_path = file_path[0]

        with open("file_paths.txt", "a") as f:
            f.write(f"{file_path}\n")

        return file_path
        
    def open_file(self, file_path):
        if self.asking:
            return None
        self.asking = True

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

    def get_images(self):
        print("Fetching images...")
        folder_path = "./img/"
        images = os.listdir(folder_path)
        # print(f"Images found: {images}")
        return images

    def log(self, message):
        print(message)

# Create an instance of the API class
api = API()

# Create a webview window and expose the API object
window = webview.create_window(
    title='My Webview',
    url='src/index.html',
    width=1500,
    height=1000
)

# Start the webview
webview.start()
