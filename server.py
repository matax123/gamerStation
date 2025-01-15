from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import subprocess
import os
import threading
import pygetwindow as gw
import time


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins; you can specify particular domains here instead of "*"
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

gameRunning = False


@app.post("/get-images/")
async def get_images():
    folder_path = "./src/img/"
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
        global gameRunning
        file_path = f"games/{input.file_name}"

        command = f"start /wait {file_path}"

        if os.path.exists(file_path):
            try:
                threading.Thread(target=start_program, args=(command,)).start()
                return "File opened!"
            except subprocess.CalledProcessError as e:
                print(f"Error opening file: {e}")
        else:
            print("File does not exist!")

@app.post("/check-game/")
async def check_game():
    print(gameRunning)
    return gameRunning

def start_program(command):
    global gameRunning
    print("Starting program...")
    gameRunning = True
    process = subprocess.Popen(command, shell=True)
    process.wait()
    gameRunning = False
    print("Program ended!")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8400, log_level="info")