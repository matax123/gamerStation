from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import uvicorn
import webview
import subprocess
import os


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins; you can specify particular domains here instead of "*"
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)



@app.get("/")
async def read_root():
    return {"message": "Welcome to FastAPI!"}

class Item(BaseModel):
    name: str
    description: str = None

@app.post("/process-item/")
async def process_item(item: Item):
    # Wait for the async process to complete
    return {"result": 'hi'} 

@app.post("/get-images/")
async def get_images():
    folder_path = "./img/"
    images = os.listdir(folder_path)
    return images

@app.post("/get-games/")
async def get_games():
    folder_path = "./games/"
    games = os.listdir(folder_path)
    return games

class OpenFileInput(BaseModel):
    file_name: str

@app.post("/open-file/")
async def open_file(input: OpenFileInput):
        file_path = "games/" + input.file_name

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
            except subprocess.CalledProcessError as e:
                print(f"Error opening file: {e}")
        else:
            print("File does not exist!")

# Entry point for running the app using `python server.py`
if __name__ == "__main__":
    # Make sure to pass the app instance as a string reference
    uvicorn.run("server:app", host="127.0.0.1", port=8400, reload=True)