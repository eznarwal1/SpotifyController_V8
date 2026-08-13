import sys

try:
    print('IMPORT_OK')
except Exception:
    import traceback
    traceback.print_exc()
    sys.exit(1)
