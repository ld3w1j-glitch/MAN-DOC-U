# V1.9 — login e criativos corrigidos

- Aplicada a arte vertical do login na lateral esquerda do acesso administrativo.
- Corrigida a composição das fotos arredondadas nos criativos.
- O erro 400 ao abrir/baixar Status e Post era causado pelo uso incorreto de `alpha_composite` com máscara no Pillow.
- Agora a composição usa `Image.paste(..., mask)`, apropriado para a máscara de cantos arredondados.
