#!/bin/sh
# 安装 Git hooks 到本地仓库
# 使用方法: bash setup-hooks.sh

HOOKS_DIR="hooks"
GIT_HOOKS_DIR=".git/hooks"

if [ ! -d "$GIT_HOOKS_DIR" ]; then
  echo "❌ 未找到 .git/hooks 目录，请确认在项目根目录运行"
  exit 1
fi

for hook in "$HOOKS_DIR"/*; do
  hook_name=$(basename "$hook")
  cp "$hook" "$GIT_HOOKS_DIR/$hook_name"
  chmod +x "$GIT_HOOKS_DIR/$hook_name"
  echo "✅ 已安装 hook: $hook_name"
done

echo ""
echo "🎉 Hooks 安装完成！以后 git pull 时会自动检测依赖变更。"
