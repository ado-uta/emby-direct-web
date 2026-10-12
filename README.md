# Emby Direct Web

Windows 本机 Emby / 115 网盘 302 直连网页播放器。沿用现有 Emby 地址和账号，在本机浏览器解封装与解码视频，无需服务器转码。

当前源码版本：**v0.18 测试版**。

## v0.18 修复

修复拖动进度后音频排程沿用旧时钟、旧片段回调干扰新队列，造成声音撕裂、延迟和杂音的问题。跳转时停止旧片段、清理回调并重置排程时钟，视频保持原 302 直连链路。

合成音轨连续三次跳转验证：过期音频排程由 113/115 个降到 0/115 个。浏览器并发播放、音轨切换、字幕切换、进度同步和 Windows 程序自检通过；真实网盘与不同设备仍需按实际播放情况验收。

## 功能

- MP4、MKV、MPEG-TS，本机 WebCodecs / WASM 解码。
- 类型 OR / AND 多选、年份选择、演员筛选、搜索及评分排序。
- 媒体详情、浏览器播放历史和后台目录预加载。
- 默认字幕，Emby 外挂及内嵌字幕切换；支持本地文本字幕。
- 新标签播放、前进 / 后退五秒，顶部播放信息和设置，最多四个播放会话。
- 目录与历史缓存保存在各自浏览器，不打包个人连接信息。

## 源码与使用说明

源码位于 [EmbyDirectWeb-Source](EmbyDirectWeb-Source/)，完整运行、构建与兼容性说明见 [项目 README](EmbyDirectWeb-Source/README.md)。

在 Windows 安装 Python 3.11，进入源码目录后执行：

```powershell
cd EmbyDirectWeb-Source
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe launcher.py
```

便携包解压后运行 `EmbyDirectWeb.exe`，并保留 `runtime` 文件夹，无需安装 Python、Node 或 Docker。便携包可作为 GitHub Release 附件发布。

第三方组件来源、许可证与可重建补丁见 [licenses](EmbyDirectWeb-Source/licenses/)。
