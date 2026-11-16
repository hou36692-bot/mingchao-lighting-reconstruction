# 聚簇光照对齐（Clustered Lighting）

> 结论先行：源帧的 clustered deferred 光照与 UE 5.8 的 Light Grid 是同一套算法——格子尺寸、深度切片公式、灯数据打包、每格灯槽上限逐项相同。本项目把源帧的 35 盏局部灯放进还原关卡，并用 CPU 复刻同一套剔除逻辑，与 UE 实际运行的 Light Grid 做逐像素比对。**这是参数与布局的对齐，不是重写剔除器。**

## 状态

| 项 | 状态 |
| --- | --- |
| 源证据 | 完成：格子常数、切片公式、灯数据布局、35 盏灯参数 |
| UE 落地 | 完成：35 盏灯落进关卡；Light Grid 用 UE 默认值即等价 |
| 数值验证 | 完成：CPU 复刻 vs UE Light Grid 逐像素 91.9% 完全一致，其余 ±1 |
| 性质 | 参数对齐 + CPU 参考实现；没有自写 compute shader（Material-only 边界） |

## 源证据

**格子划分** [事实]

- Light Grid 为 **60 × 34 × 32 = 65,280** 个格子，XY 上每格 **64 px**，Z 向 32 个深度切片，每格最多 **32** 盏灯。这些值分别对应 UE 的 `r.Forward.LightGridPixelSize=64`、`r.Forward.LightGridSizeZ=32`、`r.Forward.MaxCulledLightsPerCell=32`，且全部是默认值。
- 深度切片：`slice = log2(z · B + O) · S`，其中 **S = 4.05、B = 0.00432649、O = 0.915633**。与 UE `LightGridInjection.cpp` 的 `GetLightGridZParams` 同公式同常数；由 B、O 反解出的近裁面为 **10.0 cm**，对应 UE 的 `NearOffset = 0.095 × 100`。
- 反射探针占用格子后半段：探针段的虚拟簇号统一 **+65,280**（即 `NumGridCells`），说明源帧把反射捕获放在同一张格子的后半区。

**同源依据** [事实]：上述格子尺寸、切片三参数、每格 32 槽三项在源帧的注入 compute shader 与 UE 的 `LightGridInjection.cpp` / `LightGridInjection.usf` 中完全一致，且都是 UE 的默认值；灯色打包、点光哨兵、锥角打包也与 UE 同名函数一致。因此 UE 侧不需要改任何 `r.Forward.*` 设置，默认配置即等价。

**灯数据打包** [事实]

| 字段 | 内容 |
| --- | --- |
| 颜色 | `[+1].x × rgb10([+1].y)`；`x = Length / 0x3FF`，`y` 为 10:10:10 方向编码，与 UE `PackLightColor` 一致 |
| 点光标记 | `[+3].xy = (-2, 1)`，即 UE 点光的 `SpotAngles` 哨兵值 |
| 聚光锥角 | `[+3].xy = (cos外角, 1/(cos内角 − cos外角))` |
| 矩形灯标记 | `R2315721.w` 位 0 = 矩形灯，高位为 `tan(锥角)`，对应 UE `PackedPreProcAngleAndFlags` |
| 衰减指数 | 32 盏 `w=2`，灯 3 为 `w=3`，灯 19 为 `w=8`，对应 UE 非平方反比衰减 `(1 − (d/r)²)^w` |
| 灯 32 | 衰减指数 `w=0` → 走平方反比；预计算角/标志字段的位 0 单独标记矩形灯 |

**35 盏灯** [事实]：16 盏点光（type 1）、18 盏聚光（type 2）、1 盏矩形灯（type 3，灯 32）。方向按 UE 的约定 `Direction = −forward` 上传，因此 actor 朝向取 `−[+2].xyz`。只有灯 33/34 带阴影：它们在源帧里走球体代理 + 屏幕空间阴影遮罩，且位域 `bit22=0`，主聚簇 Pass 会跳过它们。

## UE 实现

1. **落地 35 盏灯**：解析源帧缓冲得到灯参数，按世界坐标直接生成 Point / Spot / Rect Light，放进 Outliner 文件夹并编号。关卡本身按同一世界坐标重建，相机位姿直接对应，不需要缩放或平移。
   - 强度取着色器值的最大通道（UE 这条分支不做单位换算）；灯 32 走平方反比，`cd = 值 / 100²`。
   - 灯 32 的矩形尺寸在源数据里没有解出，用 UE 默认 64×64。
2. **CPU 复刻剔除**：`cluster_ref.mjs` 按 `LightGridInjection.usf` 的 `ComputeCellBounds` / `OverlapsLight` / `IsAabbOutsideInfiniteAcuteConeApprox` 实现，输入是源帧自己的视空间灯球、视空间方向与锥角、以及源帧的格子常数。它不依赖 UE 运行结果，是独立参考实现。
3. **UE 侧不改参数**：Light Grid 的尺寸、切片、灯槽上限全部用默认值，因为默认值就等于源帧；自研部分只做可视化。
4. **调试可视化**：后处理材质 `Debug_Viz_Mode=3` 按 64 px 瓦片 + 32 片指数深度切片着色，切片函数与源帧常数一致，用于肉眼对照。

源数据到 UE actor 的映射：

| 源字段 | UE actor 属性 |
| --- | --- |
| 视空间位置 + 半径 | 世界位置与 `AttenuationRadius` |
| 颜色 / 亮度 | `Intensity`（取最大通道）与 `LightColor` |
| 衰减指数 `w` | 非平方反比衰减的指数项 |
| `[+2].xyz` | actor 朝向 = `−[+2].xyz` |
| `[+3].xy` | 内外锥角（`cos外`、`1/(cos内−cos外)` 反解） |
| 矩形标记 | RectLight（仅灯 32） |
| 位域 `bit22` | 是否参与聚簇主 Pass / 阴影 |

## 验证

| 项 | 方法 | 结果 |
| --- | --- | --- |
| 世界坐标 → 视空间 | 用源帧相机基重算 35 盏灯位置 | 与源缓冲误差 **< 0.2 cm** |
| 照亮对象一致 | UE 开/关灯差分 vs 源帧灯 Pass 前后差分 | 同一批物体：左侧围墙、两棵紫藤、右侧拱门 |
| 每像素灯数 | CPU 复刻 vs UE 实际 Light Grid（`r.Forward.LightGridDebug 1`） | **91.9% 像素完全一致，其余全部只差 ±1** |
| 局部灯与太阳能量比 | 受光区域差分 | UE 0.58，源帧 0.23，UE 偏亮约 **2.5 倍** [待确认] |

逐像素比对的做法：把 UE 的 Light Grid debug 叠加用 SceneCapture 拍下来（该叠加可被捕捉），960×540 配 `LightGridPixelSize=16` 得到与 3840/64 相同的格子划分；再把 UE 的 HSV 计数色反解成每格灯数，与 CPU 结果逐像素比较。差异集中在 Z 切片远平面：源帧远平面约 46,352 cm，由反射捕获距离决定，而 UE 关卡里没有那 8 个探针。

比对前有两个校准：debug 叠加写入的是线性色，而 PNG 存 sRGB，反解前先转线性；同一状态连拍两次会有 TAA 抖动，比对取连续稳定帧。`cluster_ref.mjs` 本身不读 UE 的中间缓冲，只吃源帧参数，因此这一比对是两条独立路径的交叉验证。

## 与源的差异

补充一点：UE5 的 Light Grid 不只服务前向，也服务 clustered deferred、Lumen 与半透明，因此"延迟管线里意义有限"的说法不成立；源帧同样是在延迟管线上使用同一套格子。

1. **UE 5.8 的 Light Grid 更先进**：多了 HZB 剔格与链表存储（`r.Forward.LightLinkedListCulling`），每格上限不再是硬性 32。源帧是固定 32 槽，这一层 UE 内部实现无法回退到旧版。
2. **反射探针缺失**：源帧的 8 个反射捕获没有放进 UE（关卡没有 Reflection Capture），所以格子后半段与远平面不同，这也是 ±1 差异的主要来源。
3. **灯 32 的矩形尺寸未知**：源数据 `[+4]/[+5]` 没有解出尺寸，UE 用默认 64×64，矩形灯覆盖范围只能近似。
4. **局部灯能量偏亮约 2.5 倍** [待确认]：UE 差分比 0.58，源帧 0.23。可能来源是源帧 PNG 导出的高光截断、接收面不完全一致、以及 UE 灯单位与源帧的换算；没有继续细查，不作结论。
5. **只用 debug 模式 1 比对**：`r.Forward.LightGridDebug 2`（逐瓦片最大值）在 SceneCapture 里只显示部分灯，原因未查，逐像素验证只用模式 1。
6. **灯阴影只有 2 盏**：只为灯 33/34 开阴影（对应源帧的球体代理 + 阴影遮罩），其余灯在源帧里也不走阴影路径。

## 相关文件

- 图示：[灯关 / 灯开 / 差分](./images/cluster-lights.png)、[CPU 复刻 vs UE Light Grid 逐像素对比](./images/cluster-grid.png)
- CPU 复刻：[cluster_ref.mjs](../tools/analysis/cluster_ref.mjs)
- 逐像素比对：[cluster_cmp.mjs](../tools/analysis/cluster_cmp.mjs)
- 灯参数解码：[mc_lights.mjs](../tools/analysis/mc_lights.mjs)
