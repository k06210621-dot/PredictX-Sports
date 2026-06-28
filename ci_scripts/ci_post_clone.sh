#!/bin/bash
# Xcode Cloud CI — post-clone script
# 在 Xcode Cloud clone 完 repository 後自動執行 pod install
# 因為 Pods/ 目錄被 .gitignore 排除，必須在 CI 環境中重新生成

set -e

echo "📦 [Xcode Cloud] 開始安裝 CocoaPods 相依套件..."

# 確認 CocoaPods 已安裝
if ! command -v pod &> /dev/null; then
    echo "🔧 安裝 CocoaPods..."
    gem install cocoapods --no-document
fi

# 執行 pod install
cd "$CI_WORKSPACE"
pod install --repo-update

echo "✅ [Xcode Cloud] CocoaPods 安裝完成"
