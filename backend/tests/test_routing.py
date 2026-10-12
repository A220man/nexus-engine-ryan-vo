import json
import pytest
from app.services.routing_service import (
    SUPPORTED_PLATFORMS,
    list_supported_platforms,
    generate_platform_config,
    generate_safe_tool_guidance,
)
from app.evaluation import evaluate_classifier_safety


def test_17_platforms_catalog():
    # Issue #45: Support across 17 platforms
    platforms = list_supported_platforms()
    assert len(platforms) == 17
    platform_ids = {p.platform_id for p in platforms}
    expected = {
        "claude-code", "gemini-cli", "vscode-copilot", "jetbrains-copilot",
        "cursor", "opencode-v1", "opencode-v2", "kilocode", "openclaw",
        "codex-cli", "qwen-code", "antigravity", "kiro", "zed", "pi", "aider", "windsurf"
    }
    assert expected.issubset(platform_ids)


def test_opencode_v2_schema_generation():
    # Issue #1187: OpenCode V2 support
    config = generate_platform_config("opencode-v2")
    assert config.platform_id == "opencode-v2"
    parsed = json.loads(config.config_snippet)
    assert parsed.get("$schema") == "https://opencode.dev/v2/mcp-schema.json"
    assert "nexus-engine" in parsed.get("mcpServers", {})


def test_pi_abortable_config():
    # Issue #959: Pi abortable configuration
    config = generate_platform_config("pi")
    parsed = json.loads(config.config_snippet)
    pi_conf = parsed.get("pi", {}).get("mcp", {}).get("nexus-engine", {})
    assert pi_conf.get("abortable") is True
    assert pi_conf.get("escAbortSignal") is True


def test_safe_guidance_no_adversarial_markers():
    # Issues #911 and #967: Safe framing without triggering auto-mode bypass
    guidance = generate_safe_tool_guidance("claude-code")
    assert "<tool_guidance>" in guidance
    assert "priority_instructions" not in guidance
    assert "disregard prior" not in guidance
    assert "a past phrase does not bind you" not in guidance

    # Formally verify with safety classifier
    assert evaluate_classifier_safety(guidance) is True


def test_quiet_mode_toggle():
    # Quiet mode opt-out
    guidance_quiet = generate_safe_tool_guidance("claude-code", quiet_mode=True)
    assert guidance_quiet == ""

    config = generate_platform_config("claude-code", quiet_mode=True)
    assert config.tool_guidance_block == ""
