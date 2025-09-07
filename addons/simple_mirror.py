"""
simple_mirror.py
--------------------
A tiny mitmproxy addon that:
  1) Lets all traffic pass through unchanged
  2) For matching requests, POSTs an exact copy of the original body to a
     configurable HTTP endpoint.

Design goals:
- Mirror only JSON by default (configurable)
- No envelopes/wrappers: send the original request body bytes as-is
- Optional correlation header for debugging
- Non-blocking by default (mirror in a background thread)

Usage example:
  mitmdump -p 8080 -s simple_mirror.py \
    --set mirror_base=http://localhost:8000 \
    --set mirror_path=/ingest \
    --set mirror_match=http://api.example.com \
    --set mirror_methods=POST,PUT,PATCH
"""

from mitmproxy import ctx, http
from urllib.parse import urljoin
import re
import threading
import uuid
import requests


class MirrorAddon:
    def __init__(self):
        self._regex = None

    def load(self, loader):
        loader.add_option("mirror_base", str, "",
                          "Base URL to mirror to (e.g., http://localhost:8000)")
        loader.add_option("mirror_path", str, "/",
                          "Path at mirror_base to POST to (default '/')")
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
        loader.add_option("mirror_timeout", float, 5.0,
                          "HTTP timeout (seconds) for mirror POST")
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
                ctx.log.info("[mirror] No mirror_match set → mirror ALL (subject to method/content-type filters)")

    def request(self, flow: http.HTTPFlow):
        # Always pass through; optionally mirror
        try:
            if not self._should_mirror(flow):
                return

            base = (ctx.options.mirror_base or "").strip()
            if not base:
                # No target configured; nothing to do
                return

            body = flow.request.raw_content or b""
            if not body:
                return  # nothing to mirror

            target = urljoin(base.rstrip("/") + "/", (ctx.options.mirror_path or "/").lstrip("/"))

            headers = {}
            ctype = flow.request.headers.get("content-type")
            if ctype:
                headers["Content-Type"] = ctype

            if ctx.options.mirror_add_header:
                headers[ctx.options.mirror_header_name] = str(uuid.uuid4())

            if ctx.options.mirror_async:
                threading.Thread(
                    target=self._post_copy,
                    args=(target, body, headers, float(ctx.options.mirror_timeout)),
                    daemon=True
                ).start()
            else:
                self._post_copy(target, body, headers, float(ctx.options.mirror_timeout))

        except Exception as e:
            ctx.log.warn(f"[mirror] Exception: {e}")

    # ---- helpers ----

    def _should_mirror(self, flow: http.HTTPFlow) -> bool:
        # Method filter
        allowed = {m.strip().upper() for m in (ctx.options.mirror_methods or "").split(",") if m.strip()}
        if allowed and flow.request.method.upper() not in allowed:
            return False

        # JSON-only filter
        if ctx.options.mirror_json_only:
            ctype = (flow.request.headers.get("content-type") or "").lower()
            if "json" not in ctype:
                return False

        # URL match
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
            # literal substring
            return match in url

    def _post_copy(self, target: str, body: bytes, headers: dict, timeout: float):
        try:
            r = requests.post(target, data=body, headers=headers, timeout=timeout)
            ctx.log.info(f"[mirror] → {target} [{r.status_code}]")
        except Exception as e:
            ctx.log.warn(f"[mirror] POST failed: {e}")


addons = [MirrorAddon()]
