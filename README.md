# NASDeployer - NAS 一键部署工具

Windows 桌面 GUI 工具，一键部署 26 个 Docker 应用到飞牛 OS (fnOS) 或极空间 (ZSpace)。

## 功能

- **图形化输入** NAS IP / 用户名 / 密码
- **SSH 连接 + Docker Compose 自动部署**
- **按 profile 分组管理**：🎬 movie / 📚 read / 🎵 pt / 🧭 nav / 🤖 ai / 🎨 draw / 📰 news / 📺 tv / 🔧 tools
- **应用原子操作**：安装 / 停止 / 重启 / 拉取最新镜像
- **实时日志** + 容器状态查看
- **NAS 资源监控**（磁盘 / 内存）
- **容器右键菜单**：日志 / 重启 / 停止

## 截图

> TODO: 加截图

## 快速开始

### 方式 1: 下载预编译 EXE (推荐)

去 [Releases](https://github.com/你的用户名/nas_deployer/releases) 下载 `NASDeployer.exe`，双击运行。

**注意**：第一次运行时 Windows Defender 可能拦截，需要"仍要运行"。

### 方式 2: 从源码构建

需要 Python 3.11+:

```cmd
git clone <repo>
cd nas_deployer
build.bat
```

输出：`dist\NASDeployer.exe`

### 方式 3: GitHub Actions 自动构建

每次 push 到 main 自动构建 Windows EXE，在 Actions 页面下载 artifacts。

## 使用流程

1. **打开 EXE**
2. **连接 Tab**：
   - 选择 NAS 类型 (fnOS / ZSpace)
   - 输入 IP、端口、用户名、密码
   - 点击 "测试连接"
3. **应用 Tab**：
   - 勾选 Profile (整组勾选) 或单独勾选应用
   - 点击 "▶ 安装选中"
4. **状态 Tab**：
   - 查看容器状态
   - 右键查看日志 / 重启 / 停止
5. **日志 Tab**：
   - 实时查看部署日志

## 前置条件（NAS 端）

- 已开启 SSH 服务
- 已安装 Docker + Docker Compose
- 当前用户在 `docker` 组（极空间需 sudo）

## 26 个应用清单

| Profile | 应用 | 端口 | 内存 |
|---|---|---|---|
| 🎬 movie | MoviePilot | 5000 | 1G |
| | qBittorrent | 8080 | 200M |
| | LibreTV | 8081 | 200M |
| | 小雅全家桶 | 5678 | 2G |
| 📚 read | Immich | 2283 | 2G |
| | Calibre-Web | 8083 | 256M |
| | Audiobookshelf | 13378 | 300M |
| | SiYuan | 6806 | 300M |
| 🎵 pt | Navidrome | 4533 | 200M |
| | MiMusic | 8181 | 300M |
| | IYUU | 8787 | 200M |
| 🧭 nav | Dashy | 8082 | 100M |
| | Lucky | 16601 | 100M |
| 🤖 ai | HivisionIDPhotos | 7860 | 1G |
| | edge-tts | 8089 | 100M |
| | yt-dlp | 8091 | 300M |
| 🎨 draw | Excalidraw | 5001 | 200M |
| | Photopea | 8085 | 200M |
| | OnlyOffice | 8087 | 1G |
| 📰 news | RSSHub | 1200 | 512M |
| | FreshRSS | 8086 | 200M |
| | PanSearch | 5522 | 200M |
| 📺 tv | m3u Manager | 8088 | 100M |
| | IPTV Auto | (cron) | 50M |
| 🔧 tools | insdown | 8888 | 200M |
| | Stirling PDF | 8084 | 300M |
| | BiliBiliTool | 8090 | 300M |

## 项目结构

```
nas_deployer/
├── src/
│   ├── app.py              # 主 GUI (ttkbootstrap)
│   ├── ssh_client.py       # SSH + Docker 编排
│   ├── apps.py             # 26 服务元数据
│   └── compose_data.py     # 内嵌 docker-compose.yml
├── .github/
│   └── workflows/
│       └── build.yml       # GitHub Actions CI
├── build.bat               # Windows 本地构建
├── requirements.txt
├── README.md
└── .gitignore
```

## 配置存储

`~/.nas_deployer/config.json` 存储 NAS 连接信息（**密码不保存**，每次输入）。

## 已知问题

1. **部分镜像名可能拉不到**（如 insdown / xiaoya / iyuu），需要确认 docker.io / ghcr.io / 镜像源可用
2. **小雅全家桶 + movie 全开 = 资源重叠**
3. **极空间默认禁 SSH**，需要先开启或用其他方式

## License

MIT

## 作者

Bingnan (18510631357a) + MiniMax-M3