# Vote Tracker

一个轻量的票数变化监测项目：定时从网页抓取每名候选人的票数，保存到 SQLite，并在浏览器里用折线图展示历史变化。

## 快速开始

```bash
cd vote-tracker
python3 app.py
```

然后打开：

```text
http://127.0.0.1:8765
```

当前配置已经接入虎扑 KPL 历史最佳阵容评选，默认每 5 分钟抓取一次“中路”分组里长生、清融两位选手的票数变化。

## 接入真实网站

### 虎扑投票活动

当前使用的是虎扑投票详情接口：

```text
https://bbsactivity.hupu.com/bbsactivityapi/activity/vote/detail?activityId=456
```

配置示例：

```json
{
  "poll_interval_seconds": 300,
  "source": {
    "type": "hupu_vote_detail",
    "activity_id": 456,
    "group_name": "中路",
    "candidate_names": ["长生", "清融"],
    "include_group_name": false,
    "api_url": "https://bbsactivity.hupu.com/bbsactivityapi/activity/vote/detail",
    "page_url": "https://activity-static.hupu.com/colorbox-activities/activity-260421-7uynl2a7/index.html?t=1776830935611&night=0",
    "headers": {
      "User-Agent": "Mozilla/5.0",
      "Referer": "https://activity-static.hupu.com/colorbox-activities/activity-260421-7uynl2a7/index.html?t=1776830935611&night=0"
    }
  }
}
```

把 `group_name` 改成其他位置名称可以跟踪不同分组，例如 `对抗路`、`打野`、`发育路`、`游走位`。`candidate_names` 用来限制只关注指定选手；如果删掉它，会跟踪该分组下全部选手。

如果删掉 `group_name`，会跟踪全部分组；这时建议把 `include_group_name` 设为 `true`，避免不同分组里重名时混在一起。

## 公开部署

本地运行时使用的是 `127.0.0.1`，只有这台电脑可以访问。这个项目已经附带 GitHub Pages 版本，公开页面文件在：

```text
docs/
```

公开页面读取的数据文件是：

```text
docs/data/history.json
```

数据更新脚本是：

```text
scripts/update_pages_data.py
```

GitHub Actions 工作流是：

```text
.github/workflows/update-pages-data.yml
```

工作流会约每 5 分钟运行一次，抓取长生、清融票数，追加到 `docs/data/history.json`，然后提交回仓库。GitHub 的定时任务可能有几分钟延迟，所以它不是严格秒级准时，但适合公开展示趋势。

### 发布到 GitHub Pages

1. 把当前 `vote-tracker` 项目推送到 GitHub 仓库。
2. 打开仓库的 `Settings` -> `Pages`。
3. `Build and deployment` 选择 `GitHub Actions`。
4. 打开仓库的 `Actions`，手动运行一次 `Deploy GitHub Pages`。
5. 打开仓库的 `Actions`，手动运行一次 `Update Pages Vote Data`，确认数据更新正常。

还需要确认仓库的 `Settings` -> `Actions` -> `General` 中，工作流有写入仓库的权限，否则它无法自动提交新的 `history.json`。如果 Pages 没有自动启用，GitHub 会在 `Deploy GitHub Pages` 的失败提示里给出启用入口。

### 其他部署路线

常见路线：

- VPS/云服务器：最稳，直接运行 `python3 app.py`，再用 Nginx 反向代理和域名访问。
- Render/Railway/Fly.io 等应用平台：省运维，但要确认服务不会频繁休眠，并配置持久磁盘保存 `data/votes.sqlite3`。
- GitHub Pages + GitHub Actions：可以做成纯静态公开网页，Actions 每 5 分钟抓取并生成 JSON；但不是当前这个“一体化 Python 服务”形态，需要改造。

### 通用 HTML 正则模式

如果以后要接入其他网页，可以把 `source.type` 改成 `http_regex`，填入目标页面 URL 和匹配规则。`item_pattern` 必须包含两个命名分组：

- `(?P<name>...)`：候选人/选项名称
- `(?P<votes>...)`：票数

如果目标网站是 JavaScript 渲染出来的，普通 HTTP 抓取可能拿不到票数。那种情况建议后续接入 Playwright 或 Selenium。

## API

- `GET /api/status`：当前配置、数据库路径、上次检查结果
- `GET /api/latest`：最近一次票数
- `GET /api/history`：全部候选人的历史票数
- `GET /api/history?candidate=名字`：单个候选人的历史票数
- `POST /api/check`：立即执行一次检查

## 数据文件

默认数据库在：

```text
data/votes.sqlite3
```
