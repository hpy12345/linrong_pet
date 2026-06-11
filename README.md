# 林榕桌宠

面向 Windows 10/11 64 位的透明置顶桌面宠物。角色会在主屏幕底部自然行走，支持点击语音互动、鼠标拖拽、系统托盘、三档尺寸、静音和可选开机启动。

## 当前特性

- `idle`、左右行走、挥手、跳跃、坐下、等待、专注和观察动画。
- 坐下后保持正面坐姿，再次点击才反向播放起身动画。
- 行走八帧逐帧播放，不通过跳帧追赶计时误差。
- 16ms 精确移动定时器、浮点位移累计和动画帧预取。
- 无边框、逐像素透明、始终置顶，不显示在任务栏。
- 离线 `zh-CN-XiaoxiaoNeural` 少女音语音资源。
- 设置保存在 `%APPDATA%\LinRongPet\settings.json`。

## 开发运行

要求 Python 3.12、Windows 10/11 和可用的系统托盘。

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[build,test]"
.venv\Scripts\python.exe -m linrong_pet
```

## 角色资产

- `src/linrong_pet/assets/spritesheet.webp`：`3072x3744` 透明高清图集，每帧 `384x416`。
- `src/linrong_pet/assets/frames/*.webp`：按状态导出的逐帧运行资源。
- `src/linrong_pet/assets/animation.json`：状态、帧数、逐帧时长和循环策略。
- `src/linrong_pet/assets/audio/*.wav`：24kHz 离线神经语音。

重新组装角色图集：

```powershell
.venv\Scripts\python.exe scripts\refine_character_assets.py `
  --animation src\linrong_pet\assets\animation.json `
  --atlas artifacts\upgrade-v1.2\spritesheet-v1.1.webp `
  --walking-strip artifacts\upgrade-v1.2\walking-right-transparent.png `
  --sitting-strip artifacts\repair-v1.3\sitting-front-transparent.png `
  --output src\linrong_pet\assets\spritesheet.webp
```

该流程以未发生脸部变形的 `1.1` 图集为母版，只执行确定性的抠图、分帧、统一比例和组图。不会再把脸部裁片交给超分模型重构。

## 验证

```powershell
.venv\Scripts\python.exe scripts\validate_voice.py `
  --audio-dir src\linrong_pet\assets\audio
.venv\Scripts\python.exe scripts\validate_assets.py `
  --animation src\linrong_pet\assets\animation.json `
  --spritesheet src\linrong_pet\assets\spritesheet.webp
.venv\Scripts\python.exe scripts\render_animation_qa.py `
  --animation src\linrong_pet\assets\animation.json `
  --spritesheet src\linrong_pet\assets\spritesheet.webp `
  --output-dir build\qa\previews-v1.3
.venv\Scripts\python.exe -m pytest
```

资产校验会检查八个行走关键帧是否全部存在且互不重复，并限制坐姿各帧的宽度变化，防止人物异常放大。

## 打包

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

输出：

- `dist\LinRongPet\LinRongPet.exe`
- `output\LinRongPet-Setup-1.3.0.exe`

安装程序按当前用户安装，无需管理员权限。开机启动默认关闭，卸载时保留用户设置。
