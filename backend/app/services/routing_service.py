import json
from typing import Dict, List, Optional
from app.models.schemas import PlatformConfigResponse

SUPPORTED_PLATFORMS = [
    {"id": "claude-code", "name": "Claude Code", "category": "CLI Agent", "version": "2.1+", "hook": "pre-tool-use"},
    {"id": "gemini-cli", "name": "Gemini CLI", "category": "CLI Agent", "version": "1.0+", "hook": "mcp-stdio"},
    {"id": "vscode-copilot", "name": "VS Code Copilot", "category": "IDE Plugin", "version": "1.88+", "hook": "mcp-bridge"},
    {"id": "jetbrains-copilot", "name": "JetBrains Copilot", "category": "IDE Plugin", "version": "2024.1+", "hook": "mcp-bridge"},
    {"id": "cursor", "name": "Cursor", "category": "IDE Native", "version": "0.38+", "hook": "mcp-config"},
    {"id": "opencode-v1", "name": "OpenCode v1", "category": "Terminal IDE", "version": "1.4+", "hook": "ts-plugin"},
    {"id": "opencode-v2", "name": "OpenCode v2", "category": "Terminal IDE", "version": "2.0+", "hook": "mcp-schema-v2"},
    {"id": "kilocode", "name": "KiloCode", "category": "IDE Native", "version": "0.9+", "hook": "mcp-stdio"},
    {"id": "openclaw", "name": "OpenClaw", "category": "Autonomous Agent", "version": "0.5+", "hook": "pre-dispatch"},
    {"id": "codex-cli", "name": "Codex CLI", "category": "CLI Agent", "version": "1.0+", "hook": "pre-tool-use"},
    {"id": "qwen-code", "name": "Qwen Code", "category": "CLI Agent", "version": "0.8+", "hook": "mcp-stdio"},
    {"id": "antigravity", "name": "Antigravity", "category": "Agentic IDE", "version": "2.0+", "hook": "skill-mcp"},
    {"id": "kiro", "name": "Kiro", "category": "Terminal IDE", "version": "0.4+", "hook": "mcp-stdio"},
    {"id": "zed", "name": "Zed Editor", "category": "Editor Native", "version": "0.140+", "hook": "mcp-stdio"},
    {"id": "pi", "name": "Pi Agent", "category": "Interactive Agent", "version": "1.0+", "hook": "abortable-mcp"},
    {"id": "aider", "name": "Aider", "category": "Pair Programming", "version": "0.50+", "hook": "shell-wrapper"},
    {"id": "windsurf", "name": "Windsurf", "category": "Agentic IDE", "version": "1.0+", "hook": "mcp-cascade"},
]


def generate_safe_tool_guidance(platform_id: str, quiet_mode: bool = False) -> str:
    """
    Constructs benign, non-adversarial tool guidance.
    Addresses issues #911 and #967:
    - Never uses <priority_instructions> or adversarial phrasing like 'a past phrase does not bind you'.
    - Uses transparent <tool_guidance> identifying local context optimization.
    - Prevents false-positive 'Auto-Mode Bypass' classifier denials.
    """
    if quiet_mode:
        return ""

    guidance = (
        "<tool_guidance>\n"
        "Nexus Engine context optimizer is active for this workspace.\n"
        "Standard coding workflow applies. When terminal or analysis output exceeds typical limits,\n"
        "the execution runner sandboxes the payload and returns an indexed summary preview.\n"
        "To inspect specific traces, test failures, or line ranges within sandboxed output,\n"
        "call the search tool with targeted regex or query terms.\n"
        "</tool_guidance>"
    )
    return guidance


def generate_platform_config(platform_id: str, quiet_mode: bool = False) -> PlatformConfigResponse:
    target = next((p for p in SUPPORTED_PLATFORMS if p["id"] == platform_id), None)
    if not target:
        target = {
            "id": platform_id,
            "name": platform_id.title(),
            "category": "Generic Agent",
            "version": "1.0",
            "hook": "mcp-stdio",
        }

    guidance = generate_safe_tool_guidance(target["id"], quiet_mode)

    # Generate tailored config json snippet
    if target["id"] == "opencode-v2":
        # Specific schema for OpenCode v2 (#1187)
        config_obj = {
            "$schema": "https://opencode.dev/v2/mcp-schema.json",
            "mcpServers": {
                "nexus-engine": {
                    "command": "python3",
                    "args": ["-m", "app.main"],
                    "url": "http://127.0.0.1:8000/api",
                    "capabilities": ["tools", "resources"],
                    "quietMode": quiet_mode,
                }
            },
        }
    elif target["id"] == "pi":
        # Abortable configuration with watchdog timeout for Pi (#959)
        config_obj = {
            "pi": {
                "mcp": {
                    "nexus-engine": {
                        "transport": "stdio",
                        "command": "python3 -m app.main",
                        "abortable": True,
                        "defaultTimeoutMs": 60000,
                        "escAbortSignal": True,
                    }
                }
            }
        }
    else:
        config_obj = {
            "mcpServers": {
                "nexus-engine": {
                    "command": "python3",
                    "args": ["-m", "app.main"],
                    "env": {"NEXUS_QUIET_MODE": "1" if quiet_mode else "0"},
                }
            }
        }

    return PlatformConfigResponse(
        platform_id=target["id"],
        name=target["name"],
        category=target["category"],
        hook_mode=target["hook"],
        config_snippet=json.dumps(config_obj, indent=2),
        tool_guidance_block=guidance,
        quiet_mode_supported=True,
        version_supported=target["version"],
    )


def list_supported_platforms() -> List[PlatformConfigResponse]:
    return [generate_platform_config(p["id"]) for p in SUPPORTED_PLATFORMS]
