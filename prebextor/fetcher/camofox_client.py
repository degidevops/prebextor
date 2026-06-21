"""CamoFox CLI subprocess wrapper for Prebextor.

Verified against the actual `camofox` CLI in this environment:

    camofox open <url> [--user <u>]
    camofox close [tabId] [--user <u>]
    camofox snapshot [tabId] [--user <u>]
    camofox eval <expression> [tabId] [--user <u>]
    camofox wait <networkidle|selector|navigation> [tabId] [--timeout <ms>] [--user <u>]

Prebextor's blueprint (§2.2) calls three MCP camofox tools as the surgical
core: snapshot, evaluate_js, get_page_html. The CLI mirrors two of those
directly (snapshot, eval). For get_page_html on a selector, there is no
direct CLI match — we emulate it via `eval
"document.querySelector('<sel>').outerHTML"`, with chunked retrieval to
respect camofox eval's stdout cap (~1MB).

Eval output format:
    ok: true
    result: <value>          # may span multiple lines
    resultType: string
    truncated: false
"""

from __future__ import annotations

import subprocess
import time
import uuid
from typing import List, Optional, Tuple


class CamoFoxClient:
    """Subprocess wrapper around `camofox`. Stateless across requests."""

    def __init__(self, default_timeout: int = 30) -> None:
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
        """`camofox open <url> --user <u>`, then wait networkidle.

        Returns the new tabId or None.
        """
        stdout, _, rc = self.run(["open", url], user=user)
        if rc != 0:
            return None
        tab_id = self.extract_tab_id(stdout)
        if tab_id:
            # Best-effort wait. Don't fail pipeline on timeout.
            self.wait("networkidle", tab_id, user=user, timeout_ms=wait_networkidle_ms)
        return tab_id

    def close_tab(self, tab_id: str, user: str) -> None:
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
        """`camofox wait <condition> <tabId> --timeout <ms> --user <u>`."""
        stdout, _, rc = self.run(
            ["wait", condition, tab_id, "--timeout", str(timeout_ms), "--user", user],
            user=user,
            timeout=max(10, timeout_ms // 1000 + 5),
        )
        return rc == 0

    def snapshot(self, tab_id: str, user: str, timeout: int = 60) -> Optional[str]:
        """`camofox snapshot <tabId> --user <u>`. Returns raw snapshot stdout."""
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
        """`camofox eval "<expr>" <tabId> --user <u>`. Returns parsed `result:`."""
        stdout, _, rc = self.run(
            ["eval", expression, tab_id],
            user=user,
            timeout=timeout,
        )
        if rc != 0:
            return None
        return self.extract_result(stdout)

    # ---------- surgical HTML retrieval (no direct CLI match) ----------

    def get_html(
        self,
        tab_id: str,
        user: str,
        selector: Optional[str] = None,
        chunk_size: int = 20000,
    ) -> Optional[str]:
        """Emulate blueprint §2.2 Phase 3 (`get_page_html`).

        Without selector: returns innerHTML of `documentElement` (chunked).
        With selector: returns outerHTML of the first element matching the
        selector (chunked). Both write to `window.__pe_html` first to avoid
        bursting the ~1MB stdout cap.
        """
        # Stage 1: determine source and staging.
        if selector:
            # Escape single quotes.
            js_selector = selector.replace("'", "\\'")
            stage_expr = (
                f"(function(){{"
                f" const el = document.querySelector('{js_selector}');"
                f" if(!el) {{ return null; }}"
                f" window.__pe_html = el.outerHTML;"
                f" return el.outerHTML.length;"
                f"}})()"
            )
            expr_kind = f"selector='{selector}'"
        else:
            stage_expr = (
                "(()=>{"
                "window.__pe_html = document.documentElement.outerHTML;"
                "return document.documentElement.outerHTML.length;"
                "})()"
            )
            expr_kind = "documentElement"

        # Stage A: stage into window.__pe_html and return length.
        length_str = self.evaluate_js(stage_expr, tab_id, user, timeout=30)
        if length_str is None:
            return None
        try:
            length = int(length_str.strip())
        except (TypeError, ValueError):
            # If the expression returned null (selector matched nothing), retry
            # with no selector so we still have something to return.
            if selector:
                return self.get_html(tab_id, user, selector=None, chunk_size=chunk_size)
            return None

        if length == 0:
            return ""

        # Stage B: chunk retrieval using JSON.stringify to keep transports safe.
        chunks: List[str] = []
        pos = 0
        while pos < length:
            end = min(pos + chunk_size, length)
            chunk_expr = (
                f"JSON.stringify(window.__pe_html.substring({pos},{end}))"
            )
            part_json = self.evaluate_js(chunk_expr, tab_id, user, timeout=30)
            if part_json is None:
                return None
            try:
                import json
                part = json.loads(part_json.strip())
            except Exception:
                # Plain-string fallback (older camofox builds).
                part = part_json
            if not part:
                break
            chunks.append(part)
            pos += len(part)

        html = "".join(chunks)
        # Drop the staging sentinel.
        try:
            self.evaluate_js("delete window.__pe_html; null;", tab_id, user, timeout=10)
        except Exception:
            pass
        return html
