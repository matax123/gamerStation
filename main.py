import webview
import multiprocessing

def run_webview():
    # window = webview.create_window('GamerStation', './src/index.html', width=1500, height=1000)
    window = webview.create_window('GamerStation', './src/index.html', fullscreen=True)
    webview.start(gui='qt', icon='./favicon.ico')

if __name__ == "__main__":
    webview_thread = multiprocessing.Process(target=run_webview)
    webview_thread.start()
    webview_thread.join()