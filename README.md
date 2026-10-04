# Maná do Céu · Cardápio, pedidos e Status

Versão 1.8.0. Projeto completo em **HTML, CSS, JavaScript, Python Flask e SQLite**, adaptado da estrutura InvitStore anexada. O cliente escolhe os pratos do dia, monta o pedido sem login e prepara uma mensagem completa para o atendimento no WhatsApp.

## Começar no Windows

1. Instale Python 3.12 e marque **Add Python to PATH**. Python 3.11 ou superior funciona.
2. Extraia o ZIP inteiro em uma **pasta nova**. Este é um projeto separado do InvitStore.
3. Abra **start_windows.bat**. Na primeira execução, ele instala as dependências; precisa de internet.
4. Informe nome do atendimento, e-mail, WhatsApp com DDD e uma senha de pelo menos 10 caracteres. Não há senha padrão.
5. O site abre em **http://127.0.0.1:5000**. O painel fica em **/login**. Deixe o terminal aberto enquanto utiliza o site.

## Configuração inicial

1. Entre no painel com a conta criada.
2. Em **Atendimento**, escolha quem recebe todos os pedidos. O telefone vem do perfil desse administrador. Configure entrega, retirada, endereço de retirada, horários e formas de pagamento. Deixe a taxa vazia quando ela precisar ser combinada; use `0,00` para entrega grátis.
3. A inicialização prepara **Pratos do dia**, **Bebidas** e **Sobremesas**. Em **Categorias**, você pode editar esses nomes ou criar outras categorias, como Acompanhamentos.
4. O sistema já deixa **22 pratos do Maná do Céu cadastrados com foto**, na categoria **Pratos do dia**. Você não precisa criar esses pratos manualmente.
5. Os pratos entram inicialmente com tamanhos **P / M / G** e valores de referência **R$ 18 / R$ 20 / R$ 26**, extraídos dos materiais enviados. Ajuste no painel caso os valores atuais sejam outros.
6. Em **Cardápio do dia**, escolha a data e marque somente os itens que serão servidos. Clique em **Publicar e gerar criativos**.

A carga dos 22 pratos também funciona ao atualizar uma instalação existente: ao iniciar esta versão pela primeira vez, os itens ausentes são adicionados sem apagar pedidos, administradores ou pratos que já existiam. As fotos ficam ligadas aos próprios produtos e são reaproveitadas no site, no carrossel da home, no Status e nos posts automáticos.

## Categorias no menu

- O cliente vê seções separadas, na ordem **Pratos do dia → Bebidas → Sobremesas**. Outras categorias também têm sua própria seção, após essas três.
- Os filtros no topo mostram uma categoria por vez ou todo o cardápio. A busca preserva a categoria selecionada; a ordenação vale dentro de cada seção.
- Todo o cardápio publicado do dia aparece junto, até o limite de 60 itens. Bebidas e sobremesas não ficam escondidas em uma página posterior.
- Se uma categoria não tiver itens selecionados para hoje, sua seção não aparece. Nenhum item é publicado apenas por pertencer a uma categoria.
- O painel de seleção diária também agrupa os itens por categoria. Todos os tipos de item podem entrar no mesmo pedido.

## Cardápio por data e Status do WhatsApp

- Os pratos são cadastrados uma vez e permanecem disponíveis para compor outros dias.
- O site público exibe somente os pratos selecionados no cardápio **publicado da data atual**, no fuso `America/Sao_Paulo`.
- A home agora pode destacar automaticamente os pratos publicados em um **carrossel/slide** logo no topo da página, usando os itens do cardápio do dia.
- É possível preparar datas futuras e salvar rascunhos. Rascunho não aparece para o cliente; salvar como rascunho uma data já publicada a retira do público.
- O administrador principal controla a seleção diária e o atendimento. Outros administradores continuam cadastrando e cuidando dos seus pratos.
- A publicação do dia mostra uma prévia da arte com logo, cores, grafismos, data, nomes dos pratos, preços, fotos dos pratos e WhatsApp do atendimento.
- O painel gera dois formatos automaticamente: **Status do WhatsApp (1080 × 1920 px)** e **Post do cardápio (1080 × 1080 px)**.
- Com mais de 4 pratos, o sistema divide automaticamente os criativos em mais de uma imagem e oferece ZIP para baixar tudo de uma vez.
- Para variações, o preço mostrado é “a partir de”. As artes usam os dados atuais no momento em que você baixa; revise antes de postar.
- A postagem no WhatsApp é feita por você. O sistema não publica nem envia mensagens automaticamente.

## Pedido do cliente

1. O cliente navega pelo cardápio de hoje, escolhe opções/tamanhos e adiciona pratos ao pedido.
2. Pode alterar quantidades, remover itens e continuar escolhendo.
3. Informa nome e WhatsApp, entrega ou retirada, endereço completo quando for entrega, referência, horário desejado, pagamento, troco e observações.
4. Ao preparar o pedido, o servidor valida a seleção diária, disponibilidade, tamanhos e preços novamente. Valores manipulados no navegador são ignorados.
5. A tela final mostra a mensagem completa e o botão **Abrir conversa no WhatsApp**. O cliente ainda deve tocar em enviar dentro do WhatsApp.
6. A solicitação fica pendente no painel. A equipe aprova ou recusa após confirmar com o cliente; aprovar desconta o estoque dos pratos e, quando houver ficha técnica, dos insumos.

A mensagem inclui número do pedido, pratos, tamanhos, quantidades, preços, subtotal, entrega, dados do cliente, endereço/local de retirada, horário, pagamento, troco e observações. Todos os itens vão para um único atendimento, mesmo quando foram cadastrados por administradores diferentes.

Abertura do WhatsApp e pagamento são etapas distintas. O site não processa cobranças nem confirma pagamentos. Quando a taxa de entrega não estiver definida, a mensagem mostra **subtotal conhecido** e **entrega a confirmar**. Horário desejado também depende de confirmação.

## Funções preservadas da estrutura InvitStore

- Administrador principal cria e desativa contas da equipe.
- Administradores cuidam dos próprios pratos; o principal pode gerenciar todos.
- Perfil com foto e WhatsApp; galeria de imagens e fotos das variações.
- Categorias, busca, ordenação, disponibilidade e paginação nos listados administrativos.
- Pedidos pendentes, aprovação, custos/insumos, ficha técnica, despesas e resultado mensal.
- Uploads validados, sessões administrativas, proteção CSRF, limitação de tentativas de login e revogação de sessões ao trocar senha/desativar conta.

## Linux / macOS

Execute `sh start_linux.sh` na pasta do projeto. O primeiro cadastro é interativo e o servidor local usa Waitress.

## Importar novamente o catálogo oficial de pratos

Se quiser restaurar itens ausentes ou completar fotos/tamanhos dos 22 pratos, execute:

```bash
# Windows
.venv\Scripts\python.exe -m flask --app run importar-pratos-mana

# Linux/macOS
.venv/bin/python -m flask --app run importar-pratos-mana
```

O comando não apaga seus produtos. Ele adiciona os pratos ausentes e pode completar foto/tamanhos quando estiverem faltando.

## Dados e backup

No PC, os dados ficam em `instance/`: `mana_do_ceu.db`, `uploads/` e `secret.key`. Faça backup da pasta inteira com o aplicativo parado. Não coloque essa pasta nem senhas em repositórios públicos. Para atualizar da versão 1.0, pare o aplicativo, faça backup de `instance/` e substitua os arquivos do projeto mantendo essa pasta. Abra `start_windows.bat` ou execute `sh start_linux.sh` novamente. A inicialização cria somente as categorias padrão ausentes; preserva pratos, pedidos, contas e categorias existentes. Escolha a categoria adequada ao editar itens já cadastrados. Esta atualização não altera colunas do banco. Não copie o banco do InvitStore por cima deste projeto.

Em produção, use uma única instância/réplica com volume persistente. O projeto inclui Dockerfile, Procfile e railway.json. Leia **docs/PUBLICACAO.md** para publicar no Railway. Esta entrega contém o código pronto para instalar; **não inclui uma hospedagem já publicada**.

## Onde ficam os elementos

- `app/static/img/mana/`: 33 SVGs de marca, elementos, faixas e pranchas.
- `app/static/img/status/`: exportações PNG dos vetores usados na arte gerada pelo servidor.
- `app/static/css/mana.css`: aplicação visual da Maná do Céu.
- `app/services/status_image.py`: geração das imagens do cardápio.
- `app/services/daily_menu.py`: seleção por dia e fuso horário.
- `app/services/menu_categories.py`: categorias padrão e agrupamento dos itens.
- `docs/`: publicação, decisões, identidade e validação.

## Testes

Instale `requirements-dev.txt` e execute `python -m pytest -q`. Consulte **docs/VALIDACAO.md** para os cenários verificados e os limites desta revisão.

Desenvolvimento: **Washington Luis de Oliveira Ladeira**.
