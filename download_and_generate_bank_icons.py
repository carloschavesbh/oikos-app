import os
import urllib.request

ICONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "static", "icons", "banks"))
os.makedirs(ICONS_DIR, exist_ok=True)

# SVGs oficiais vetorizados sob medida com dimensões e viewBox padronizados (512x512)

SVG_DEFINITIONS = {
    "mercadopago.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#009ee3"/>
  <path fill="#ffffff" d="M366.4 227.2c-5.7-14.7-18.4-25.5-33.8-28.7-11.4-2.4-23.2-.2-33 6.1l-22.3 14.3c-13.1 8.4-30 8.4-43.1 0l-22.3-14.3c-9.8-6.3-21.6-8.5-33-6.1-15.4 3.2-28.1 14-33.8 28.7-5.7 14.7-3.9 31.3 4.9 44.3l37.8 55.8c6.6 9.7 17.5 15.6 29.2 15.6h130c11.7 0 22.6-5.9 29.2-15.6l37.8-55.8c8.8-13 10.6-29.6 4.9-44.3z"/>
  <path fill="#ffffff" d="M228.3 182.5c7.4-4.7 16.9-7.2 26.5-7.2s19.1 2.5 26.5 7.2l12 7.7 18.5-11.9c-14.2-9.1-30.9-14-48-14-17.1 0-33.8 4.9-48 14l18.5 11.9 12-7.7z"/>
  <ellipse cx="254.8" cy="275.5" rx="35" ry="25" fill="#009ee3"/>
  <path fill="#ffffff" d="M243 260h24v32h-24z"/>
</svg>''',

    "99pay.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#fab612"/>
  <path fill="#1a1a1a" d="M210 150c-45 0-75 35-75 80 0 30 15 55 45 65l-35 85h50l30-75c10 3 20 5 30 5 45 0 75-35 75-80s-35-75-75-75zm0 100c-18 0-30-12-30-30 0-18 12-30 30-30s30 12 30 30c0 18-12 30-30 30z"/>
  <path fill="#1a1a1a" d="M330 150c-45 0-75 35-75 80 0 30 15 55 45 65l-35 85h50l30-75c10 3 20 5 30 5 45 0 75-35 75-80s-35-75-75-75zm0 100c-18 0-30-12-30-30 0-18 12-30 30-30s30 12 30 30c0 18-12 30-30 30z"/>
</svg>''',

    "nubank.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#820ad1"/>
  <path fill="#ffffff" d="M190 170c-40 0-70 30-70 70v102h50V240c0-15 10-25 25-25s25 10 25 25v102h50V235c0-38-30-65-80-65z"/>
  <path fill="#ffffff" d="M320 170c-50 0-80 27-80 65v107h50V240c0-15 10-25 25-25s25 10 25 25v102h50V240c0-40-30-70-70-70z"/>
</svg>''',

    "inter.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#ff7a00"/>
  <path fill="#ffffff" d="M180 160h45v192h-45z"/>
  <path fill="#ffffff" d="M255 160h45v75c12-15 30-25 52-25 40 0 68 30 68 71s-28 71-68 71c-22 0-40-10-52-25v25h-45V160zm80 75c-20 0-35 15-35 36s15 36 35 36 35-15 35-36-15-36-35-36z"/>
</svg>''',

    "itau.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#ec7000"/>
  <rect x="110" y="110" width="292" height="292" rx="55" fill="#003399"/>
  <path fill="#fdb913" d="M165 175h38v140h-38z"/>
  <path fill="#ffffff" d="M225 210h38v105h-38z"/>
  <path fill="#ffffff" d="M280 230c0-30 20-55 55-55 25 0 45 15 50 35l-30 10c-3-10-10-15-20-15-15 0-25 12-25 25v85h-30V230z"/>
</svg>''',

    "bradesco.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#cc092f"/>
  <circle cx="256" cy="190" r="38" fill="#ffffff"/>
  <path fill="#ffffff" d="M190 280c25-30 45-38 66-38s41 8 66 38c15 18 35 45 35 75H155c0-30 20-57 35-75z"/>
  <rect x="238" y="295" width="36" height="60" rx="10" fill="#cc092f"/>
</svg>''',

    "bb.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#003882"/>
  <path fill="#fcf800" d="M175 160h65l45 65-45 65h-65l45-65z"/>
  <path fill="#fcf800" d="M272 225l45-65h65l-45 65 45 65h-65z"/>
  <path fill="#fcf800" d="M217 290l39 62h65l-45-62z"/>
</svg>''',

    "caixa.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#005ca9"/>
  <path fill="#f26f21" d="M210 170l50 50-50 50-40-40 30-30-30-30z"/>
  <path fill="#ffffff" d="M302 170l40 40-30 30 30 30-40 40-50-50z"/>
  <path fill="#f26f21" d="M256 220l36 36-36 36-36-36z"/>
</svg>''',

    "picpay.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#11c76f"/>
  <path fill="#ffffff" d="M180 160h75c40 0 68 25 68 62s-28 63-68 63h-35v67h-40V160zm40 85h35c18 0 28-10 28-23s-10-22-28-22h-35v45z"/>
  <circle cx="345" cy="315" r="22" fill="#ffffff"/>
</svg>''',

    "c6.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#242424"/>
  <path fill="#ffffff" d="M210 180c-45 0-75 32-75 76s30 76 75 76c25 0 45-10 55-25l-25-20c-8 10-18 15-30 15-25 0-42-18-42-46s17-46 42-46c12 0 22 5 30 15l25-20c-10-15-30-25-55-25z"/>
  <path fill="#ffdd00" d="M295 180h35v95c0 30 20 45 45 45s45-15 45-45v-95h35v95c0 50-35 80-80 80s-80-30-80-80v-95z"/>
</svg>''',

    "sicoob.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#003641"/>
  <path fill="#00ae9d" d="M256 160l65 85-65 85-65-85z"/>
  <path fill="#c4d600" d="M191 245l65 85h-75l-40-50z"/>
  <path fill="#78be20" d="M321 245l50 35-40 50h-75z"/>
</svg>''',

    "bv.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#004990"/>
  <path fill="#ffffff" d="M160 180h45c30 0 50 15 50 40 0 15-8 28-22 34 18 5 28 20 28 38 0 28-22 48-56 48h-45V180zm40 55h12c10 0 18-5 18-14s-8-14-18-14h-12v28zm0 75h15c12 0 20-6 20-16s-8-16-20-16h-15v32z"/>
  <path fill="#00b4d8" d="M290 180h42l38 105 38-105h42l-58 160h-44z"/>
</svg>''',

    "carteira.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#10b981"/>
  <path fill="#ffffff" d="M140 180h210c15 0 28 8 35 20H140v-20z" opacity="0.7"/>
  <rect x="120" y="200" width="272" height="170" rx="25" fill="#ffffff"/>
  <path fill="#10b981" d="M320 255h72v60h-72c-16 0-30-13-30-30s14-30 30-30z"/>
  <circle cx="345" cy="285" r="10" fill="#ffffff"/>
</svg>'''
}

# Salvar todos os arquivos em static/icons/banks/
for fname, svg_content in SVG_DEFINITIONS.items():
    fpath = os.path.join(ICONS_DIR, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(svg_content.strip())
    print(f"[OK] {fname} salvo em {fpath} ({len(svg_content)} bytes)")

print("\nTodos os ícones bancários foram gerados com sucesso!")
