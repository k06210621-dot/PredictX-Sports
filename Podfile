platform :ios, '17.0'
use_frameworks!
inhibit_all_warnings!

project 'PredictX-Sports.xcodeproj'

target 'PredictX Sports' do
  pod 'Google-Mobile-Ads-SDK', '~> 11.0'
end

post_install do |installer|
  installer.pods_project.targets.each do |target|
    target.build_configurations.each do |config|
      config.build_settings['DEBUG_INFORMATION_FORMAT'] = 'dwarf-with-dsym'
    end
  end
end