import json
from pathlib import Path
from mcp import StdioServerParameters

BASE = Path(__file__).resolve().parent.parent

class CrewaiConnServer:
    @staticmethod
    def get_params(server_name):
        with open(BASE / "server_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        server_config = config["mcpServers"][server_name]
        command = server_config["command"]
        args = server_config["args"]
        env = server_config.get("env", None)
        return StdioServerParameters(
            command=command,
            args=args,
            env=env
        )
