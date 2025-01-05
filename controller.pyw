import asyncio
import websockets
import pygame
import json

async def handle_client(websocket):
    pygame.init()
    pygame.joystick.init()

    print(f"Number of joysticks detected: {pygame.joystick.get_count()}")

    if pygame.joystick.get_count() > 0:
        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        print(f"Joystick name: {joystick.get_name()}")
        print("Joystick detected on startup!")
    else:
        print("No joystick found.")
        return  # Important: Exit if no joystick is found

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.JOYAXISMOTION:
                    data = {"type": "axis", "axis": event.axis, "value": event.value}
                    json_data = json.dumps(data)
                    await websocket.send(json_data)
                    print(f"Sent: {json_data}")
                elif event.type == pygame.JOYBUTTONDOWN:
                    data = {"type": "button", "button": event.button, "value": 1}
                    json_data = json.dumps(data)
                    await websocket.send(json_data)
                    print(f"Sent: {json_data}")
                elif event.type == pygame.JOYBUTTONUP:
                    data = {"type": "button", "button": event.button, "value": 0}
                    json_data = json.dumps(data)
                    await websocket.send(json_data)
                    print(f"Sent: {json_data}")
                elif event.type == pygame.JOYHATMOTION:
                    data = {"type": "hat", "hat": event.hat, "value": event.value}
                    json_data = json.dumps(data)
                    await websocket.send(json_data)
                    print(f"Sent: {json_data}")
            await asyncio.sleep(0.01)  # Important: Keep this for efficiency
    except websockets.exceptions.ConnectionClosedOK:
        print("Client disconnected gracefully.")
    except websockets.exceptions.ConnectionClosedError:
        print("Client disconnected unexpectedly.")
    except asyncio.CancelledError:
        print("Task cancelled. Cleaning up...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        pygame.quit()  # Clean up pygame resources
        print("Pygame resources cleaned up.")

async def main():
    # Start the WebSocket server
    server = await websockets.serve(handle_client, "localhost", 8765)
    print("WebSocket server started on ws://localhost:8765")

    try:
        # Keep the server running
        await asyncio.Future()  # Run forever
    except asyncio.CancelledError:
        print("Server shutting down...")
    finally:
        # Close the server gracefully
        server.close()
        await server.wait_closed()
        print("WebSocket server closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted by user.")