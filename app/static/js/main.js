'use strict';
document.querySelectorAll('[data-auto-submit]').forEach(el => el.addEventListener('change', () => el.form.requestSubmit()));
document.querySelectorAll('[data-confirm]').forEach(form => form.addEventListener('submit', event => {
  if (!window.confirm(form.dataset.confirm)) event.preventDefault();
}));
const menu = document.querySelector('[data-toggle-menu]');
if (menu) menu.addEventListener('click', () => {
  const open = menu.getAttribute('aria-expanded') !== 'true';
  menu.setAttribute('aria-expanded', String(open));
  document.getElementById('admin-nav').classList.toggle('open', open);
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && menu) {menu.setAttribute('aria-expanded','false');document.getElementById('admin-nav').classList.remove('open');}
});
document.querySelectorAll('[data-qty]').forEach(button => button.addEventListener('click', () => {
  const input = button.closest('.quantity-control').querySelector('input');
  const next = Number(input.value || 1) + Number(button.dataset.qty);
  input.value = Math.max(Number(input.min || 1), Math.min(Number(input.max || 999), next));
}));
const variants = document.querySelector('[data-variant-select]');
if (variants) variants.addEventListener('change', () => {
  const option = variants.selectedOptions[0];
  const gallery = document.querySelector('[data-product-gallery]');
  const mainImage = document.querySelector('[data-gallery-main]');
  if (!option.value) {
    if (gallery?.dataset.defaultImage && mainImage) mainImage.src = gallery.dataset.defaultImage;
    return;
  }
  document.querySelector('[data-product-price]').textContent = new Intl.NumberFormat('pt-BR', {style:'currency',currency:'BRL'}).format(Number(option.dataset.price)/100);
  document.querySelector('[data-stock-label]').textContent = `${option.dataset.stock} unidade(s) disponível(is)`;
  const quantity = document.getElementById('quantity');
  quantity.max = option.dataset.stock;
  if (Number(quantity.value) > Number(quantity.max)) quantity.value = quantity.max;
  if (option.dataset.image && mainImage) {
    mainImage.src = option.dataset.image;
    document.querySelectorAll('[data-gallery-image]').forEach(button => button.classList.toggle('selected', button.dataset.galleryImage === option.dataset.image));
  }
});
document.querySelectorAll('[data-gallery-image]').forEach(button => button.addEventListener('click', () => {
  const mainImage = document.querySelector('[data-gallery-main]');
  if (!mainImage) return;
  mainImage.src = button.dataset.galleryImage;
  document.querySelectorAll('[data-gallery-image]').forEach(item => item.classList.toggle('selected', item === button));
}));
const zoomArea = document.querySelector('[data-zoom-area]');
if (zoomArea) zoomArea.addEventListener('mousemove', event => {
  const bounds = zoomArea.getBoundingClientRect();
  zoomArea.style.setProperty('--zoom-x', `${(event.clientX - bounds.left) / bounds.width * 100}%`);
  zoomArea.style.setProperty('--zoom-y', `${(event.clientY - bounds.top) / bounds.height * 100}%`);
});
const addVariant = document.querySelector('[data-add-variant]');
if (addVariant) addVariant.addEventListener('click', () => {
  const list = document.getElementById('variant-list');
  if (list.children.length >= 50) {window.alert('Use no máximo 50 variações.');return;}
  list.appendChild(document.getElementById('variant-template').content.cloneNode(true));
  list.lastElementChild.querySelector('[name=variant_label]').focus();
});
document.addEventListener('click', event => {
  const button = event.target.closest('[data-remove-variant]');
  if (button) button.closest('.variant-row').remove();
});
const imageInput = document.querySelector('[data-image-input]');
let imageObjectURL;
if (imageInput) imageInput.addEventListener('change', () => {
  const file = imageInput.files[0];
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) {window.alert('Use uma imagem com até 8 MB.');imageInput.value='';return;}
  if (!['image/jpeg','image/png','image/webp'].includes(file.type)) {window.alert('Use JPG, PNG ou WebP.');imageInput.value='';return;}
  if (imageObjectURL) URL.revokeObjectURL(imageObjectURL);
  imageObjectURL = URL.createObjectURL(file);
  const img = new Image();img.src=imageObjectURL;img.alt='Prévia da imagem selecionada';
  document.querySelector('[data-image-preview]').replaceChildren(img);
});
const validImage = file => {
  if (file.size > 8 * 1024 * 1024) {window.alert('Cada imagem deve ter até 8 MB.');return false;}
  if (!['image/jpeg','image/png','image/webp'].includes(file.type)) {window.alert('Use imagens JPG, PNG ou WebP.');return false;}
  return true;
};
const galleryInput = document.querySelector('[data-gallery-input]');
if (galleryInput) galleryInput.addEventListener('change', () => {
  const files = [...galleryInput.files];
  if (files.length > 8 || files.some(file => !validImage(file))) {galleryInput.value='';return;}
  const preview = document.querySelector('[data-gallery-preview]');
  preview.replaceChildren(...files.map(file => {
    const img = new Image();img.src=URL.createObjectURL(file);img.alt=`Prévia de ${file.name}`;
    const item=document.createElement('div');item.className='admin-gallery-item';item.appendChild(img);return item;
  }));
});
document.addEventListener('change', event => {
  const input = event.target.closest('[data-variant-image-input]');
  if (!input || !input.files[0]) return;
  const file=input.files[0];
  if (!validImage(file)) {input.value='';return;}
  let img=input.closest('.variant-image-field').querySelector('img');
  if (!img) {img=new Image();input.closest('.variant-image-field').prepend(img);}
  img.src=URL.createObjectURL(file);img.alt='Prévia da imagem da variação';
});

