platform :ios, '17.0'
use_frameworks!
inhibit_all_warnings!

project 'PredictX-Sports.xcodeproj'

target 'PredictX Sports' do
end

post_install do |installer|
  installer.pods_project.targets.each do |target|
    target.build_configurations.each do |config|
      config.build_settings['DEBUG_INFORMATION_FORMAT'] = 'dwarf-with-dsym'
      # 強制覆蓋所有 Pod 的 deployment target 到 17.0（修復 Google-Mobile-Ads-SDK 12.0 衝突）
      config.build_settings['IPHONEOS_DEPLOYMENT_TARGET'] = '17.0'
    end
  end
end