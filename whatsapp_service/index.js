const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');
const bodyParser = require('body-parser');

const app = express();
const port = 3005;

app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

console.log('Iniciando cliente de WhatsApp...');

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

client.on('qr', (qr) => {
    console.log('\n=============================================================');
    console.log('ESCANEA ESTE CÓDIGO QR CON TU WHATSAPP (Dispositivos Vinculados)');
    console.log('=============================================================\n');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('\n✅ ¡Cliente de WhatsApp conectado y listo!');
});

client.on('authenticated', () => {
    console.log('Autenticado correctamente.');
});

client.on('auth_failure', msg => {
    console.error('Error de autenticación:', msg);
});

// Endpoint para enviar mensajes
app.post('/send-message', async (req, res) => {
    const { number, message } = req.body;

    if (!number || !message) {
        return res.status(400).json({ error: 'Faltan parámetros number o message' });
    }

    // Formatear número (quitar caracteres no numéricos)
    const cleanNumber = number.replace(/\D/g, '');
    const chatId = cleanNumber + "@c.us";

    try {
        const response = await client.sendMessage(chatId, message);
        console.log(`✅ Mensaje enviado a ${cleanNumber}`);
        res.json({ status: 'success', id: response.id._serialized });
    } catch (error) {
        console.error('❌ Error enviando mensaje:', error);
        res.status(500).json({ error: 'Error al enviar mensaje: ' + error.message });
    }
});

client.on('message', message => {
    console.log(`Mensaje recibido de ${message.from}: ${message.body}`);
    if (message.body.toLowerCase() === 'ping') {
        message.reply('🤖 Pong! El sistema Energy está conectado.');
    }
});

client.initialize();

app.listen(port, () => {
    console.log(`🚀 API de WhatsApp escuchando en http://localhost:${port}`);
});
