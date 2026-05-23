@echo off
chcp 65001 >nul
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                   运维排障 Agent v1.0                        ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Python，请先安装Python 3.9+
    pause
    exit /b 1
)

:: 检查依赖
echo 📦 检查并安装依赖...
pip install -r requirements.txt -q

:: 检查.env文件
if not exist .env (
    echo.
    echo ⚠️  未找到 .env 文件
    echo    请复制 .env.example 为 .env 并配置API密钥
    echo.
    copy .env.example .env
    echo    已创建 .env 文件，请编辑配置后重新运行
    pause
    exit /b 1
)

:: 运行
echo.
echo 🚀 启动运维排障Agent...
echo.
python -m ops_agent %*

pause
