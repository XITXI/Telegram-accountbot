# 阿里云分销商余额监控机器人

>  **重大更新**: 已从测试版本升级为生产就绪版本，支持真实的阿里云GetCreditInfo API调用！

## 快速开始

### 1. 环境设置
```bash
# 确保在python3.9环境中运行
conda activate python3.9
```

### 2. 配置凭证
1. 复制配置文件: `copy .env.example .env`
2. 编辑`.env`文件，设置您的真实阿里云AK/SK

### 3. 启动机器人
- **Windows用户**: 双击运行 `start_bot.bat`
- **手动启动**: `conda activate python3.9 && python main.py`

### 4. 验证配置（推荐）
运行凭证测试脚本：
```bash
conda activate python3.9
python test_aliyun_credentials.py
```

##  新功能

###  真实API集成
-  使用阿里云GetCreditInfo API获取真实的客户信用信息
-  移除了所有模拟数据，确保数据准确性
-  详细的错误处理和用户友好的错误信息

###  智能凭证验证
-  优先使用GetCreditInfo API验证AK/SK有效性
-  避免因其他API权限差异导致的误判
-  支持配置测试UID进行完整的凭证验证

###  环境变量支持
-  支持从`.env`文件加载分销商凭证
-  安全的凭证管理，避免硬编码
-  灵活的配置选项

###  增强的部署体验
-  一键启动脚本 (`start_bot.bat`)
-  自动环境检查和依赖安装
-  凭证验证测试工具
-  详细的部署文档

##  重要文件

| 文件 | 描述 |
|------|------|
| `.env.example` | 环境变量配置模板 |
| `start_bot.bat` | Windows一键启动脚本 |
| `test_aliyun_credentials.py` | 凭证验证测试工具 |
| `DEPLOYMENT.md` | 详细部署指南 |
| `aliyun_client.py` | 更新的阿里云客户端（真实API调用） |

##  配置参数

### 必需配置
- `ALIYUN_ACCESS_KEY_ID`: 阿里云Access Key ID
- `ALIYUN_ACCESS_KEY_SECRET`: 阿里云Access Key Secret
- `BOT_TOKEN`: Telegram机器人Token
- `ADMIN_CHAT_IDS`: 管理员Telegram ID

### 推荐配置
- `ALIYUN_RESELLER_TEST_UID`: 用于凭证验证的测试用户UID

##  API权限要求

您的阿里云AK/SK需要具有以下权限：
- `bss:GetCreditInfo` - 获取用户信用信息（核心权限）

##  支持

遇到问题？
1. 查看日志文件 `bot.log`
2. 运行 `python test_aliyun_credentials.py` 验证配置
3. 参考 `DEPLOYMENT.md` 获取详细说明

---

**注意**: 此版本专为阿里云分销商设计，需要具有GetCreditInfo权限的有效凭证才能正常工作。
