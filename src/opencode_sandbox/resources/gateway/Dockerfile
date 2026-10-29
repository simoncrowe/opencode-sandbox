FROM alpine:3.22

RUN apk add --no-cache socat tini

COPY entrypoint.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/sbin/tini", "--", "/usr/local/bin/entrypoint.sh"]
