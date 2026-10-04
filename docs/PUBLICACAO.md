# Publicação · Maná do Céu

O código usa Flask e SQLite e mantém os arquivos de implantação da base InvitStore. Não foi feita uma implantação na conta do usuário nesta entrega.

## Railway com Docker

1. Coloque o conteúdo interno da pasta `Mana_do_Ceu_Web_v1_1` na raiz de um novo repositório e conecte-o a um serviço Railway. O projeto possui Dockerfile e railway.json.
2. Conecte ao serviço um volume com caminho `/data`. SQLite, fotos e chave da sessão dependem dele. O processo de produção verifica o volume antes de iniciar.
3. Configure as variáveis da primeira conta: `ADMIN_NAME`, `ADMIN_EMAIL`, `ADMIN_WHATSAPP` e `ADMIN_PASSWORD`. O WhatsApp deve ser brasileiro com DDD. A senha deve ter entre 10 e 128 caracteres. Defina esses valores nas variáveis do serviço, não em arquivos enviados ao repositório.
4. O Dockerfile já configura `APP_ENV=production`, `DATA_DIR=/data` e `REQUIRE_DATA_VOLUME=1`. Use uma réplica. O servidor inicia com um worker Gunicorn e quatro threads.
5. Aplique a publicação e gere o domínio HTTPS na plataforma. Se quiser configurar links absolutos, use `PUBLIC_BASE_URL` sem barra final.
6. Entre em `/login`, configure **Atendimento**, confira as categorias Pratos do dia, Bebidas e Sobremesas e cadastre os itens, publique **Cardápio do dia** e confira um pedido de teste.

`SECRET_KEY` é opcional: quando não definida, é gerada uma vez no volume e reutilizada. Se você a definir, use pelo menos 32 caracteres aleatórios e preserve o valor nas atualizações.

As variáveis `ADMIN_*` só criam a primeira conta em banco vazio. Elas não redefinem senhas existentes. Depois da configuração inicial, a senha do admin pode ser removida das variáveis. Troque senhas pelo painel ou pelo comando `flask --app run redefinir-senha EMAIL`.

## Operação e atualizações

- Use HTTPS para as sessões administrativas em produção.
- Preserve `/data` e faça backup com o serviço parado antes de atualizações.
- O banco desta instalação chama-se `mana_do_ceu.db`.
- No início, `db.create_all()` cria as tabelas ausentes. Alterações futuras de colunas exigirão migração específica.
- `TRUSTED_HOSTS`, se usado, deve incluir os domínios necessários para acesso e verificação de saúde; uma configuração incorreta pode bloquear requisições legítimas.
- `/health` verifica conexão com o banco.
- Os horários exibidos são informativos. A equipe controla **Aceitar pedidos** e o cardápio publicado da data.

## Outra hospedagem

O mesmo Dockerfile pode ser usado num provedor que aceite Python, HTTPS e armazenamento persistente. Monte `/data` e mantenha uma única réplica para este SQLite.
