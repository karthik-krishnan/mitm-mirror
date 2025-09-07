# Simple mitmproxy mirror image (no product coupling)
FROM mitmproxy/mitmproxy:latest

# Install Python deps needed by the addon
RUN python -m pip install --no-cache-dir requests==2.32.3

# Copy addon into container
COPY addons/simple_mirror.py /addons/simple_mirror.py

# Defaults (all overridable at runtime)
ENV MITM_LISTEN_PORT=8080
ENV MIRROR_BASE=
ENV MIRROR_PATH=/
ENV MIRROR_MATCH=
ENV MIRROR_METHODS=POST,PUT,PATCH
ENV MIRROR_JSON_ONLY=true
ENV MIRROR_ADD_HEADER=true
ENV MIRROR_HEADER_NAME=X-Mirror-Correlation-Id
ENV MIRROR_TIMEOUT=5.0
ENV MIRROR_ASYNC=true

EXPOSE 8080 8081

# Pass envs to addon via --set (works on both Linux & macOS)
CMD ["sh", "-lc", "\
  mitmdump -p ${MITM_LISTEN_PORT} \
    -s /addons/simple_mirror.py \
    --set mirror_base=${MIRROR_BASE} \
    --set mirror_path=${MIRROR_PATH} \
    --set mirror_match=${MIRROR_MATCH} \
    --set mirror_methods=${MIRROR_METHODS} \
    --set mirror_json_only=${MIRROR_JSON_ONLY} \
    --set mirror_add_header=${MIRROR_ADD_HEADER} \
    --set mirror_header_name=${MIRROR_HEADER_NAME} \
    --set mirror_timeout=${MIRROR_TIMEOUT} \
    --set mirror_async=${MIRROR_ASYNC} \
"]
