#!/bin/bash

# 阿里云余额监控机器人更新脚本
# 用于快速更新应用代码

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

# 备份数据库
backup_database() {
    log_step "备份数据库..."
    
    if [[ -f "$APP_DIR/bot_data.db" ]]; then
        BACKUP_DIR="/opt/backups/$APP_NAME/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        cp "$APP_DIR/bot_data.db" "$BACKUP_DIR/"
        log_info "数据库已备份到: $BACKUP_DIR/bot_data.db"
    fi
}

# 更新代码
update_code() {
    log_step "更新应用代码..."
    
    cd "$APP_DIR"
    
    # 停止服务
    systemctl stop $APP_NAME
    
    # 拉取最新代码
    sudo -u $APP_USER git fetch origin
    sudo -u $APP_USER git reset --hard origin/main
    
    # 更新依赖
    sudo -u $APP_USER bash -c "
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
    "
    
    log_info "代码更新完成"
}

# 重启服务
restart_service() {
    log_step "重启服务..."
    
    systemctl start $APP_NAME
    
    # 等待服务启动
    sleep 5
    
    if systemctl is-active --quiet $APP_NAME; then
        log_info "✅ 服务重启成功"
    else
        log_error "❌ 服务重启失败"
        systemctl status $APP_NAME
        exit 1
    fi
}

# 检查服务状态
check_status() {
    log_step "检查服务状态..."
    
    echo "服务状态:"
    systemctl status $APP_NAME --no-pager -l
    
    echo
    echo "最近日志:"
    journalctl -u $APP_NAME -n 20 --no-pager
}

# 主函数
main() {
    log_info "开始更新 $APP_NAME..."
    
    check_root
    backup_database
    update_code
    restart_service
    check_status
    
    log_info "🎉 更新完成！"
}

# 运行主函数
main "$@"
