@echo off
REM Windows 构建脚本 - 打包为可执行文件
REM 需要先安装: pip install pyinstaller

echo === 构建 AI智能工具箱 Windows 版 ===

cd /d "%~dp0"

REM 清理
if exist dist\windows rmdir /s /q dist\windows
mkdir dist\windows

REM 使用 PyInstaller 打包（Windows 上需安装所有依赖）
pyinstaller --onedir --name AI智能工具箱 --noconsole ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "config;config" ^
  --add-data "converters;converters" ^
  --add-data "src;src" ^
  run.py

REM 移动到输出目录
move /y dist\AI智能工具箱 dist\windows\

echo === 构建完成 ===
echo 输出目录: dist\windows\AI智能工具箱\
echo 运行: dist\windows\AI智能工具箱\AI智能工具箱.exe
