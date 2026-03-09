(function() {
    console.log('Model-viewer loader: Starting...');
    // Evitamos que el cargador se encuentre a sí mismo buscando el .min.js específico
    if (!document.querySelector('script[src*="model-viewer.min.js"]')) {
        const script = document.createElement('script');
        script.type = 'module';
        script.src = '/static/core/js/model-viewer.min.js';
        
        script.onload = () => console.log('Model-viewer loader: Library loaded successfully');
        script.onerror = () => console.error('Model-viewer loader: FAILED to load library');
        
        document.head.appendChild(script);
        console.log('Model-viewer loader: Module tag injected');
    } else {
        console.log('Model-viewer loader: Library already present');
    }
})();
