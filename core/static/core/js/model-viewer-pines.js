/**
 * Model-viewer Pins/Hotspots Manager
 * Soporte para Fotos, Edición, Eliminación, Vinculación y Zoom de Imagen.
 */

window.toggle3DFullscreen = function(btn) {
    const container = btn.closest('.viewer-container');
    if (!document.fullscreenElement) {
        container.requestFullscreen().catch(err => {
            console.error(`Error al intentar modo pantalla completa: ${err.message}`);
        });
    } else {
        document.exitFullscreen();
    }
};

document.addEventListener('fullscreenchange', () => {
    const fullscreenEl = document.fullscreenElement;
    document.querySelectorAll('.viewer-container').forEach(c => {
        if (fullscreenEl && c.contains(fullscreenEl)) {
            c.classList.add('is-fullscreen');
        } else {
            c.classList.remove('is-fullscreen');
        }
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const viewers = document.querySelectorAll('model-viewer');

    const style = document.createElement('style');
    style.textContent = `
        .viewer-container { display: flex; transition: all 0.3s ease; background: #f8fafc; position: relative; overflow: hidden; }
        .viewer-container.is-fullscreen { background: #0f172a !important; width: 100vw; height: 100vh; }
        
        .sidebar-3d { 
            width: 0; opacity: 0; height: 100%; background: rgba(15, 23, 42, 0.95); 
            border-left: 1px solid #334155; transition: all 0.3s ease; overflow-y: auto;
            color: white; font-family: sans-serif; display: flex; flex-direction: column; z-index: 10;
        }
        .is-fullscreen .sidebar-3d { width: 320px; opacity: 1; }
        .sidebar-header { padding: 20px; border-bottom: 1px solid #334155; font-weight: bold; font-size: 1.1rem; }
        .sidebar-list { list-style: none; padding: 10px; margin: 0; }
        
        .sidebar-item { 
            padding: 12px; margin-bottom: 8px; border-radius: 8px; background: #1e293b; 
            cursor: pointer; transition: all 0.2s; border: 1px solid transparent; display: flex; align-items: center;
            position: relative;
        }
        .sidebar-item:hover { background: #334155; border-color: #475569; }
        .sidebar-item-img { width: 45px; height: 45px; border-radius: 6px; margin-right: 12px; object-fit: cover; background: #0f172a; }
        
        .sidebar-step-badge {
            position: absolute; top: -5px; left: -5px; background: #3b82f6; color: white;
            width: 20px; height: 20px; border-radius: 50%; font-size: 10px; font-weight: bold;
            display: flex; align-items: center; justify-content: center; border: 2px solid #1e293b;
        }

        .sidebar-actions { display: flex; gap: 5px; margin-top: 5px; opacity: 0; transition: opacity 0.2s; }
        .sidebar-item:hover .sidebar-actions { opacity: 1; }
        .sidebar-btn { 
            padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; border: none; font-weight: 600;
        }
        .btn-edit-pin { background: #3b82f6; color: white; }
        .btn-delete-pin { background: #ef4444; color: white; }

        .hotspot-context-menu {
            display: none; position: absolute; z-index: 20000; background: white; 
            border: 1px solid #cbd5e1; border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            padding: 6px 0; min-width: 180px; font-family: sans-serif; color: #1e293b;
        }

        .pin-info-card {
            display: none; position: absolute; z-index: 15000; background: white; 
            border-radius: 12px; box-shadow: 0 15px 35px rgba(0,0,0,0.3);
            width: 220px; padding: 0; overflow: hidden; font-family: sans-serif;
            pointer-events: auto; transform: translate(-50%, -100%); margin-top: -15px;
            animation: pinCardOpen 0.25s ease-out;
        }
        @keyframes pinCardOpen {
            from { opacity: 0; transform: translate(-50%, -90%) scale(0.9); }
            to { opacity: 1; transform: translate(-50%, -100%) scale(1); }
        }
        .pin-info-card img { width: 100%; height: 130px; object-fit: cover; background: #f1f5f9; display: block; cursor: zoom-in; }
        .pin-info-card .card-body { padding: 15px; }
        .pin-info-card .card-title { font-weight: bold; font-size: 14px; margin: 0 0 10px 0; color: #1e293b; }
        .pin-info-card .btn-next-step { 
            width: 100%; padding: 8px; background: #10b981; color: white; border: none; 
            border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 12px;
            display: flex; align-items: center; justify-content: center; gap: 5px;
        }
        .pin-info-card .btn-next-step:hover { background: #059669; }

        .hotspot-marker {
            width: 24px; height: 24px; border-radius: 50%; border: 2.5px solid white;
            background: rgba(239, 68, 68, 0.95); cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            transition: transform 0.2s;
        }
        .hotspot-marker:hover { transform: scale(1.2); }
        
        .hotspot-modal {
            display: none; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
            background: white; padding: 25px; border-radius: 12px; z-index: 20002;
            width: 320px; box-shadow: 0 25px 60px rgba(0,0,0,0.6); font-family: sans-serif; color: #1e293b;
        }
        .hotspot-modal-overlay {
            display: none; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.7); z-index: 20001; backdrop-filter: blur(4px);
        }

        .img-zoom-overlay {
            display: none; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.9); z-index: 30000; cursor: zoom-out;
            align-items: center; justify-content: center; backdrop-filter: blur(5px);
        }
        .img-zoom-overlay img { max-width: 90%; max-height: 90%; border: 4px solid white; border-radius: 10px; box-shadow: 0 20px 50px rgba(0,0,0,0.8); }
        
        .hotspot-modal h3 { margin: 0 0 15px 0; color: #1e293b; font-size: 1.1rem; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px; }
        .hotspot-modal label { display: block; font-size: 11px; font-weight: bold; margin-bottom: 4px; color: #64748b; text-transform: uppercase; }
        .hotspot-modal input[type="text"], .hotspot-modal select { width: 100%; padding: 10px; margin-bottom: 15px; border: 1px solid #e2e8f0; border-radius: 6px; box-sizing: border-box; }
        .hotspot-modal .btn-group { display: flex; gap: 10px; margin-top: 15px; }
        .hotspot-modal button { flex: 1; padding: 12px; border-radius: 6px; border: none; cursor: pointer; font-weight: bold; font-size: 13px; }
    `;
    document.head.appendChild(style);

    viewers.forEach(viewer => {
        const container = viewer.closest('.viewer-container');
        const modelType = viewer.dataset.modelType;
        const objectId = viewer.dataset.objectId;
        if (!modelType || !objectId) return;

        // Cleanup
        container.querySelectorAll('.sidebar-3d, .pin-info-card, .hotspot-context-menu, .hotspot-modal-overlay, .hotspot-modal, .img-zoom-overlay').forEach(el => el.remove());

        const sidebar = document.createElement('div');
        sidebar.className = 'sidebar-3d';
        sidebar.innerHTML = `<div class="sidebar-header">📍 Central de Pines</div><ul class="sidebar-list"></ul>`;
        container.appendChild(sidebar);

        const infoCard = document.createElement('div');
        infoCard.className = 'pin-info-card';
        infoCard.innerHTML = `<img><div class="card-body"><p class="card-title"></p><button class="btn-next-step">Siguiente Paso ➡️</button></div>`;
        container.appendChild(infoCard);

        const zoomOverlay = document.createElement('div');
        zoomOverlay.className = 'img-zoom-overlay';
        zoomOverlay.innerHTML = `<img>`;
        zoomOverlay.onclick = (e) => { e.stopPropagation(); zoomOverlay.style.display = 'none'; };
        container.appendChild(zoomOverlay);

        const contextMenu = document.createElement('div');
        contextMenu.className = 'hotspot-context-menu';
        container.appendChild(contextMenu);

        // Zoom image event
        infoCard.querySelector('img').onclick = (e) => {
            e.stopPropagation();
            zoomOverlay.querySelector('img').src = e.target.src;
            zoomOverlay.style.display = 'flex';
        };

        // Blocking propagation globally
        viewer.addEventListener('click', (e) => {
            e.stopPropagation();
            infoCard.style.display = 'none';
        });
        viewer.addEventListener('mousedown', (e) => e.stopPropagation());

        // Modal Elements
        const overlay = document.createElement('div');
        overlay.className = 'hotspot-modal-overlay';
        overlay.onclick = (e) => { e.stopPropagation(); closePinModal(container); };
        container.appendChild(overlay);

        const modal = document.createElement('div');
        modal.className = 'hotspot-modal';
        modal.innerHTML = `
            <h3 class="modal-title">Detalle del Punto</h3>
            <label>Nombre / Nota:</label>
            <input type="text" class="pin-note-input" placeholder="Nombre descriptivo...">
            
            <label>Siguiente Paso (Vincular):</label>
            <select class="pin-next-select">
                <option value="">-- Ninguno (Fin) --</option>
            </select>

            <label>Adjuntar Foto:</label>
            <input type="file" class="pin-photo-input" accept="image/*" style="margin-bottom: 10px;">
            <div class="pin-current-img-msg" style="margin-bottom:10px; display:none; font-size:10px; color:#3b82f6; font-weight:bold;">✅ Foto actualmente vinculada.</div>
            
            <div class="btn-group">
                <button class="btn-cancel-pin" style="background:#e2e8f0; color:#475569;">Descartar</button>
                <button class="btn-save-pin" style="background:#3b82f6; color:white;">Guardar Cambios</button>
            </div>
        `;
        container.appendChild(modal);

        modal.onclick = (e) => e.stopPropagation();
        modal.querySelector('.btn-cancel-pin').onclick = (e) => { e.stopPropagation(); closePinModal(container); };

        const updateRendering = () => {
            const hotspots = viewer.dataset.hotspots ? JSON.parse(viewer.dataset.hotspots) : [];
            renderHotspotsAndSidebar(viewer, hotspots, sidebar, container, contextMenu, infoCard);
        };
        updateRendering();

        viewer.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            e.stopPropagation(); 
            infoCard.style.display = 'none';
            const rect = container.getBoundingClientRect();
            contextMenu.style.left = `${e.clientX - rect.left}px`;
            contextMenu.style.top = `${e.clientY - rect.top}px`;
            contextMenu.style.display = 'block';
            contextMenu.innerHTML = '';

            const hit = viewer.positionAndNormalFromPoint(e.clientX, e.clientY);
            if (hit) {
                const addBtn = createMenuItem('📍 Agregar Nuevo Pin', '#3b82f6');
                addBtn.onclick = (ev) => { 
                    ev.stopPropagation(); 
                    contextMenu.style.display = 'none';
                    openPinModal(container, viewer, modelType, objectId, hit); 
                };
                contextMenu.appendChild(addBtn);
            }
        });

        document.addEventListener('click', () => {
            contextMenu.style.display = 'none';
        });
    });

    function createMenuItem(text, color) {
        const btn = document.createElement('div');
        btn.textContent = text;
        btn.style.cssText = `padding: 12px 16px; cursor: pointer; font-size: 13px; color: ${color}; font-weight: 600; border-bottom: 1px solid #f1f5f9;`;
        btn.onmouseover = () => btn.style.background = '#f1f5f9';
        btn.onmouseout = () => btn.style.background = 'transparent';
        return btn;
    }

    function renderHotspotsAndSidebar(viewer, hotspots, sidebar, container, contextMenu, infoCard) {
        viewer.querySelectorAll('.hotspot-marker').forEach(m => m.remove());
        const list = sidebar.querySelector('.sidebar-list');
        list.innerHTML = '';

        hotspots.forEach((pin, index) => {
            const marker = document.createElement('button');
            marker.className = 'hotspot-marker';
            marker.slot = `hotspot-${pin.id}`;
            marker.dataset.position = pin.position;
            marker.dataset.normal = pin.normal;
            
            // Clic Izquierdo -> Mostrar Card sobre el Pin
            marker.onclick = (e) => { 
                e.stopPropagation(); 
                e.preventDefault();
                contextMenu.style.display = 'none';
                showInfoCard(container, infoCard, viewer, e, pin, hotspots);
            };

            marker.oncontextmenu = (e) => {
                e.preventDefault();
                e.stopPropagation();
                infoCard.style.display = 'none';
                
                const rect = container.getBoundingClientRect();
                contextMenu.style.left = `${e.clientX - rect.left}px`;
                contextMenu.style.top = `${e.clientY - rect.top}px`;
                contextMenu.style.display = 'block';
                contextMenu.innerHTML = '';

                const editBtn = createMenuItem('✏️ Editar Detalle', '#3b82f6');
                editBtn.onclick = (ev) => {
                    ev.stopPropagation();
                    contextMenu.style.display = 'none';
                    openPinModal(container, viewer, viewer.dataset.modelType, viewer.dataset.objectId, null, pin);
                };
                
                const deleteBtn = createMenuItem('🗑️ Eliminar Pin', '#ef4444');
                deleteBtn.onclick = (ev) => {
                    ev.stopPropagation();
                    contextMenu.style.display = 'none';
                    if (confirm('¿Seguro que deseas eliminar este pin?')) {
                        let h = JSON.parse(viewer.dataset.hotspots);
                        h = h.filter(p => p.id !== pin.id);
                        viewer.dataset.hotspots = JSON.stringify(h);
                        renderHotspotsAndSidebar(viewer, h, sidebar, container, contextMenu, infoCard);
                        saveHotspots(viewer.dataset.modelType, viewer.dataset.objectId, h);
                    }
                };

                contextMenu.appendChild(editBtn);
                contextMenu.appendChild(deleteBtn);
            };

            viewer.appendChild(marker);

            const item = document.createElement('li');
            item.className = 'sidebar-item';
            const imgHtml = pin.image_url ? `<img src="${pin.image_url}" class="sidebar-item-img">` : '<div class="sidebar-item-img" style="display:flex; align-items:center; justify-content:center; color:#475569; font-size:18px; border: 1px dashed #475569;">📷</div>';
            
            item.innerHTML = `
                <div class="sidebar-step-badge">${index + 1}</div>
                ${imgHtml}
                <div style="flex: 1;">
                    <div style="font-weight: 600; font-size: 13px; color: #e2e8f0;">${pin.note}</div>
                    <div class="sidebar-actions">
                        <button class="sidebar-btn btn-edit-pin">✏️ Editar</button>
                        <button class="sidebar-btn btn-delete-pin">🗑️ Borrar</button>
                    </div>
                </div>
            `;
            
            item.querySelector('.btn-edit-pin').onclick = (e) => {
                e.stopPropagation();
                openPinModal(container, viewer, viewer.dataset.modelType, viewer.dataset.objectId, null, pin);
            };
            item.querySelector('.btn-delete-pin').onclick = (e) => {
                e.stopPropagation();
                if (confirm('¿Eliminar este pin?')) {
                    let h = JSON.parse(viewer.dataset.hotspots);
                    h = h.filter(p => p.id !== pin.id);
                    viewer.dataset.hotspots = JSON.stringify(h);
                    renderHotspotsAndSidebar(viewer, h, sidebar, container, contextMenu, infoCard);
                    saveHotspots(viewer.dataset.modelType, viewer.dataset.objectId, h);
                }
            };

            item.onclick = (e) => {
                e.stopPropagation();
                viewer.cameraTarget = pin.position;
            };
            list.appendChild(item);
        });
    }

    function showInfoCard(container, infoCard, viewer, event, pin, allHotspots) {
        viewer.cameraTarget = pin.position;
        
        const rect = container.getBoundingClientRect();
        const x = event ? event.clientX : rect.left + rect.width/2;
        const y = event ? event.clientY : rect.top + rect.height/2;

        infoCard.style.left = `${x - rect.left}px`;
        infoCard.style.top = `${y - rect.top}px`;
        
        const img = infoCard.querySelector('img');
        if (pin.image_url) {
            img.src = pin.image_url;
            img.style.display = 'block';
        } else {
            img.style.display = 'none';
        }
        
        infoCard.querySelector('.card-title').textContent = pin.note;
        
        const nextBtn = infoCard.querySelector('.btn-next-step');
        if (pin.next_pin_id) {
            nextBtn.style.display = 'flex';
            nextBtn.onclick = (e) => {
                e.stopPropagation();
                const nextPin = allHotspots.find(h => h.id === pin.next_pin_id);
                if (nextPin) {
                    infoCard.style.display = 'none';
                    viewer.cameraTarget = nextPin.position;
                    // Proyectar el punto 3D para posicionar la card si el marker ya está renderizado
                    // Pero como el marker es asíncrono en su posición, usamos un timeout pequeño.
                    setTimeout(() => {
                        const nextMarker = viewer.querySelector(`button[slot="hotspot-${nextPin.id}"]`);
                        if (nextMarker) {
                            const markerRect = nextMarker.getBoundingClientRect();
                            showInfoCard(container, infoCard, viewer, { clientX: markerRect.left + 12, clientY: markerRect.top + 12 }, nextPin, allHotspots);
                        } else {
                            showInfoCard(container, infoCard, viewer, null, nextPin, allHotspots);
                        }
                    }, 500);
                }
            };
        } else {
            nextBtn.style.display = 'none';
        }

        infoCard.style.display = 'block';
    }

    function openPinModal(container, viewer, modelType, objectId, hit, existingPin = null) {
        const modal = container.querySelector('.hotspot-modal');
        const overlay = container.querySelector('.hotspot-modal-overlay');
        const saveBtn = modal.querySelector('.btn-save-pin');
        const nextSelect = modal.querySelector('.pin-next-select');
        
        const hotspots = JSON.parse(viewer.dataset.hotspots || '[]');

        nextSelect.innerHTML = '<option value="">-- Ninguno (Fin) --</option>';
        hotspots.forEach(h => {
            if (existingPin && h.id === existingPin.id) return;
            const opt = document.createElement('option');
            opt.value = h.id;
            opt.textContent = h.note;
            if (existingPin && existingPin.next_pin_id === h.id) opt.selected = true;
            nextSelect.appendChild(opt);
        });

        modal.querySelector('.modal-title').textContent = existingPin ? '✏️ Actualizar Pin' : '📍 Nuevo Pin de Detalle';
        modal.querySelector('.pin-note-input').value = existingPin ? existingPin.note : '';
        modal.querySelector('.pin-photo-input').value = '';
        modal.querySelector('.pin-current-img-msg').style.display = (existingPin && existingPin.image_url) ? 'block' : 'none';

        modal.style.display = 'block';
        overlay.style.display = 'block';

        saveBtn.onclick = async (e) => {
            e.stopPropagation();
            const noteInput = modal.querySelector('.pin-note-input');
            const note = noteInput.value.trim() || "Detalle sin nombre";
            const photoFile = modal.querySelector('.pin-photo-input').files[0];
            const nextPinId = nextSelect.value;
            let imageUrl = existingPin ? existingPin.image_url : null;

            if (photoFile) {
                saveBtn.innerText = '⚡ Subiendo archivo...';
                saveBtn.disabled = true;
                imageUrl = await uploadPhoto(photoFile);
                saveBtn.innerText = 'Guardar Cambios';
                saveBtn.disabled = false;
            }

            if (existingPin) {
                const idx = hotspots.findIndex(p => p.id === existingPin.id);
                if (idx !== -1) {
                    hotspots[idx].note = note;
                    hotspots[idx].image_url = imageUrl;
                    hotspots[idx].next_pin_id = nextPinId;
                }
            } else {
                hotspots.push({
                    id: 'pin-' + Date.now(),
                    position: hit.position.toString(),
                    normal: hit.normal.toString(),
                    note: note,
                    image_url: imageUrl,
                    next_pin_id: nextPinId
                });
            }

            viewer.dataset.hotspots = JSON.stringify(hotspots);
            const contextMenu = container.querySelector('.hotspot-context-menu');
            const infoCard = container.querySelector('.pin-info-card');
            renderHotspotsAndSidebar(viewer, hotspots, sidebar, container, contextMenu, infoCard);
            saveHotspots(modelType, objectId, hotspots);
            closePinModal(container);
        };
    }

    function closePinModal(container) {
        container.querySelector('.hotspot-modal').style.display = 'none';
        container.querySelector('.hotspot-modal-overlay').style.display = 'none';
    }

    async function uploadPhoto(file) {
        const fd = new FormData();
        fd.append('image', file);
        try {
            const resp = await fetch('/activos/api/subir-foto-3d/', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
                body: fd
            });
            const data = await resp.json();
            return data.url;
        } catch (err) { return null; }
    }

    async function saveHotspots(type, id, data) {
        try {
            await fetch('/activos/api/guardar-punto-3d/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify({ model_type: type, object_id: id, hotspots: data })
            });
        } catch (err) { }
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1)); break;
                }
            }
        }
        return cookieValue;
    }
});
