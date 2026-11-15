# ADR-001：初始工程结构

状态：仓库结构已采用；Flutter 选型待 W2 真机验证。日期：2026-11-15。

采用单仓库、Python 3.12 / FastAPI 模块化单体及独立 Worker 入口，业务领域与 AI 适配层放在 packages。现阶段 Python 模块共享一份依赖锁和构建，暂不拆成多个部署微服务。

移动端先落 Flutter 界面骨架；既有需求保留 Flutter / React Native 的评估门槛，录音、离线加密、后台行为及人员适配验证不通过时可以在业务实现前调整。

初版 API 仅实现健康检查。就绪检查固定返回 503，模型网关拒绝调用，Worker 仅离线验证事件。认证、数据库、DLP、持久化、队列和支付都不伪装成已实现。后续设计保持 PostgreSQL 权威、Outbox、租约／fencing、版本校验与删除墓碑。

CI 负责 Python 和 Flutter 的检查；原生 iOS 构建需 macOS / Xcode，Android 构建需 Android SDK，纳入后续平台工程工作。
