# 图片清单（docs/images）

本目录 14 张 PNG 全部由 `tools/png.mjs`（`crop` / `resize`）从源工作区的验证截图重编码生成：
输出为 8-bit RGB PNG，**不含 EXIF / 文本块 / 编辑器元数据**；源图未被修改。

- 源图根：`UE还原记录/截图/`（仓库外），LUT 对比图来自 `shots/tune/`（仓库外）。
- 生成命令模板：
  - 裁剪：`node tools/png.mjs crop <in> <out> <x> <y> <w> <h>`
  - 缩放：`node tools/png.mjs resize <in> <out> <width>`（高度按比例）
  - 既裁剪又缩放的图先裁到临时文件，再缩放；下表「处理」列给出完整参数。
- 体积：14 张合计 **11.61 MB**，单图最大 1.10 MB（目标：单图 < 1.5 MB，总量 < 12 MB）。
- **宽度说明**：计划起初为 1600/1800 宽，实测总量 16.3 MB 超预算，按预案降到 1400/1280
  （SH 调试图为 800），下表记录实际值。

## 清单

| # | 文件 | 来源（相对 `UE还原记录/截图/`） | 处理（裁剪 x,y,w,h → 缩放宽度） | 输出尺寸 | 大小 | 用途 | 含游戏画面 |
|---|---|---|---|---|---|---|---|
| 1 | `hero-ue-vs-ww.png` | `Veg/30_f36153_before_after_ww.png` | crop 964,0,1924,540 → resize 1280 | 1280×359 | 1.07 MB | README 首屏（左 UE 还原后，右鸣潮同机位） | **是**（右格） |
| 2 | `total-comparison.png` | `Total/01_ueOrig_ueRestored_ww61250.png` | resize 1400 | 1400×261 | 0.92 MB | README 结构对比；图注须写明**不含 SH/LUT/AO** | **是**（第三格） |
| 3 | `tune-final.png` | `Tune/06_round2_before_after_ww.png` | crop 0,32,1070,268 → resize 1400 | 1400×351 | 0.90 MB | TOD 文档 / 备选效果图；只保留 UE 改前/改后 | 否（裁剪已去掉游戏格，顶部 32 px 编辑器条已裁） |
| 4 | `tune-pipeline.png` | `Tune/03_viewport_vs_capture_vs_ww.png` | crop 0,32,1607,268 → resize 1400 | 1400×233 | 0.83 MB | `docs/toolchain.md`；视口 / SceneCapture / 鸣潮 三条路径 | **是**（右格） |
| 5 | `sh-debug-sphere.png` | `SH/80_dbg_sh_sphere.png` | resize 800 | 800×450 | 0.81 MB | SH 文档（调试球可视化） | 否 |
| 6 | `lut-compare.png` | `shots/tune/sbs_lut2.png`（仓库外） | resize 1400 | 1400×261 | 0.92 MB | LUT 文档；图注说明含鸣潮第三格 | **是**（第三格） |
| 7 | `csm-modes.png` | `CSM/60_modes_sbs.png` | crop 0,48,3848,672 → resize 1400 | 1400×244 | 0.82 MB | CSM 文档；VSM / UE CSM / UE MC-CSM 三模式（均为 UE） | 否 |
| 8 | `csm-bands.png` | `CSM/61_bands_sbs.png` | crop 0,48,2564,672 → resize 1280 | 1280×335 | 0.90 MB | CSM 文档；级联色带 | 否 |
| 9 | `cluster-lights.png` | `Cluster/02_ue_mclights_off_on_diff.png` | resize 1400 | 1400×261 | 0.70 MB | 聚簇文档；灯关 / 开 / 差分 | 否 |
| 10 | `cluster-grid.png` | `Cluster/03_lightgrid_wwreplica_ue_diff.png` | resize 1400 | 1400×261 | 0.05 MB | 聚簇文档；Light Grid 逐像素对比（文字是内容，未裁剪） | 否 |
| 11 | `water-compare.png` | `Water/03_ww_ref_ueApprox_wwCoeff.png` | resize 1400 | 1400×261 | 0.88 MB | 水面文档；图注须写明三格天空/时段不一致 | **是**（含鸣潮格） |
| 12 | `tod-hours.png` | `TOD/02_hours_6_14.5_18.5.png` | resize 1400 | 1400×261 | 0.85 MB | TOD 文档；6 / 14.5 / 18.5 时 | 否 |
| 13 | `veg-shore.png` | `Veg/21_f61250_shore_band_before_after_ww.png` | resize 1280 | 1280×285 | 0.90 MB | 植被文档；岸边草带对比 | **是**（底格） |
| 14 | `veg-close.png` | `Veg/10_user_before_after.png` | resize 1280 | 1280×359 | 1.05 MB | 植被文档；俯视近景 | 否 |

含游戏画面的共 6 张：#1、#2、#4、#6、#11、#13。其余 8 张为 UE 渲染结果或调试可视化。

## 版权说明

- 本目录中出现的《鸣潮》（Wuthering Waves）游戏画面仅用于**研究与评论**（对照分析还原效果），
  版权归原权利方所有，**不在本仓库 MIT 许可范围内**。
- UE 渲染截图与调试可视化由本项目作者生成，随仓库许可发布。
- 完整边界见仓库根 `NOTICE.md` 与 `LICENSE`。
