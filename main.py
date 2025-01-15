import webview
import multiprocessing

def run_webview(debug):
    window = webview.create_window('My Webview App', './src/index.html', width=1500, height=1000)
    webview.start(gui='qt', icon='./favicon.ico')

if __name__ == "__main__":
    debug = False

    try:
        webview_thread = multiprocessing.Process(target=run_webview, args=(debug,))
        webview_thread.start()
        webview_thread.join()

    except Exception as e:
        print(f"An error occurred: {e}")