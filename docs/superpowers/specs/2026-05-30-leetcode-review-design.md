# LeetCode 记忆曲线复习工具 — 设计文档

**日期：** 2026-05-30

---

## 概述

一个本地 Web 应用，帮助用户按 SM-2 间隔重复算法复习 LeetCode 已解题目。自动从 leetcode.com 拉取提交历史，以表格形式展示待复习题目，用户直接在表格中选择掌握程度，系统计算下次复习日期。

---

## 技术栈

- **后端：** Python + Flask
- **数据库：** SQLite（本地文件，零运维）
- **前端：** 单页 HTML + 原生 JS（无构建工具）
- **定时任务：** APScheduler（内嵌在 Flask 进程）
- **LeetCode 数据源：** 非官方 GraphQL API（`https://leetcode.com/graphql`），session cookie 认证

---

## 项目结构

```
leetcode-review/
├── app.py              # Flask 主入口、路由
├── lc_client.py        # LeetCode GraphQL 拉取逻辑
├── scheduler.py        # APScheduler 每日定时同步
├── sm2.py              # SM-2 算法实现
├── db.py               # SQLite CRUD 操作
├── config.py           # 配置（LEETCODE_SESSION、定时时间等）
├── templates/
│   └── index.html      # 唯一页面
└── leetcode.db         # SQLite 数据库（运行时自动创建）
```

---

## 数据模型

### `problems` 表
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PRIMARY KEY | 题目 slug（如 `two-sum`） |
| `title` | TEXT | 题目标题 |
| `number` | INTEGER | 题号 |
| `difficulty` | TEXT | `Easy` / `Medium` / `Hard` |
| `url` | TEXT | `https://leetcode.com/problems/{slug}/` |
| `first_solved_at` | INTEGER | 首次 AC Unix 时间戳 |

### `reviews` 表
| 字段 | 类型 | 说明 |
|------|------|------|
| `problem_id` | TEXT PRIMARY KEY (FK) | 关联 `problems.id` |
| `due_date` | TEXT (ISO date) | 下次应复习日期 |
| `interval` | INTEGER | 当前间隔天数 |
| `ease_factor` | REAL | SM-2 难度系数，初始 2.5 |
| `repetitions` | INTEGER | 已成功复习次数 |
| `last_reviewed_at` | TEXT (ISO date) | 上次复习日期，NULL 表示从未复习 |

### `sync_log` 表
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PRIMARY KEY | 自增 |
| `synced_at` | INTEGER | 同步完成时间戳 |
| `new_problems` | INTEGER | 本次新增题目数 |

---

## SM-2 算法

掌握度评分映射：

| 用户选择 | SM-2 quality 值 |
|----------|----------------|
| Again | 1 |
| Hard | 2 |
| Good | 4 |
| Easy | 5 |

标准 SM-2 公式：
- `quality >= 3`：`interval = max(1, round(interval * ease_factor))`，repetitions + 1
- `quality < 3`：interval 重置为 1，repetitions 重置为 0
- `ease_factor = ease_factor + 0.1 - (5 - quality) * 0.08 + (5 - quality)^2 * 0.02`，最小值 1.3

新题首次加入时：`interval=1, ease_factor=2.5, repetitions=0, due_date=first_solved_at+1天`

---

## LeetCode 数据同步

**认证：** 用户在 `config.py` 中配置 `LEETCODE_SESSION` cookie 值（从浏览器 DevTools 复制）。

**GraphQL 端点：** `https://leetcode.com/graphql`

**拉取策略：**
- **首次（全量）：** 分页查询 `submissionList`（offset 递增，limit=20），过滤 status=AC，直到无更多数据。每页请求间隔 0.5 秒避免频率限制。
- **每日增量：** 查询上次同步时间戳之后的提交，只写入新题。
- **按需触发：** 每次打开页面时，自动检查今天是否已同步过（查 `sync_log`），若未同步则立即触发一次增量同步。
- **手动触发：** 界面上提供"立即同步"按钮，随时强制触发一次增量同步。

无需常驻服务器，无需 APScheduler。

**Cookie 失效处理：** 同步失败时，界面顶部显示 banner 提示用户更新 session cookie。

---

## 界面设计

单页，分两个区域：

### 区域 1：今日待复习
逾期 + 今天到期的题目，按逾期天数降序排列（最紧急在最上面）。

| 题号 | 题目 | 难度 | 到期日 | 逾期 | 掌握度 |
|------|------|------|--------|------|--------|
| 1 | [Two Sum](https://leetcode.com/problems/two-sum/) | Easy | 2026-05-28 | 2天前 | Again · Hard · Good · Easy |

- 点击题目标题直接跳转到 LeetCode 题目页
- 点击掌握度按钮后，该行立即淡出，计数器更新
- 页面顶部显示"今日待复习 X 题，已完成 Y 题"

### 区域 2：未来计划
未到期题目，默认折叠，可展开查看。

| 题号 | 题目 | 难度 | 下次复习 | 剩余天数 |
|------|------|------|---------|---------|

### 其他 UI 元素
- 右上角"立即同步"按钮 + 上次同步时间
- Cookie 失效时顶部 banner 提示

---

## API 路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 返回主页面 |
| GET | `/api/reviews` | 获取今日待复习 + 未来计划数据（JSON） |
| POST | `/api/review/<problem_id>` | 提交掌握度评分，触发 SM-2 更新 |
| POST | `/api/sync` | 手动触发增量同步 |

---

## 配置

`config.py` 中需要用户设置：
```python
LEETCODE_SESSION = "your_session_cookie_here"
SYNC_HOUR = 2        # 每日同步时间（24小时制）
```

---

## 错误处理

- LeetCode API 请求失败：记录日志，不影响本地复习功能
- Cookie 失效（401/403）：界面提示，不崩溃
- 首次全量拉取中断：下次重启重新全量拉取，已存题目通过 `problems.id` 去重，不会产生重复数据

---

## 部署方式

**macOS LaunchAgent**——开机自动启动 Flask，后台静默运行。

项目提供一个 `install.py` 脚本，运行一次完成所有配置：
1. 生成 `~/Library/LaunchAgents/com.leetcode-review.plist`
2. 注册到 launchd（`launchctl load`）
3. 立即启动服务

之后只需打开浏览器访问 `http://localhost:5000`，无需手动启动服务器。

卸载同样由脚本处理（`python install.py --uninstall`）。

---

## 不在范围内

- 用户登录/多用户支持
- 移动端适配
- 代码提交内容查看
- 统计图表 / 热力图
