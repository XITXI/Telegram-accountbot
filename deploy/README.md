# 阿里云余额监控机器人部署指南

本指南将帮助您将Telegram机器人部署到阿里云ECS服务器，并配置webhook实时运行。

## 前置要求

- 阿里云ECS服务器 (Ubuntu 18.04+ 或 Debian 10+)
- 域名 `bot.junxit.top` 已解析到服务器IP
- Telegram Bot Token
- 管理员Telegram用户ID

## 快速部署

### 1. 服务器环境准备

```bash
# 下载项目代码
git clone https://github.com/XITXI/Telegram-accountbot.git
cd Telegram-accountbot

# 运行环境安装脚本
chmod +x deploy/setup.sh
bash deploy/setup.sh
```

### 2. 部署应用

```bash
# 运行部署脚本
sudo chmod +x deploy/deploy.sh
sudo bash deploy/deploy.sh
```

部署脚本会自动：
- 克隆最新代码到 `/opt/aliyun-balance-bot`
- 创建Python虚拟环境并安装依赖
- 配置systemd服务
- 配置Nginx反向代理
- 设置SSL证书 (可选择Let's Encrypt自动获取)
- 启动所有服务

### 3. 配置环境变量

在部署过程中，脚本会提示您输入必要的配置信息：

- **BOT_TOKEN**: 您的Telegram Bot Token
- **ADMIN_CHAT_IDS**: 管理员Telegram用户ID (多个用逗号分隔)
- **ALIYUN_ACCESS_KEY_ID**: 阿里云Access Key ID (可选)
- **ALIYUN_ACCESS_KEY_SECRET**: 阿里云Access Key Secret (可选)

## 手动配置

如果需要手动配置，请参考以下步骤：

### 1. 创建环境变量文件

```bash
sudo cp /opt/aliyun-balance-bot/.env.example /opt/aliyun-balance-bot/.env
sudo nano /opt/aliyun-balance-bot/.env
```

配置内容：
```env
BOT_TOKEN=your_bot_token_here
WEBHOOK_URL=https://bot.junxit.top
PORT=5000
ADMIN_CHAT_IDS=your_telegram_user_id
CHECK_INTERVAL=300
ENABLE_MONITORING=true
DATABASE_PATH=bot_data.db
```

### 2. 设置文件权限

```bash
sudo chown botuser:botuser /opt/aliyun-balance-bot/.env
sudo chmod 600 /opt/aliyun-balance-bot/.env
```

### 3. 启动服务

```bash
sudo systemctl start aliyun-balance-bot
sudo systemctl enable aliyun-balance-bot
```

## SSL证书配置

### 使用Let's Encrypt (推荐)

```bash
# 安装certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d bot.junxit.top

# 设置自动续期
sudo crontab -e
# 添加以下行：
# 0 12 * * * /usr/bin/certbot renew --quiet
```

### 使用自定义证书

将证书文件放置到以下位置：
- 证书文件: `/etc/ssl/certs/bot.junxit.top.crt`
- 私钥文件: `/etc/ssl/private/bot.junxit.top.key`

## 服务管理

### 查看服务状态
```bash
sudo systemctl status aliyun-balance-bot
```

### 查看日志
```bash
# 查看应用日志
sudo journalctl -u aliyun-balance-bot -f

# 查看Nginx日志
sudo tail -f /var/log/nginx/bot.junxit.top.access.log
sudo tail -f /var/log/nginx/bot.junxit.top.error.log
```

### 重启服务
```bash
sudo systemctl restart aliyun-balance-bot
```

### 更新应用
```bash
sudo bash /opt/aliyun-balance-bot/deploy/update.sh
```

## 监控和维护

### 设置监控脚本

```bash
# 添加监控脚本到crontab
sudo crontab -e

# 添加以下行，每5分钟检查一次服务状态
*/5 * * * * /opt/aliyun-balance-bot/deploy/monitor.sh
```

### 健康检查

访问以下URL检查服务状态：
- 健康检查: `https://bot.junxit.top/health`
- Webhook端点: `https://bot.junxit.top/webhook`

## 故障排除

### 常见问题

1. **服务启动失败**
   ```bash
   sudo journalctl -u aliyun-balance-bot -n 50
   ```

2. **Nginx配置错误**
   ```bash
   sudo nginx -t
   sudo systemctl status nginx
   ```

3. **SSL证书问题**
   ```bash
   sudo certbot certificates
   sudo certbot renew --dry-run
   ```

4. **端口被占用**
   ```bash
   sudo netstat -tlnp | grep :5000
   sudo netstat -tlnp | grep :443
   ```

### 日志位置

- 应用日志: `journalctl -u aliyun-balance-bot`
- Nginx访问日志: `/var/log/nginx/bot.junxit.top.access.log`
- Nginx错误日志: `/var/log/nginx/bot.junxit.top.error.log`
- 监控脚本日志: `/var/log/aliyun-balance-bot-monitor.log`

## 安全建议

1. **防火墙配置**
   ```bash
   sudo ufw enable
   sudo ufw allow ssh
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```

2. **定期更新系统**
   ```bash
   sudo apt update && sudo apt upgrade
   ```

3. **备份数据库**
   ```bash
   sudo cp /opt/aliyun-balance-bot/bot_data.db /opt/backups/
   ```

4. **监控日志**
   定期检查日志文件，关注异常访问和错误信息。

## 支持

如果遇到问题，请：
1. 查看日志文件
2. 检查服务状态
3. 确认网络连接
4. 验证配置文件

更多信息请参考项目文档或提交Issue。
