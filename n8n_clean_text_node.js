// Limpiar el texto extraído
const rawText = $input.item.json.text || '';

// Eliminar espacios en blanco excesivos
const cleanedText = rawText
    .replace(/\s+/g, ' ')  // Múltiples espacios a uno solo
    .replace(/\n\s*\n/g, '\n')  // Múltiples saltos de línea a uno
    .trim();

// Forzar HTTP en el callback URL (temporal hasta que SSL esté configurado)
let callbackUrl = $('Webhook').item.json.body.callback_url;
if (callbackUrl.startsWith('https://')) {
    callbackUrl = callbackUrl.replace('https://', 'http://');
}

return {
    texto: cleanedText,
    documento_id: $('Webhook').item.json.body.documento_id,
    callback_url: callbackUrl
};
