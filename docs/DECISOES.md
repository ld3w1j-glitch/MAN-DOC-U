# Decisões da adaptação

A base utilizada foi o ZIP `INVITSTORE-main(2).zip` anexado pelo usuário. Foram preservados Flask, blueprints, SQLAlchemy/SQLite, templates Jinja, uploads, administradores, galerias/variações e gestão de custos. Esta entrega é uma aplicação separada, com banco `mana_do_ceu.db`.

A marca veio do manual e da identidade Maná do Céu fornecidos na conversa, junto às duas coleções de elementos aprovadas e vetorizadas. A aplicação usa os SVGs nas telas e exportações PNG desses vetores para compor as imagens geradas por Pillow.

O pedido centraliza o atendimento em um administrador configurável. O vínculo de autor de cada prato continua preservado para edição, enquanto o pedido pode reunir vários autores. Os preços são lidos novamente no servidor e nenhuma cobrança é processada no site.

O carrinho guarda identificadores e quantidades na sessão assinada. Endereço e dados do cliente ficam no pedido no banco, não na sessão do navegador. A tela de mensagem só pode ser acessada pela sessão que preparou o pedido. Uma chave de envio evita duplicar a mesma solicitação.

As aprovações usam transação de escrita serializada no SQLite para evitar que duas confirmações descontem o mesmo estoque simultaneamente. O principal pode aprovar todos os pedidos; o responsável escolhido pode aprovar os que foram encaminhados a ele.

O cardápio diário separa cadastro e oferta: cadastrar um prato não o coloca automaticamente à venda. Somente pratos do menu publicado da data atual podem ser selecionados. As datas são calculadas em America/Sao_Paulo. Os menus futuros não substituem o menu de hoje.

As artes do Status são geradas localmente com dados atuais, sem APIs de terceiros, em 1080 × 1920 px. Até seis pratos são exibidos por imagem; o restante forma páginas adicionais. A equipe baixa os arquivos e posta manualmente. As imagens não confirmam venda, pagamento ou disponibilidade final.

O menu público e a seleção administrativa agrupam os itens pela categoria cadastrada. As três categorias padrão são criadas na inicialização após existir um administrador principal. Categorias existentes, inclusive inativas e nomes com diferenças de maiúsculas, são preservadas; os produtos existentes não são reclassificados automaticamente. O menu público carrega todos os itens do dia, limitado a 60 na publicação, para mostrar todas as seções juntas.
