# OpenGUIRobot · v1.0 技术文档

> 配合 [`PRD.md`](./PRD.md)。架构总览见 [`ARCHITECTURE.md`](../../../ARCHITECTURE.md)。

---

## 1. 技术目标

- 让 v0.4 的功能集合通过**第三方审计**
- 把 LLM / 视觉适配从"几家"提到"全家桶"，并提供 fallback chain 网关
- 建立可持续的 LTS 维护流程
- 输出可对外公开的**性能基线 + 兼容性矩阵**

---

## 2. 模块清单与工作分解

| 模块 | 包 | 工作 | 估时 |
|---|---|---|---|
| LLM Gateway | `openguirobot.llm.gateway` | provider chain + fallback + cost 统一计 | 4 |
| Provider · OpenAI / Anthropic / Bedrock / Vertex | `openguirobot.llm.providers` | 已有 + 补齐 | 4 |
| Provider · DashScope / 豆包 / 智谱 / Kimi | 同上 | 新增 + contract test | 6 |
| Vision Provider 全集 | `openguirobot.vision.providers` | Qwen-VL / InternVL / MiniCPM-V / GPT-4o / Gemini | 6 |
| 兼容性 CI 矩阵 | `.github/workflows/compat.yml` | 12+ 组合 nightly | 3 |
| SBOM / 供应链 | `tools/sbom` | CycloneDX + cosign 签名 | 2 |
| 安全审计修复 | 跨包 | 审计反馈处理 | 8 |
| 文档 · CONTRIBUTING | `docs/CONTRIBUTING.md` | 完整开发流程 | 2 |
| 文档 · DEPLOYMENT | `docs/DEPLOYMENT.md` | 单机 / K8s / 私有化 / 灾备 / 升级 | 3 |
| 文档 · SECURITY | `docs/SECURITY.md` | 威胁模型 + 披露流程 | 2 |
| 文档 · MIGRATION | `docs/MIGRATION.md` | Appium/Selenium/Espresso/EarlGrey | 2 |
| 文档 · FAQ / COMPATIBILITY / CHANGELOG | `docs/` | 持续整理 | 2 |
| ADR 整理 | `docs/adr/` | 至少 10 篇 ADR | 3 |
| 性能基准 | `bench/` | 自动跑 + 报告生成 | 3 |
| 负载测试 | `bench/load/` | 长跑 72h | 2 |
| LTS 流程 | `.github/` | release branch + backport bot | 2 |

合计：约 54 人天。

---

## 3. 关键技术决策

### 3.1 LLM Gateway 抽象

不让上层代码感知 provider 切换，统一通过 Gateway：

```python
class LLMGateway:
    def __init__(self, chain: list[LLMClient], policy: ChainPolicy): ...
    async def chat(self, messages, **kw) -> Completion:
        for client in self._select_clients(kw):
            try:
                return await client.chat(messages, **kw)
            except RetryableError as e:
                self._record_fallback(client, e)
        raise AllProvidersFailed
```

Policy 决定：

- 谁是 primary（成本 / 延迟 / 准确率优先）
- 何时 fallback（错误码 / 超时 / 成本超限）
- 是否对相同输入做 dedupe cache

### 3.2 Contract Test：每个 provider 必须过同一组测试

```python
@pytest.mark.parametrize("provider", ALL_LLM_PROVIDERS)
def test_chat_basic(provider):
    out = provider.chat([msg("hello")])
    assert out.text
    assert out.usage.tokens_in > 0
    assert out.cost_usd > 0
```

这保证社区贡献新 provider 时质量底线一致。

### 3.3 兼容性矩阵在 GitHub Actions 用 matrix

```yaml
strategy:
  matrix:
    os: [ubuntu-22.04, macos-14]
    python: ["3.11", "3.12"]
    appium: ["2.5.x"]
    android_api: [28, 31, 34]
```

每晚跑一遍，结果发布到 `docs/COMPATIBILITY.md`（自动更新）。

### 3.4 SBOM + 供应链

- `cyclonedx-bom` 生成 SBOM
- `cosign` 签名所有 docker 镜像
- GitHub Releases 附带 `checksums.txt` 与 PGP 签名
- 关键依赖 pin 住 hash（pip 用 `--require-hashes`）

### 3.5 LTS 分支策略

```
main (持续开发)
  └─ release/1.x  (LTS, 18 个月)
       ├─ v1.0.0
       ├─ v1.0.1
       ├─ v1.0.2 (CVE patch)
       └─ ...
  └─ release/1.1  (LTS, 18 个月)
       └─ ...
```

- 每个 LTS 分支由 ChannelManager bot 接收 backport
- CVE patch 自动从 main 反向 cherry-pick 到所有活跃 LTS
- `gpg --verify` 检查每个 release tag

---

## 4. 接口与数据模型

### 4.1 LLM Chain 配置

```yaml
llm:
  chain:
    - name: primary
      provider: anthropic
      model: claude-sonnet-4-6
      max_retries: 2
      timeout_s: 60
    - name: fallback-cn
      provider: dashscope
      model: qwen-max
      condition: region == "cn" or primary_unavailable
    - name: local
      provider: local_vllm
      endpoint: http://localhost:8001/v1
      model: Qwen3-Coder-32B
      condition: offline_mode
  budget:
    monthly_usd_per_tenant: 500
    soft_warning_pct: 80
    hard_stop_pct: 100
```

### 4.2 兼容性矩阵自动生成

```python
# tools/gen-compat.py
results = parse_nightly_logs("ci-logs/compat/")
markdown = render_matrix(results)
write("docs/COMPATIBILITY.md", markdown)
# CI 检查：如果矩阵变更超过阈值，open issue
```

### 4.3 ADR 模板

```markdown
# ADR-NNNN: <decision title>

- Status: Accepted | Superseded
- Date: YYYY-MM-DD
- Deciders: …

## Context
## Decision
## Consequences
## Alternatives
```

至少包含的 ADR：

- ADR-0001 Code-as-Action vs ToolCall
- ADR-0002 Sandbox 走 bwrap 而非 Docker
- ADR-0003 不使用 Celery，改用 APScheduler + Arq + Pull Queue
- ADR-0004 KuzuDB 嵌入式而非 NebulaGraph
- ADR-0005 Dashboard 选 Ant Design Pro
- ADR-0006 多租户走 RLS + 应用层双隔离
- ADR-0007 LTS 18 个月
- …

---

## 5. 部署与发布形态

### 5.1 发布渠道

| 渠道 | 内容 |
|---|---|
| PyPI | `pip install openguirobot[all]` |
| Docker Hub | `openguirobot/api:1.0.0`、`openguirobot/web:1.0.0` |
| Helm | `helm repo add ogr https://charts.openguirobot.dev`、`helm install ogr ogr/openguirobot --version 1.0.0` |
| GitHub Releases | 源码 tar.gz + SBOM + 签名 |
| 内部镜像（私有化客户）| 离线 tar 包，含模型权重 |

### 5.2 升级与回滚

- minor 升级（1.0 → 1.1）：Helm `upgrade --atomic`，DB 用 Alembic 自动迁移；预先跑 migration dry-run
- patch 升级（1.0.x）：滚动更新，无需停服
- 回滚：Helm `rollback`；DB 提供 backward-compatible migration（不删字段，加 default）
- 数据备份：postgres-operator + WAL；KuzuDB 文件 snapshot 工具

---

## 6. 测试策略

| 类型 | 范围 |
|---|---|
| Contract test | 每个 LLM / Vision provider 同一套测试 |
| 兼容性矩阵 | nightly CI |
| 性能基准 | 每周固定硬件跑一次，结果存入 `bench/results/` |
| 负载测试 | 72h 长跑 + 内存 / fd 检查 |
| 安全 | OWASP ZAP / Nuclei / Trivy / Semgrep / `cargo-audit` 等价 |
| 升级 / 回滚 | 自动化模拟 |

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 国产 LLM 接口稳定性 | contract test + 月度抓 break + adapter 内做兜底 |
| 审计反馈密集修复 | 提前进度安排 4 周；高危必修，中低危按 v1.0.x 跟进 |
| LTS 维护成本爆炸 | 主分支保持向后兼容；CI 自动 backport 配置 |
| 性能基线机器差异 | 公开硬件型号 + Docker 镜像，使第三方可复现 |
| 文档维护断档 | 每份文档强制 owner；CI 检查死链 + 文档构建 |

---

## 8. 工作分解结构（WBS）

```
W1  LLM 适配全量
    ├─ Gateway + Chain + Policy
    ├─ Bedrock / Vertex / DashScope / 豆包 / 智谱 / Kimi
    └─ Contract test 框架

W2  Vision 适配全量
    ├─ InternVL / MiniCPM-V / Gemini
    ├─ 能力矩阵
    └─ 本地 vLLM 模型矩阵

W3  文档第一波
    ├─ CONTRIBUTING / DEPLOYMENT / SECURITY / MIGRATION
    └─ ADR 模板 + 整理 1–6

W4  文档第二波 + 矩阵
    ├─ FAQ / COMPATIBILITY / CHANGELOG / ADR 整理 7+
    ├─ 兼容性 matrix CI
    └─ SBOM / cosign

W5  安全审计配合
    ├─ 配合外部审计
    ├─ 修复 critical / high
    └─ 公开报告草稿

W6  性能 / 负载
    ├─ bench 框架 + 基线
    ├─ 72h 长跑
    └─ 升级 / 回滚演练

W7  客户升级试点
    ├─ 5 家试点客户从 v0.4 升级
    └─ bug fix

W8  GA 收尾
    ├─ LTS 政策 + release schedule
    ├─ v1.0.0 GA
    └─ 社区公告
```

---

## 9. 留给 v1.x 的开放问题

- 没有"业务地图"高级特性，复杂业务场景仍依赖 Code-as-Action 重头探索
- 没有"视频→图谱"自动抽取，新 case 入库仍需人工
- 没有 IDE 插件，工程师在 IDE 中没有原生体验
- 没有商业版与开源版的能力差异化
