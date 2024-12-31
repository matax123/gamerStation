from fastapi import FastAPI
from pydantic import BaseModel
import time
import uvicorn

app = FastAPI()

# Example of a Pydantic model for structured input and output
class Item(BaseModel):
    name: str
    description: str = None

# Simulate an async operation (like an API call or long-running task)
async def async_process(item: Item):
    # Simulate a delay (e.g., fetching data, processing, etc.)
    time.sleep(2)  # Simulate a blocking operation (remove this for real async code)
    return f"Processed {item.name}"

@app.get("/")
async def read_root():
    return {"message": "Welcome to FastAPI!"}

@app.post("/process-item/")
async def process_item(item: Item):
    # Wait for the async process to complete
    result = await async_process(item)
    return {"result": result}

# Entry point for running the app using `python server.py`
if __name__ == "__main__":
    # Make sure to pass the app instance as a string reference
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
