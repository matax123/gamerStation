import sys
import os

# Add the libs directory to sys.path so Python can find the modules there
sys.path.append(os.path.join(os.path.dirname(__file__), 'Python313', 'dependencies'))

import asyncio
import websockets
import pygame
import json

def event_device_id(event):
    """Devuelve un identificador estable para el mando que generó el evento."""
    return getattr(event, "instance_id", getattr(event, "joy", 0))


async def handle_client(websocket):
    pygame.init()
    pygame.joystick.init()

    joysticks = {}
    for index in range(pygame.joystick.get_count()):
        joystick = pygame.joystick.Joystick(index)
        joystick.init()
        joysticks[joystick.get_instance_id()] = joystick
        print(f"Joystick {index}: {joystick.get_name()}")

    print(f"Number of joysticks detected: {len(joysticks)}")
    if not joysticks:
        print("No joystick found.")
        return  # Important: Exit if no joystick is found

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.JOYDEVICEADDED:
                    device_index = getattr(event, "device_index", None)
                    if device_index is not None:
                        joystick = pygame.joystick.Joystick(device_index)
                        joystick.init()
                        joysticks[joystick.get_instance_id()] = joystick
                        print(f"Joystick conectado: {joystick.get_name()}")
                    continue
                if event.type == pygame.JOYDEVICEREMOVED:
                    joysticks.pop(getattr(event, "instance_id", -1), None)
                    continue

                device = event_device_id(event)
                if event.type == pygame.JOYAXISMOTION:
                    data = {"type": "axis", "device": device, "axis": event.axis, "value": event.value}
                    json_data = json.dumps(data)
                    await websocket.send(json_data)
                    print(f"Sent: {json_data}")
                elif event.type == pygame.JOYBUTTONDOWN:
                    data = {"type": "button", "device": device, "button": event.button, "value": 1}
                    json_data = json.dumps(data)
                    await websocket.send(json_data)
                    print(f"Sent: {json_data}")
                elif event.type == pygame.JOYBUTTONUP:
                    data = {"type": "button", "device": device, "button": event.button, "value": 0}
                    json_data = json.dumps(data)
                    await websocket.send(json_data)
                    print(f"Sent: {json_data}")
                elif event.type == pygame.JOYHATMOTION:
                    data = {"type": "hat", "device": device, "hat": event.hat, "value": event.value}
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
    server = await websockets.serve(handle_client, "localhost", 8401)
    print("WebSocket server started on ws://localhost:8401")

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

asyncio.run(main())
