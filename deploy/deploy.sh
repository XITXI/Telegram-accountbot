#!/bin/bash

# 阿里云余额监控机器人部署脚本
# 此脚本用于部署应用到生产环境

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
APP_NAME="aliyun-balance-bot"
APP_USER="botuser"
APP_DIR="/opt/$APP_NAME"
REPO_URL="https://github.com/XITXI/Telegram-accountbot.git"
DOMAIN="bot.junxit.top"

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本需要root权限运行"
        exit 1
    fi
}

# 停止现有服务
stop_services() {
    log_step "停止现有服务..."
    
    if systemctl is-active --quiet $APP_NAME; then
        systemctl stop $APP_NAME
        log_info "已停止 $APP_NAME 服务"
    fi
}

# 备份现有数据
backup_data() {
    if [[ -d "$APP_DIR" ]]; then
        log_step "备份现有数据..."
        
        BACKUP_DIR="/opt/backups/$APP_NAME/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        if [[ -f "$APP_DIR/bot_data.db" ]]; then
            cp "$APP_DIR/bot_data.db" "$BACKUP_DIR/"
            log_info "数据库已备份到: $BACKUP_DIR/bot_data.db"
        fi
        
        if [[ -f "$APP_DIR/.env" ]]; then
            cp "$APP_DIR/.env" "$BACKUP_DIR/"
            log_info "环境配置已备份到: $BACKUP_DIR/.env"
        fi
    fi
}

# 克隆或更新代码
deploy_code() {
    log_step "部署应用代码..."
    
    if [[ -d "$APP_DIR/.git" ]]; then
        log_info "更新现有代码..."
        cd "$APP_DIR"
        sudo -u $APP_USER git fetch origin
        sudo -u $APP_USER git reset --hard origin/main
    else
        log_info "克隆新代码..."
        rm -rf "$APP_DIR"
        sudo -u $APP_USER git clone "$REPO_URL" "$APP_DIR"
    fi
    
    # 设置权限
    chown -R $APP_USER:$APP_USER "$APP_DIR"
    chmod +x "$APP_DIR/deploy/"*.sh
}

# 设置Python虚拟环境
setup_venv() {
    log_step "设置Python虚拟环境..."
    
    cd "$APP_DIR"
    
    # 创建虚拟环境
    if [[ ! -d "venv" ]]; then
        sudo -u $APP_USER python3.10 -m venv venv
    fi
    
    # 激活虚拟环境并安装依赖
    sudo -u $APP_USER bash -c "
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
    "
    
    log_info "Python虚拟环境设置完成"
}

# 配置环境变量
setup_env() {
    log_step "配置环境变量..."
    
    if [[ ! -f "$APP_DIR/.env" ]]; then
        log_warn "未找到 .env 文件，请手动创建并配置"
        log_info "参考文件: $APP_DIR/.env.example"
        
        read -p "是否现在配置环境变量? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            configure_env_interactive
        fi
    else
        log_info "环境变量文件已存在: $APP_DIR/.env"
    fi
}

# 交互式配置环境变量
configure_env_interactive() {
    log_info "开始交互式配置..."
    
    read -p "请输入Telegram Bot Token: " BOT_TOKEN
    read -p "请输入管理员Telegram用户ID (多个用逗号分隔): " ADMIN_CHAT_IDS
    read -p "请输入阿里云Access Key ID (可选): " ALIYUN_ACCESS_KEY_ID
    read -p "请输入阿里云Access Key Secret (可选): " ALIYUN_ACCESS_KEY_SECRET
    
    # 创建.env文件
    cat > "$APP_DIR/.env" << EOF
# Telegram Bot配置
BOT_TOKEN=$BOT_TOKEN
WEBHOOK_URL=https://$DOMAIN
PORT=5000

# 管理员配置
ADMIN_CHAT_IDS=$ADMIN_CHAT_IDS

# 监控配置
CHECK_INTERVAL=300
ENABLE_MONITORING=true

# 数据库配置
DATABASE_PATH=bot_data.db

# 阿里云配置
ALIYUN_ACCESS_KEY_ID=$ALIYUN_ACCESS_KEY_ID
ALIYUN_ACCESS_KEY_SECRET=$ALIYUN_ACCESS_KEY_SECRET
EOF
    
    chown $APP_USER:$APP_USER "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    
    log_info "环境变量配置完成"
}

# 配置systemd服务
setup_systemd() {
    log_step "配置systemd服务..."
    
    # 复制服务文件
    cp "$APP_DIR/deploy/$APP_NAME.service" "/etc/systemd/system/"
    
    # 重新加载systemd
    systemctl daemon-reload
    
    # 启用服务
    systemctl enable $APP_NAME
    
    log_info "systemd服务配置完成"
}

# 配置Nginx
setup_nginx() {
    log_step "配置Nginx..."
    
    # 复制配置文件
    cp "$APP_DIR/deploy/nginx.conf" "/etc/nginx/sites-available/$DOMAIN"
    
    # 创建软链接
    if [[ ! -L "/etc/nginx/sites-enabled/$DOMAIN" ]]; then
        ln -s "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/"
    fi
    
    # 删除默认配置
    if [[ -L "/etc/nginx/sites-enabled/default" ]]; then
        rm "/etc/nginx/sites-enabled/default"
    fi
    
    # 测试配置
    nginx -t
    
    log_info "Nginx配置完成"
}

# 设置SSL证书
setup_ssl() {
    log_step "设置SSL证书..."
    
    if [[ ! -f "/etc/ssl/certs/$DOMAIN.crt" ]]; then
        log_warn "SSL证书不存在，请手动配置SSL证书"
        log_info "证书路径: /etc/ssl/certs/$DOMAIN.crt"
        log_info "私钥路径: /etc/ssl/private/$DOMAIN.key"
        
        read -p "是否使用Let's Encrypt自动获取证书? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            setup_letsencrypt
        fi
    else
        log_info "SSL证书已存在"
    fi
}

# 设置Let's Encrypt证书
setup_letsencrypt() {
    log_info "安装Certbot..."
    
    # 安装certbot
    apt update
    apt install -y certbot python3-certbot-nginx
    
    # 获取证书
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@"$DOMAIN"
    
    # 设置自动续期
    (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
    
    log_info "Let's Encrypt证书设置完成"
}

# 启动服务
start_services() {
    log_step "启动服务..."
    
    # 重新加载Nginx
    systemctl reload nginx
    
    # 启动应用服务
    systemctl start $APP_NAME
    
    # 检查服务状态
    sleep 5
    if systemctl is-active --quiet $APP_NAME; then
        log_info "✅ $APP_NAME 服务启动成功"
    else
        log_error "❌ $APP_NAME 服务启动失败"
        systemctl status $APP_NAME
        exit 1
    fi
    
    if systemctl is-active --quiet nginx; then
        log_info "✅ Nginx 服务运行正常"
    else
        log_error "❌ Nginx 服务异常"
        systemctl status nginx
        exit 1
    fi
}

# 显示部署信息
show_deployment_info() {
    log_step "部署完成！"
    
    echo
    echo "==================== 部署信息 ===================="
    echo "应用名称: $APP_NAME"
    echo "应用目录: $APP_DIR"
    echo "域名: https://$DOMAIN"
    echo "Webhook URL: https://$DOMAIN/webhook"
    echo "健康检查: https://$DOMAIN/health"
    echo "=================================================="
    echo
    
    log_info "常用命令:"
    echo "  查看服务状态: systemctl status $APP_NAME"
    echo "  查看日志: journalctl -u $APP_NAME -f"
    echo "  重启服务: systemctl restart $APP_NAME"
    echo "  查看Nginx日志: tail -f /var/log/nginx/$DOMAIN.*.log"
    echo
    
    log_info "请确保:"
    echo "  1. 域名 $DOMAIN 已正确解析到此服务器"
    echo "  2. 防火墙已开放 80 和 443 端口"
    echo "  3. Telegram Bot Token 已正确配置"
    echo "  4. 管理员用户ID已正确设置"
}

# 主函数
main() {
    log_info "开始部署 $APP_NAME..."
    
    check_root
    stop_services
    backup_data
    deploy_code
    setup_venv
    setup_env
    setup_systemd
    setup_nginx
    setup_ssl
    start_services
    show_deployment_info
    
    log_info "🎉 部署完成！"
}

# 运行主函数
main "$@"
