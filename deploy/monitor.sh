#!/bin/bash

# 阿里云余额监控机器人监控脚本
# 用于监控服务状态和自动重启

# 配置变量
APP_NAME="aliyun-balance-bot"
WEBHOOK_URL="https://bot.junxit.top/health"
LOG_FILE="/var/log/$APP_NAME-monitor.log"
MAX_RESTART_ATTEMPTS=3
RESTART_INTERVAL=60

# 日志函数
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# 检查服务状态
check_service() {
    if systemctl is-active --quiet "$APP_NAME"; then
        return 0
    else
        return 1
    fi
}

# 检查健康端点
check_health() {
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 "$WEBHOOK_URL" 2>/dev/null)
    
    if [[ "$response" == "200" ]]; then
        return 0
    else
        return 1
    fi
}

# 重启服务
restart_service() {
    log_message "尝试重启服务 $APP_NAME"
    
    systemctl restart "$APP_NAME"
    sleep 30
    
    if check_service; then
        log_message "服务重启成功"
        return 0
    else
        log_message "服务重启失败"
        return 1
    fi
}

# 发送告警通知
send_alert() {
    local message="$1"
    log_message "ALERT: $message"
    
    # 这里可以添加邮件或其他通知方式
    # 例如发送邮件给管理员
    # echo "$message" | mail -s "Bot Service Alert" admin@example.com
}

# 主监控逻辑
main() {
    local restart_count=0
    
    log_message "开始监控服务 $APP_NAME"
    
    # 检查服务状态
    if ! check_service; then
        log_message "服务未运行，尝试启动"
        systemctl start "$APP_NAME"
        sleep 30
    fi
    
    # 检查健康端点
    if ! check_health; then
        log_message "健康检查失败，服务可能异常"
        
        # 尝试重启服务
        while [[ $restart_count -lt $MAX_RESTART_ATTEMPTS ]]; do
            restart_count=$((restart_count + 1))
            log_message "第 $restart_count 次重启尝试"
            
            if restart_service; then
                # 等待服务稳定
                sleep 60
                
                # 再次检查健康状态
                if check_health; then
                    log_message "服务恢复正常"
                    exit 0
                else
                    log_message "重启后健康检查仍然失败"
                fi
            fi
            
            if [[ $restart_count -lt $MAX_RESTART_ATTEMPTS ]]; then
                log_message "等待 $RESTART_INTERVAL 秒后重试"
                sleep $RESTART_INTERVAL
            fi
        done
        
        # 所有重启尝试都失败
        send_alert "服务 $APP_NAME 重启失败，已达到最大重试次数"
        exit 1
    else
        log_message "服务运行正常"
    fi
}

# 运行主函数
main "$@"
