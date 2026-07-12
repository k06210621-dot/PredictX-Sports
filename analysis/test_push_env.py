
import sys
print(f'=== Push 環境測試 {__import__("datetime").datetime.now().isoformat()} ===', flush=True)
print(f'Python: {sys.version}', flush=True)

# 嘗試 httpx
try:
    import httpx
    print(f'✓ httpx {httpx.__version__}', flush=True)
    try:
        import h2
        print(f'✓ h2 已安裝', flush=True)
    except ImportError:
        print(f'❌ h2 未安裝', flush=True)
except ImportError as e:
    print(f'❌ httpx: {e}', flush=True)
    sys.exit(1)

# 嘗試 push_service
try:
    import push_service
    print(f'✓ push_service loaded from {push_service.__file__}', flush=True)
    print(f'  APNS_KEY_ID: {push_service.APNS_KEY_ID}', flush=True)
    print(f'  APNS_TEAM_ID: {push_service.APNS_TEAM_ID}', flush=True)
    print(f'  APNS_TOPIC: {push_service.APNS_TOPIC}', flush=True)
    print(f'  APNS_P8_BASE64 設定: {"是" if push_service.APNS_P8_BASE64 else "否"}', flush=True)
except Exception as e:
    print(f'❌ push_service: {e}', flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('=== 全部測試通過 ===', flush=True)
