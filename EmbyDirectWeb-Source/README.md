# Emby Direct Web

面向 Windows 的 Emby / 115 网盘 302 直连网页播放器。沿用现有 Emby 的地址、账号和媒体库，让视频在本机浏览器解封装、解码和播放，无需服务器转码。

当前版本：**v0.17 测试版**。优先使用 Windows Chrome 或 Edge。

## 下载哪一个

| 文件 | 用途 |
| --- | --- |
| `EmbyDirectWeb-Windows-v0.17.zip` | 直接使用：解压后运行 EXE，不用安装 Python、Node 或 Docker |
| `EmbyDirectWeb-Source-v0.17.zip` | 开发或提交 GitHub：包含项目源码、网页资源、第三方播放器资源、依赖说明和测试 |

建议把源码放在 GitHub 仓库，把这两个 ZIP 放在同版本 Release 附件中。源码包解压后的项目内容可以直接作为仓库内容。

## 功能

- 登录现有 Emby / 302 服务，浏览媒体库、海报、影片介绍、演员和媒体规格。
- 类型多选支持 OR / AND，支持年份下拉选择、演员筛选、搜索及上映时间、添加时间、年份、评分排序。
- 点击海报播放图标在新标签播放，点击其他区域进入详情；详情返回保留筛选状态。
- 支持 MP4、MKV、MPEG-TS；通过 WebCodecs 优先硬件解码，必要时使用本地 WASM。
- 自动启用可用字幕，支持 Emby 外挂、内嵌及本地 SRT / ASS / SSA / VTT；可选择、切换或关闭。
- 播放键旁支持前进 / 后退五秒，提供音轨、倍速、音量及进度控制。
- 播放信息和设置位于顶部，提供不含密码、令牌及签名直链的读取与字幕诊断。
- 提供继续观看、当前浏览器播放历史和后台媒体目录预加载，最多四个播放会话。

## 便携包使用

1. 解压 `EmbyDirectWeb-Windows-v0.17.zip`，保留 EXE 同目录的 `runtime` 文件夹。
2. 双击 `EmbyDirectWeb.exe`，浏览器会自动打开本机网页。
3. 填写原 Emby / 302 地址、用户名和密码。无需填写 115 Cookie，也不需要改 HK 服务器。
4. 进入媒体库筛选影片并播放。右下角托盘图标可重新打开页面或退出程序；关闭网页不会退出程序。

“记住连接信息”默认关闭；勾选后仅在当前浏览器记住地址和用户名，不保存密码。

## 视频如何直连

```text
Emby / 302 服务 → 登录、媒体目录、原文件跳转地址
115 网盘 → Windows 本机按 Range 读取 → 浏览器本地解封装与解码
```

本机 HTTP 服务解决网盘直链与浏览器访问的兼容问题，因此开发者工具中的视频地址显示为 `127.0.0.1` 是正常现象。视频不经过 HK 服务器转发，不请求服务器转码或字幕烧录，也不先下载整部影片。

默认仅监听 `127.0.0.1:18765`；端口被占用时改用空闲端口。当前视频最终地址限定为 115.com、115cdn.com、115cdn.net 及其子域名。

## 浏览器存储

媒体目录和历史播放保存在当前浏览器 IndexedDB，按 Emby 地址和账号隔离；目录十分钟后后台更新，单次索引上限五万条。筛选设置可清除当前账号的浏览器缓存与历史。

密码不持久化，Emby 令牌仅在程序运行期间保存在内存。分享发布 ZIP 不包含个人地址、账号、历史或浏览器资料。不同浏览器或不同本机端口的存储互相独立；“历史播放”记录本网页的播放，“继续观看”读取 Emby 进度。

## 从源码运行

在 Windows 安装 Python 3.11 后，在源码目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe launcher.py
```

源码包附带已固定版本的网页播放器和 WASM 资源，直接运行无需 Node。需要重新生成第三方网页资源时，安装 Node 后执行 `npm ci` 和 `python tools/vendor.py`；该步骤需要下载上游资源，并应用记录在 `licenses/libmedia-patches.md` 中的兼容补丁。

## 构建 Windows 便携包

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe tools/build.py
.\.venv\Scripts\python.exe tools/source_release.py
```

输出便携包与独立源码包。依赖分别锁定在 Python requirements 和 npm package-lock 中；源码包不会包含虚拟环境、node_modules、编译目录、测试视频或测试日志。

## 验证与限制

后端测试：`python -m unittest discover -s tests -p "test_*.py"`。前端逻辑测试：`node tests/test_browser_catalog.cjs`、`node tests/test_player_controls.cjs`、`node tests/test_seek_estimate.cjs`。真实浏览器集成测试：`python tools/browser_smoke.py`，需要已安装 Chrome 及开发依赖；FFmpeg 只生成测试样本，不参与生产播放。

已验证 H.264 / AAC、AC3、HEVC / EAC3、多音轨、SRT / ASS 外挂切换、并发播放与进度同步。测试样本不能代表全部 4K、HDR、Dolby Vision、DTS 或字幕组合；图片型外挂字幕暂不支持，不承诺音频位流直通。

首次预加载速度取决于 Emby 响应；视频定位受 CDN 延迟和文件关键帧间隔影响，五秒按钮表示定位目标。115 的 UA / IP 绑定可能影响直链，需要在高级连接设置中填写现有方案要求的 User-Agent。只接受原文件跳转，遇到不兼容入口不会回退到 HK 视频转发。

## 项目文件与第三方组件

`server.py` 为本机接口与媒体读取，`core.py` 为直链及读取辅助，`catalog.py` 为媒体查询，`subtitles.py` 为字幕轨道处理，`launcher.py` 为托盘入口，`web/` 为网页与播放器资源，`tools/` 为构建和验证脚本。

播放器依赖 libmedia AVPlayerUI 1.3.1。第三方许可证、来源和本地补丁保留在 `licenses/`，版本信息保留在 `web/vendor/versions.json`。项目自有代码的授权以仓库维护者最终选择的许可证为准；第三方组件继续遵守各自许可证。

历史开发记录见 `docs/CHANGELOG.md`。
