# identity

账号、租户和设备会话；F01/F18，WP03。未实现认证，禁止信任客户端 tenant_id。

状态：待实现。后续按 router、service、repository 划分；仓库层每次查询必须限定认证租户，业务变更与 Outbox 同事务。不得添加以真实客户数据运行的演示端点。
