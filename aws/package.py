from pathlib import Path
import zipfile
root = Path(__file__).resolve().parent.parent
out = root / 'backend-api.zip'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for name in ('app.py', 'storage.py', 'lambda_handler.py'):
        z.write(root / 'backend' / name, name)
    z.write(root / 'aws/web_handler.py', 'web_handler.py')
    for p in (root / 'frontend/dist').rglob('*'):
        if p.is_file():
            z.write(p, 'web/' + p.relative_to(root / 'frontend/dist').as_posix())
print(out)
