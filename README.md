# Catálogo Carmax Santos

Página com o estoque da Carmax Santos que se atualiza sozinha.

- `scraper.py` lê https://carmaxsantos.com.br/estoque e grava `docs/estoque.json`.
- `.github/workflows/atualizar.yml` roda o robô de hora em hora (e pelo botão **Run workflow** na aba Actions).
- `docs/index.html` é a página publicada pelo GitHub Pages.
