import sys
import json
import logging

# Log to stderr so we don't corrupt stdout JSON-RPC
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("mock-mcp")

def read_request():
    try:
        line = sys.stdin.readline()
        if not line:
            return None
        return json.loads(line)
    except Exception as e:
        logger.error(f"Failed to read request: {e}")
        return None

def send_response(response):
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()

def main():
    logger.info("Mock MCP Server started")
    
    while True:
        req = read_request()
        if req is None:
            break
            
        req_id = req.get("id")
        method = req.get("method")
        
        logger.info(f"Received: {method}")
        
        if method == "initialize":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {"name": "mock-server", "version": "1.0"}
                }
            })
            
        elif method == "notifications/initialized":
            # No response needed for notifications
            pass
            
        elif method == "tools/list":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "mock_echo",
                            "description": "Echoes back the input",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "message": {"type": "string"}
                                }
                            }
                        },
                        {
                            "name": "mock_add",
                            "description": "Adds two numbers",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "a": {"type": "number"},
                                    "b": {"type": "number"}
                                }
                            }
                        }
                    ]
                }
            })
            
        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})
            
            result_text = ""
            if name == "mock_echo":
                result_text = f"Echo: {args.get('message')}"
            elif name == "mock_add":
                val = float(args.get("a", 0)) + float(args.get("b", 0))
                result_text = f"Sum: {val}"
            else:
                result_text = "Unknown tool"
                
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result_text
                        }
                    ]
                }
            })
            
        else:
            # Unknown method, just ignore or error (but keep running)
            if req_id is not None:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": "Method not found"}
                })

if __name__ == "__main__":
    main()


