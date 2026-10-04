# Validação da entrega

Executados **57 testes automatizados**, todos aprovados no ambiente de desenvolvimento.

Cenários cobertos: catálogo sem login, busca, ordenação, seções por categoria, preservação de filtros, exibição de todas as categorias mesmo com mais de 12 pratos, seleção diária agrupada, criação das categorias padrão na primeira conta e atualização sem duplicar ou reativar categorias existentes, permissões administrativas, sessões/CSRF, revogação de acesso, criação de contas, validação de uploads, galeria/variações e preços; pedido central com itens de vários autores; endereço e pagamento; taxa fixa, taxa desconhecida e retirada; troco; validação de campos; alteração de estoque/cardápio; cálculo no servidor; envio repetido sem duplicação; aprovação e baixa de estoque; configuração do atendimento; menus publicados, rascunhos e futuras datas; geração autenticada de PNG 1080 × 1920; e exportação de várias imagens em ZIP.

O código Python foi compilado e as imagens geradas foram abertas para revisão visual. A prévia de Status incluída usa apenas dados de demonstração, com identificação explícita.

A inspeção do site por navegador no ambiente remoto foi bloqueada no acesso à prévia local. Portanto, esta entrega não afirma testes visuais em navegadores desktop/celular nem envio real no WhatsApp. O layout foi implementado com regras responsivas, e o fluxo deve ser conferido no dispositivo e no número reais antes de divulgar.

Esta validação não equivale a implantação em produção. Nenhum pedido foi enviado para uma pessoa e nenhum pagamento foi processado.
