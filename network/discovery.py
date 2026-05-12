import asyncio
import httpx
import os
from core.instance import get_blockchain
from network.websocket import ws_manager

async def p2p_discovery_loop():
    """Continuous background task to discover peers and heal network splits."""
    await asyncio.sleep(3)
    bc = get_blockchain()
    port = os.environ.get("PORT", "8000")
    my_url = f"http://127.0.0.1:{port}"
    seed_node = "http://127.0.0.1:8000"

    try:
        # Bootstrapping
        if my_url != seed_node:
            bc.register_node(seed_node)
    except Exception as e:
        print(f"⚠️ [Discovery] Failed to register seed node: {e}")

    while True:
        try:
            known_nodes = list(bc.nodes)
            nodes_changed = False
            
            for node in known_nodes:
                if node == my_url:
                    continue
                    
                try:
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        # Announce myself
                        await client.post(f"{node}/nodes/register", json={"nodes": [my_url]})
                        
                        # Ask for friends
                        resp = await client.get(f"{node}/nodes")
                        if resp.status_code == 200:
                            peers = resp.json().get("nodes", [])
                            for peer in peers:
                                if peer != my_url and peer not in known_nodes:
                                    bc.register_node(peer)
                                    nodes_changed = True
                                    print(f"✅ [Node {port}] Discovered new peer: {peer}")
                except Exception:
                    pass # Peer is offline, safely ignore
            
            # If we found new people, instantly update our UI!
            if nodes_changed:
                await ws_manager.broadcast({
                    "type": "nodes_updated",
                    "nodes": list(bc.nodes)
                })
                
        except Exception as e:
            print(f"⚠️ [Discovery] Loop Error: {e}")
            
        await asyncio.sleep(8)