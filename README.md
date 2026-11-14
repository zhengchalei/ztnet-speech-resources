# ZTNET 语音资源

为 ZTNET Cloud / Edge 提供预编译的 eSpeak-NG 轻量普通话资源。普通使用者直接在应用中一键安装，无需编译或填写下载地址。

## 下载

在 [Releases](https://github.com/zhengchalei/ztnet-speech-resources/releases/latest) 下载：

- [linux-arm64.zip](https://github.com/zhengchalei/ztnet-speech-resources/releases/download/espeak-ng-1.52.0-20261114/linux-arm64.zip)：RK3588、RK3562 等 Linux ARM64 Edge。
- [linux-x64.zip](https://github.com/zhengchalei/ztnet-speech-resources/releases/download/espeak-ng-1.52.0-20261114/linux-x64.zip)：Linux x86-64 Cloud / Edge。
- `catalog.json`：平台、版本、大小、SHA-256 和固定下载地址，供 Cloud 自动读取。

每个标准 ZIP 包含运行程序、普通话字典、MP3 编码程序和许可文件。它不是安装到系统里的 apt 软件包，也不是单独的 ONNX 模型。资源安装后在节点持久目录保存，断网可用。应用升级无需重新发布语音资源。

## 手动上传

无法访问 GitHub 时，在其他电脑下载对应 ZIP，在 Cloud 的“AI 中心 → 能力配置 → 本地语音”上传为共享资源。Edge 跟随 Cloud 后一键下载；也可直接在 Edge 高级设置中导入本机对应 ZIP。不要解压或改名 ZIP 内文件。

## 维护与独立发布

需要 Python 3.11+、Docker（Linux 容器）及已登录的 GitHub CLI。构建命令：

```sh
python scripts/prepare_local_tts.py --output output/speech-release
```

准备中文 Release 说明后发布新标签（每次使用新标签，既有资源保持不变）：

```sh
python scripts/publish_local_tts.py --tag espeak-ng-1.52.0-YYYYMMDD --notes release-notes.md
```

发布脚本先校验包内容并上传完整草稿，再发布为 latest。对应的第三方源码与构建材料通过 `--extra-asset <源码归档>` 一并上传。Cloud 同步最新 Release 只更新资源来源，节点安装仍需显式点击。

## 许可和来源

本仓库构建脚本使用 MIT 许可。第三方软件保留其原始许可，详见每个 ZIP 的 `licenses/`。eSpeak-NG 1.52.0 使用 GPL-3.0-or-later，FFmpeg 7.1.1 使用 LGPL，LAME 3.100 使用 LGPL；各组件的许可不因打包而改变。首个 Release 同时提供对应来源和构建材料。

- [eSpeak-NG 1.52.0 源代码](https://github.com/espeak-ng/espeak-ng/tree/1.52.0)
- [FFmpeg 7.1.1 源代码](https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz)
- [Debian LAME 来源](https://sources.debian.org/src/lame/)
- [Debian glibc 来源](https://sources.debian.org/src/glibc/)
