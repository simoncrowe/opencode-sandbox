FROM alpine:3.22

RUN apk add --no-cache tinyproxy socat tini

COPY entrypoint.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/sbin/tini", "--", "/usr/local/bin/entrypoint.sh"]
