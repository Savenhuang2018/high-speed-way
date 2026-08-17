# 高速公路服务区「车主服务 + 点评」MVP

高速路上的"大众点评 + 服务区导览"：车主可查看沿途服务区业态、商户评分与点评；运营方可管理服务区与商户、审核点评。

## 技术栈
- **后端**：Python 标准库（`http.server` + `sqlite3`），**零第三方依赖，开箱即跑**
- **数据**：SQLite（单文件 `service_area.db`）
- **前端**：静态 HTML + 原生 JS（由后端直接托管）
- 另附 FastAPI + SQLAlchemy 版参考实现（`app/`，需 pip 安装依赖）

> 说明：原规划采用 FastAPI，但当前环境 pip 安装需审批且超时，故主实现改为纯标准库以保证可运行、可验证。产品结构与接口设计与原方案一致。

## 快速开始

### 1. 启动服务
```bash
cd ~/service-area-dianping
python3 server.py 8123
```
首次启动自动建表并写入演示数据。浏览器打开：http://127.0.0.1:8123

### 高德地图数据接入（可选）
`/route/areas` 沿途服务区默认用本地种子数据。接入高德真实服务区 POI：
1. 在高德开放平台 https://lbs.amap.com 申请 Web 服务 API key（免费）
2. 配置 key（二选一）：
   - `export AMAP_KEY=你的key`
   - 或写入 `~/.hermes/.env`：`AMAP_KEY=你的key`
3. 重启服务。配置后 `/route/areas` 会自动调用高德搜索"高速公路服务区" POI 并同步入库，结合几何算法沿线筛选；未配置 key 时自动回退本地数据，不影响使用。

> 说明：高德**网页版**搜索接口有反爬滑块验证，无法程序化抓取；正规接入使用 Web 服务 API（需免费 key），稳定合规。

### 2. 运行测试（零依赖）
```bash
python3 test_stdlib.py
```
22 项集成测试，覆盖：服务区/商户/点评的 CRUD、业态筛选、点评审核闭环、评分重算、非法评分校验、优惠券领取去重、运营数据看板统计、智能审核（敏感词/低分转人工）、商户回复点评、沿途服务区、服务区搜索、收藏。
（当前共 44 项）

## API 一览
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /health | 健康检查 |
| GET | /service-areas | 服务区列表 |
| GET | /service-areas/search?q= | 搜索服务区（名称/高速/桩号/描述，含商户数/评分/业态） |
| GET | /route/areas?cur_lat=&cur_lng=&dest_lat=&dest_lng=&max_off_km= | 沿途服务区（按沿程距离升序，高德/本地数据源） |
| POST | /service-areas | 新建服务区 |
| GET | /merchants?service_area_id=&category=&min_rating= | 商户列表（可筛选） |
| GET | /merchants/{id} | 商户详情（含评分、点评数） |
| POST | /merchants | 新建商户 |
| GET | /reviews?merchant_id={id} | 某商户已审核点评 |
| POST | /reviews | 发表点评（智能审核：高分自动过，敏感词/低分转人工） |
| POST | /reviews/{id}/approve | 审核通过点评 |
| POST | /reviews/{id}/reply | 商户回复点评 |
| GET | /coupons?merchant_id= | 优惠券列表 |
| POST | /coupons/{id}/claim | 领取优惠券 {user_id} |
| GET | /users/me/coupons?user_id= | 我的优惠券 |
| GET | /stats/dashboard | 运营数据看板（客流/点评/业态/差评预警） |
| GET | /favorites?user_id= | 我的收藏服务区 |
| POST | /favorites/toggle | 收藏/取消收藏 {user_id, area_id} |
| GET | /users/{id} | 用户详情 |
| POST | /users | 创建用户 |

## 项目结构
```
server.py            # 主服务（零依赖，含静态首页托管）
amap.py              # 高德地图接入模块（搜索/路径规划/解析/幂等入库）
eval_deepseek.sh     # DeepSeek 评测脚本（lm-evaluation-harness via 火山引擎）
static/index.html    # 前端页面（车主端：美团风格首页，沿途服务区）
static/admin.html    # 运营后台页面
docs/market-research.md  # 市场调研报告
test_stdlib.py       # 零依赖集成测试
test_amap.py         # 高德模块测试
verify_running.py    # 运行中服务验证脚本
requirements.txt     # FastAPI 版依赖（可选）
app/                 # FastAPI + SQLAlchemy 参考实现
  main.py            #   应用入口
  database.py        #   数据库
  models.py          #   ORM 模型
  schemas.py         #   Pydantic 模型
  crud.py            #   数据访问
  api/               #   路由
  seed.py            #   种子数据
tests/               # FastAPI 版测试（需 pip 依赖）
```

## 下一步（路线图）
- [x] 优惠券体系、商户回复
- [x] 差评预警与审核算法（敏感词/低分自动转人工）
- [ ] 对接充电桩实时状态（充电平台 API / 人工上报）
- [ ] 微信小程序端（复用现有 API）
- [ ] 运营 PC 后台（商户管理、点评审核、数据看板）

## DeepSeek 评测（lm-evaluation-harness）
基于 lm-eval 0.4.12，通过火山引擎方舟评测 DeepSeek 模型。
```bash
# 评测 gsm8k（5 个样本）
./eval_deepseek.sh gsm8k 5

# 评测多个任务（100 样本）
./eval_deepseek.sh mmlu,arc_challenge 100
```
- 模型：deepseek-v4-flash-ga-260731（可改 eval_deepseek.sh 顶部）
- 说明：生成类任务（gsm8k/mmlu 等）适用；multiple_choice 类（hellaswag 等）因 chat 模型无 logprobs 不支持
- 评测真实调用火山引擎 API，消耗 token
- 认证：从 `~/.hermes/.env` 的 ARK key 读取
