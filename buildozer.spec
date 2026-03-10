[app]
# 应用标题
title = 简易语音记账

# 包名
package.name = billapp

# 包域名
package.domain = org.example

# 源代码目录
source.dir = .

# 主程序文件
source.include_exts = py,png,jpg,kv,atlas,ttf,txt

# 版本号
version = 1.0.0

# 依赖项
requirements = python3,kivy,android,pyjnius

# 安卓API设置
android.api = 33
android.minapi = 21
android.sdk = 33
android.ndk = 25b

# 权限申请
android.permissions = INTERNET,RECORD_AUDIO,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# 应用图标（可选）
# android.presplash_color = #FFFFFF
# icon.filename = icon.png

# 方向
orientation = portrait

# 全屏
fullscreen = 0

# 服务（后台运行，可选）
# services = 

# 构建模式
debug = 1

# 日志级别
log_level = 2

[buildozer]
log_level = 2
warn_on_root = 1
