import subprocess
import time
import urllib.request
import json
import os
import sys

def start_node(port):
    """Starts a uvicorn node in a new terminal window."""
    env = os.environ.copy()
    env["PORT"] = str(port)  # Pass the dynamic port to our blockchain.py

    print(f"Launching Node on port {port}...")
    
    # Use sys.executable to guarantee we use the current Python environment
    # This fixes the [WinError 2] FileNotFoundError on Windows
    command = [sys.executable, "-m", "uvicorn", "main:app", "--port", str(port)]
    
    if sys.platform == "win32":
        # Opens a completely new Command Prompt window for the node
        return subprocess.Popen(
            command,
            env=env,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        # Fallback for Mac/Linux
        return subprocess.Popen(command, env=env)

def register_peer(target_port, peer_url):
    """Sends an API request to register a peer node."""
    url = f"http://localhost:{target_port}/nodes/register"
    data = json.dumps({"nodes": [peer_url]}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            print(f"  [✓] Successfully told Node {target_port} about {peer_url}")
    except Exception as e:
        print(f"  [✗] Failed to register {peer_url} on Node {target_port}: {e}")

if __name__ == "__main__":
    print("=== NovaChain Network Launcher ===\n")

    # 1. Start the nodes
    node_a = start_node(8000)
    node_b = start_node(8001)

    # 2. Wait for uvicorn to fully boot up
    print("\nWaiting 4 seconds for servers to initialize...")
    time.sleep(4)

    # 3. Link them together via their APIs
    print("\nLinking nodes together into a network...")
    register_peer(8000, "http://localhost:8001")
    register_peer(8001, "http://localhost:8000")

    print("\n=== NETWORK IS LIVE ===")
    print("▶ Node A Dashboard: http://localhost:8000")
    print("▶ Node B Dashboard: http://localhost:8001")
    print("\nKeep this runner script open. Press Ctrl+C here to kill both nodes.")

    # Keep the runner alive until you stop it
    try:
        node_a.wait()
        node_b.wait()
    except KeyboardInterrupt:
        print("\nShutting down network...")
        node_a.terminate()
        node_b.terminate()
        print("Done.")