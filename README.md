# mitm-mirror

A tiny, generic **mitmproxy** addon packaged as a container. It runs as an explicit HTTP proxy and **mirrors matching requests** to a configurable HTTP endpoint while letting original requests pass through **unchanged**.

> No coupling to any specific validator/service. Point it at any HTTP URL.

---

## Features

* Explicit HTTP proxy (default `:8080`)
* Pass-through to the original destination
* Mirrors **original request body bytes** to a target endpoint
* Filters by **method**, **URL substring or regex**, and optionally **Content-Type: json**
* Optional correlation header on mirrored requests
* Non-blocking by default (mirror in a background thread)

---

## Quick start (Docker)

```bash
# Build
docker build -t yourorg/mitm-mirror:1.0.0 .

# Run (mirror JSON POST/PUT/PATCH bodies to a local endpoint)
docker run --rm -it \
  -p 8080:8080 \
  -e MIRROR_BASE=http://host.docker.internal:8000 \
  -e MIRROR_PATH=/ \
  -e MIRROR_MATCH=http://api.example.com \
  yourorg/mitm-mirror:1.0.0
```

Then set your device/OS **HTTP Proxy** to your host IP and port **8080**.

> For macOS/Windows Docker, `host.docker.internal` resolves to your host machine.

---

## Configuration (env → passed as `--set` to mitmproxy)

| Env var              | Default                   | Purpose                                                                  |
| -------------------- | ------------------------- | ------------------------------------------------------------------------ |
| `MITM_LISTEN_PORT`   | `8080`                    | Proxy listen port                                                        |
| `MIRROR_BASE`        | *(empty)*                 | **Required**. Target base URL (e.g., `http://host.docker.internal:8000`) |
| `MIRROR_PATH`        | `/`                       | Path at the base to POST to                                              |
| `MIRROR_MATCH`       | *(empty)*                 | Substring OR `regex:<pattern>` to choose which URLs to mirror            |
| `MIRROR_METHODS`     | `POST,PUT,PATCH`          | Comma-separated list of HTTP methods to mirror                           |
| `MIRROR_JSON_ONLY`   | `true`                    | Mirror only when `Content-Type` contains `json`                          |
| `MIRROR_ADD_HEADER`  | `true`                    | Add a correlation header to mirrored requests                            |
| `MIRROR_HEADER_NAME` | `X-Mirror-Correlation-Id` | Correlation header name                                                  |
| `MIRROR_TIMEOUT`     | `5.0`                     | Timeout (seconds) for mirror POST                                        |
| `MIRROR_ASYNC`       | `true`                    | Send mirror in a background thread (non-blocking)                        |

Example URL filters:

* Substring: `MIRROR_MATCH=http://api.example.com`
* Regex: `MIRROR_MATCH=regex:^https?://api\.example\.com(/|$)`

---

## Regex tip

`.` matches any character in regex. If you mean a literal dot, escape it: `\.`

Examples:

* Substring: `--set mirror_match=http://192.168.1.10:2000`
* Regex: `--set mirror_match=regex:^http://192\.168\.1\.10:2000`

---

## HTTPS & CA trust

For HTTPS interception, install and **trust** the mitmproxy CA certificate on the device/OS. Apps with **certificate pinning** cannot be intercepted.

---

## License

MIT © Karthik Krishnan
