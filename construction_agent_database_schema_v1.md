# 《数据库表结构草案 v1》

## 1. 文档目的

本文档用于定义《建筑公司 Agent 系统 PRD v1》对应的第一阶段数据库结构草案，供产品、后端、前端和算法开发共同讨论。

目标：

- 明确 MVP 期核心实体
- 明确表之间的主外键关系
- 明确哪些字段是必填
- 支持“排班、语音记录、评价沉淀、重排、可解释问答”五大核心场景
- 为后续规则引擎、评分模型和学习系统预留扩展位

---

## 2. 建模原则

1. 先满足 MVP，再预留扩展
2. 业务主表和日志表分离
3. 结构化字段优先，文本备注兜底
4. 不把 AI 结果直接当唯一真相，保留人工确认字段
5. 关键改动必须可追溯

---

## 3. 核心实体总览

MVP 核心表建议如下：

- `users`
- `employees`
- `employee_skills`
- `employee_certificates`
- `employee_pair_preferences`
- `sites`
- `site_daily_requirements`
- `vehicles`
- `vehicle_status_logs`
- `schedule_plans`
- `schedule_assignments`
- `schedule_override_logs`
- `observation_logs`
- `rule_configs`
- `attendance_records`
- `daily_briefings`

其中：

- `schedule_plans` 表示某一天某次排班方案
- `schedule_assignments` 表示方案中的具体分配明细
- `observation_logs` 是语音记录、评价、风险、决策的统一事件入口

---

## 4. 表结构草案

## 4.1 users

系统用户表，用于登录、权限和操作审计。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| username | varchar(64) | 是 | 登录名 |
| display_name | varchar(64) | 是 | 显示名 |
| role | varchar(32) | 是 | `owner` / `dispatcher` / `foreman` / `admin` |
| phone | varchar(32) | 否 | 手机号 |
| email | varchar(128) | 否 | 邮箱 |
| password_hash | varchar(255) | 是 | 密码哈希 |
| status | varchar(16) | 是 | `active` / `inactive` |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

索引建议：
- `idx_users_role`
- `uk_users_username`

---

## 4.2 employees

员工主表。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| employee_code | varchar(32) | 是 | 员工编号 |
| name | varchar(64) | 是 | 姓名 |
| phone | varchar(32) | 否 | 手机 |
| gender | varchar(16) | 否 | 性别 |
| birth_date | date | 否 | 出生日期 |
| role_type | varchar(32) | 是 | 主岗位，如木工、电工、焊工、普工 |
| level | varchar(32) | 否 | 等级，如初级/中级/高级/班组长 |
| can_drive | boolean | 是 | 是否可驾驶 |
| can_lead_team | boolean | 是 | 是否可带队 |
| can_work_alone | boolean | 是 | 是否可独立作业 |
| home_area | varchar(128) | 否 | 常驻区域/出发区域 |
| availability_status | varchar(32) | 是 | `available` / `leave` / `training` / `injured` / `inactive` |
| max_daily_hours | decimal(4,1) | 否 | 最大日工作时长 |
| fatigue_score | decimal(5,2) | 否 | 疲劳分 |
| performance_score | decimal(5,2) | 否 | 表现分 |
| safety_score | decimal(5,2) | 否 | 安全分 |
| communication_score | decimal(5,2) | 否 | 沟通分 |
| learning_score | decimal(5,2) | 否 | 学习分 |
| hire_date | date | 否 | 入职日期 |
| notes | text | 否 | 备注 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

索引建议：
- `uk_employees_employee_code`
- `idx_employees_role_type`
- `idx_employees_availability_status`

---

## 4.3 employee_skills

员工技能表，一人多技能。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| employee_id | bigint FK | 是 | 员工 ID |
| skill_name | varchar(64) | 是 | 技能名称 |
| skill_level | varchar(32) | 否 | 技能等级 |
| proficiency_score | decimal(5,2) | 否 | 熟练度评分 |
| is_primary | boolean | 是 | 是否主技能 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

外键：
- `employee_id -> employees.id`

索引建议：
- `idx_employee_skills_employee_id`
- `idx_employee_skills_skill_name`

---

## 4.4 employee_certificates

员工证照表。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| employee_id | bigint FK | 是 | 员工 ID |
| certificate_type | varchar(64) | 是 | 证书类型 |
| certificate_no | varchar(64) | 否 | 证书编号 |
| issued_date | date | 否 | 发证日期 |
| expiry_date | date | 否 | 到期日期 |
| status | varchar(16) | 是 | `valid` / `expired` / `pending` |
| notes | text | 否 | 备注 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

索引建议：
- `idx_employee_certificates_employee_id`
- `idx_employee_certificates_certificate_type`
- `idx_employee_certificates_expiry_date`

---

## 4.5 employee_pair_preferences

员工搭班偏好/禁配表。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| employee_id | bigint FK | 是 | 员工 A |
| partner_employee_id | bigint FK | 是 | 员工 B |
| relation_type | varchar(32) | 是 | `preferred` / `avoid` / `mentor` / `apprentice` |
| score | decimal(5,2) | 否 | 搭配评分 |
| source | varchar(32) | 是 | `manual` / `system` / `feedback` |
| notes | text | 否 | 备注 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

约束建议：
- `(employee_id, partner_employee_id, relation_type)` 唯一

---

## 4.6 sites

工地主表。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| site_code | varchar(32) | 是 | 工地编号 |
| name | varchar(128) | 是 | 工地名称 |
| address | varchar(255) | 是 | 地址 |
| latitude | decimal(10,7) | 否 | 纬度 |
| longitude | decimal(10,7) | 否 | 经度 |
| distance_from_base_km | decimal(8,2) | 否 | 距离公司/仓库公里数 |
| customer_name | varchar(128) | 否 | 客户名称 |
| customer_priority | varchar(32) | 否 | 客户优先级 |
| project_status | varchar(32) | 是 | `planned` / `active` / `paused` / `completed` |
| risk_level | varchar(32) | 否 | 风险等级 |
| weather_sensitive | boolean | 是 | 是否受天气影响 |
| requires_team_lead | boolean | 是 | 是否必须带队人 |
| notes | text | 否 | 备注 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

索引建议：
- `uk_sites_site_code`
- `idx_sites_project_status`
- `idx_sites_customer_priority`

---

## 4.7 site_daily_requirements

工地每日需求表。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| site_id | bigint FK | 是 | 工地 ID |
| work_date | date | 是 | 日期 |
| start_time | time | 否 | 开工时间 |
| required_headcount | int | 是 | 所需人数 |
| required_vehicle_type | varchar(64) | 否 | 需要车辆类型 |
| required_tools | json | 否 | 需要工具列表 |
| required_skills | json | 否 | 需要技能列表 |
| required_certificates | json | 否 | 需要证书列表 |
| urgency_level | varchar(32) | 是 | 紧急程度 |
| task_description | text | 否 | 当日任务说明 |
| notes | text | 否 | 备注 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

约束建议：
- `(site_id, work_date)` 唯一

索引建议：
- `idx_site_daily_requirements_work_date`
- `idx_site_daily_requirements_urgency_level`

---

## 4.8 vehicles

车辆主表。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| vehicle_code | varchar(32) | 是 | 车辆编号 |
| plate_number | varchar(32) | 是 | 车牌号 |
| vehicle_type | varchar(64) | 是 | 车型/用途 |
| seat_capacity | int | 是 | 座位数 |
| load_type | varchar(128) | 否 | 载货类型 |
| current_status | varchar(32) | 是 | `available` / `repair` / `in_use` / `inactive` |
| maintenance_status | varchar(32) | 否 | 保养状态 |
| current_location | varchar(128) | 否 | 当前停放点 |
| preferred_use_case | varchar(128) | 否 | 适用场景 |
| notes | text | 否 | 备注 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

约束建议：
- `uk_vehicles_vehicle_code`
- `uk_vehicles_plate_number`

---

## 4.9 vehicle_status_logs

车辆状态日志表。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| vehicle_id | bigint FK | 是 | 车辆 ID |
| status | varchar(32) | 是 | 状态 |
| issue_type | varchar(64) | 否 | 问题类型 |
| description | text | 否 | 说明 |
| reported_by | bigint FK | 否 | 上报人 |
| resolved_at | datetime | 否 | 解决时间 |
| created_at | datetime | 是 | 创建时间 |

索引建议：
- `idx_vehicle_status_logs_vehicle_id`
- `idx_vehicle_status_logs_status`

---

## 4.10 attendance_records

员工出勤表。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| employee_id | bigint FK | 是 | 员工 ID |
| work_date | date | 是 | 日期 |
| attendance_status | varchar(32) | 是 | `present` / `leave` / `sick` / `late` / `absent` |
| available_from | time | 否 | 可开始时间 |
| available_to | time | 否 | 可结束时间 |
| reason | varchar(255) | 否 | 原因 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

约束建议：
- `(employee_id, work_date)` 唯一

---

## 4.11 schedule_plans

排班方案表，表示某一天的一次排班结果。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| plan_date | date | 是 | 排班日期 |
| plan_version | int | 是 | 版本号 |
| plan_status | varchar(32) | 是 | `draft` / `confirmed` / `cancelled` |
| generated_by_type | varchar(32) | 是 | `system` / `manual` |
| generator_run_id | varchar(64) | 否 | 调度引擎运行 ID |
| summary | text | 否 | 方案摘要 |
| risk_summary | text | 否 | 风险摘要 |
| confirmed_by | bigint FK | 否 | 确认人 |
| confirmed_at | datetime | 否 | 确认时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

约束建议：
- `(plan_date, plan_version)` 唯一

---

## 4.12 schedule_assignments

排班明细表，表示某个方案下某工地的具体人车安排。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| schedule_plan_id | bigint FK | 是 | 排班方案 ID |
| site_id | bigint FK | 是 | 工地 ID |
| vehicle_id | bigint FK | 否 | 车辆 ID |
| assignment_status | varchar(32) | 是 | `planned` / `confirmed` / `changed` |
| generated_reason | text | 否 | 生成理由 |
| risk_notes | text | 否 | 风险说明 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

说明：
- 一条 `schedule_assignments` 代表“某工地的一个班组安排”
- 该班组的具体员工建议拆到从表

---

## 4.13 schedule_assignment_employees

排班-员工关联表。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| assignment_id | bigint FK | 是 | 排班明细 ID |
| employee_id | bigint FK | 是 | 员工 ID |
| team_role | varchar(32) | 否 | `leader` / `member` / `trainee` |
| pair_score_snapshot | decimal(5,2) | 否 | 当次搭班快照分 |
| employee_site_score_snapshot | decimal(5,2) | 否 | 员工到工地快照分 |
| created_at | datetime | 是 | 创建时间 |

约束建议：
- `(assignment_id, employee_id)` 唯一

---

## 4.14 schedule_override_logs

手动改排和原因记录表。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| schedule_plan_id | bigint FK | 是 | 排班方案 ID |
| assignment_id | bigint FK | 否 | 排班明细 ID |
| changed_by | bigint FK | 是 | 修改人 |
| reason_type | varchar(64) | 是 | 如 `owner_preference` / `absence` / `weather` / `vehicle_issue` |
| reason_text | text | 是 | 原因说明 |
| original_payload | json | 否 | 原方案快照 |
| new_payload | json | 否 | 新方案快照 |
| should_learn | boolean | 是 | 是否进入学习 |
| learned_status | varchar(32) | 是 | `pending` / `processed` / `ignored` |
| created_at | datetime | 是 | 创建时间 |

索引建议：
- `idx_schedule_override_logs_schedule_plan_id`
- `idx_schedule_override_logs_should_learn`

---

## 4.15 observation_logs

统一观察/记录表，是语音记录和评价沉淀的核心入口。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| source_type | varchar(32) | 是 | `voice` / `text` / `manual` / `system` |
| source_user_id | bigint FK | 否 | 来源用户 |
| raw_input | text | 否 | 原始输入 |
| transcript_text | text | 否 | 转写文本 |
| event_type | varchar(64) | 是 | `employee_feedback` / `site_requirement` / `schedule_instruction` / `risk_alert` / `idea` / `decision` |
| target_type | varchar(32) | 否 | `employee` / `site` / `vehicle` / `schedule_plan` |
| target_id | bigint | 否 | 目标对象 ID |
| sentiment | varchar(16) | 否 | `positive` / `neutral` / `negative` |
| tags | json | 否 | 标签列表 |
| extracted_structured_data | json | 否 | AI 抽取结构 |
| impacts_scheduling | boolean | 是 | 是否影响排班 |
| action_required | boolean | 是 | 是否需后续处理 |
| action_status | varchar(32) | 是 | `pending` / `done` / `ignored` |
| confirmed_by_user | boolean | 是 | 是否已人工确认 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

索引建议：
- `idx_observation_logs_event_type`
- `idx_observation_logs_target_type_target_id`
- `idx_observation_logs_impacts_scheduling`
- `idx_observation_logs_action_status`

---

## 4.16 rule_configs

规则配置表。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| rule_name | varchar(128) | 是 | 规则名称 |
| rule_type | varchar(64) | 是 | `hard_constraint` / `soft_constraint` / `preference` |
| rule_priority | int | 是 | 优先级 |
| active_status | boolean | 是 | 是否启用 |
| condition_json | json | 是 | 触发条件 |
| action_json | json | 是 | 动作/约束 |
| description | text | 否 | 说明 |
| created_by | bigint FK | 否 | 创建人 |
| updated_by | bigint FK | 否 | 更新人 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

示例：
- 条件：`{"site_risk_level":"high"}`
- 动作：`{"requires_team_lead":true,"min_certificates":["高处作业证"]}`

---

## 4.17 daily_briefings

每日摘要表。

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | bigint PK | 是 | 主键 |
| briefing_date | date | 是 | 日期 |
| briefing_type | varchar(16) | 是 | `morning` / `evening` |
| content_markdown | longtext | 是 | 摘要内容 |
| generated_by_type | varchar(32) | 是 | `system` / `manual` |
| related_plan_id | bigint FK | 否 | 关联排班方案 |
| created_at | datetime | 是 | 创建时间 |

约束建议：
- `(briefing_date, briefing_type)` 唯一

---

## 5. 表关系说明

主要关系如下：

- `employees` 1:N `employee_skills`
- `employees` 1:N `employee_certificates`
- `employees` N:N `employees` 通过 `employee_pair_preferences`
- `sites` 1:N `site_daily_requirements`
- `vehicles` 1:N `vehicle_status_logs`
- `employees` 1:N `attendance_records`
- `schedule_plans` 1:N `schedule_assignments`
- `schedule_assignments` 1:N `schedule_assignment_employees`
- `schedule_plans` 1:N `schedule_override_logs`
- `observation_logs` 可弱关联到 `employees` / `sites` / `vehicles` / `schedule_plans`
- `daily_briefings` 可关联到 `schedule_plans`

---

## 6. 建议的枚举值

### 6.1 员工状态
- `available`
- `leave`
- `training`
- `injured`
- `inactive`

### 6.2 车辆状态
- `available`
- `in_use`
- `repair`
- `inactive`

### 6.3 排班状态
- `draft`
- `confirmed`
- `cancelled`

### 6.4 事件类型
- `employee_feedback`
- `site_requirement`
- `schedule_instruction`
- `risk_alert`
- `idea`
- `decision`

### 6.5 关系类型
- `preferred`
- `avoid`
- `mentor`
- `apprentice`

---

## 7. 关键查询场景

数据库设计必须支持这些高频查询：

1. 查询某天所有可用员工
2. 查询某天某工地的需求
3. 查询某员工的技能、证照、最近评价
4. 查询某两个员工是否存在禁配/优选关系
5. 查询某天全部工地的排班建议
6. 查询某个排班方案被人工修改过哪些地方
7. 查询最近影响排班的语音记录
8. 查询某工地最近 7 天的问题与要求
9. 查询某台车当前状态和最近故障记录
10. 查询每天早晚摘要

---

## 8. 推荐的技术实现建议

### 8.1 数据库
MVP 推荐：
- MySQL 8.x 或 PostgreSQL

如果更看重 JSON 能力和复杂查询，PostgreSQL 更合适。  
如果团队更熟悉 MySQL，也完全可行。

### 8.2 JSON 字段使用建议
以下内容适合放 JSON：

- `required_skills`
- `required_certificates`
- `required_tools`
- `tags`
- `condition_json`
- `action_json`
- `extracted_structured_data`
- `original_payload`
- `new_payload`

原则：
- 高频筛选字段尽量拆列
- 低频扩展字段放 JSON

---

## 9. MVP 必需字段与可后补字段

### 9.1 必需先做
- 员工基础字段
- 工地基础字段
- 车辆基础字段
- 出勤状态
- 每日工地需求
- 排班方案与明细
- 语音记录主表
- 规则配置
- 改排原因

### 9.2 可以后补
- 精细评分字段
- 复杂地理坐标逻辑
- 高级证照生命周期提醒
- 更多 AI 抽取字段
- 更细粒度绩效维度

---

## 10. 初版 ER 口头描述

可以先按下面的业务理解走：

- 一个员工可以有多个技能、多个证照、多个观察记录
- 一个工地每天有一条需求记录
- 一天可以有多个排班版本
- 一个排班版本下，每个工地会形成一个或多个班组安排
- 一个班组安排包含多个员工，可能带一台车
- 任何手动调整都需要记录 override log
- 任何语音或文本输入都先进 observation_logs，再决定是否落到别的业务表

---

## 11. 下一步建议

有了这份表结构草案，下一步最适合继续做的是：

1. 输出《接口清单草案 v1》
2. 输出《页面原型清单 v1》
3. 输出《调度评分规则草案 v1》
4. 输出《语音输入转结构化字段规范 v1》

---

## 12. 一句话总结

这套数据库不是为了“存聊天记录”，而是为了把建筑公司的**人、车、工地、规则、评价、变更和老板经验**，变成可计算、可查询、可学习的经营基础设施。
