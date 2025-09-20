#!/bin/bash

# 阿里云余额监控机器人部署脚本
# 适用于 Ubuntu/Debian 系统

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

# 检查是否为root用户
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "请不要使用root用户运行此脚本"
        exit 1
    fi
}

# 检查系统
check_system() {
    log_info "检查系统环境..."
    
    if ! command -v apt &> /dev/null; then
        log_error "此脚本仅支持 Ubuntu/Debian 系统"
        exit 1
    fi
    
    # 检查系统版本
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        log_info "检测到系统: $NAME $VERSION"
    fi
}

# 更新系统
update_system() {
    log_info "更新系统包..."
    sudo apt update
    sudo apt upgrade -y
}

# 安装基础软件
install_basic_packages() {
    log_info "安装基础软件包..."
    sudo apt install -y \
        curl \
        wget \
        git \
        unzip \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release \
        build-essential \
        libssl-dev \
        libffi-dev \
        python3-dev
}

# 安装Python 3.10
install_python() {
    log_info "安装Python 3.10..."
    
    if ! command -v python3.10 &> /dev/null; then
        sudo add-apt-repository ppa:deadsnakes/ppa -y
        sudo apt update
        sudo apt install -y python3.10 python3.10-venv python3.10-dev
    fi
    
    # 安装pip
    if ! command -v pip3 &> /dev/null; then
        curl https://bootstrap.pypa.io/get-pip.py | python3.10
    fi
    
    log_info "Python版本: $(python3.10 --version)"
}

# 安装Nginx
install_nginx() {
    log_info "安装Nginx..."
    
    if ! command -v nginx &> /dev/null; then
        sudo apt install -y nginx
    fi
    
    # 启动并启用Nginx
    sudo systemctl start nginx
    sudo systemctl enable nginx
    
    log_info "Nginx版本: $(nginx -v 2>&1)"
}

# 安装Docker (可选)
install_docker() {
    read -p "是否安装Docker? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "安装Docker..."
        
        # 添加Docker官方GPG密钥
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        
        # 添加Docker仓库
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        # 安装Docker
        sudo apt update
        sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        
        # 将当前用户添加到docker组
        sudo usermod -aG docker $USER
        
        log_info "Docker安装完成，请重新登录以使用Docker"
    fi
}

# 创建用户和目录
setup_user_and_directories() {
    log_info "创建应用用户和目录..."
    
    # 创建用户
    if ! id "botuser" &>/dev/null; then
        sudo useradd -r -s /bin/bash -d /opt/aliyun-balance-bot botuser
    fi
    
    # 创建目录
    sudo mkdir -p /opt/aliyun-balance-bot
    sudo mkdir -p /opt/aliyun-balance-bot/logs
    sudo mkdir -p /opt/aliyun-balance-bot/data
    
    # 设置权限
    sudo chown -R botuser:botuser /opt/aliyun-balance-bot
}

# 配置防火墙
setup_firewall() {
    log_info "配置防火墙..."
    
    if command -v ufw &> /dev/null; then
        # 启用UFW
        sudo ufw --force enable
        
        # 允许SSH
        sudo ufw allow ssh
        
        # 允许HTTP和HTTPS
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        
        # 显示状态
        sudo ufw status
    else
        log_warn "UFW未安装，请手动配置防火墙"
    fi
}

# 主函数
main() {
    log_info "开始部署阿里云余额监控机器人..."
    
    check_root
    check_system
    update_system
    install_basic_packages
    install_python
    install_nginx
    install_docker
    setup_user_and_directories
    setup_firewall
    
    log_info "基础环境安装完成！"
    log_info "接下来请："
    log_info "1. 配置SSL证书"
    log_info "2. 克隆项目代码"
    log_info "3. 配置环境变量"
    log_info "4. 启动服务"
    
    echo
    log_info "运行以下命令继续部署："
    echo "sudo bash deploy/deploy.sh"
}

# 运行主函数
main "$@"
