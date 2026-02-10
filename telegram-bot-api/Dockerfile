FROM aiogram/telegram-bot-api:latest

# Install proxychains-ng to tunnel MTProto through HTTP/SOCKS proxy
RUN apk add --no-cache proxychains-ng

# proxychains config: use XRay HTTP proxy on host (network_mode: host)
RUN echo "strict_chain" > /etc/proxychains/proxychains.conf && \
    echo "proxy_dns" >> /etc/proxychains/proxychains.conf && \
    echo "tcp_read_time_out 15000" >> /etc/proxychains/proxychains.conf && \
    echo "tcp_connect_time_out 8000" >> /etc/proxychains/proxychains.conf && \
    echo "[ProxyList]" >> /etc/proxychains/proxychains.conf && \
    echo "http 127.0.0.1 10809" >> /etc/proxychains/proxychains.conf

# Wrap entrypoint with proxychains
COPY entrypoint-proxy.sh /entrypoint-proxy.sh
RUN chmod +x /entrypoint-proxy.sh

ENTRYPOINT ["/entrypoint-proxy.sh"]
