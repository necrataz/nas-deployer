@echo off
REM ==============================================================================
REM NASDeployer Windows 本地构建脚本
REM 用法: 双击运行, 或在 cmd / PowerShell 中执行
REM 输出: dist\NASDeployer.exe
REM ==============================================================================

chcp 65001 >nul
echo === NASDeployer Windows 构建 ===
echo.

REM 1. 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 未安装. 请先装 Python 3.11+: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [INFO] Python 版本:
python --version
echo.

REM 2. 创建虚拟环境（如果不存在）
if not exist venv (
    echo [INFO] 创建虚拟环境 venv\...
    python -m venv venv
)

REM 3. 激活虚拟环境
echo [INFO] 激活虚拟环境...
call venv\Scripts\activate.bat

REM 4. 安装依赖
echo [INFO] 安装依赖...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] 依赖安装失败
    pause
    exit /b 1
)

REM 5. 语法检查
echo.
echo [INFO] 语法检查...
python -m py_compile src\app.py
python -m py_compile src\ssh_client.py
python -m py_compile src\apps.py
python -m py_compile src\compose_data.py

REM 6. 清理之前的构建
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist NASDeployer.spec del NASDeployer.spec

REM 7. PyInstaller 打包
echo.
echo [INFO] 开始打包 EXE (可能需要 1-3 分钟)...
pyinstaller --onefile --windowed ^
    --name NASDeployer ^
    --add-data "src\compose_data.py;." ^
    src\app.py

if %errorlevel% neq 0 (
    echo [ERROR] 打包失败
    pause
    exit /b 1
)

REM 8. 完成
echo.
echo ============================================
echo   Build success!
echo   EXE: %cd%\dist\NASDeployer.exe
echo.
echo   双击运行即可, 无需安装 Python
echo ============================================
echo.
pause