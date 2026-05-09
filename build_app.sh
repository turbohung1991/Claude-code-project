#!/bin/bash
# 构建 macOS .app 应用包
set -e

APP_NAME="AI智能工具箱"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="/usr/bin/python3"
APP_DIR="$PROJECT_DIR/dist/${APP_NAME}.app"
CONTENTS="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

echo "=== 构建 ${APP_NAME}.app ==="

# 清理旧构建
rm -rf "$APP_DIR"

# 创建 .app 目录结构
mkdir -p "$MACOS_DIR" "$RESOURCES"

# 创建启动脚本
cat > "$MACOS_DIR/launch.sh" << 'LAUNCH_SCRIPT'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(dirname "$(dirname "$DIR")")/Resources/project"

# 设置环境变量
export PATH="/usr/bin:/usr/local/bin:$PATH"

# 启动 Flask 应用
cd "$PROJECT"
exec /usr/bin/python3 app.py
LAUNCH_SCRIPT
chmod +x "$MACOS_DIR/launch.sh"

# 复制项目文件到 Resources
echo "复制项目文件..."
rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
      --exclude='downloads' --exclude='dist' --exclude='build' \
      --exclude='.claude' --exclude='.playwright-mcp' \
      --exclude='.DS_Store' --exclude='*.log' \
      "$PROJECT_DIR/" "$RESOURCES/project/"

# 创建可执行入口（Python 脚本）
cat > "$MACOS_DIR/$APP_NAME" << PYTHON_SCRIPT
#!/usr/bin/python3
"""macOS .app 启动器"""
import subprocess
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'Resources', 'project')

os.chdir(PROJECT_DIR)
sys.path.insert(0, PROJECT_DIR)

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.expanduser('~'), '.vibecoding', '.env'))
except ImportError:
    pass

from app import app

PORT = int(os.environ.get('PORT', 7860))

print(f'Starting on http://localhost:{PORT}')
app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
PYTHON_SCRIPT
chmod +x "$MACOS_DIR/$APP_NAME"

# 创建 Info.plist
cat > "$CONTENTS/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>AI智能工具箱</string>
    <key>CFBundleIdentifier</key>
    <string>com.vibecoding.toolkit</string>
    <key>CFBundleName</key>
    <string>AI智能工具箱</string>
    <key>CFBundleDisplayName</key>
    <string>AI智能工具箱</string>
    <key>CFBundleVersion</key>
    <string>2.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
</dict>
</plist>
PLIST

# 创建图标（使用系统图标作为占位）
# 如果需要自定义图标，替换为 .icns 文件
if [ -f "$PROJECT_DIR/icon.icns" ]; then
    cp "$PROJECT_DIR/icon.icns" "$RESOURCES/"
    /usr/libexec/PlistBuddy -c "Set :CFBundleIconFile icon.icns" "$CONTENTS/Info.plist" 2>/dev/null || true
fi

SIZE=$(du -sh "$APP_DIR" | cut -f1)
echo "=== 构建完成: $APP_DIR ($SIZE) ==="
echo ""
echo "启动方式："
echo "  open '$APP_DIR'"
echo "  或双击 Finder 中的 ${APP_NAME}.app"
