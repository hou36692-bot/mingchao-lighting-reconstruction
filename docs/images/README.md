# 图片清单（docs/images）

本目录的 9 张 PNG 都由 `tools/image/png.mjs`（`crop` / `resize`）从验证截图重编码生成，输出为 8-bit RGB PNG，不含 EXIF、文本块或编辑器元数据。源截图不在仓库内。

- 源图根目录：`UE还原记录/截图/`（仓库外）。
- 生成命令：
  - 裁剪：`node tools/image/png.mjs crop <in> <out> <x> <y> <w> <h>`
  - 缩放：`node tools/image/png.mjs resize <in> <out> <width>`（高度按比例）
  - 既裁剪又缩放的图先裁到临时文件，再缩放；下表「处理」列给出完整参数。
- 单图不超过 1.1 MB。

## 清单

| 文件 | 来源（相对 `UE还原记录/截图/`） | 处理（裁剪 x,y,w,h → 缩放宽度） | 输出尺寸 | 用途 | 含游戏画面 |
|---|---|---|---|---|---|
| `hero-ue-vs-ww.png` | `Veg/30_f36153_before_after_ww.png` | crop 964,0,1924,540 → resize 1280 | 1280×359 | README 首图（左 UE 还原，右鸣潮同机位） | 是（右格） |
| `tune-pipeline.png` | `Tune/03_viewport_vs_capture_vs_ww.png` | crop 0,32,1607,268 → resize 1400 | 1400×233 | README、工具链文档；视口 / SceneCapture / 鸣潮 | 是（右格） |
| `csm-modes.png` | `CSM/60_modes_sbs.png` | crop 0,48,3848,672 → resize 1400 | 1400×244 | CSM 文档；VSM / UE CSM / 对齐后的 CSM（均为 UE） | 否 |
| `csm-bands.png` | `CSM/61_bands_sbs.png` | crop 0,48,2564,672 → resize 1280 | 1280×335 | README、CSM 文档；级联色带 | 否 |
| `cluster-lights.png` | `Cluster/02_ue_mclights_off_on_diff.png` | resize 1400 | 1400×261 | README、聚簇文档；关灯 / 开灯 / 差分 | 否 |
| `cluster-grid.png` | `Cluster/03_lightgrid_wwreplica_ue_diff.png` | resize 1400 | 1400×261 | 聚簇文档；Light Grid 逐像素对比（图中文字是内容） | 否 |
| `water-compare.png` | `Water/03_ww_ref_ueApprox_wwCoeff.png` | resize 1400 | 1400×261 | README、水面文档；三格天空与时段不一致，只比较水体 | 是（左格） |
| `veg-shore.png` | `Veg/21_f61250_shore_band_before_after_ww.png` | resize 1280 | 1280×285 | README、植被文档；岸边草带改前 / 改后 / 鸣潮 | 是（底格） |
| `veg-close.png` | `Veg/10_user_before_after.png` | resize 1280 | 1280×359 | 植被文档；俯视近景改前 / 改后 | 否 |

含游戏画面的共 4 张：`hero-ue-vs-ww.png`、`tune-pipeline.png`、`water-compare.png`、`veg-shore.png`。其余为 UE 渲染结果或调试可视化。

`diagrams/` 下是手绘的 SVG 示意图（证据链、模块映射、AO 采样），不含游戏画面。

## 版权说明

- 本目录中出现的《鸣潮》（Wuthering Waves）游戏画面只用于研究与评论，权利归原权利人，不在本仓库 MIT 许可范围内。
- UE 渲染截图、调试可视化和示意图由本项目作者生成，随仓库许可发布。
- 完整说明见仓库根目录的 `NOTICE.md` 与 `LICENSE`。
