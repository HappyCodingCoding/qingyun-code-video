---
name: qingyun-code-video
description: >-
  Make videos with code — web pages (Canvas, HTML/CSS/SVG, WebGL shaders, Three.js), frameworks such as Remotion, HyperFrames and Manim, or any other stack that renders video frame by frame — with music and sound effects synthesized in code and voiceover from a TTS engine. Web pages render through Playwright + FFmpeg, frameworks through their own renderers. Works from an idea, source content (article, script, product page, codebase) or a reference video: proposes three distinct plans, each with a shot-by-shot summary and a key-frame or short preview, then writes a production spec and builds the MP4 once the user picks one. Use whenever the user wants to make, animate or render a video, motion graphic, animated explainer, product promo, kinetic-typography piece, pixel-art or retro animation or UI motion demo, or to recreate the look of a reference video — including Chinese requests like「做个视频」「用代码做视频」「做个动效」「做个动画」「做个宣传片」「帮我复刻这个视频」. Also use when the user has green-screen character clips from a video model and wants code-built scenes around them. Not for generating footage with video models, editing in Premiere/CapCut/AE, or subtitling an existing video.
---

# qingyun-code-video：用代码做视频

用代码写画面，逐帧渲染成 MP4：网页（Canvas、HTML/CSS/SVG、WebGL、Three.js）暴露 `window.render(t)`，传入视频时间轴上的任意时间点 t（秒），就能直接画出那一刻的画面，由脚本调用 Playwright 逐帧截图、FFmpeg 合成；Remotion、HyperFrames、Manim 等框架用各自的渲染命令出片。配乐和音效用代码合成，配音用语音合成（TTS）。

先把规划摆到用户面前，确认了再动手：确认制作参数 → 三个方案，每个配一张关键帧图片或几秒预览视频 → 用户选定 → 写成 `production-spec.md` → 按它逐镜头制作并逐镜头自检 → 渲染整片并自检 → 交付。

## 工作目录

在当前目录下建 `code-videos/<slug>/`，所有东西放在里面：

```
code-videos/<slug>/
  source/             // 用户给的素材、参考视频抽帧、分析笔记（notes.md）
  previews/           // 三个方案的预览（plan-a.png / plan-b.mp4 ...）
  production-spec.md  // 用户选定方案后写的完整制作规格，第 6、7 步按它制作
  index.html          // 成片的画面代码（或 Remotion / HyperFrames / Manim 工程）
  audio/              // 合成的配乐、音效、配音
  qa/                 // 自检用的静帧和抽帧图
  out/draft.mp4       // 第 7 步自检用的低清版
  out/final.mp4       // 成片
```

所有命令都在 `code-videos/<slug>/` 里运行，其他相对路径都相对这个目录；命令里的 `scripts/` 指本 skill 目录下的 `scripts/`，运行时换成它的绝对路径。

文中的「风格」指整体视觉：画风、配色、字体、版式和动效语言；只说渲染方式（扁平插画、像素风、彩铅手绘等）时用「画风」。

## 第 0 步：检查环境

运行一次 `python3 scripts/check_env.py`，检查网页出片和声音合成所需的依赖项：python3、FFmpeg、numpy、edge-tts、Playwright、浏览器及其 WebGL 支持。若缺少依赖项，告知用户缺少哪些，并询问用户是否安装它们。

若后面的视频制作方案采用了 Remotion、HyperFrames、Manim 中的任意一种或多种，在第 4 步做预览之前，运行 `python3 scripts/check_env.py --only <框架名>`（可写多个，如 `--only remotion manim`）检查这些框架所需的依赖项，各框架需要什么见 [references/code-stack.md](references/code-stack.md) 的「两种出片方式」中的「需要」一项。若缺少依赖项，同样告知用户缺少哪些，并询问用户是否安装它们。

若用户不同意安装，告诉用户缺少这些依赖项后哪些步骤做不了，不要换用其他工具绕过。

## 第 1 步：分析用户输入

用户的输入可能同时包含下面几类，逐类处理，把分析结果写进 `source/notes.md`，后面各步以它为准：

- **明确的要求**（时长、画幅、风格、配色、字体、配音等）：原样记下；第 2 步不再就这些项提问。
- **想法**：提炼出视频的核心信息（想让观众记住的一句话），并发散出几种可能的表现形式，供第 3 步写方案时选用。
- **原材料**（文章、口播稿、产品网址、产品代码库、数据表等）：先读完原材料，再提炼出核心信息、目标受众和视频里必须出现的事实（名称、数字、年份等）。事实原样记下，不要编造或改动。
- **参考视频**：如果是网络链接，先运行 `python3 scripts/check_env.py --only yt-dlp` 确认 yt-dlp 已安装（缺少时同第 0 步处理），再运行 `yt-dlp -o "source/ref.%(ext)s" <链接>` 下载；下载失败时，请用户提供视频文件。然后运行 `python3 scripts/analyze_video.py <视频> --out source/ref`，得到时长、分辨率、帧率、镜头切换时间点和一张抽帧图；要看清字体和配色时，加 `--frames <秒数>` 导出这几个时间点的整帧。基于这些结果分析参考视频的镜头结构、节奏、配色和字体，并对照 [references/code-stack.md](references/code-stack.md) 推断它采用的技术组合。只学习参考视频的结构和手法，不要照搬其内容、素材和文案。
- **音乐文件**：运行 `python3 scripts/audio_tools.py beats <音乐文件> > source/beats.json`，测出 BPM、节拍（beats）、重拍（downbeats）和鼓点（hits）。第 3 步编排镜头时，镜头切换和关键动作落在这张节拍表上，用法见 craft-rules.md 的「声音」。
- **绿幕人物片段**：运行 `python3 scripts/analyze_video.py <片段> --out source/greenscreen --frames 1`，看导出的整帧确认人物完整、背景是纯绿幕；再运行 `ffmpeg -v error -ss 1 -i <片段> -vf "crop=16:16:8:8,scale=1:1" -frames:v 1 -f rawvideo -pix_fmt rgb24 - | xxd -p` 取左上角绿幕的实际颜色（输出 6 位十六进制色值），记进 `source/notes.md`，供抠像使用，做法见 code-stack.md 的「视频模型角色 + 代码场景」。

## 第 2 步：确认制作参数

根据 `source/notes.md` 里的分析结果，为这支视频定一套推荐参数，覆盖下表各项。第 1 步记下的明确要求直接采用；其余各项按内容和用途推断（比如发小红书用 3:4，口播稿按每秒约 4 个字估算时长），推断不出时用默认值。

| 参数 | 可选值 | 默认值 |
|---|---|---|
| 时长 | 秒数 | 无，按内容估算 |
| 画幅 | 16:9 / 9:16 / 3:4 / 4:5 / 1:1 | 16:9 |
| 帧率 | 24 / 30 / 60 fps | 30 fps |
| 配色 | 主色 …，辅色1 …, 辅色2 … | 无，按内容和品牌定 |
| 内容字体 | 字体名称 | 系统中文字体（见 craft-rules.md 的「字体」） |
| 配乐 | 代码合成 / 用户提供的音频文件 | 代码合成 |
| 配音 | 要或不要；音色、语速 | 要 |
| 字幕 | 显示或不显示；颜色、字体、字号 | 有配音时显示 |

然后分两轮询问用户：

1. 列出这套推荐参数，询问用户直接采用还是逐项调整。
2. 若用户选择直接采用，进入第 3 步。若用户选择逐项调整，为每个用户没有明确过的参数提一个问题：推荐值作为第一个选项并标明「推荐」，再给 2–3 个其他选项；问完进入第 3 步。

若最终参数里要配音，告诉用户：配音默认用 edge-tts，旁白文字会发到微软的在线服务；文稿需要保密时，改用 Kokoro 等本地语音模型或用户提供的配音文件（见 code-stack.md 的「声音层」）。

把最终参数写进 `source/notes.md`，第 5 步写 production-spec.md 时按它填写 `<overview>`。

## 第 3 步：写三个方案

阅读 [references/code-stack.md](references/code-stack.md) ，为每个方案选择技术组合；再按照 [references/plan-format.md](references/plan-format.md) 的「格式」和「三个方案怎么拉开」写三个方案。

- 把第 2 步确定的参数（时长、画幅、帧率、配乐来源、配音、字幕）应用到全部三个方案。配色和字体也以第 2 步为准；仅当方案的画风需要不同的配色或字体时才调整，并在该方案的「配色」或「字体」一栏写明改了什么。
- 三个方案的差别要落在风格、叙事结构或技术组合上；不能只在另一个方案上微调（如只换配色）得出新方案。
- 每个方案的第一个镜头（成片视频时间轴上的 0–3 秒）都要抓人：成片第 0 秒就有内容，不从黑屏或空画面淡入；3 秒内用一句大字（有配音时同时作为第一句旁白）讲明这支视频讲什么，并让它成为钩子：一个大胆或有意思的说法、先亮结论、一个反常识的数字，比如讲题视频开场说「这道四年级数学题，全班都错了！」「这道四年级数学题，把老师难住了」。只给画面、数字或做到一半的动作而不点明主题，观众不知道在看什么，会直接划走。观众在前 3 秒决定看不看下去，开场不抓人，后面做得再好也没人看到。本条只规定方案里第一个镜头怎么写，不决定第 4 步预览哪个镜头：预览仍搭最有代表性的镜头，不一定是开场。

写好后先不要发给用户；在第 4 步做完预览后，连同预览一起呈现给用户。

## 第 4 步：给每个方案做预览

预览让用户在正式渲染之前看到每个方案的画面。动手前先读 [references/craft-rules.md](references/craft-rules.md) 的「页面骨架」「字体」和「每一帧只由它在视频时间轴上的时间点算出」三节，用到 p5.js、Three.js 或 GSAP 时再读 code-stack.md 的「网页（默认）」，按这些规则写预览代码；这样用户选中方案后，第 6 步可以直接在该方案的预览代码上接着做。

每个方案的预览只搭该方案最有代表性的一个镜头，不用搭整条视频时间轴：预览用这个镜头自己的时间轴，镜头开头为 0，下面命令里的秒数也按它算。第 6 步把这个镜头接进成片时，用视频时间轴上的 t 减去镜头的起点，换算成镜头自己的时间。文字、配色和字体都用方案里的真实内容，不要用占位文字或色块。下面是网页的命令，用框架时见 code-stack.md 的「两种出片方式」。

- **关键帧**（默认）：渲染这个镜头最能代表方案风格的时刻，存成 PNG：`python3 scripts/render.py previews/plan-a.html previews/plan-a.png --still <秒数> --size <宽>x<高>`。
- **2–4 秒小样**：若方案的卖点在画面运动（界面变形、节拍卡点、转场），改做小样：`python3 scripts/render.py previews/plan-b.html previews/plan-b.mp4 --size <宽>x<高> --fps <帧率> --duration 3`。

`<宽>x<高>` 按方案的画幅取：16:9 用 1920x1080，9:16 用 1080x1920，3:4 用 1080x1440，4:5 用 1080x1350，1:1 用 1080x1080。

每个预览做好后先自己检查：关键帧直接看图；小样用 `python3 scripts/analyze_video.py previews/plan-b.mp4 --out qa/plan-b` 出抽帧图再看。修正字溢出、元素挤在一起、画面太空等问题。

做完预览后，填写每个方案的「预计耗时」：单帧耗时（取预览渲染的实测值：`render.py` 会打印每帧耗时，用框架时按渲染命令的总用时除以帧数）× 总帧数 × 子帧数（不加运动模糊时为 1）× 1.3。

最后把三个方案连同预览文件路径一起呈现给用户，请用户选一个方案，或说明要怎样混合、修改。用户要求修改时，按要求改参数或方案，重做受影响方案的预览，再请用户确认，直到用户选定方案。

## 第 5 步：写 production-spec.md

用户选定方案后，以 `source/notes.md` 和选定的方案（含用户要求的修改）为依据，按 [references/production-spec-template.md](references/production-spec-template.md) 的模板和填写要求写 `production-spec.md`。第 6、7 步严格按 production-spec.md 制作。

写完告诉用户 production-spec.md 的路径。

## 第 6 步：制作

动手前把 [references/craft-rules.md](references/craft-rules.md) 整份读完。按 production-spec.md 的 `<build>` 使用选定的技术组合，从选定方案的预览代码接着做（网页把 `previews/plan-<x>.html` 复制成 `index.html`）；各技术组合的渲染命令见 code-stack.md 的「两种出片方式」。最要紧的四条规则：

1. **每一帧只由它在视频时间轴上的时间点算出**。网页里 `window.render(t)` 画出第 t 秒，Remotion、HyperFrames 里画面由当前帧号或时间轴位置算出；不用 `requestAnimationFrame`、`setTimeout`、CSS transition，随机数带固定种子，帧和帧之间不保存状态。这样任何一帧都能单独重渲，改一个镜头不会影响别的镜头。
2. **逐个镜头制作**。每做完一个镜头，渲染它开头、中间、结尾 3 张静帧（网页一条命令渲完：`python3 scripts/render.py index.html qa/shot<n>.png --still <开头>,<中间>,<结尾> --size <宽>x<高>`）并检查：文字有没有溢出、元素有没有重叠、主体够不够大；再对照代码里的进出场时间，确认每段文字至少停留 2.5 秒。修好再做下一个镜头。网页的尺寸和位置要按窗口宽高算（见 craft-rules.md 的「多画幅」），第 7 步按一半分辨率渲低清版时画面才不会错位。
3. **声音和画面用同一张时间轴**。有配音时，先把 production-spec.md 各镜头的「旁白」按顺序连成全文，写进 `audio/voice-script.txt`，段落之间空一行（合成时每个空行插入 `--pause` 秒停顿，默认 0.6 秒，让观众在段落之间喘口气；某处要更长的停顿时，比如出题后留给观众思考，在那里单独写一段 `[pause <秒数>]`，合成时换成这么长的静音），运行 `python3 scripts/audio_tools.py tts audio/voice-script.txt audio/voice.wav --voice <音色> --rate=<语速>` 合成配音（语速如 `-8%`，要用等号连写，否则负值会被当成参数），以它写出的 `audio/voice.json` 作为时间轴：每一句有开始、结束时间，句内每个词也有（`words`）；镜头切换对齐句子，句中的动作（比如读到某个数字时让数字落位）对齐对应的词（改用其他语音模型或用户提供的配音时，同样要拿到逐句和逐词时间戳，写成同样格式的 `audio/voice.json`）；没有配音时用节拍网格（用户提供的音乐用 `source/beats.json`，代码合成的配乐按 BPM 算）。镜头切换和关键动作落在时间轴上，音效放在画面动作发生的那一帧。
4. **镜头要动**。用推、拉、跟随，让主体至少占画面三分之一。

## 第 7 步：渲染和验收

1. **合成声音**
   - 配乐：代码合成时，按 craft-rules.md 的「配乐」写成 `audio/music.wav`；用户提供音乐时，下面混音命令的 `--music` 直接用那个文件。
   - 音效：网页在画面代码里登记音效，存进 `window.sfxEvents`（写法见 craft-rules.md 的「声音」），运行 `python3 scripts/render.py index.html audio/sfx-timeline.json --sfx-events --duration <时长>` 导出 `audio/sfx-timeline.json`；框架把关键动作的时间点手写进这个文件（格式和可用的音效名见 `python3 scripts/audio_tools.py -h`），镜头代码用镜头自己的时间时，写入前先换算成视频时间轴上的时间点：镜头起点 + 镜头内的时间。再运行 `python3 scripts/audio_tools.py sfx audio/sfx-timeline.json audio/sfx.wav`。
   - 混音：运行 `python3 scripts/audio_tools.py mix audio/mix-raw.wav --music audio/music.wav --sfx audio/sfx.wav --voice audio/voice.wav`（没有的音轨省略对应参数），配音出现时它会自动压低配乐。
   - 标准化和检查：运行 `python3 scripts/audio_tools.py normalize audio/mix-raw.wav audio/mix.wav` 把响度调到 -14 LUFS，再运行 `python3 scripts/audio_tools.py check audio/mix.wav --out qa/audio`，看响度数值、波形图和频谱图。
2. **低清版自检**：按一半分辨率、不加运动模糊渲整片 `out/draft.mp4`（网页：`python3 scripts/render.py index.html out/draft.mp4 --size <宽÷2>x<高÷2> --fps <帧率> --duration <时长> --audio audio/mix.wav --workers <N>`；框架见 code-stack.md 的「两种出片方式」）。运行 `python3 scripts/analyze_video.py out/draft.mp4 --out qa/draft` 出抽帧图，再运行 `python3 scripts/analyze_video.py out/draft.mp4 --out qa/phone --cells 15 --cell-width <手机宽度>` 出手机尺寸抽帧图（手机宽度按画幅取，见 craft-rules.md「自检打分」的「手机可读」），按 craft-rules.md 的「自检打分」打分，再按其中「怎么用分数」修改，直到每项 8 分及以上或做满 3 轮。字的清晰度和细线条在低清版里看不准，用正式分辨率的静帧检查（`render.py --still`）。
3. **渲染整片**：自检通过后只渲一次正式版。网页运行 `python3 scripts/render.py index.html out/final.mp4 --size <宽>x<高> --fps <帧率> --duration <时长> --audio audio/mix.wav --workers <N>`，各参数取 production-spec.md 的「规格」，`<宽>x<高>` 用其中的像素尺寸；`--workers` 让 N 个浏览器并行渲染分段再无损拼接，N 取 CPU 核数的一半左右，30 秒以内的短片不用加。production-spec.md 的「运动模糊」写了子帧数时，加 `--subframes <子帧数>`，加之前告诉用户渲染时间会变成原来的 <子帧数> 倍。用框架时按 code-stack.md 的「两种出片方式」出画面、混入声音。
4. **核对验收清单**：运行 `python3 scripts/analyze_video.py out/final.mp4 --out qa/final` 出抽帧图，对照 craft-rules.md 的「验收清单」逐项核对。有不符合的项时，找到原因修好：响度问题回到第 1 项重新混音和标准化，再用 FFmpeg 把新的 `audio/mix.wav` 换进成片（`-map 0:v -map 1:a -c:v copy`）；配音比视频长时，按 `audio/voice.json` 调整各镜头的时间，需要延长总时长时先请用户确认；其他问题回到对应镜头的代码修改。改动只影响一段时间时，只重渲这一段并换进成片：渲出和成片同尺寸、同帧率的片段（网页用 `render.py` 的 `--start` / `--duration`，框架见 code-stack.md），再运行 `python3 scripts/splice.py out/final.mp4 <片段1.mp4>@<起点秒数> <片段2.mp4>@<起点秒数> …`，同一轮的所有片段一次换进去；片段起点取整秒、时长取整秒（或一直到片尾）时，它不重新编码，几秒就换完。改动影响多个镜头（比如全片的字号、配色）时重渲整片。修好后重新出抽帧图，再从头核对整份清单，直到全部符合。事实类内容无法确认时不要猜改，单独列出来，第 8 步交付时请用户核对。

## 第 8 步：交付

把以下内容告诉用户，文件和目录都写完整路径：

- 成片：`out/final.mp4`
- 制作规格：`production-spec.md`
- 自检记录：`qa/review_log.md`
- 工程目录：`code-videos/<slug>/`
- 简短说明：这次的关键创作决定、整片的实际渲染用时，以及无法解决的问题（包括自检做满 3 轮后仍低于 8 分的项，写明时间点）。
- 待核对的事实：第 7 步列出的无法确认的事实类内容，请用户逐条核对。

## 特殊情况

- **用户想要真人或写实角色**：告诉用户代码画不出写实的人物，并建议用户先用视频模型生成**纯绿幕背景**的人物片段；用户提供片段后，按 code-stack.md 的「视频模型角色 + 代码场景」抠像，再用代码搭场景、大字和动效。
- **渲染太慢**：先降低分辨率或帧率渲一版低清版，确认节奏和画面后再渲正式版；正式版的分辨率、帧率和运动模糊按 production-spec.md 来，不要为了省时间降低。运动模糊和 WebGL 后期最耗时；正式版的预计渲染时间明显超过方案里的「预计耗时」时，告诉用户新的预计时长，由用户决定是否去掉这两项。
- **浏览器里 WebGL 不可用**：`check_env.py` 报告 WebGL2 不可用时，告诉用户；第 3 步不要给出依赖 WebGL 着色器、Three.js 或 p5.brush 的方案，也不要把这类方案私自改用 Canvas 2D 来做。用到 WebGL 的方案，正式渲染前先渲一帧，确认着色器真的生效。
- **用户只想要制作规格**：做完第 5 步就停下，把 `production-spec.md` 的完整路径交给用户。
