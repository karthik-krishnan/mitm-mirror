"""
simple_mirror.py
--------------------
A tiny mitmproxy addon that:
  1) Lets all traffic pass through unchanged
  2) For matching requests, POSTS an exact copy of the **original body** to a
     RequestWeaver (or any) HTTP endpoint.

Design goals:
- Mirror only JSON by default (configurable)
- No wrapping/envelopes: send the same bytes as the original body
- Add one correlation header for debugging (configurable, can be disabled)
- Never block the client: send mirror in a background thread by default

Usage (mitmdump):
  mitmdump -p 8080 -s simple_mirror.py \
    --set mirror_base=http://mirror.example.com \
    --set mirror_path=/ \
    --set mirror_match=http://api.example.com \
    --set mirror_methods=POST,PUT,PATCH

'mirror_match' supports either plain substring matching or regex when prefixed with 'regex:'.
Example regex: --set mirror_match=regex:^https?://api\\.example\\.com(/|$)
"""

from mitmproxy import ctx, http
from urllib.parse import urljoin
import urllib.request, urllib.error
import re
import threading
import uuid


class MirrorAddon:
    def __init__(self):
        self._regex = None

    def load(self, loader):
        # Use only str/bool/int here; avoid float to prevent type errors.
        loader.add_option("mirror_base", str, "",
                          "Base URL to mirror to (e.g., http://localhost:8000)")
        loader.add_option("mirror_path", str, "/",
                          "Path at mirror_base to POST to")
        loader.add_option("mirror_match", str, "",
                          "Substring or 'regex:<pattern>' to select which requests to mirror")
        loader.add_option("mirror_methods", str, "POST,PUT,PATCH",
                          "Comma-separated HTTP methods to mirror")
        loader.add_option("mirror_json_only", bool, True,
                          "If true, mirror only requests with JSON Content-Type")
        loader.add_option("mirror_add_header", bool, True,
                          "Add correlation header to mirrored request")
        loader.add_option("mirror_header_name", str, "X-Mirror-Correlation-Id",
                          "Correlation header name")
        loader.add_option("mirror_timeout_secs", int, 5,
                          "HTTP timeout in seconds for mirror POST (integer)")
        loader.add_option("mirror_async", bool, True,
                          "Send mirror in a background thread (non-blocking)")

    def configure(self, updates):
        mm = ctx.options.mirror_match or ""
        if mm.startswith("regex:"):
            pat = mm[len("regex:"):]
            try:
                self._regex = re.compile(pat)
                ctx.log.info(f"[mirror] Using regex match: {pat}")
            except re.error as e:
                ctx.log.warn(f"[mirror] Invalid regex in mirror_match: {e}")
                self._regex = None
        else:
            self._regex = None
            if mm:
                ctx.log.info(f"[mirror] Using substring match: {mm}")
            else:
                ctx.log.info("[mirror] No mirror_match → mirror ALL (subject to method/content-type filters)")

    def request(self, flow: http.HTTPFlow):
        # Always pass through; optionally mirror
        try:
            if not self._should_mirror(flow):
                return

            base = (ctx.options.mirror_base or "").strip()
            if not base:
                return

            body = flow.request.raw_content or b""
            if not body:
                return

            target = urljoin(base.rstrip("/") + "/", (ctx.options.mirror_path or "/").lstrip("/"))

            headers = {}
            ctype = flow.request.headers.get("content-type")
            if ctype:
                headers["Content-Type"] = ctype

            if ctx.options.mirror_add_header:
                headers[ctx.options.mirror_header_name] = str(uuid.uuid4())

            timeout = max(1, int(ctx.options.mirror_timeout_secs))

            if ctx.options.mirror_async:
                threading.Thread(
                    target=self._post_copy,
                    args=(target, body, headers, timeout),
                    daemon=True,
                ).start()
            else:
                self._post_copy(target, body, headers, timeout)

        except Exception as e:
            ctx.log.warn(f"[mirror] Exception: {e}")

    # ---- helpers ----

    def _should_mirror(self, flow: http.HTTPFlow) -> bool:
        allowed = {m.strip().upper() for m in (ctx.options.mirror_methods or "").split(",") if m.strip()}
        if allowed and flow.request.method.upper() not in allowed:
            return False

        if ctx.options.mirror_json_only:
            ctype = (flow.request.headers.get("content-type") or "").lower()
            if "json" not in ctype:
                return False

        url = flow.request.pretty_url
        match = ctx.options.mirror_match or ""
        if not match:
            return True

        if self._regex:
            try:
                return bool(self._regex.search(url))
            except Exception as e:
                ctx.log.warn(f"[mirror] regex error: {e}")
                return False
        else:
            return match in url

    def _post_copy(self, target: str, body: bytes, headers: dict, timeout_secs: int):
        req = urllib.request.Request(target, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout_secs) as resp:
                ctx.log.info(f"[mirror] → {target} [{resp.status}]")
        except urllib.error.HTTPError as e:
            ctx.log.warn(f"[mirror] POST failed: {e.code} {e.reason}")
        except Exception as e:
            ctx.log.warn(f"[mirror] POST failed: {e}")


addons = [MirrorAddon()]
