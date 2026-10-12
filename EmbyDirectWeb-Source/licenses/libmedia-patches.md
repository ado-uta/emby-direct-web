# libmedia 1.3.1 本地兼容修改
上游 https://github.com/zhaohappy/libmedia ，提交152f629d3021fd8013efa464fcb7b55f9fbe7753，LGPLv3。
1. AVPlayer.startAudioContext：仅当实例实际启用enableAudioWorklet时加载Worklet，尊重既有选项。原逻辑即使关闭选项仍等待Worklet。当前应用使用内核自带的非Worklet输出路径。
2. AVPlayerUI.destroy：先销毁键盘与UI，再销毁基础播放器，防止UI观察者调用已释放控制器。
精确可重建补丁在tools/vendor.py中；解码WASM未修改。不包含视频编码器。上游源码归其原作者所有。

TS seek patch (0.6): forward optional directwebDurationMs from load.formatOptions to the demux context; in TS chunk 502, use verified file size / Emby duration for the first byte-position estimate, starting two seconds early. Keep original timestamp validation, bounded binary fallback and keyframe scanning. Missing/invalid duration uses upstream behavior. No byte-only seek or transcoding.

0.7 TS seek: retain up to64 observed packet-position/timestamp pairs per open demux context. Use monotonic pair interpolation/extrapolation inside current byte bounds to aim two seconds before requested timestamp. Repeated, out-of-range, missing or non-monotonic estimates fall back to interval midpoint. Upstream timestamp check/keyframe scanning remain unchanged.

0.8: when at least two timestamps were observed during earlier seeks in the current demux context, apply the same bounded interpolation to the initial seek estimate too. No new file fetch, persistent index or unvalidated byte-only seek.

0.18 AudioSourceBufferNode seek fix: clear/disconnect detach onended, stop and disconnect scheduled source nodes, and reset startTime. Scheduling rebases past timestamps to AudioContext.currentTime to prevent post-seek buffer overlap. Rebuildable patch in tools/audio_patch.py, applied by tools/vendor.py. Audio decode and server/video handling are unchanged. Synthetic 48kHz AC3 probe after three seeks: before 113/115 late blocks (max 773ms), after 0/115 (max 0ms).
