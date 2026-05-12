import os
import subprocess
import sys
import time

def start_node(port: int):
    env = os.environ.copy()
    env["PORT"] = str(port)
    command = [sys.executable, "-m", "uvicorn", "main:app", "--port", str(port)]
    if sys.platform == "win32":
        return subprocess.Popen(command, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
    return subprocess.Popen(command, env=env)

if __name__ == "__main__":
    print("=== NovaChain Enterprise Launcher ===")
    
    # Start the Seed Node first
    node_a = start_node(8000)
    time.sleep(1) # Give seed node a 1 second head start
    
    # Start as many peers as you want!
    node_b = start_node(8001)
    node_c = start_node(8002)
    node_d = start_node(8003)

    print("\nNodes launched. They will find each other automatically in 3 seconds!")
    
    try:
        node_a.wait()
    except KeyboardInterrupt:
        node_a.terminate()
        node_b.terminate()
        node_c.terminate()
        node_d.terminate()