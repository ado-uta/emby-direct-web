# GitHub 发布文案

## 仓库名称

emby-direct-web

## 仓库描述

Windows 本机 Emby / 115 网盘 302 直连网页播放器，支持 MKV、MP4、多音轨和外挂字幕，无需服务器转码；提供类型与年份筛选、播放历史及浏览器预加载。

## 源码包说明

EmbyDirectWeb-Source-v0.18.zip：适合开发、修改或提交 GitHub，包含 Python 本机服务、网页源码、固定版本的播放器与 WASM 资源、构建脚本、测试和第三方许可证。解压后把 EmbyDirectWeb-Source 目录中的内容上传到仓库，不需要上传 ZIP、虚拟环境或测试产物。根目录 README 提供运行与构建步骤。

## 便携包说明

EmbyDirectWeb-Windows-v0.18.zip：Windows 直接使用版。解压后双击 EmbyDirectWeb.exe，保留 runtime 文件夹。无需安装 Python、Node 或 Docker，填写现有 Emby / 302 地址及账号即可使用。包内不包含个人连接信息或浏览器历史。

## Release 标题

v0.18 — 跳转后音频撕裂修复

## Release 正文

修复拖动进度后旧音频排程时钟及回调导致的撕裂杂音；保留顶部播放工具栏、前后五秒跳转和默认字幕。目录及历史缓存保存在各自浏览器。

附件分为源码包与 Windows 便携包。普通用户下载 Windows 包，开发者下载 Source 包。视频保持 115 到本机的原文件播放，不使用服务器转码。当前为测试版本，复杂编码、图片型外挂字幕和长关键帧间隔文件仍有兼容或定位限制。

仓库使用项目根目录 README；两个下载包建议作为 Release 附件。
