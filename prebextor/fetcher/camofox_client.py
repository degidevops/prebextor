"""CamoFox CLI subprocess wrapper for Prebextor.

Verified against the actual `camofox` CLI in this environment:

    camofox open <url> [--user <u>]
    camofox close [tabId] [--user <u>]
    camofox snapshot [tabId] [--user <u>]
    camofox eval <expression> [tabId] [--user <u>]
    camofox wait <condition> [tabId] [--timeout <ms>] [--user <u>]
    camofox get-page-html [tabId] [--selector <sel>] [--user <u>]

Eval output format:
    ok: true
    result: <value>
    resultType: string
    truncated: false
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from typing import List, Optional, Tuple


class CamoFoxClient:
    """Subprocess wrapper around `camofox`. Stateless across requests."""

    def __init__(self, default_timeout: int = 60) -> None:
        self.default_timeout = default_timeout

    # ---------- availability ----------

    @staticmethod
    def is_available() -> bool:
        try:
            r = subprocess.run(
                ["camofox", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return r.returncode == 0
        except Exception:
            return False

    # ---------- low-level runner ----------

    def run(
        self,
        args: List[str],
        user: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[str, str, int]:
        cmd = ["camofox"]
        if user:
            cmd.extend(["--user", user])
        cmd.extend(args)
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout or self.default_timeout,
        )
        return r.stdout, r.stderr, r.returncode

    # ---------- result parsers ----------

    @staticmethod
    def extract_result(stdout: str) -> Optional[str]:
        """Parse `result: <value>` (multiline OK) from a camofox eval output."""
        lines = stdout.splitlines()
        in_result = False
        out: List[str] = []
        for line in lines:
            if line.startswith("result: "):
                in_result = True
                tail = line[len("result: "):]
                if tail:
                    out.append(tail)
                continue
            if in_result and line.startswith(("resultType:", "truncated:", "ok:")):
                break
            if in_result:
                out.append(line)
        joined = "\n".join(out).strip()
        return joined or None

    @staticmethod
    def extract_tab_id(stdout: str) -> Optional[str]:
        for line in stdout.splitlines():
            if line.startswith("tabId: "):
                return line.split("tabId: ", 1)[1].strip()
        return None

    # ---------- high-level operations ----------

    def open_tab(
        self,
        url: str,
        user: str,
        wait_networkidle_ms: int = 15000,
    ) -> Optional[str]:
        """Open URL in new tab, wait for networkidle. Returns tabId."""
        stdout, _, rc = self.run(["open", url], user=user)
        if rc != 0:
            return None
        tab_id = self.extract_tab_id(stdout)
        if tab_id:
            self.wait("networkidle", tab_id, user=user, timeout_ms=wait_networkidle_ms)
        return tab_id

    def close_tab(self, tab_id: str, user: str) -> None:
        """Close tab and release resources."""
        try:
            self.run(["close", tab_id], user=user, timeout=10)
        except Exception:
            pass

    def wait(
        self,
        condition: str,
        tab_id: str,
        user: str,
        timeout_ms: int = 15000,
    ) -> bool:
        """Wait for condition (networkidle|selector|navigation)."""
        stdout, _, rc = self.run(
            ["wait", condition, tab_id, "--timeout", str(timeout_ms), "--user", user],
            user=user,
            timeout=max(10, timeout_ms // 1000 + 5),
        )
        return rc == 0

    def snapshot(self, tab_id: str, user: str, timeout: int = 60) -> Optional[str]:
        """Get accessibility tree snapshot. DEPRECATED — do not use."""
        stdout, _, rc = self.run(["snapshot", tab_id], user=user, timeout=timeout)
        if rc != 0:
            return None
        return stdout

    def evaluate_js(
        self,
        expression: str,
        tab_id: str,
        user: str,
        timeout: Optional[int] = None,
    ) -> Optional[str]:
        """Execute JS expression in tab. Returns parsed result string."""
        stdout, _, rc = self.run(
            ["eval", expression, tab_id],
            user=user,
            timeout=timeout,
        )
        if rc != 0:
            return None
        return self.extract_result(stdout)

    # ---------- HTML retrieval (v2: direct eval, no staging) ----------

    def get_html(
        self,
        tab_id: str,
        user: str,
        selector: Optional[str] = None,
        chunk_size: int = 15000,
    ) -> Optional[str]:
        """Get outerHTML of element matching selector (chunked, no staging).

        Uses direct evaluate_js return for small HTML, chunked for large.
        No window.__pe_html staging — avoids stale reference issues.
        """
        if selector:
            js_selector = selector.replace("'", "\\'")
            get_js = (
                f"(function(){{"
                f" const el = document.querySelector('{js_selector}');"
                f" if(!el) return null;"
                f" return el.outerHTML;"
                f"}})()"
            )
        else:
            get_js = "document.documentElement.outerHTML"

        # First try: direct eval (works for small pages)
        result = self.evaluate_js(get_js, tab_id, user, timeout=30)
        if result is not None:
            return result

        # Fallback: chunked via JSON.stringify (for large HTML)
        if selector:
            js_selector = selector.replace("'", "\\'")
            length_js = (
                f"(function(){{"
                f" const el = document.querySelector('{js_selector}');"
                f" if(!el) return 0;"
                f" return el.outerHTML.length;"
                f"}})()"
            )
        else:
            length_js = "document.documentElement.outerHTML.length"

        length_str = self.evaluate_js(length_js, tab_id, user, timeout=30)
        if length_str is None:
            return None

        try:
            length = int(str(length_str).strip())
        except (TypeError, ValueError):
            return None

        if length == 0:
            return ""

        # Chunked retrieval using JSON.stringify for proper escaping
        chunks: List[str] = []
        pos = 0
        while pos < length:
            end = min(pos + chunk_size, length)
            chunk_js = f"JSON.stringify((function(){{ const el = document.querySelector('{selector.replace(chr(39), chr(92)+chr(39)) if selector else ''}'); return el ? el.outerHTML : document.documentElement.outerHTML; }})().substring({pos},{end}))"
            part_json = self.evaluate_js(chunk_js, tab_id, user, timeout=30)
            if part_json is None:
                break
            try:
                part = json.loads(str(part_json).strip())
            except Exception:
                part = str(part_json)
            if not part:
                break
            chunks.append(part)
            pos += len(part)

        return "".join(chunks)

    def get_text(
        self,
        tab_id: str,
        user: str,
        selector: Optional[str] = None,
    ) -> Optional[str]:
        """Get innerText of element matching selector (direct, no HTML).

        This is the preferred method for content extraction — returns
        clean text directly from DOM, avoiding HTML noise issues.
        """
        if selector:
            js_selector = selector.replace("'", "\\'")
            js = (
                f"(function(){{"
                f" const el = document.querySelector('{js_selector}');"
                f" if(!el) return null;"
                f" return el.innerText;"
                f"}})()"
            )
        else:
            js = "document.body ? document.body.innerText : ''"

        return self.evaluate_js(js, tab_id, user, timeout=30)
