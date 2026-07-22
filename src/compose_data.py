# ==============================================================================
# NAS 一键部署工具 - 内嵌 docker-compose.yml
# 来源: nas_deploy_v1/docker-compose.yml (v1.0)
# ==============================================================================

DOCKER_COMPOSE_YML = """networks:
  nas_net:
    driver: bridge
    name: nas_net

services:
  # ============ MOVIE PROFILE ============
  moviepilot:
    image: jxxghp/moviepilot-v2:latest
    container_name: moviepilot
    restart: unless-stopped
    profiles: ["movie", "all"]
    ports: ["5000:5000"]
    volumes:
      - ./configs/moviepilot:/config
      - ./movies:/media/movies
      - ./downloads:/media/downloads
    environment:
      - NGINX_PORT=5000
      - SUPERUSER=admin
      - SUPERPASS=ChangeMe123!
      - TZ=Asia/Shanghai
    networks: [nas_net]

  qbittorrent:
    image: linuxserver/qbittorrent:latest
    container_name: qbittorrent
    restart: unless-stopped
    profiles: ["movie", "all"]
    ports: ["8080:8080", "6881:6881", "6881:6881/udp"]
    volumes:
      - ./configs/qbittorrent:/config
      - ./downloads:/downloads
    environment:
      - WEBUI_PORT=8080
      - TZ=Asia/Shanghai
    networks: [nas_net]

  libretv:
    image: libreteam/libretv:latest
    container_name: libretv
    restart: unless-stopped
    profiles: ["movie", "all"]
    ports: ["8081:8081"]
    networks: [nas_net]

  xiaoya:
    image: xiaoyaliu/alist:latest
    container_name: xiaoya
    restart: unless-stopped
    profiles: ["movie", "all"]
    ports: ["5678:5678"]
    volumes:
      - ./configs/xiaoya:/data
    networks: [nas_net]

  # ============ READ PROFILE ============
  immich:
    image: ghcr.io/immich-app/immich-server:release
    container_name: immich
    restart: unless-stopped
    profiles: ["read", "all"]
    ports: ["2283:2283"]
    volumes:
      - ./configs/immich:/usr/src/app/upload
      - ./photos:/usr/src/app/external
    environment:
      - DB_HOSTNAME=immich_postgres
      - DB_USERNAME=postgres
      - DB_PASSWORD=ChangeMe123!
      - DB_DATABASE_NAME=immich
      - REDIS_HOSTNAME=immich_redis
      - JWT_SECRET=ChangeMeToRandom32Char!
    depends_on: ["immich_postgres", "immich_redis"]
    networks: [nas_net]

  immich_postgres:
    image: tensorchord/pgvecto-rs:pg16-v0.3.0
    container_name: immich_postgres
    restart: unless-stopped
    profiles: ["read", "all"]
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=ChangeMe123!
      - POSTGRES_DB=immich
    volumes:
      - ./configs/immich_db:/var/lib/postgresql/data
    networks: [nas_net]

  immich_redis:
    image: redis:7-alpine
    container_name: immich_redis
    restart: unless-stopped
    profiles: ["read", "all"]
    networks: [nas_net]

  calibre_web:
    image: linuxserver/calibre-web:latest
    container_name: calibre_web
    restart: unless-stopped
    profiles: ["read", "all"]
    ports: ["8083:8083"]
    volumes:
      - ./configs/calibre:/config
      - ./books:/books
    environment:
      - TZ=Asia/Shanghai
    networks: [nas_net]

  audiobookshelf:
    image: ghcr.io/advplyr/audiobookshelf:latest
    container_name: audiobookshelf
    restart: unless-stopped
    profiles: ["read", "all"]
    ports: ["13378:80"]
    volumes:
      - ./configs/audiobookshelf:/config
      - ./books:/audiobooks
    environment:
      - TZ=Asia/Shanghai
    networks: [nas_net]

  siyuan:
    image: b3log/siyuan:latest
    container_name: siyuan
    restart: unless-stopped
    profiles: ["read", "all"]
    ports: ["6806:6806"]
    volumes:
      - ./configs/siyuan:/home/siyuan/Documents/SiYuan
    networks: [nas_net]

  # ============ PT PROFILE ============
  navidrome:
    image: deluan/navidrome:latest
    container_name: navidrome
    restart: unless-stopped
    profiles: ["pt", "all"]
    ports: ["4533:4533"]
    volumes:
      - ./configs/navidrome:/data
      - ./music:/music:ro
    environment:
      - ND_SCANSCHEDULE=1h
      - TZ=Asia/Shanghai
    networks: [nas_net]

  mimusic:
    image: xjasonlyu/mimusic:latest
    container_name: mimusic
    restart: unless-stopped
    profiles: ["pt", "all"]
    ports: ["8181:8181"]
    volumes:
      - ./configs/mimusic:/app/data
      - ./music:/music:ro
    networks: [nas_net]

  iyuu:
    image: iyuan/iyuuplus:latest
    container_name: iyuu
    restart: unless-stopped
    profiles: ["pt", "all"]
    ports: ["8787:8787"]
    volumes:
      - ./configs/iyuu:/iyuu/data
    networks: [nas_net]

  # ============ NAV PROFILE ============
  dashy:
    image: lissy93/dashy:latest
    container_name: dashy
    restart: unless-stopped
    profiles: ["nav", "all"]
    ports: ["8082:8080"]
    volumes:
      - ./configs/dashy:/app/user-data
    networks: [nas_net]

  lucky:
    image: gdy666/lucky:latest
    container_name: lucky
    restart: unless-stopped
    profiles: ["nav", "all"]
    ports: ["16601:16601"]
    volumes:
      - ./configs/lucky:/goodluck
    network_mode: host

  # ============ AI PROFILE ============
  hivision:
    image: linzeyi/hivision_idphotos:latest
    container_name: hivision
    restart: unless-stopped
    profiles: ["ai", "all"]
    ports: ["7860:7860"]
    volumes:
      - ./configs/hivision:/app/data
    networks: [nas_net]

  edge_tts:
    image: ghcr.io/satyam-singh-19/edge-tts-web-ui:latest
    container_name: edge_tts
    restart: unless-stopped
    profiles: ["ai", "all"]
    ports: ["8089:8080"]
    networks: [nas_net]

  yt_dlp_web:
    image: lscrnl/me-tube:latest
    container_name: yt_dlp_web
    restart: unless-stopped
    profiles: ["ai", "all"]
    ports: ["8091:8081"]
    volumes:
      - ./configs/metube:/config
      - ./downloads:/downloads
    networks: [nas_net]

  # ============ DRAW PROFILE ============
  excalidraw:
    image: excalidraw/excalidraw:latest
    container_name: excalidraw
    restart: unless-stopped
    profiles: ["draw", "all"]
    ports: ["5001:80"]
    networks: [nas_net]

  photopea:
    image: ivandejan/photopea:latest
    container_name: photopea
    restart: unless-stopped
    profiles: ["draw", "all"]
    ports: ["8085:8080"]
    networks: [nas_net]

  onlyoffice:
    image: onlyoffice/documentserver:latest
    container_name: onlyoffice
    restart: unless-stopped
    profiles: ["draw", "all"]
    ports: ["8087:80"]
    volumes:
      - ./configs/onlyoffice:/var/www/onlyoffice/Data
    networks: [nas_net]

  # ============ NEWS PROFILE ============
  rsshub:
    image: diygod/rsshub:latest
    container_name: rsshub
    restart: unless-stopped
    profiles: ["news", "all"]
    ports: ["1200:1200"]
    environment:
      - TZ=Asia/Shanghai
    networks: [nas_net]

  freshrss:
    image: freshrss/freshrss:latest
    container_name: freshrss
    restart: unless-stopped
    profiles: ["news", "all"]
    ports: ["8086:80"]
    volumes:
      - ./configs/freshrss:/var/www/FreshRSS/data
    environment:
      - TZ=Asia/Shanghai
      - CRON_MIN=1
    networks: [nas_net]

  pansearch:
    image: nvzai/pansearch:latest
    container_name: pansearch
    restart: unless-stopped
    profiles: ["news", "all"]
    ports: ["5522:80"]
    networks: [nas_net]

  # ============ TV PROFILE ============
  m3u_manager:
    image: sergeytykhonov/m3u-proxy:latest
    container_name: m3u_manager
    restart: unless-stopped
    profiles: ["tv", "all"]
    ports: ["8088:8080"]
    volumes:
      - ./configs/m3u:/config
    networks: [nas_net]

  iptv_auto:
    image: jiangjiahui/iptv-auto-update:latest
    container_name: iptv_auto
    restart: unless-stopped
    profiles: ["tv", "all"]
    volumes:
      - ./configs/iptv:/config
      - ./tv:/tv
    environment:
      - TZ=Asia/Shanghai
      - CRON=0 6 * * *
    networks: [nas_net]

  # ============ TOOLS PROFILE ============
  insdown:
    image: ghcr.io/svenstaro/insdown:latest
    container_name: insdown
    restart: unless-stopped
    profiles: ["tools", "all"]
    ports: ["8888:8080"]
    volumes:
      - ./ins:/data
    networks: [nas_net]

  stirling_pdf:
    image: stirlingtools/stirling-pdf:latest
    container_name: stirling_pdf
    restart: unless-stopped
    profiles: ["tools", "all"]
    ports: ["8084:8080"]
    volumes:
      - ./configs/stirling:/configs
    environment:
      - TZ=Asia/Shanghai
    networks: [nas_net]

  bilibili_tool:
    image: nickzyu/bilibili-tool:latest
    container_name: bilibili_tool
    restart: unless-stopped
    profiles: ["tools", "all"]
    ports: ["8090:8080"]
    volumes:
      - ./configs/bilibili:/app/data
      - ./downloads:/downloads
    environment:
      - TZ=Asia/Shanghai
    networks: [nas_net]

  # ============ MIHOMO VPN (v2.0.6: 从 net profile 独立, 改走首页一键安装) ============
  # mihomo (Clash.Meta) 透明代理 — 帮 docker pull 走代理, 解决 GFW 拦 docker.io
  # 配置在 ./configs/mihomo/config.yaml (用户填订阅 URL)
  # 用法: 首页 (连接 Tab) 红色 VPN 卡片 → [🚀 一键安装并配置 VPN]
  #       后续 docker pull 走 http://127.0.0.1:7890
  # UI 控制台: http://<NAS_IP>:9091/ui (yacd)
  mihomo:
    image: metacubex/mihomo:latest
    container_name: mihomo
    restart: unless-stopped
    # v2.0.6: 不再依赖 net profile, 走默认 profile (用户从首页 VPN 卡片触发)
    profiles: ["all"]
    ports:
      - "7890:7890"     # HTTP/SOCKS5 mixed proxy
      - "9091:9091"     # yacd 控制面板
    volumes:
      - ./configs/mihomo:/root/.config/mihomo
    network_mode: host   # 与 docker network 并存; host 模式让 7890 直接是 127.0.0.1
"""