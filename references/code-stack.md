# 代码类型和组合

选技术的原则：**先定画面风格，再选能做出这种风格、最简单的那一种代码**。能用一种做完就不要混用多种；要混的时候，按「内容层 → 质感层 → 声音层」叠，每一层单独能跑、单独能检查。

## 八种代码

| 代码 | 擅长 | 典型画面 | 不适合 |
|---|---|---|---|
| Canvas 2D | 一笔一笔画的二维画面 | 像素风、扁平插画、手绘线条、粒子、图表 | 大段需要排版的文字（没有自动换行和排版，文字改用 HTML 叠在画布上） |
| HTML / CSS / SVG | 界面和文字 | 界面动效、大字排版、卡片、数据图表、图标描边动画 | 成千上万个粒子、复杂质感 |
| WebGL 着色器 | 每个像素单独算颜色的质感 | 老电视弧面和扫描线、胶片颗粒、网点、水面反光、光晕 | 直接画内容（一般先用 Canvas 画内容，再送进着色器） |
| Three.js | 3D 场景 | 产品转台、3D 文字、点云、低多边形场景、体素世界 | 写实人物 |
| p5.js + p5.brush | 手绘笔触 | 彩铅、水彩、蜡笔绘本 | 需要很快渲染的长片（笔刷很慢，先测单帧耗时）；WebGL 不可用的环境（p5.brush 要用 WEBGL 模式） |
| GSAP / HyperFrames | 时间轴动画、快节奏动效短片 | 发布会风格、卡点动效 | 简单的进场和出场（自己写缓动和弹簧就够） |
| Remotion（React） | 长片、多场景、复用产品代码库里的 React 组件 | 产品宣传片、知识讲解、历史回顾类短片 | 一次性的十几秒小动效（单个 HTML 更快） |
| Manim（Python） | 数学和原理讲解 | 公式推导、坐标轴、图形变换 | 设计感强的品牌动效 |

## 声音层

优先使用用户提供的音源，否则用 Python + numpy 从零合成配乐和音效。配音默认用 edge-tts（`audio_tools.py tts`，会把旁白文字发到微软的在线服务，并输出逐句、逐词时间戳）；用 Kokoro、用户提供的语音模型或配音文件时，要另外拿到逐句、逐词时间戳。

## 默认选择

- 用户没点名：**单个 HTML 文件 + render(t)**，内容用 Canvas 或 HTML/CSS/SVG，要 3D 时用 Three.js，需要质感再加一层 WebGL 着色器。
- 用户有 React 产品代码库、要多场景长片、或者点名 React：Remotion。每个场景一个组件，动画全部用当前帧号算。
- 用户点名 HyperFrames 时才用：先安装它的 skill（`npx skills add heygen-com/hyperframes`），按它的规范写。
- 数学、物理、算法讲解：Manim。

## 两种出片方式

网页由 `scripts/render.py` 逐帧截图；框架用自己的渲染器出无声画面，最后统一用 FFmpeg 混入声音：
`ffmpeg -i <画面.mp4> -i audio/mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -shortest out/final.mp4`

下面 `<Comp>` 是 Remotion 的 Composition ID，`<Scene>` 是 Manim 的场景类名。

**网页（默认）**
- 画面：页面暴露 `window.render(t)`，骨架见 craft-rules.md。库自带的动画循环要关掉，改由 render(t) 驱动：
  - p5.js：调用 `noLoop()`，在 render(t) 里调用 `redraw()`；`draw()` 里用 t，不用 `frameCount` 和 `millis()`。
  - Three.js：建渲染器时设 `preserveDrawingBuffer: true`；不用 `setAnimationLoop()` 和 `Clock`，在 render(t) 里调用 `renderer.render()`；模型自带的动画用 `mixer.setTime(t)`。
  - GSAP：所有补间都放进一条 `paused: true` 的时间轴，在 render(t) 里调用 `tl.seek(t)`。
- 本地文件：render.py 通过本地 HTTP 服务打开页面（根目录是运行命令的 `code-videos/<slug>/`），页面可以用 `fetch()` 读 `audio/voice.json` 等项目文件、`import` 本地 ES 模块；直接双击打开的 `file://` 页面做不到这两件事。
- 视频素材：用户的视频放进网页时，在 render(t) 里把 `video.currentTime` 设到对应时间，并返回一个等 `seeked` 事件的 Promise（时间没变时直接返回）；render.py 会等这个 Promise 完成再截图。
- 静帧：`python3 scripts/render.py index.html shot.png --still 2.0 --size 1920x1080`；多个时间点用逗号隔开（`--still 1,6,10`），在同一个浏览器里渲完，存成 `shot-t1.png`、`shot-t6.png`、`shot-t10.png`
- 片段：`python3 scripts/render.py index.html seg.mp4 --size 1920x1080 --fps 30 --start 8 --duration 3`；换进成片：`python3 scripts/splice.py out/final.mp4 seg.mp4@8`，多个片段一次写完；起点和时长取整秒时不重新编码（Remotion 片段同样可以换进去，起点 = 起始帧号 ÷ fps；它的成片没有逐秒关键帧，换片段时会重新编码一次）
- 整片：`python3 scripts/render.py index.html out/final.mp4 --size 1920x1080 --fps 30 --duration 30 --audio audio/mix.wav`（直接带上声音）；长片加 `--workers 4`，4 个浏览器并行渲染分段再拼接
- 运动模糊：`--subframes 4`，渲染时间变成 4 倍。

**Remotion**
- 需要：Node.js 18+；Remotion 装在工程里（`npx create-video@latest` 新建工程）。
- 画面：`useCurrentFrame()` 取当前帧号，用 `interpolate()` / `spring()` 算出状态；秒数 = 帧号 ÷ fps。尺寸、帧率和总帧数在 `<Composition>` 里按 production-spec.md 的规格设置。
- 静帧：`npx remotion still <Comp> shot.png --frame=60`
- 片段：`npx remotion render <Comp> seg.mp4 --frames=240-329`
- 整片：`npx remotion render <Comp> <画面.mp4>`
- 运动模糊：`@remotion/motion-blur` 的 `<CameraMotionBlur>`，渲染时间按它的 `samples` 数成倍增加。

**HyperFrames**
- 需要：Node.js 22+ 和它的 skill（安装命令见「默认选择」）。
- 画面：动画写成暂停的 GSAP 时间轴，由渲染器跳到每一帧；写法按它的 skill。命令都在工程目录里运行。
- 静帧：`npx hyperframes snapshot --at 2.0`，PNG 存在 `snapshots/`；`--at` 可写多个时间点，如 `--at 1,3.5,6`。
- 片段：没有分段渲染；改完先用 `snapshot --at` 检查那几秒，再整片重渲。
- 整片：`npx hyperframes render -o <画面.mp4> --fps <帧率> --quality high`；低清版用 `--quality draft`。
- 运动模糊：没有内置。

**Manim**
- 需要：`manim` 命令（按官方文档安装，它依赖 Cairo、Pango 等系统库）；用到 `Tex` / `MathTex` 公式时还要装 LaTeX。
- 画面：`self.play()` 按顺序搭场景，每一帧接着上一帧的状态，不能像网页那样单独算任意一帧。
- 静帧：`manim -s -ql scene.py <Scene>`，存场景的最后一帧。
- 片段：`manim -ql -n <起>,<止> scene.py <Scene>`；`-n` 是动画序号（从 0 数起），不是秒数；`-ql` 是 480p15 低清。
- 整片：`manim -qh --fps <帧率> scene.py <Scene>`，输出在 `media/videos/scene/` 下按分辨率和帧率命名的文件夹里。16:9 以外的画幅加 `-r <宽>,<高>`，比如 9:16 用 `-r 1080,1920`；画面高度固定为 8 个单位，竖屏时宽度只剩约 4.5 个单位，版式要按竖屏重排。
- 运动模糊：没有内置。

## 风格 → 组合速查

| 想要的效果 | 组合 | 参考的公开案例（学手法，不照搬） |
|---|---|---|
| 像素动画 | Canvas 2D 小画布（如 128×96）整数倍放大 + 姿势按 8–12fps 量化 | @majidmanzarpour 的像素巫师 |
| 高级感界面动效 | HTML/CSS/SVG + 闭式弹簧 + 节拍网格 + 4 子帧运动模糊 + 合成界面音效 | @twoclipping 开源的界面变形模板 |
| 动效作品集 / 片头 | HTML 大字排版 + SVG 手写标注 + Canvas 粒子 + 合成音效 | 「15 秒动效作品集」一句话提示词的一批作品 |
| 复古游戏 / 老电视 | Canvas 像素内容 → WebGL CRT 着色器（弧面、扫描线、荧光点、光晕） | @prasenx 的游戏史短片 |
| 年代跨度大的历史片 | 每个年代换一种画风：Canvas 像素、着色器质感、Three.js 3D，统一配乐贯穿 | @prasenx 的游戏史短片 |
| 知识叙事长片 | Remotion + SVG/Canvas 场景 + 一个贯穿全片的视觉主角 + 旁白 + 合成配乐 | @kimmonismus 的 AI 发展史 |
| 产品宣传片 | Remotion 或 HTML + 用 Playwright 截取真实产品网页并记录元素坐标 + 镜头推到真实按钮上 | @aiwarts 的 GoodCase 宣传片 |

## 视频模型角色 + 代码场景

代码画不好写实人物和复杂的舞蹈动作。这时候让视频模型只负责人物，其他全部用代码：

1. 用户用视频模型（Grok、即梦、可灵、Seedance 等）生成人物片段，**要求纯绿色背景**，人物全身入镜、不要出画。
2. 背景、大字、贴纸、分屏、3D 环绕文字用代码做成一层视频（render.py 渲染），背景和大字按 `source/beats.json` 每一拍变一次，人物片段本身不用改。
3. 抠像和叠加放在同一条命令里做（单独抠像存成 MP4 会丢掉透明通道）。`0x19FF0A` 换成 SKILL.md 第 1 步从抽帧里取的绿幕实际颜色，先只出一帧给用户看边缘：
   `ffmpeg -ss 1 -i <背景.mp4> -ss 1 -i <人物.mp4> -filter_complex "[1:v]chromakey=0x19FF0A:0.16:0.08,despill=type=green[fg];[0:v][fg]overlay=(W-w)/2:H-h" -frames:v 1 qa/key-check.png`
   人物大小不合适时，在 `chromakey` 前加 `scale=-2:<人物高度>`。
4. 边缘没问题后，同一条命令去掉 `-ss 1` 和 `-frames:v 1`，overlay 加上 `:shortest=1`，输出 `-c:v libx264 -crf 16 -pix_fmt yuv420p <画面.mp4>`，再按「两种出片方式」混入声音。分屏就是同一段人物错开几帧叠多次。

公开案例：@Gorden_Sun 的甜酷舞蹈（Grok 绿幕人物 + 网页动效背景）、@AbaneChan 的股票主题自我介绍（Grok 生成三段舞蹈 + 作品集提示词）。
