# V1.3 — Tipografia oficial aplicada

A versão anterior usava fallbacks como Arial/Lato em partes da interface.
Nesta revisão, os arquivos de fonte fornecidos no kit MANÁDOCÉU foram incorporados localmente.

- **Lilita One** — títulos grandes, hero e chamadas da marca.
- **Fredoka** — nomes dos pratos, categorias e subtítulos.
- **Nunito Sans** — textos corridos, navegação, botões, formulários e interface administrativa.

Os arquivos estão em `app/static/fonts/` e são carregados com `@font-face`, sem depender de Google Fonts ou internet.
A geração da imagem de Status também foi atualizada para usar essas fontes.
