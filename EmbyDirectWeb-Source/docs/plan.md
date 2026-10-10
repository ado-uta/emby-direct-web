# 实现与验证计划
使用 writing-plans 技能；本会话直接执行用户已批准的设计。
1. core.py：URL、转码禁用、Range、重定向判断；tests/test_core.py 先红后绿。
2. server.py：仅本机 HTTP 服务、随机会话凭据、Emby API 白名单、直链流读取、进度回报。tests/test_server.py 用假 Emby/网盘 HTTP 服务验证 302、Range、令牌不外泄、拒绝 HK 视频回退。
3. web/：登录、媒体库、搜索、文件夹、续播、多区域播放器，固定 @libmedia/avplayer-ui 1.3.1，本地静态解码依赖。
4. 浏览器验证 UI 与真实本地样本播放、打包 EXE、启动包验证、中文使用说明。真实用户 Emby/115 登录不在自动化测试中输入，需要最终实机验收。
