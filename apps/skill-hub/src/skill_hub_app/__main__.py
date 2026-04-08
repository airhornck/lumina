"""独立进程：python -m skill_hub_app（stdio MCP，供 Claude Desktop 等调试）。"""

from skill_hub_app.factory import build_skill_hub_mcp

if __name__ == "__main__":
    build_skill_hub_mcp().run()
