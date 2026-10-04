# V1.8 — 22 pratos prontos + imagens + menu lateral rolável

Nesta versão o catálogo oficial é preparado automaticamente para o chefe não precisar cadastrar os pratos um por um.

## Catálogo inicial

São criados 22 pratos, todos com foto, na categoria **Pratos do dia**. A carga é idempotente: itens já existentes não são duplicados.

Os tamanhos iniciais são **P, M e G**, com valores de referência R$ 18,00 / R$ 20,00 / R$ 26,00 conforme os materiais recebidos. O administrador pode editar tudo depois.

## Fluxo do chefe

1. Abra **Cardápio do dia**.
2. Veja os pratos já cadastrados com miniaturas.
3. Marque os pratos disponíveis naquele dia.
4. Publique.
5. Os mesmos itens alimentam o cardápio público, o carrossel da home, o Status 1080×1920 e o Post 1080×1080.

## Atualização de instalações existentes

Na primeira inicialização desta versão é criado um marcador no `DATA_DIR`. Antes disso, o sistema adiciona os pratos ausentes e completa imagens/tamanhos que estiverem faltando, preservando o restante do banco.

## Painel lateral

O menu lateral do painel agora possui rolagem própria em telas baixas e no modo móvel, evitando que os itens inferiores fiquem inacessíveis.
