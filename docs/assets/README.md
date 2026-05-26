# Logo assets

`logo.svg` is the current logo source. `logo-{16,32,...,1024}.png`, `favicon.ico`, and `logo.icns` are all rendered from it.

To replace the logo with a different image:

1. Drop your high-resolution logo (PNG, JPG, or SVG) at `docs/assets/logo-source.png` (or `.jpg` / `.svg`) — at least 1024×1024.
2. Run from the project root:
   ```bash
   python -c "
   from PIL import Image
   import os
   src = 'docs/assets/logo-source.png'  # or .jpg / .svg
   img = Image.open(src).convert('RGBA')
   for s in [16, 32, 48, 64, 128, 256, 512, 1024]:
       r = img.resize((s, s), Image.LANCZOS)
       r.save(f'docs/assets/logo-{s}.png')
   imgs = [Image.open(f'docs/assets/logo-{s}.png') for s in [16,32,48,64,128,256]]
   imgs[0].save('docs/assets/favicon.ico', format='ICO', sizes=[(s,s) for s in [16,32,48,64,128,256]], append_images=imgs[1:])
   icns_imgs = [Image.open(f'docs/assets/logo-{s}.png') for s in [16,32,64,128,256,512,1024]]
   icns_imgs[0].save('docs/assets/logo.icns', format='ICNS', sizes=[(s,s) for s in [16,32,64,128,256,512,1024]], append_images=icns_imgs[1:])
   "
   ```
3. Commit and push. The landing page, favicon, and app icons all pick up the new files automatically.
