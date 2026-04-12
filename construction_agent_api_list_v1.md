# 《接口清单草案 v1》

## 1. 文档信息

**文档名称**：接口清单草案 v1  
**适用项目**：建筑公司 Agent 系统  
**对应文档**：
- 《建筑公司 Agent 系统 PRD v1》
- 《数据库表结构草案 v1》

**文档目标**：
- 供后端、前端、测试、算法、AI 工程团队统一理解系统接口边界
- 明确 MVP 阶段需要实现的接口
- 定义主要请求/响应结构
- 为后续扩展预留统一风格

---

## 2. 接口设计原则

1. **MVP 优先**
   先覆盖排班、语音记录、问答解释、重排、基础资料管理五大主流程。

2. **业务接口和 AI 接口分层**
   - 业务接口：员工、工地、车辆、排班、规则等
   - AI 接口：语音转写、结构化抽取、问答解释、摘要生成

3. **统一 REST 风格**
   第一阶段建议采用 REST API，便于前后端和第三方系统快速集成。

4. **所有关键修改必须可追踪**
   对排班确认、人工改排、规则调整等关键操作保留审计字段。

5. **先返回结构化结果，再由前端决定展示**
   AI 输出不直接决定 UI，必须经过结构化响应。

---

## 3. 通用约定

## 3.1 Base URL

```bash
/api/v1
```

## 3.2 认证方式

第一阶段建议：
- 登录后获取 token
- 后续请求通过 Header 传递

```http
Authorization: Bearer <token>
```

## 3.3 通用响应格式

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "request_id": "req_123456"
}
```

说明：
- `code = 0` 表示成功
- 非 0 表示失败
- `request_id` 用于排查日志

## 3.4 分页格式

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [],
    "page": 1,
    "page_size": 20,
    "total": 100
  }
}
```

## 3.5 时间格式

统一使用：
- 日期：`YYYY-MM-DD`
- 时间：`HH:mm:ss`
- 日期时间：ISO 8601 或 `YYYY-MM-DD HH:mm:ss`

---

## 4. 认证与用户接口

## 4.1 用户登录

**POST** `/auth/login`

### 请求体

```json
{
  "username": "owner01",
  "password": "******"
}
```

### 返回

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "token": "jwt_or_session_token",
    "user": {
      "id": 1,
      "username": "owner01",
      "display_name": "老板",
      "role": "owner"
    }
  }
}
```

---

## 4.2 获取当前用户信息

**GET** `/auth/me`

### 返回

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": 1,
    "username": "owner01",
    "display_name": "老板",
    "role": "owner"
  }
}
```

---

## 5. 员工管理接口

## 5.1 员工列表

**GET** `/employees`

### 查询参数
- `keyword`
- `role_type`
- `availability_status`
- `can_lead_team`
- `page`
- `page_size`

### 返回字段
- id
- employee_code
- name
- role_type
- level
- availability_status
- can_drive
- can_lead_team
- performance_score
- safety_score

---

## 5.2 员工详情

**GET** `/employees/{employee_id}`

### 返回
- 基础信息
- 技能列表
- 证照列表
- 最近评价
- 推荐搭档
- 禁配对象
- 最近排班记录

---

## 5.3 新增员工

**POST** `/employees`

### 请求体

```json
{
  "employee_code": "E001",
  "name": "老周",
  "phone": "13800000000",
  "role_type": "木工",
  "level": "高级",
  "can_drive": true,
  "can_lead_team": true,
  "can_work_alone": true,
  "home_area": "城北"
}
```

---

## 5.4 更新员工

**PUT** `/employees/{employee_id}`

---

## 5.5 删除/停用员工

**PATCH** `/employees/{employee_id}/status`

### 请求体

```json
{
  "availability_status": "inactive"
}
```

---

## 5.6 员工技能列表

**GET** `/employees/{employee_id}/skills`

---

## 5.7 新增员工技能

**POST** `/employees/{employee_id}/skills`

### 请求体

```json
{
  "skill_name": "看图纸",
  "skill_level": "中级",
  "proficiency_score": 82,
  "is_primary": false
}
```

---

## 5.8 删除员工技能

**DELETE** `/employees/{employee_id}/skills/{skill_id}`

---

## 5.9 员工证照列表

**GET** `/employees/{employee_id}/certificates`

---

## 5.10 新增员工证照

**POST** `/employees/{employee_id}/certificates`

### 请求体

```json
{
  "certificate_type": "高处作业证",
  "certificate_no": "CERT-001",
  "issued_date": "2025-01-01",
  "expiry_date": "2027-01-01",
  "status": "valid"
}
```

---

## 5.11 员工搭班偏好列表

**GET** `/employees/{employee_id}/pair-preferences`

---

## 5.12 新增/更新员工搭班偏好

**POST** `/employees/{employee_id}/pair-preferences`

### 请求体

```json
{
  "partner_employee_id": 12,
  "relation_type": "preferred",
  "score": 90,
  "source": "manual",
  "notes": "适合一起带新人"
}
```

---

## 6. 工地管理接口

## 6.1 工地列表

**GET** `/sites`

### 查询参数
- `keyword`
- `project_status`
- `customer_priority`
- `risk_level`
- `page`
- `page_size`

---

## 6.2 工地详情

**GET** `/sites/{site_id}`

### 返回
- 工地基本信息
- 最近需求
- 风险信息
- 历史问题
- 最近安排
- 相关观察记录

---

## 6.3 新增工地

**POST** `/sites`

### 请求体

```json
{
  "site_code": "S001",
  "name": "城南住宅项目",
  "address": "XX路88号",
  "customer_name": "某地产",
  "customer_priority": "high",
  "project_status": "active",
  "risk_level": "medium",
  "weather_sensitive": true,
  "requires_team_lead": true
}
```

---

## 6.4 更新工地

**PUT** `/sites/{site_id}`

---

## 6.5 工地每日需求列表

**GET** `/sites/{site_id}/daily-requirements`

### 查询参数
- `start_date`
- `end_date`

---

## 6.6 新增工地每日需求

**POST** `/sites/{site_id}/daily-requirements`

### 请求体

```json
{
  "work_date": "2026-04-13",
  "start_time": "08:00:00",
  "required_headcount": 2,
  "required_vehicle_type": "小货车",
  "required_tools": ["切割机", "焊机"],
  "required_skills": ["焊接", "看图纸"],
  "required_certificates": ["焊工证"],
  "urgency_level": "high",
  "task_description": "钢结构加固"
}
```

---

## 6.7 更新工地每日需求

**PUT** `/sites/{site_id}/daily-requirements/{requirement_id}`

---

## 7. 车辆管理接口

## 7.1 车辆列表

**GET** `/vehicles`

### 查询参数
- `keyword`
- `current_status`
- `vehicle_type`
- `page`
- `page_size`

---

## 7.2 车辆详情

**GET** `/vehicles/{vehicle_id}`

### 返回
- 基础信息
- 当前状态
- 维护记录摘要
- 最近排班记录

---

## 7.3 新增车辆

**POST** `/vehicles`

### 请求体

```json
{
  "vehicle_code": "V001",
  "plate_number": "粤A12345",
  "vehicle_type": "小货车",
  "seat_capacity": 5,
  "load_type": "工具+材料",
  "current_status": "available"
}
```

---

## 7.4 更新车辆

**PUT** `/vehicles/{vehicle_id}`

---

## 7.5 更新车辆状态

**POST** `/vehicles/{vehicle_id}/status-logs`

### 请求体

```json
{
  "status": "repair",
  "issue_type": "brake_issue",
  "description": "刹车异响，暂停远途安排"
}
```

---

## 8. 出勤管理接口

## 8.1 查询某天出勤

**GET** `/attendance`

### 查询参数
- `work_date`

---

## 8.2 批量提交当天出勤

**POST** `/attendance/batch`

### 请求体

```json
{
  "work_date": "2026-04-13",
  "records": [
    {
      "employee_id": 1,
      "attendance_status": "present",
      "available_from": "08:00:00",
      "available_to": "18:00:00"
    },
    {
      "employee_id": 2,
      "attendance_status": "leave",
      "reason": "请假"
    }
  ]
}
```

---

## 9. 排班接口

## 9.1 生成排班草案

**POST** `/schedules/generate`

### 请求体

```json
{
  "plan_date": "2026-04-13",
  "site_ids": [1, 2, 3],
  "constraints": {
    "prefer_nearby": true,
    "respect_manual_preferences": true,
    "prioritize_high_priority_sites": true
  },
  "owner_notes": "优先保障2号和5号工地，新人尽量跟老周"
}
```

### 返回
- 排班方案 ID
- 方案版本
- 工地-班组-车辆安排
- 风险摘要
- 冲突列表
- 解释摘要

---

## 9.2 获取某天排班方案列表

**GET** `/schedules`

### 查询参数
- `plan_date`
- `plan_status`

---

## 9.3 获取排班方案详情

**GET** `/schedules/{schedule_plan_id}`

### 返回
- 方案信息
- 各工地安排
- 每组员工
- 车辆分配
- 原因说明
- 风险说明
- 是否已确认

---

## 9.4 确认排班方案

**POST** `/schedules/{schedule_plan_id}/confirm`

### 请求体

```json
{
  "confirmed_note": "按此执行"
}
```

---

## 9.5 手动改排

**POST** `/schedules/{schedule_plan_id}/override`

### 请求体

```json
{
  "assignment_id": 101,
  "new_assignment": {
    "site_id": 2,
    "vehicle_id": 5,
    "employee_ids": [3, 8]
  },
  "reason_type": "owner_preference",
  "reason_text": "小王本周尽量跟老周一起"
}
```

### 返回
- 最新方案明细
- override 记录 ID

---

## 9.6 重排某天方案

**POST** `/schedules/{schedule_plan_id}/recalculate`

### 请求体

```json
{
  "trigger_type": "absence",
  "trigger_payload": {
    "employee_id": 8,
    "reason": "临时请假"
  }
}
```

### 返回
- 新版本方案
- 受影响工地
- 风险变化
- 建议差异

---

## 9.7 获取排班变更记录

**GET** `/schedules/{schedule_plan_id}/override-logs`

---

## 10. 观察记录与语音接口

## 10.1 上传语音并转写

**POST** `/voice/transcribe`

### 请求方式
- `multipart/form-data`

### 表单字段
- `file`
- `source_user_id`

### 返回

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "transcript_text": "记录一下，老刘今天协调很好，但收尾有点慢"
  }
}
```

---

## 10.2 语音转结构化记录

**POST** `/observations/parse`

### 请求体

```json
{
  "source_type": "voice",
  "source_user_id": 1,
  "raw_input": "记录一下，老刘今天协调很好，但收尾有点慢"
}
```

### 返回

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "event_type": "employee_feedback",
    "target_type": "employee",
    "target_id": 15,
    "sentiment": "mixed",
    "tags": ["协调能力", "收尾速度"],
    "extracted_structured_data": {
      "positive": ["协调能力强"],
      "negative": ["收尾速度偏慢"]
    },
    "impacts_scheduling": false,
    "action_required": false
  }
}
```

---

## 10.3 创建观察记录

**POST** `/observations`

### 请求体

```json
{
  "source_type": "voice",
  "source_user_id": 1,
  "raw_input": "7号车今天刹车感觉不对，先别跑远",
  "event_type": "risk_alert",
  "target_type": "vehicle",
  "target_id": 7,
  "sentiment": "negative",
  "tags": ["刹车", "远途禁用"],
  "extracted_structured_data": {
    "vehicle_usage_limit": "no_long_distance"
  },
  "impacts_scheduling": true,
  "action_required": true
}
```

---

## 10.4 观察记录列表

**GET** `/observations`

### 查询参数
- `event_type`
- `target_type`
- `target_id`
- `impacts_scheduling`
- `action_status`
- `start_date`
- `end_date`
- `page`
- `page_size`

---

## 10.5 观察记录详情

**GET** `/observations/{observation_id}`

---

## 10.6 更新观察记录状态

**PATCH** `/observations/{observation_id}`

### 请求体

```json
{
  "action_status": "done",
  "confirmed_by_user": true
}
```

---

## 11. 规则接口

## 11.1 规则列表

**GET** `/rules`

### 查询参数
- `rule_type`
- `active_status`
- `page`
- `page_size`

---

## 11.2 新增规则

**POST** `/rules`

### 请求体

```json
{
  "rule_name": "高风险工地必须带队",
  "rule_type": "hard_constraint",
  "rule_priority": 100,
  "active_status": true,
  "condition_json": {
    "site_risk_level": "high"
  },
  "action_json": {
    "requires_team_lead": true
  },
  "description": "高风险工地不能安排无带队经验班组"
}
```

---

## 11.3 更新规则

**PUT** `/rules/{rule_id}`

---

## 11.4 启用/停用规则

**PATCH** `/rules/{rule_id}/status`

### 请求体

```json
{
  "active_status": false
}
```

---

## 12. 问答解释接口

## 12.1 调度问答

**POST** `/ai/qa`

### 请求体

```json
{
  "question": "为什么今天安排老周和小王去5号工地？",
  "context": {
    "plan_date": "2026-04-13",
    "schedule_plan_id": 1001
  }
}
```

### 返回

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "answer": "因为5号工地需要会看图纸且有带队经验的人。老周具备带队经验，小王处于学习阶段，适合跟班。此外，两人最近搭班反馈稳定。",
    "referenced_entities": {
      "employees": [1, 2],
      "site_id": 5,
      "schedule_plan_id": 1001
    }
  }
}
```

---

## 12.2 员工适配问答

**POST** `/ai/match/employees`

### 请求体

```json
{
  "employee_id": 15,
  "for_site_id": 3,
  "top_n": 5
}
```

### 返回
- 推荐搭档列表
- 评分
- 原因说明

---

## 12.3 工地适配问答

**POST** `/ai/match/site-team`

### 请求体

```json
{
  "site_id": 3,
  "candidate_employee_ids": [1, 2, 3, 4, 5],
  "top_n": 3
}
```

### 返回
- 推荐班组组合
- 评分明细
- 风险说明

---

## 13. 摘要接口

## 13.1 生成早间摘要

**POST** `/briefings/morning/generate`

### 请求体

```json
{
  "briefing_date": "2026-04-13"
}
```

---

## 13.2 生成晚间摘要

**POST** `/briefings/evening/generate`

### 请求体

```json
{
  "briefing_date": "2026-04-13"
}
```

---

## 13.3 获取摘要列表

**GET** `/briefings`

### 查询参数
- `briefing_date`
- `briefing_type`

---

## 13.4 获取摘要详情

**GET** `/briefings/{briefing_id}`

---

## 14. 首页与仪表盘接口

## 14.1 今日总览

**GET** `/dashboard/today-overview`

### 查询参数
- `date`

### 返回建议包含
- 今日员工出勤数
- 今日工地数
- 今日车辆可用数
- 今日方案状态
- 风险提醒数量
- 待处理观察记录数

---

## 15. MVP 必需接口清单

第一阶段必须实现：

### 认证
- `POST /auth/login`
- `GET /auth/me`

### 员工
- `GET /employees`
- `GET /employees/{id}`
- `POST /employees`
- `PUT /employees/{id}`

### 工地
- `GET /sites`
- `GET /sites/{id}`
- `POST /sites`
- `PUT /sites/{id}`
- `GET /sites/{id}/daily-requirements`
- `POST /sites/{id}/daily-requirements`

### 车辆
- `GET /vehicles`
- `GET /vehicles/{id}`
- `POST /vehicles`
- `PUT /vehicles/{id}`
- `POST /vehicles/{id}/status-logs`

### 出勤
- `GET /attendance`
- `POST /attendance/batch`

### 排班
- `POST /schedules/generate`
- `GET /schedules`
- `GET /schedules/{id}`
- `POST /schedules/{id}/confirm`
- `POST /schedules/{id}/override`
- `POST /schedules/{id}/recalculate`
- `GET /schedules/{id}/override-logs`

### 观察记录 / 语音
- `POST /voice/transcribe`
- `POST /observations/parse`
- `POST /observations`
- `GET /observations`
- `GET /observations/{id}`
- `PATCH /observations/{id}`

### 规则
- `GET /rules`
- `POST /rules`
- `PUT /rules/{id}`
- `PATCH /rules/{id}/status`

### AI 问答
- `POST /ai/qa`
- `POST /ai/match/employees`
- `POST /ai/match/site-team`

### 摘要
- `POST /briefings/morning/generate`
- `POST /briefings/evening/generate`
- `GET /briefings`
- `GET /briefings/{id}`

### 仪表盘
- `GET /dashboard/today-overview`

---

## 16. 可放到 v2 的接口

可后续扩展，不作为 MVP 必需：

- 批量导入员工/工地/车辆
- 规则模拟运行接口
- 评分明细调试接口
- 多方案对比接口
- 通知发送接口
- 考勤系统集成接口
- ERP / 项目系统同步接口
- 多公司/多组织支持接口

---

## 17. 错误码建议

| code | 含义 |
|---:|---|
| 0 | 成功 |
| 4001 | 参数错误 |
| 4002 | 未登录或 token 无效 |
| 4003 | 无权限 |
| 4041 | 数据不存在 |
| 4091 | 状态冲突 |
| 4221 | 规则校验失败 |
| 5001 | 系统内部错误 |
| 5002 | AI 服务调用失败 |
| 5003 | 调度引擎运行失败 |

---

## 18. 一句话总结

这份接口清单的目标，是让建筑公司 Agent 系统第一阶段能把**排班、语音记录、问答解释、重排和经验沉淀**真正串起来，而不是只做一个会聊天的外壳。
