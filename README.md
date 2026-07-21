# NASDeployer - NAS 一键部署工具

Windows 桌面 GUI 工具，一键部署 26 个 Docker 应用到飞牛 OS (fnOS) 或极空间 (ZSpace)。

## v1.1 新增功能

- **多 NAS profile 切换**: 顶部 dropdown 切换 fnOS/ZSpace 等多个 NAS
- **keyring 密码自动保存**: 密码存 Windows Credential Manager, 二次启动自动填
- **实时进度窗口**: 安装/拉取镜像时弹进度条 + 实时日志流, 可取消
- **应用搜索 + 分组折叠**: 搜索框 + "仅显示已选" + 全选/全不选按钮

## v1.1 迁移

v1.0 的单 NAS 配置 `~/.nas_deployer/config.json` 自动迁移到 v1.1 的多 NAS profile, 无需手动操作.

## 功能

- **多 NAS 管理**: dropdown 切换, ➕/✏️/🗑 增删改
- **密码安全**: keyring (Windows Credential Manager) 加密存储
- **图形化输入** NAS IP / 用户名 / 密码
- **SSH 连接 + Docker Compose 自动部署**
- **按 profile 分组管理**：🎬 movie / 📚 read / 🎵 pt / 🧭 nav / 🤖 ai / 🎨 draw / 📰 news / 📺 tv / 🔧 tools
- **应用原子操作**：安装 / 停止 / 重启 / 拉取最新镜像
- **实时进度窗口**: docker compose pull/up 输出逐行显示, 可中途取消
- **应用搜索**: 名称/描述/ID 模糊匹配
- **仅显示已选**: 隐藏未勾选的应用, 方便管理大批量
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
2. **顶部栏**: 点 `➕` 添加 NAS (或选已添加的)
   - 名称 / 类型 / IP / 端口 / 用户名, 保存
3. **连接 Tab**:
   - 选好 NAS, 输入密码 (可勾选 "保存到 keyring")
   - 点 "🔌 测试并连接"
4. **应用 Tab**:
   - 搜索框过滤应用
   - 勾选 Profile (整组勾选) 或单独勾选
   - 点 "▶ 安装选中" → 弹进度窗口看实时日志
5. **状态 Tab**:
   - 查看容器状态
   - 右键查看日志 / 重启 / 停止
6. **日志 Tab**:
   - 实时查看所有操作的日志

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
│   ├── app.py              # 主 GUI (ttkbootstrap, 多 NAS + 搜索)
│   ├── ssh_client.py       # SSH + Docker 编排 (含流式命令)
│   ├── apps.py             # 26 服务元数据
│   ├── compose_data.py     # 内嵌 docker-compose.yml
│   ├── nas_profile.py      # 多 NAS profile 管理 + keyring
│   └── progress_window.py  # 进度条 + 实时日志流窗口
├── tests/
│   ├── test_ssh_client.py  # SSH mock 测试
│   └── test_nas_profile.py # NAS profile + keyring 测试
├── .github/
│   └── workflows/
│       └── build.yml       # GitHub Actions CI
├── build.bat               # Windows 本地构建
├── requirements.txt
├── README.md
└── .gitignore
```

## 配置存储

- `~/.nas_deployer/profiles.json` - NAS profile 列表 (不含密码)
- 密码存系统 keyring (Windows Credential Manager) - `keyring set NASDeployer <profile_id>`

## 已知问题

1. **部分镜像名可能拉不到**（如 insdown / xiaoya / iyuu），需要确认 docker.io / ghcr.io / 镜像源可用
2. **小雅全家桶 + movie 全开 = 资源重叠**
3. **极空间默认禁 SSH**，需要先开启或用其他方式

## License

MIT

## 作者

Bingnan (18510631357a) + MiniMax-M3