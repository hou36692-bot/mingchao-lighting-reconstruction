# config/ 说明

本目录存放本次光照还原的**配置参考与摘录**，不是可以直接覆盖到某个 UE 工程里的完整配置文件。

## 文件

| 文件 | 内容 | 是否可直接使用 |
| --- | --- | --- |
| `ue-rendering-settings.ini` | 与还原相关的 `r.*` 渲染设置摘录（UE 5.8） | 否，仅供对照；请手动合并到 `Config/DefaultEngine.ini` |
| `mpc-restore-control.md` | `MPC_RestoreControl` 参数表、开关约定、后处理挂载顺序 | 否，是说明文档 |
| `tools.env.example` | 工具脚本使用的环境变量模板 | 是，复制后填入本地路径 |

## 重要说明

- `ue-rendering-settings.ini` **不是**完整的 `DefaultEngine.ini`。项目标识、平台配置、插件列表、分辨率设置，以及安全令牌、项目 ID、移动端文件服务等字段均已排除。
- 仓库不包含 UE 工程、`.uproject`、`.uasset`、`.umap`、`Content/`、`Intermediate/`、`Saved/` 或 `Binaries/`。
- 仓库也不包含逆向源数据（RDC、抓帧导出、灯数据、植被网格等）。因此这些配置只能作为参考，无法单独复现画面。
- `.ini` 中的值与最终视口效果相关；不同引擎小版本或工程资产可能需要对参数做微调。

## 配套 UE 资产路径

配置文件与文档中出现的资产路径，均对应一个未随仓库分发的参考工程。其布局如下（仅作阅读代码时的对照）：

```
/Game/Reconstruction/Rendering/
├── _Restore/
│   ├── Common/      MPC_RestoreControl、M_PP_RestoreDebugViz
│   ├── AO/          M_PP_CustomAO、M_Dbg_AO_Test
│   ├── Water/       M_Water_Restore_SLW、MI_Water_Restore_SLW
│   └── Veg/         SM_WWGrass_TriCard_A/B、M_WWGrass、MI_WWGrass
├── Water/           原始水体材质（泡沫/焦散/涟漪/法线）
├── Grass/           原始地表草材质与蓝图
└── Sky/             天空与云材质
```

关卡：`/Game/Maps/L_SuiBo_LightingReverse`（由原场景复制而来，所有还原改动只在此关卡和 `_Restore/` 内进行）。

## 使用建议

1. 先读 `mpc-restore-control.md` 理解开关模型与 PPV 顺序。
2. 把 `ue-rendering-settings.ini` 的键值**逐条**合并进自己的工程，而不是整文件替换。
3. 复制 `tools.env.example` 为 `tools.env`，填入自己的路径后再运行工具；`tools.env` 已被 `.gitignore` 忽略。
4. 若资产路径不同，请同步修改工具脚本中的 `/Game/...` 常量；仓库只保证文档中的布局一致性，不提供自动迁移。
