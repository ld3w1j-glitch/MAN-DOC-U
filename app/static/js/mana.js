'use strict';
const checkout = document.querySelector('[data-checkout]');
const moneyBR = cents => new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(cents/100);
if (checkout) {
  const update = () => {
    const delivery = checkout.querySelector('[name="fulfillment"]:checked')?.value === 'delivery';
    const address = checkout.querySelector('[data-address-fields]');
    address.hidden = !delivery;
    address.querySelectorAll('input').forEach(input => {input.disabled = !delivery; input.required = delivery && input.hasAttribute('data-delivery-required');});
    const cash = checkout.querySelector('[name="payment_method"]').value === 'cash';
    checkout.querySelector('[data-cash-fields]').hidden = !cash;
    checkout.querySelector('[name="change_for"]').disabled = !cash;
    const known = !delivery || checkout.dataset.deliveryFee !== '';
    const fee = delivery ? Number(checkout.dataset.deliveryFee || 0) : 0;
    document.querySelector('[data-summary-fee]').textContent = known ? moneyBR(fee) : 'A confirmar';
    document.querySelector('[data-total-label]').textContent = known ? 'Total' : 'Subtotal conhecido';
    document.querySelector('[data-summary-total]').textContent = moneyBR(Number(checkout.dataset.subtotal)+fee);
  };
  checkout.addEventListener('change',update); update();
  checkout.addEventListener('submit', () => {const button=checkout.querySelector('[data-checkout-submit]');button.disabled=true;button.textContent='Preparando pedido…';});
  window.addEventListener('pageshow',()=>{const button=checkout.querySelector('[data-checkout-submit]');if(button.textContent==='Preparando pedido…'){button.disabled=false;button.textContent='Preparar pedido no WhatsApp';}});
}
const copy = document.querySelector('[data-copy-order]');
if(copy)copy.addEventListener('click',async()=>{
  const content=document.querySelector('[data-order-message]').textContent;
  try {await navigator.clipboard.writeText(content);document.querySelector('[data-copy-status]').textContent='Mensagem copiada. Cole na conversa com o atendimento.';}
  catch {document.querySelector('[data-copy-status]').textContent='Selecione a mensagem abaixo para copiar manualmente.';}
});

const publicMenuButton = document.querySelector('[data-public-menu]');
const publicNav = document.querySelector('[data-public-nav]');
if (publicMenuButton && publicNav) {
  const closePublicMenu = () => {
    publicMenuButton.setAttribute('aria-expanded', 'false');
    publicNav.classList.remove('open');
  };
  publicMenuButton.addEventListener('click', () => {
    const open = publicMenuButton.getAttribute('aria-expanded') !== 'true';
    publicMenuButton.setAttribute('aria-expanded', String(open));
    publicNav.classList.toggle('open', open);
  });
  publicNav.querySelectorAll('a').forEach(link => link.addEventListener('click', closePublicMenu));
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closePublicMenu(); });
}

const carouselRoot = document.querySelector('[data-menu-carousel]');
if (carouselRoot) {
  const viewport = carouselRoot.querySelector('[data-carousel-viewport]');
  const track = carouselRoot.querySelector('.mana-slider-track');
  const cards = [...carouselRoot.querySelectorAll('.mana-slide-card')];
  const prev = document.querySelector('[data-carousel-prev]');
  const next = document.querySelector('[data-carousel-next]');
  const dotsHost = carouselRoot.querySelector('[data-carousel-dots]');
  let autoplay;

  const cardStep = () => cards[0] ? cards[0].getBoundingClientRect().width + 18 : viewport.clientWidth;
  const pageCount = () => {
    const step = cardStep();
    return Math.max(1, Math.round((track.scrollWidth - viewport.clientWidth) / step) + 1);
  };
  const currentPage = () => {
    const step = cardStep();
    return Math.min(pageCount() - 1, Math.max(0, Math.round(viewport.scrollLeft / step)));
  };
  const updateDots = () => {
    [...dotsHost.children].forEach((dot, index) => dot.classList.toggle('active', index === currentPage()));
  };
  const buildDots = () => {
    dotsHost.replaceChildren();
    for (let i = 0; i < pageCount(); i += 1) {
      const dot = document.createElement('button');
      dot.type = 'button';
      dot.className = 'mana-slider-dot';
      dot.setAttribute('aria-label', `Ir para o grupo ${i + 1}`);
      dot.addEventListener('click', () => viewport.scrollTo({ left: cardStep() * i, behavior: 'smooth' }));
      dotsHost.appendChild(dot);
    }
    updateDots();
  };
  const move = direction => viewport.scrollBy({ left: cardStep() * direction, behavior: 'smooth' });
  const startAutoplay = () => {
    stopAutoplay();
    if (pageCount() <= 1) return;
    autoplay = window.setInterval(() => {
      const page = currentPage();
      const nextPage = page + 1 >= pageCount() ? 0 : page + 1;
      viewport.scrollTo({ left: cardStep() * nextPage, behavior: 'smooth' });
    }, 4500);
  };
  const stopAutoplay = () => { if (autoplay) window.clearInterval(autoplay); };

  buildDots();
  startAutoplay();
  prev?.addEventListener('click', () => move(-1));
  next?.addEventListener('click', () => move(1));
  viewport.addEventListener('scroll', () => window.requestAnimationFrame(updateDots));
  window.addEventListener('resize', () => { buildDots(); startAutoplay(); });
  carouselRoot.addEventListener('mouseenter', stopAutoplay);
  carouselRoot.addEventListener('mouseleave', startAutoplay);
  carouselRoot.addEventListener('focusin', stopAutoplay);
  carouselRoot.addEventListener('focusout', startAutoplay);
}
