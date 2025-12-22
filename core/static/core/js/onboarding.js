document.addEventListener('DOMContentLoaded', function () {
    // Solo ejecutar en el dashboard principal o si somos redirigidos
    if (window.location.pathname === '/admin/' || window.location.pathname === '/admin') {
        initOnboarding();
    }
});

async function initOnboarding() {
    // Cargar Intro.js dinámicamente si no está presente
    if (typeof introJs === 'undefined') {
        await Promise.all([
            loadScript('https://cdn.jsdelivr.net/npm/intro.js@7.2.0/intro.min.js'),
            loadStyle('https://cdn.jsdelivr.net/npm/intro.js@7.2.0/introjs.min.css')
        ]);
    }

    // Verificar si el usuario ya vio el tutorial (usando una cookie temporal o consultando al server)
    // Para mayor robustez, consultamos un atributo inyectado o una pequeña api
    const response = await fetch('/finalizar-tutorial/', {
        method: 'GET',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    }).catch(() => null);

    // Nota: El GET fallará porque el view espera POST para finalizar, 
    // pero podemos usarlo para chequear si el usuario está logueado y tiene perfil.
    // Sin embargo, una forma más sencilla es inyectar una variable en el admin.

    // Por ahora, usemos localStorage como primer filtro
    if (localStorage.getItem('tutorial_visto')) return;

    startTour();
}

function startTour() {
    introJs().setOptions({
        nextLabel: 'Siguiente',
        prevLabel: 'Anterior',
        doneLabel: 'Finalizar',
        steps: [
            {
                title: '¡Bienvenido a Energía!',
                intro: 'Este es el panel de administración centralizado para la gestión de activos y energía.'
            },
            {
                element: document.querySelector('#nav-sidebar'),
                intro: 'Aquí encontrarás todos los módulos del sistema: Activos, Mantenimiento, Documentos y Comunicaciones.',
                position: 'right'
            },
            {
                element: document.querySelector('.content-header'),
                intro: 'Este es tu resumen diario. Puedes ver el estado de los equipos y las tareas pendientes.',
                position: 'bottom'
            },
            {
                element: document.querySelector('.user-panel'),
                intro: 'Desde aquí puedes gestionar tu perfil y notificaciones.',
                position: 'left'
            }
        ]
    }).oncomplete(function () {
        marcarTutorialComoVisto();
    }).onexit(function () {
        // Podríamos preguntar si quiere volver a verlo
    }).start();
}

function marcarTutorialComoVisto() {
    localStorage.setItem('tutorial_visto', 'true');
    fetch('/finalizar-tutorial/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        }
    });
}

function loadScript(url) {
    return new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = url;
        script.onload = resolve;
        document.head.appendChild(script);
    });
}

function loadStyle(url) {
    return new Promise((resolve) => {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = url;
        link.onload = resolve;
        document.head.appendChild(link);
    });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
