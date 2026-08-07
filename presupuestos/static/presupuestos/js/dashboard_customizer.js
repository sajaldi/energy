/**
 * DashboardCustomizer - Módulo principal para personalización del dashboard de requisiciones.
 * Permite seleccionar columnas visibles, ordenarlas, y guardar vistas personalizadas.
 *
 * Sub-módulos:
 *   - ColumnSelector: Panel dropdown de checkboxes para activar/desactivar columnas
 *   - TableManager: Manipulación DOM de columnas en ambas tablas (Resumen General y Mis Requisiciones)
 *   - SortManager: Ordenamiento en cliente con ciclo de 3 estados y comparadores por tipo
 *   - ViewManager: (implementado en tarea separada)
 *   - Persistence: Persistencia temporal en localStorage
 */
const DashboardCustomizer = (function () {
    'use strict';

    // ─── Constantes ───────────────────────────────────────────────────────────────

    /** Orden fijo de todas las columnas disponibles */
    const COLUMNS_ORDER = [
        'requisicion', 'fecha', 'asunto', 'prioridad',
        'estado', 'total', 'oc', 'tipo', 'solicitante',
        'aprobador', 'motivo', 'partida', 'proveedor', 'acciones'
    ];

    /** Columnas visibles por defecto al cargar sin vista personalizada */
    const DEFAULT_COLUMNS = [
        'requisicion', 'fecha', 'asunto', 'prioridad',
        'estado', 'total', 'oc', 'acciones'
    ];

    /** Columnas que permiten ordenamiento */
    const SORTABLE_COLUMNS = [
        'requisicion', 'fecha', 'asunto', 'prioridad', 'estado', 'total'
    ];

    /** Columnas que no se pueden desactivar */
    const NON_REMOVABLE = ['acciones'];

    /** Definiciones de cada columna: label para UI y tipo de ordenamiento */
    const COLUMN_DEFS = {
        requisicion: { label: 'N° Requisición', sortType: 'alphanumeric' },
        fecha:       { label: 'Fecha',          sortType: 'date' },
        asunto:      { label: 'Asunto',         sortType: 'alpha' },
        prioridad:   { label: 'Prioridad',      sortType: 'severity', order: ['Normal', 'Alta', 'Urgencia', 'Emergencia'] },
        estado:      { label: 'Estado',         sortType: 'alpha' },
        total:       { label: 'Total',          sortType: 'numeric' },
        oc:          { label: 'O/C',            sortType: null },
        tipo:        { label: 'Tipo',           sortType: 'alpha' },
        solicitante: { label: 'Solicitante',    sortType: 'alpha' },
        aprobador:   { label: 'Aprobador',      sortType: 'alpha' },
        motivo:      { label: 'Motivo',         sortType: 'alpha' },
        partida:     { label: 'Partida Presup.', sortType: 'alpha' },
        proveedor:   { label: 'Proveedor',      sortType: 'alpha' },
        acciones:    { label: 'Acciones',       sortType: null }
    };

    // ─── Estado interno ───────────────────────────────────────────────────────────

    /** Columnas actualmente visibles (IDs) */
    let activeColumns = [...DEFAULT_COLUMNS];

    // ─── TableManager ─────────────────────────────────────────────────────────────

    /**
     * TableManager manipula las columnas del DOM en ambas tablas del dashboard.
     * Trabaja con elementos que tienen atributos `data-column-id`.
     */
    const TableManager = {
        /**
         * Obtiene las dos tablas del dashboard.
         * @returns {HTMLTableElement[]}
         */
        getTables: function () {
            const generalTable = document.querySelector('#tab-general .table-modern');
            const personalTable = document.querySelector('#tab-personales .table-modern');
            const tables = [];
            if (generalTable) tables.push(generalTable);
            if (personalTable) tables.push(personalTable);
            return tables;
        },

        /**
         * Aplica la visibilidad de columnas a ambas tablas.
         * Muestra las columnas en activeColumns y oculta las demás.
         * @param {string[]} columns - Array de IDs de columnas a mostrar
         */
        applyColumns: function (columns) {
            const tables = this.getTables();
            tables.forEach(function (table) {
                TableManager._applyColumnsToTable(table, columns);
            });
        },

        /**
         * Aplica visibilidad de columnas a una tabla específica.
         * @param {HTMLTableElement} table
         * @param {string[]} columns - Columnas a mostrar
         */
        _applyColumnsToTable: function (table, columns) {
            // Procesar headers (th)
            var headerCells = table.querySelectorAll('thead th[data-column-id]');
            headerCells.forEach(function (th) {
                var colId = th.getAttribute('data-column-id');
                th.style.display = columns.indexOf(colId) !== -1 ? '' : 'none';
            });

            // Procesar celdas de datos (td)
            var rows = table.querySelectorAll('tbody tr');
            rows.forEach(function (row) {
                var cells = row.querySelectorAll('td[data-column-id]');
                cells.forEach(function (td) {
                    var colId = td.getAttribute('data-column-id');
                    td.style.display = columns.indexOf(colId) !== -1 ? '' : 'none';
                });
            });

            // Actualizar colspan de fila vacía si existe
            var emptyRow = table.querySelector('tbody tr td[colspan]');
            if (emptyRow) {
                emptyRow.setAttribute('colspan', columns.length);
            }
        },

        /**
         * Inserta una columna en la posición correcta según COLUMNS_ORDER.
         * @param {string} columnId - ID de la columna a activar
         */
        showColumn: function (columnId) {
            if (activeColumns.indexOf(columnId) !== -1) return; // Ya visible

            // Determinar posición de inserción basada en COLUMNS_ORDER
            var targetIndex = COLUMNS_ORDER.indexOf(columnId);
            var insertAt = activeColumns.length;
            for (var i = 0; i < activeColumns.length; i++) {
                if (COLUMNS_ORDER.indexOf(activeColumns[i]) > targetIndex) {
                    insertAt = i;
                    break;
                }
            }
            activeColumns.splice(insertAt, 0, columnId);
            this.applyColumns(activeColumns);
        },

        /**
         * Oculta una columna preservando datos de filas existentes.
         * @param {string} columnId - ID de la columna a desactivar
         * @returns {boolean} true si se ocultó, false si fue impedida
         */
        hideColumn: function (columnId) {
            // No permitir desactivar columnas no removibles
            if (NON_REMOVABLE.indexOf(columnId) !== -1) return false;

            // Verificar que no sea la última columna de datos
            var dataColumns = activeColumns.filter(function (col) {
                return NON_REMOVABLE.indexOf(col) === -1;
            });
            if (dataColumns.length <= 1) {
                // Impedir desactivación de la última columna de datos
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Acción no permitida',
                        text: 'Al menos una columna de datos debe permanecer activa además de Acciones.',
                        confirmButtonColor: '#6366f1'
                    });
                }
                return false;
            }

            var idx = activeColumns.indexOf(columnId);
            if (idx !== -1) {
                activeColumns.splice(idx, 1);
                this.applyColumns(activeColumns);
            }
            return true;
        },

        /**
         * Retorna las columnas activas actualmente.
         * @returns {string[]}
         */
        getActiveColumns: function () {
            return activeColumns.slice();
        },

        /**
         * Establece las columnas activas directamente (para carga de vistas).
         * @param {string[]} columns
         */
        setActiveColumns: function (columns) {
            activeColumns = columns.slice();
            this.applyColumns(activeColumns);
        }
    };

    // ─── ColumnSelector ───────────────────────────────────────────────────────────

    /**
     * ColumnSelector renderiza y controla el panel dropdown de selección de columnas.
     * Muestra 14 checkboxes (uno por columna disponible).
     * La casilla "Acciones" está marcada y deshabilitada.
     */
    const ColumnSelector = {
        /** Referencia al panel DOM */
        _panel: null,
        /** Referencia al botón que abre el panel */
        _button: null,
        /** Flag de si el panel está abierto */
        _isOpen: false,

        /**
         * Inicializa el selector, creando el botón y el panel.
         * @param {HTMLElement} container - Elemento donde insertar el botón
         */
        init: function (container) {
            if (!container) return;

            // Crear botón "Columnas"
            this._button = document.createElement('button');
            this._button.type = 'button';
            this._button.className = 'btn-custom btn-outline-custom btn-column-selector';
            this._button.innerHTML = '⚙️ Columnas';
            this._button.style.cssText = 'padding: 8px 16px; font-size: 0.85rem; position: relative;';
            this._button.addEventListener('click', this._toggle.bind(this));
            container.appendChild(this._button);

            // Crear panel dropdown
            this._panel = this._createPanel();
            this._button.style.position = 'relative';
            this._button.parentElement.style.position = 'relative';
            document.body.appendChild(this._panel);

            // Event listeners para cerrar
            document.addEventListener('click', this._handleOutsideClick.bind(this));
            document.addEventListener('keydown', this._handleEscape.bind(this));
        },

        /**
         * Crea el panel dropdown con los 14 checkboxes.
         * @returns {HTMLElement}
         */
        _createPanel: function () {
            var panel = document.createElement('div');
            panel.className = 'column-selector-panel';
            panel.style.cssText = [
                'display: none;',
                'position: fixed;',
                'z-index: 10000;',
                'background: white;',
                'border: 1px solid #e2e8f0;',
                'border-radius: 8px;',
                'box-shadow: 0 10px 40px rgba(0,0,0,0.15);',
                'padding: 12px 16px;',
                'min-width: 220px;',
                'max-height: 400px;',
                'overflow-y: auto;'
            ].join('');

            // Título del panel
            var title = document.createElement('div');
            title.style.cssText = 'font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #6a6d70; padding-bottom: 8px; border-bottom: 1px solid #f1f5f9; margin-bottom: 8px;';
            title.textContent = 'Columnas visibles';
            panel.appendChild(title);

            // Crear un checkbox por cada columna
            var self = this;
            COLUMNS_ORDER.forEach(function (colId) {
                var def = COLUMN_DEFS[colId];
                var wrapper = document.createElement('label');
                wrapper.style.cssText = 'display: flex; align-items: center; gap: 8px; padding: 6px 4px; cursor: pointer; font-size: 0.85rem; color: #1e293b; border-radius: 4px; transition: background 0.1s;';
                wrapper.addEventListener('mouseenter', function () { wrapper.style.background = '#f8fafc'; });
                wrapper.addEventListener('mouseleave', function () { wrapper.style.background = ''; });

                var checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.setAttribute('data-column-selector', colId);
                checkbox.checked = activeColumns.indexOf(colId) !== -1;
                checkbox.style.cssText = 'width: 16px; height: 16px; accent-color: #6366f1;';

                // Acciones está siempre marcada y deshabilitada
                if (NON_REMOVABLE.indexOf(colId) !== -1) {
                    checkbox.checked = true;
                    checkbox.disabled = true;
                    wrapper.style.opacity = '0.7';
                    wrapper.style.cursor = 'not-allowed';
                }

                checkbox.addEventListener('change', function () {
                    self._handleCheckboxChange(colId, checkbox.checked, checkbox);
                });

                var labelText = document.createElement('span');
                labelText.textContent = def.label;

                wrapper.appendChild(checkbox);
                wrapper.appendChild(labelText);
                panel.appendChild(wrapper);
            });

            return panel;
        },

        /**
         * Maneja cambio en un checkbox del selector.
         * @param {string} colId
         * @param {boolean} checked
         * @param {HTMLInputElement} checkbox
         */
        _handleCheckboxChange: function (colId, checked, checkbox) {
            if (checked) {
                TableManager.showColumn(colId);
            } else {
                var success = TableManager.hideColumn(colId);
                if (!success) {
                    // Revertir el checkbox si no se permitió
                    checkbox.checked = true;
                }
            }
            // Persistir en localStorage si el módulo Persistence existe
            if (DashboardCustomizer.Persistence && DashboardCustomizer.Persistence.saveColumns) {
                DashboardCustomizer.Persistence.saveColumns(activeColumns);
            }
            // Actualizar estado del botón Guardar Vista si ViewManager existe
            if (DashboardCustomizer.ViewManager && DashboardCustomizer.ViewManager._updateSaveButton) {
                DashboardCustomizer.ViewManager._updateSaveButton();
            }
        },

        /**
         * Toggle del panel.
         * @param {Event} e
         */
        _toggle: function (e) {
            e.stopPropagation();
            if (this._isOpen) {
                this.close();
            } else {
                this.open();
            }
        },

        /**
         * Abre el panel actualizando el estado de los checkboxes.
         */
        open: function () {
            // Sincronizar checkboxes con estado actual
            var checkboxes = this._panel.querySelectorAll('input[data-column-selector]');
            checkboxes.forEach(function (cb) {
                var colId = cb.getAttribute('data-column-selector');
                if (NON_REMOVABLE.indexOf(colId) === -1) {
                    cb.checked = activeColumns.indexOf(colId) !== -1;
                }
            });

            // Posicionar el panel fijo debajo del botón
            var rect = this._button.getBoundingClientRect();
            this._panel.style.top = (rect.bottom + 4) + 'px';
            this._panel.style.right = (window.innerWidth - rect.right) + 'px';

            this._panel.style.display = 'block';
            this._isOpen = true;
        },

        /**
         * Cierra el panel.
         */
        close: function () {
            this._panel.style.display = 'none';
            this._isOpen = false;
        },

        /**
         * Cierra el panel si se hace clic fuera de él.
         * @param {Event} e
         */
        _handleOutsideClick: function (e) {
            if (!this._isOpen) return;
            if (this._panel && !this._panel.contains(e.target) && !this._button.contains(e.target)) {
                this.close();
            }
        },

        /**
         * Cierra el panel al presionar Escape.
         * @param {KeyboardEvent} e
         */
        _handleEscape: function (e) {
            if (e.key === 'Escape' && this._isOpen) {
                this.close();
            }
        },

        /**
         * Actualiza los checkboxes para reflejar un nuevo estado de columnas.
         * Útil cuando se aplica una vista o se restablece.
         */
        syncCheckboxes: function () {
            if (!this._panel) return;
            var checkboxes = this._panel.querySelectorAll('input[data-column-selector]');
            checkboxes.forEach(function (cb) {
                var colId = cb.getAttribute('data-column-selector');
                if (NON_REMOVABLE.indexOf(colId) === -1) {
                    cb.checked = activeColumns.indexOf(colId) !== -1;
                }
            });
        }
    };

    // ─── SortManager ─────────────────────────────────────────────────────────────

    /**
     * SortManager maneja el ordenamiento en cliente de las filas del dashboard.
     *
     * Características:
     * - Ciclo de 3 estados al hacer clic en encabezado: asc → desc → reset (Fecha desc)
     * - Comparadores por tipo de dato: alphanumeric, date, alpha, severity, numeric
     * - Indicador visual (▲/▼) en el encabezado de la columna activa
     * - Excluye O/C y Acciones del ordenamiento
     * - Sub-orden por Fecha desc para valores duplicados (estabilidad)
     * - Estado de ordenamiento aislado por pestaña
     */
    const SortManager = {
        /**
         * Estado de sort por pestaña. Cada clave es un ID de pestaña.
         * Valor: { column: string|null, direction: 'asc'|'desc'|null }
         */
        _sortState: {},

        /** IDs de las pestañas */
        _tabIds: ['tab-general', 'tab-personales'],

        /**
         * Inicializa el SortManager: adjunta click handlers a encabezados ordenables.
         */
        init: function () {
            var self = this;

            // Inicializar estado por pestaña (default: Fecha desc)
            this._tabIds.forEach(function (tabId) {
                self._sortState[tabId] = { column: 'fecha', direction: 'desc' };
            });

            // Adjuntar handlers a cada tabla
            this._tabIds.forEach(function (tabId) {
                var tabEl = document.getElementById(tabId);
                if (!tabEl) return;

                var table = tabEl.querySelector('.table-modern');
                if (!table) return;

                var headers = table.querySelectorAll('thead th[data-column-id]');
                headers.forEach(function (th) {
                    var colId = th.getAttribute('data-column-id');

                    if (SORTABLE_COLUMNS.indexOf(colId) !== -1) {
                        // Columna ordenable: cursor pointer y click handler
                        th.style.cursor = 'pointer';
                        th.style.userSelect = 'none';
                        th.addEventListener('click', function () {
                            self._handleHeaderClick(tabId, colId, table);
                        });
                    } else {
                        // Columnas no ordenables (O/C, Acciones): sin cursor interactivo
                        th.style.cursor = 'default';
                    }
                });
            });

            // Aplicar orden inicial (Fecha desc) a ambas pestañas
            this._tabIds.forEach(function (tabId) {
                var tabEl = document.getElementById(tabId);
                if (!tabEl) return;
                var table = tabEl.querySelector('.table-modern');
                if (!table) return;
                self._applySort(tabId, table);
                self._updateIndicators(tabId, table);
            });
        },

        /**
         * Maneja clic en un encabezado de columna ordenable.
         * Ciclo: asc → desc → reset (Fecha desc)
         * @param {string} tabId - ID de la pestaña
         * @param {string} colId - ID de la columna clickeada
         * @param {HTMLTableElement} table - Tabla DOM
         */
        _handleHeaderClick: function (tabId, colId, table) {
            var state = this._sortState[tabId];

            if (state.column === colId) {
                // Misma columna: avanzar en el ciclo
                if (state.direction === 'asc') {
                    state.direction = 'desc';
                } else if (state.direction === 'desc') {
                    // Tercer clic: reset a Fecha desc
                    state.column = 'fecha';
                    state.direction = 'desc';
                }
            } else {
                // Columna diferente: empezar con asc
                state.column = colId;
                state.direction = 'asc';
            }

            this._applySort(tabId, table);
            this._updateIndicators(tabId, table);

            // Persistir estado si el módulo Persistence existe
            if (DashboardCustomizer.Persistence && DashboardCustomizer.Persistence.saveSortState) {
                DashboardCustomizer.Persistence.saveSortState(state.column, state.direction);
            }

            // Actualizar estado del botón Guardar Vista si ViewManager existe
            if (DashboardCustomizer.ViewManager && DashboardCustomizer.ViewManager._updateSaveButton) {
                DashboardCustomizer.ViewManager._updateSaveButton();
            }
        },

        /**
         * Aplica el ordenamiento actual al DOM de la tabla.
         * @param {string} tabId - ID de la pestaña
         * @param {HTMLTableElement} table - Tabla DOM
         */
        _applySort: function (tabId, table) {
            var state = this._sortState[tabId];
            if (!state || !state.column || !state.direction) return;

            var tbody = table.querySelector('tbody');
            if (!tbody) return;

            var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
            if (rows.length === 0) return;

            // Filtrar filas vacías (con colspan)
            var dataRows = rows.filter(function (row) {
                return !row.querySelector('td[colspan]');
            });
            var emptyRows = rows.filter(function (row) {
                return row.querySelector('td[colspan]');
            });

            if (dataRows.length <= 1) return;

            var self = this;
            var sortCol = state.column;
            var sortDir = state.direction;
            var comparator = this._getComparator(sortCol);

            // Ordenar filas
            dataRows.sort(function (rowA, rowB) {
                var valA = self._getCellValue(rowA, sortCol);
                var valB = self._getCellValue(rowB, sortCol);

                var result = comparator(valA, valB);

                if (sortDir === 'desc') {
                    result = -result;
                }

                // Sub-orden por Fecha descendente para valores iguales (estabilidad)
                if (result === 0 && sortCol !== 'fecha') {
                    var dateA = self._getCellValue(rowA, 'fecha');
                    var dateB = self._getCellValue(rowB, 'fecha');
                    var dateComparator = self._getComparator('fecha');
                    // Sub-orden siempre descendente (más reciente primero)
                    result = -dateComparator(dateA, dateB);
                }

                return result;
            });

            // Re-insertar filas en el orden nuevo
            dataRows.forEach(function (row) {
                tbody.appendChild(row);
            });
            // Mantener filas vacías al final
            emptyRows.forEach(function (row) {
                tbody.appendChild(row);
            });
        },

        /**
         * Obtiene el valor de texto de una celda para la columna dada.
         * @param {HTMLTableRowElement} row
         * @param {string} colId
         * @returns {string}
         */
        _getCellValue: function (row, colId) {
            var cell = row.querySelector('td[data-column-id="' + colId + '"]');
            if (!cell) return '';
            // Usar data-sort-value si existe, sino textContent
            var sortVal = cell.getAttribute('data-sort-value');
            return sortVal !== null ? sortVal : (cell.textContent || '').trim();
        },

        /**
         * Retorna la función comparadora para el tipo de dato de la columna.
         * @param {string} colId
         * @returns {Function}
         */
        _getComparator: function (colId) {
            var def = COLUMN_DEFS[colId];
            if (!def || !def.sortType) return this._comparators.alpha;
            return this._comparators[def.sortType] || this._comparators.alpha;
        },

        /**
         * Conjunto de funciones comparadoras por tipo de dato.
         */
        _comparators: {
            /**
             * Comparación alfanumérica estándar (string con números embebidos).
             * Usa localeCompare con opción numérica para ordenar "REQ-2" antes de "REQ-10".
             */
            alphanumeric: function (a, b) {
                var strA = (a || '').toLowerCase();
                var strB = (b || '').toLowerCase();
                return strA.localeCompare(strB, undefined, { numeric: true, sensitivity: 'base' });
            },

            /**
             * Comparación cronológica de fechas.
             * Soporta formatos: "DD/MM/YYYY", "YYYY-MM-DD", "DD-MM-YYYY"
             */
            date: function (a, b) {
                var dateA = SortManager._parseDate(a);
                var dateB = SortManager._parseDate(b);
                return dateA - dateB;
            },

            /**
             * Comparación alfabética case-insensitive con locale español.
             */
            alpha: function (a, b) {
                var strA = (a || '').toLowerCase();
                var strB = (b || '').toLowerCase();
                return strA.localeCompare(strB, 'es', { sensitivity: 'base' });
            },

            /**
             * Comparación por severidad: Normal < Alta < Urgencia < Emergencia
             */
            severity: function (a, b) {
                var order = ['Normal', 'Alta', 'Urgencia', 'Emergencia'];
                var idxA = order.indexOf(a);
                var idxB = order.indexOf(b);
                // Valores no reconocidos van al final
                if (idxA === -1) idxA = order.length;
                if (idxB === -1) idxB = order.length;
                return idxA - idxB;
            },

            /**
             * Comparación numérica. Maneja formato de moneda "L.1,234,500.00"
             */
            numeric: function (a, b) {
                var numA = SortManager._parseNumber(a);
                var numB = SortManager._parseNumber(b);
                return numA - numB;
            }
        },

        /**
         * Parsea una fecha string a timestamp numérico.
         * @param {string} str - Formato esperado: "DD/MM/YYYY" o "YYYY-MM-DD" o "DD-MM-YYYY"
         * @returns {number} Timestamp en ms, o 0 si no se pudo parsear
         */
        _parseDate: function (str) {
            if (!str || typeof str !== 'string') return 0;
            str = str.trim();

            // Intentar formato DD/MM/YYYY o DD-MM-YYYY
            var parts = str.split(/[\/\-]/);
            if (parts.length === 3) {
                var first = parseInt(parts[0], 10);
                var second = parseInt(parts[1], 10);
                var third = parseInt(parts[2], 10);

                // Si el primer grupo tiene 4 dígitos: YYYY-MM-DD
                if (parts[0].length === 4) {
                    return new Date(first, second - 1, third).getTime() || 0;
                }
                // Si no: DD/MM/YYYY o DD-MM-YYYY
                return new Date(third, second - 1, first).getTime() || 0;
            }

            // Fallback: intentar Date.parse
            var parsed = Date.parse(str);
            return isNaN(parsed) ? 0 : parsed;
        },

        /**
         * Parsea un string numérico, eliminando símbolos de moneda y separadores.
         * Maneja formato "L.1,234,500.00" (Lempiras hondureños)
         * @param {string} str
         * @returns {number}
         */
        _parseNumber: function (str) {
            if (!str || typeof str !== 'string') return 0;
            // Remover prefijo monetario (L. o L), espacios, y símbolo $
            var cleaned = str.replace(/^[L\$]\s*\.?\s*/, '');
            // Remover comas (separador de miles)
            cleaned = cleaned.replace(/,/g, '');
            // Parsear como float
            var num = parseFloat(cleaned);
            return isNaN(num) ? 0 : num;
        },

        /**
         * Actualiza los indicadores visuales (▲/▼) en los encabezados de la tabla.
         * @param {string} tabId - ID de la pestaña
         * @param {HTMLTableElement} table - Tabla DOM
         */
        _updateIndicators: function (tabId, table) {
            var state = this._sortState[tabId];

            // Limpiar todos los indicadores en esta tabla
            var headers = table.querySelectorAll('thead th[data-column-id]');
            headers.forEach(function (th) {
                var indicator = th.querySelector('.sort-indicator');
                if (indicator) {
                    indicator.remove();
                }
            });

            // Agregar indicador a la columna activa
            if (state && state.column && state.direction) {
                var activeHeader = table.querySelector('thead th[data-column-id="' + state.column + '"]');
                if (activeHeader) {
                    var span = document.createElement('span');
                    span.className = 'sort-indicator';
                    span.style.cssText = 'margin-left: 4px; font-size: 0.7rem; opacity: 0.8;';
                    span.textContent = state.direction === 'asc' ? '▲' : '▼';
                    activeHeader.appendChild(span);
                }
            }
        },

        /**
         * Obtiene el estado de sort de una pestaña.
         * @param {string} tabId
         * @returns {{ column: string|null, direction: string|null }}
         */
        getState: function (tabId) {
            return this._sortState[tabId] || { column: null, direction: null };
        },

        /**
         * Establece el estado de sort para una pestaña específica (para carga de vistas).
         * @param {string} tabId
         * @param {string|null} column
         * @param {string|null} direction - 'asc' o 'desc'
         */
        setState: function (tabId, column, direction) {
            this._sortState[tabId] = { column: column, direction: direction };
            var tabEl = document.getElementById(tabId);
            if (!tabEl) return;
            var table = tabEl.querySelector('.table-modern');
            if (!table) return;
            this._applySort(tabId, table);
            this._updateIndicators(tabId, table);
        },

        /**
         * Aplica un criterio de sort a ambas pestañas (para carga de vista personalizada).
         * @param {string|null} column
         * @param {string|null} direction
         */
        applyToBoth: function (column, direction) {
            var self = this;
            this._tabIds.forEach(function (tabId) {
                self.setState(tabId, column, direction);
            });
        },

        /**
         * Restablece el ordenamiento a default (Fecha desc) en ambas pestañas.
         */
        reset: function () {
            this.applyToBoth('fecha', 'desc');
        },

        /**
         * Obtiene el ID de la pestaña activa actualmente.
         * @returns {string}
         */
        _getActiveTabId: function () {
            for (var i = 0; i < this._tabIds.length; i++) {
                var tabEl = document.getElementById(this._tabIds[i]);
                if (tabEl && tabEl.style.display !== 'none' && !tabEl.classList.contains('hidden')) {
                    return this._tabIds[i];
                }
            }
            return this._tabIds[0];
        }
    };

    // ─── API Pública ──────────────────────────────────────────────────────────────

    return {
        // Constantes (expuestas para property tests y sub-módulos)
        COLUMNS_ORDER: COLUMNS_ORDER,
        DEFAULT_COLUMNS: DEFAULT_COLUMNS,
        SORTABLE_COLUMNS: SORTABLE_COLUMNS,
        NON_REMOVABLE: NON_REMOVABLE,
        COLUMN_DEFS: COLUMN_DEFS,

        // Sub-módulos
        TableManager: TableManager,
        ColumnSelector: ColumnSelector,
        SortManager: SortManager,

        // ─── ViewManager ──────────────────────────────────────────────────────────────

        /**
         * ViewManager gestiona las vistas personalizadas del dashboard: CRUD vía API,
         * barra de UI con selector/dropdown y botones, y sincronización con ColumnSelector/SortManager.
         */
        ViewManager: {
            /** Referencia al elemento contenedor de la barra de vistas */
            _bar: null,
            /** Elemento <select> del dropdown de vistas */
            _select: null,
            /** Botón "Guardar Vista" */
            _saveBtn: null,
            /** Botón "Restablecer Vista" */
            _resetBtn: null,
            /** Array de vistas cargadas desde la API */
            _views: [],
            /** ID de la vista activa (o null si ninguna) */
            _activeViewId: null,
            /** Base URL de la API */
            _apiBase: '/presupuestos/requisiciones/dashboard/api/views/',

            /**
             * Obtiene el CSRF token de las cookies del navegador.
             * @returns {string|null}
             */
            _getCookie: function (name) {
                var cookieValue = null;
                if (document.cookie && document.cookie !== '') {
                    var cookies = document.cookie.split(';');
                    for (var i = 0; i < cookies.length; i++) {
                        var cookie = cookies[i].trim();
                        if (cookie.substring(0, name.length + 1) === (name + '=')) {
                            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                            break;
                        }
                    }
                }
                return cookieValue;
            },

            /**
             * Inicializa el ViewManager: crea la barra de UI.
             * La carga de vistas se hace por separado via loadAndApplyLastUsed().
             * @param {HTMLElement} container - Elemento donde insertar la barra (antes de las tabs)
             */
            init: function (container) {
                if (!container) return;
                this._createBar(container);
            },

            /**
             * Crea la barra de vistas con el dropdown, botones Guardar y Restablecer.
             * @param {HTMLElement} container
             */
            _createBar: function (container) {
                var self = this;

                // Contenedor principal de la barra
                this._bar = document.createElement('div');
                this._bar.className = 'views-bar';
                this._bar.style.cssText = 'display: flex; align-items: center; gap: 10px; padding: 10px 16px; margin-bottom: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; flex-wrap: wrap;';

                // Label
                var label = document.createElement('span');
                label.textContent = 'Vista:';
                label.style.cssText = 'font-size: 0.85rem; font-weight: 600; color: #475569;';
                this._bar.appendChild(label);

                // Dropdown/select
                this._select = document.createElement('select');
                this._select.className = 'view-selector';
                this._select.style.cssText = 'padding: 6px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; border-radius: 6px; background: white; color: #1e293b; min-width: 160px; cursor: pointer;';
                this._select.addEventListener('change', function () {
                    self._onViewSelected();
                });
                this._bar.appendChild(this._select);

                // Botón Eliminar Vista
                var deleteBtn = document.createElement('button');
                deleteBtn.type = 'button';
                deleteBtn.className = 'btn-delete-view';
                deleteBtn.innerHTML = '🗑️';
                deleteBtn.title = 'Eliminar vista seleccionada';
                deleteBtn.style.cssText = 'padding: 6px 10px; font-size: 0.85rem; border: 1px solid #fecaca; border-radius: 6px; background: #fff5f5; color: #dc2626; cursor: pointer; transition: background 0.15s;';
                deleteBtn.addEventListener('click', function () {
                    self._onDeleteClicked();
                });
                this._bar.appendChild(deleteBtn);
                this._deleteBtn = deleteBtn;

                // Separador
                var sep = document.createElement('span');
                sep.style.cssText = 'width: 1px; height: 24px; background: #e2e8f0; margin: 0 4px;';
                this._bar.appendChild(sep);

                // Botón Guardar Vista
                this._saveBtn = document.createElement('button');
                this._saveBtn.type = 'button';
                this._saveBtn.className = 'btn-custom btn-outline-custom btn-save-view';
                this._saveBtn.textContent = '💾 Guardar Vista';
                this._saveBtn.style.cssText = 'padding: 6px 14px; font-size: 0.85rem; border: 1px solid #6366f1; border-radius: 6px; background: white; color: #6366f1; cursor: pointer; font-weight: 500; transition: all 0.15s;';
                this._saveBtn.disabled = true;
                this._saveBtn.addEventListener('click', function () {
                    self._onSaveClicked();
                });
                this._bar.appendChild(this._saveBtn);

                // Botón Restablecer Vista
                this._resetBtn = document.createElement('button');
                this._resetBtn.type = 'button';
                this._resetBtn.className = 'btn-custom btn-outline-custom btn-reset-view';
                this._resetBtn.textContent = '↺ Restablecer';
                this._resetBtn.style.cssText = 'padding: 6px 14px; font-size: 0.85rem; border: 1px solid #94a3b8; border-radius: 6px; background: white; color: #64748b; cursor: pointer; font-weight: 500; transition: all 0.15s;';
                this._resetBtn.addEventListener('click', function () {
                    self._onResetClicked();
                });
                this._bar.appendChild(this._resetBtn);

                // Insertar la barra en el contenedor
                container.insertBefore(this._bar, container.firstChild);
            },

            /**
             * Carga las vistas del usuario desde la API y puebla el dropdown.
             * Retorna una Promise que resuelve con el array de vistas.
             * @returns {Promise<Array>}
             */
            loadViews: function () {
                var self = this;
                return fetch(this._apiBase, {
                    method: 'GET',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                .then(function (response) {
                    if (!response.ok) throw new Error('Error al cargar vistas');
                    return response.json();
                })
                .then(function (data) {
                    self._views = data.views || [];
                    self._populateSelect();
                    return self._views;
                })
                .catch(function (err) {
                    console.error('ViewManager.loadViews error:', err);
                    self._showErrorToast('No se pudieron cargar las vistas guardadas.');
                    return [];
                });
            },

            /**
             * Carga las vistas y aplica la última vista usada (is_last_used=true).
             * Si no hay última vista usada o fue eliminada, NO aplica nada (la lógica de fallback
             * se maneja en DashboardCustomizer.init).
             * @returns {Promise<boolean>} true si se aplicó una vista, false si no
             */
            loadAndApplyLastUsed: function () {
                var self = this;
                return this.loadViews().then(function (views) {
                    // Buscar la vista con is_last_used=true
                    var lastUsed = null;
                    for (var i = 0; i < views.length; i++) {
                        if (views[i].is_last_used) {
                            lastUsed = views[i];
                            break;
                        }
                    }

                    if (lastUsed) {
                        // Aplicar la última vista usada
                        self._activeViewId = lastUsed.id;
                        self._populateSelect();

                        // Aplicar columnas
                        var columns = lastUsed.columns;
                        if (Array.isArray(columns) && columns.length > 0) {
                            DashboardCustomizer.setActiveColumns(columns);
                        }

                        // Aplicar ordenamiento a ambas pestañas
                        DashboardCustomizer.SortManager.applyToBoth(
                            lastUsed.sort_column || 'fecha',
                            lastUsed.sort_direction || 'desc'
                        );

                        // Sincronizar localStorage con la vista aplicada
                        if (DashboardCustomizer.Persistence) {
                            DashboardCustomizer.Persistence.saveColumns(columns);
                            DashboardCustomizer.Persistence.saveSortState(
                                lastUsed.sort_column || 'fecha',
                                lastUsed.sort_direction || 'desc'
                            );
                        }

                        return true;
                    }

                    return false;
                });
            },

            /**
             * Puebla el dropdown con las vistas cargadas (ya vienen ordenadas alfabéticamente del API).
             */
            _populateSelect: function () {
                // Limpiar opciones existentes
                this._select.innerHTML = '';

                // Opción por defecto
                var defaultOpt = document.createElement('option');
                defaultOpt.value = '';
                defaultOpt.textContent = '— Seleccionar vista —';
                this._select.appendChild(defaultOpt);

                // Ordenar vistas alfabéticamente por nombre (por seguridad, aunque la API ya ordena)
                var sorted = this._views.slice().sort(function (a, b) {
                    return (a.name || '').localeCompare(b.name || '', 'es', { sensitivity: 'base' });
                });

                for (var i = 0; i < sorted.length; i++) {
                    var view = sorted[i];
                    var opt = document.createElement('option');
                    opt.value = view.id;
                    opt.textContent = view.name;
                    if (view.id === this._activeViewId) {
                        opt.selected = true;
                    }
                    this._select.appendChild(opt);
                }

                // Mostrar u ocultar botón de eliminar según haya selección
                this._updateDeleteButton();
            },

            /**
             * Maneja la selección de una vista del dropdown.
             */
            _onViewSelected: function () {
                var viewId = this._select.value;
                this._updateDeleteButton();

                if (!viewId) {
                    this._activeViewId = null;
                    return;
                }

                this.applyView(parseInt(viewId, 10));
            },

            /**
             * Aplica una vista: actualiza columnas, sort, marca como última usada vía API.
             * @param {number} viewId - ID de la vista a aplicar
             */
            applyView: function (viewId) {
                var self = this;
                var view = this._findView(viewId);
                if (!view) return;

                // Aplicar columnas
                var columns = view.columns;
                if (Array.isArray(columns) && columns.length > 0) {
                    DashboardCustomizer.setActiveColumns(columns);
                }

                // Aplicar ordenamiento a ambas pestañas
                DashboardCustomizer.SortManager.applyToBoth(
                    view.sort_column || 'fecha',
                    view.sort_direction || 'desc'
                );

                // Sincronizar localStorage
                if (DashboardCustomizer.Persistence) {
                    DashboardCustomizer.Persistence.saveColumns(columns);
                    DashboardCustomizer.Persistence.saveSortState(view.sort_column, view.sort_direction);
                }

                this._activeViewId = viewId;

                // Marcar como última usada vía API
                fetch(this._apiBase + viewId + '/apply/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': this._getCookie('csrftoken'),
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(function (response) {
                    if (!response.ok) throw new Error('Error al aplicar vista');
                })
                .catch(function (err) {
                    console.error('ViewManager.applyView error:', err);
                    self._showErrorToast('No se pudo registrar la vista como última usada.');
                });

                // Actualizar estado del botón Guardar
                this._updateSaveButton();
            },

            /**
             * Maneja clic en "Guardar Vista": muestra SweetAlert2 input para nombre.
             */
            _onSaveClicked: function () {
                var self = this;

                if (typeof Swal === 'undefined') {
                    alert('Error: SweetAlert2 no está disponible.');
                    return;
                }

                Swal.fire({
                    title: 'Guardar Vista',
                    input: 'text',
                    inputLabel: 'Nombre de la vista',
                    inputPlaceholder: 'Escribe un nombre para la vista...',
                    inputAttributes: {
                        maxlength: 100,
                        autocapitalize: 'off'
                    },
                    showCancelButton: true,
                    confirmButtonText: 'Guardar',
                    cancelButtonText: 'Cancelar',
                    confirmButtonColor: '#6366f1',
                    inputValidator: function (value) {
                        if (!value || !value.trim()) {
                            return 'El nombre de la vista es obligatorio.';
                        }
                        if (value.trim().length > 100) {
                            return 'El nombre no puede exceder 100 caracteres.';
                        }
                        return null;
                    }
                }).then(function (result) {
                    if (result.isConfirmed && result.value) {
                        self.saveView(result.value.trim());
                    }
                });
            },

            /**
             * Guarda una nueva vista con el nombre proporcionado.
             * @param {string} name - Nombre de la vista
             */
            saveView: function (name) {
                var self = this;
                var columns = DashboardCustomizer.getActiveColumns();
                var activeTabId = DashboardCustomizer.SortManager._getActiveTabId();
                var sortState = DashboardCustomizer.SortManager.getState(activeTabId);

                var body = {
                    name: name,
                    columns: columns,
                    sort_column: sortState.column || null,
                    sort_direction: sortState.direction || null
                };

                fetch(this._apiBase, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': this._getCookie('csrftoken'),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify(body)
                })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { ok: response.ok, status: response.status, data: data };
                    });
                })
                .then(function (result) {
                    if (!result.ok) {
                        // Error del servidor: mostrar mensaje específico
                        var msg = result.data.message || 'Error al guardar la vista.';
                        self._showErrorToast(msg);
                        return;
                    }

                    // Éxito: actualizar lista y seleccionar la nueva vista
                    var newView = result.data.view;
                    self._views.push(newView);
                    self._activeViewId = newView.id;
                    self._populateSelect();

                    // Marcar como última usada
                    fetch(self._apiBase + newView.id + '/apply/', {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': self._getCookie('csrftoken'),
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    }).catch(function () {});

                    self._showSuccessToast('Vista "' + newView.name + '" guardada exitosamente.');
                    self._updateSaveButton();
                })
                .catch(function (err) {
                    console.error('ViewManager.saveView error:', err);
                    self._showErrorToast('Error de red al guardar la vista.');
                });
            },

            /**
             * Maneja clic en el botón eliminar: solicita confirmación con SweetAlert2.
             */
            _onDeleteClicked: function () {
                var self = this;
                var viewId = parseInt(this._select.value, 10);
                if (!viewId) return;

                var view = this._findView(viewId);
                if (!view) return;

                if (typeof Swal === 'undefined') {
                    if (confirm('¿Eliminar la vista "' + view.name + '"?')) {
                        self.deleteView(viewId);
                    }
                    return;
                }

                Swal.fire({
                    title: '¿Eliminar vista?',
                    text: '¿Estás seguro de eliminar la vista "' + view.name + '"? Esta acción no se puede deshacer.',
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonText: 'Sí, eliminar',
                    cancelButtonText: 'Cancelar',
                    confirmButtonColor: '#dc2626',
                    cancelButtonColor: '#6b7280'
                }).then(function (result) {
                    if (result.isConfirmed) {
                        self.deleteView(viewId);
                    }
                });
            },

            /**
             * Elimina una vista vía API.
             * @param {number} viewId - ID de la vista a eliminar
             */
            deleteView: function (viewId) {
                var self = this;

                fetch(this._apiBase + viewId + '/delete/', {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': this._getCookie('csrftoken'),
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(function (response) {
                    if (!response.ok) {
                        return response.json().then(function (data) {
                            throw new Error(data.message || 'Error al eliminar la vista.');
                        });
                    }
                    return response.json();
                })
                .then(function () {
                    // Remover la vista del array local
                    self._views = self._views.filter(function (v) { return v.id !== viewId; });

                    // Si era la vista activa, limpiar
                    if (self._activeViewId === viewId) {
                        self._activeViewId = null;
                    }

                    self._populateSelect();
                    self._showSuccessToast('Vista eliminada exitosamente.');
                    self._updateSaveButton();
                })
                .catch(function (err) {
                    console.error('ViewManager.deleteView error:', err);
                    self._showErrorToast(err.message || 'Error al eliminar la vista.');
                });
            },

            /**
             * Maneja clic en "Restablecer Vista": aplica Columnas_Default, orden Fecha desc,
             * limpia última vista usada vía API, y sincroniza localStorage. (Req 4.6)
             */
            _onResetClicked: function () {
                var self = this;

                // 1. Aplicar columnas default
                DashboardCustomizer.setActiveColumns(DashboardCustomizer.DEFAULT_COLUMNS.slice());

                // 2. Aplicar orden default (Fecha desc) a ambas pestañas
                DashboardCustomizer.SortManager.reset();

                // 3. Limpiar localStorage y re-guardar defaults para mantener sincronía
                if (DashboardCustomizer.Persistence) {
                    DashboardCustomizer.Persistence.clear();
                    DashboardCustomizer.Persistence.saveColumns(DashboardCustomizer.DEFAULT_COLUMNS);
                    DashboardCustomizer.Persistence.saveSortState('fecha', 'desc');
                }

                // 4. Limpiar selección activa en la barra de vistas
                this._activeViewId = null;
                if (this._select) {
                    this._select.value = '';
                }
                this._updateDeleteButton();
                this._updateSaveButton();

                // 5. Limpiar filtros de columna y departamento (globales del template)
                if (typeof window.clearAllColumnFilters === 'function') {
                    window.clearAllColumnFilters();
                }
                if (typeof window.clearDepartmentFilter === 'function') {
                    window.clearDepartmentFilter();
                }

                // 6. Llamar API reset para limpiar última vista usada del usuario (Req 4.6)
                fetch(this._apiBase + 'reset/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': this._getCookie('csrftoken'),
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(function (response) {
                    if (!response.ok) throw new Error('Error al restablecer');
                })
                .catch(function (err) {
                    console.error('ViewManager._onResetClicked error:', err);
                    self._showErrorToast('No se pudo restablecer la vista en el servidor.');
                });
            },

            /**
             * Actualiza el estado habilitado/deshabilitado del botón "Guardar Vista".
             * Se habilita solo cuando la configuración actual difiere del default.
             */
            _updateSaveButton: function () {
                if (!this._saveBtn) return;

                var isDifferent = this._configDiffersFromDefault();
                this._saveBtn.disabled = !isDifferent;
                this._saveBtn.style.opacity = isDifferent ? '1' : '0.5';
                this._saveBtn.style.cursor = isDifferent ? 'pointer' : 'not-allowed';
            },

            /**
             * Comprueba si la configuración actual difiere de los defaults.
             * Defaults: DEFAULT_COLUMNS + sort Fecha desc.
             * @returns {boolean}
             */
            _configDiffersFromDefault: function () {
                var currentCols = DashboardCustomizer.getActiveColumns();
                var defaultCols = DashboardCustomizer.DEFAULT_COLUMNS.slice();

                // Comparar columnas (orden importa)
                if (currentCols.length !== defaultCols.length) return true;
                for (var i = 0; i < currentCols.length; i++) {
                    if (currentCols[i] !== defaultCols[i]) return true;
                }

                // Comparar sort: default es fecha desc
                var activeTabId = DashboardCustomizer.SortManager._getActiveTabId();
                var sortState = DashboardCustomizer.SortManager.getState(activeTabId);
                if (sortState.column !== 'fecha' || sortState.direction !== 'desc') return true;

                return false;
            },

            /**
             * Actualiza la visibilidad/estado del botón eliminar.
             */
            _updateDeleteButton: function () {
                if (!this._deleteBtn) return;
                var hasSelection = !!this._select.value;
                this._deleteBtn.disabled = !hasSelection;
                this._deleteBtn.style.opacity = hasSelection ? '1' : '0.4';
                this._deleteBtn.style.cursor = hasSelection ? 'pointer' : 'not-allowed';
            },

            /**
             * Busca una vista por ID en el array local.
             * @param {number} viewId
             * @returns {Object|null}
             */
            _findView: function (viewId) {
                for (var i = 0; i < this._views.length; i++) {
                    if (this._views[i].id === viewId) return this._views[i];
                }
                return null;
            },

            /**
             * Muestra un toast de éxito con SweetAlert2.
             * @param {string} message
             */
            _showSuccessToast: function (message) {
                if (typeof Swal === 'undefined') return;
                Swal.fire({
                    icon: 'success',
                    title: message,
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    timer: 3000,
                    timerProgressBar: true
                });
            },

            /**
             * Muestra un toast de error con SweetAlert2.
             * @param {string} message
             */
            _showErrorToast: function (message) {
                if (typeof Swal === 'undefined') {
                    console.error('ViewManager error:', message);
                    return;
                }
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: message,
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    timer: 5000,
                    timerProgressBar: true
                });
            },

            /**
             * Obtiene el ID de la vista activa actualmente.
             * @returns {number|null}
             */
            getActiveViewId: function () {
                return this._activeViewId;
            },

            /**
             * Establece la vista activa por ID (para carga inicial desde contexto Django).
             * @param {number} viewId
             */
            setActiveViewId: function (viewId) {
                this._activeViewId = viewId;
                if (this._select) {
                    this._select.value = viewId || '';
                    this._updateDeleteButton();
                }
            }
        },

        // ─── Persistence ──────────────────────────────────────────────────────────────

        /**
         * Persistence maneja la persistencia temporal de configuración en localStorage.
         * Guarda columnas visibles y criterio de ordenamiento.
         * Degrada elegantemente si localStorage no está disponible.
         */
        Persistence: {
            /** Keys de localStorage */
            KEYS: {
                COLUMNS: 'dashboard_columns',
                SORT_COL: 'dashboard_sort_col',
                SORT_DIR: 'dashboard_sort_dir'
            },

            /**
             * Verifica si localStorage está disponible.
             * @returns {boolean}
             */
            isAvailable: function () {
                try {
                    var testKey = '__dashboard_ls_test__';
                    localStorage.setItem(testKey, '1');
                    localStorage.removeItem(testKey);
                    return true;
                } catch (e) {
                    return false;
                }
            },

            /**
             * Guarda las columnas visibles en localStorage.
             * @param {string[]} columns - Array de IDs de columnas visibles
             */
            saveColumns: function (columns) {
                if (!this.isAvailable()) return;
                try {
                    localStorage.setItem(this.KEYS.COLUMNS, JSON.stringify(columns));
                } catch (e) {
                    // Silenciar errores de quota u otros
                }
            },

            /**
             * Carga las columnas desde localStorage.
             * @returns {string[]} Columnas guardadas o DEFAULT_COLUMNS si no hay datos válidos
             */
            loadColumns: function () {
                if (!this.isAvailable()) return DEFAULT_COLUMNS.slice();
                try {
                    var raw = localStorage.getItem(this.KEYS.COLUMNS);
                    if (raw === null) return DEFAULT_COLUMNS.slice();
                    var parsed = JSON.parse(raw);
                    if (!Array.isArray(parsed) || parsed.length === 0) {
                        this._clearKey(this.KEYS.COLUMNS);
                        return DEFAULT_COLUMNS.slice();
                    }
                    // Filtrar solo columnas válidas
                    var valid = parsed.filter(function (col) {
                        return COLUMNS_ORDER.indexOf(col) !== -1;
                    });
                    if (valid.length === 0) {
                        this._clearKey(this.KEYS.COLUMNS);
                        return DEFAULT_COLUMNS.slice();
                    }
                    return valid;
                } catch (e) {
                    // JSON inválido: limpiar y retornar default
                    this._clearKey(this.KEYS.COLUMNS);
                    return DEFAULT_COLUMNS.slice();
                }
            },

            /**
             * Guarda el estado de ordenamiento en localStorage.
             * @param {string|null} column - ID de columna ordenada, o null
             * @param {string|null} direction - 'asc', 'desc', o null
             */
            saveSortState: function (column, direction) {
                if (!this.isAvailable()) return;
                try {
                    if (column === null || column === undefined) {
                        localStorage.removeItem(this.KEYS.SORT_COL);
                    } else {
                        localStorage.setItem(this.KEYS.SORT_COL, String(column));
                    }
                    if (direction === null || direction === undefined) {
                        localStorage.removeItem(this.KEYS.SORT_DIR);
                    } else {
                        localStorage.setItem(this.KEYS.SORT_DIR, String(direction));
                    }
                } catch (e) {
                    // Silenciar errores
                }
            },

            /**
             * Carga el estado de ordenamiento desde localStorage.
             * @returns {{column: string|null, direction: string|null}}
             */
            loadSortState: function () {
                var defaultState = { column: null, direction: null };
                if (!this.isAvailable()) return defaultState;
                try {
                    var col = localStorage.getItem(this.KEYS.SORT_COL);
                    var dir = localStorage.getItem(this.KEYS.SORT_DIR);

                    // Validar columna
                    if (col !== null && SORTABLE_COLUMNS.indexOf(col) === -1) {
                        this._clearKey(this.KEYS.SORT_COL);
                        this._clearKey(this.KEYS.SORT_DIR);
                        return defaultState;
                    }
                    // Validar dirección
                    if (dir !== null && dir !== 'asc' && dir !== 'desc') {
                        this._clearKey(this.KEYS.SORT_DIR);
                        dir = null;
                    }

                    return {
                        column: col || null,
                        direction: dir || null
                    };
                } catch (e) {
                    return defaultState;
                }
            },

            /**
             * Elimina todas las keys del dashboard de localStorage.
             */
            clear: function () {
                if (!this.isAvailable()) return;
                try {
                    localStorage.removeItem(this.KEYS.COLUMNS);
                    localStorage.removeItem(this.KEYS.SORT_COL);
                    localStorage.removeItem(this.KEYS.SORT_DIR);
                } catch (e) {
                    // Silenciar errores
                }
            },

            /**
             * Elimina una key específica de localStorage.
             * @param {string} key
             * @private
             */
            _clearKey: function (key) {
                try {
                    localStorage.removeItem(key);
                } catch (e) {
                    // Silenciar errores
                }
            }
        },

        /**
         * Inicializa el DashboardCustomizer.
         * Debe invocarse después de que el DOM esté cargado.
         *
         * Lógica de carga inicial (Requisitos 4.1–4.6):
         * 1. Si options.lastView existe (inyectado desde contexto Django) → aplicar esa vista
         * 2. Si no hay lastView → cargar configuración desde localStorage (Persistence)
         * 3. Si no hay datos en localStorage → usar DEFAULT_COLUMNS con Fecha desc
         * 4. Sincronizar localStorage con la configuración aplicada
         *
         * @param {Object} [options] - Opciones de inicialización
         * @param {Object|null} [options.lastView] - Última vista usada (desde contexto Django)
         *        Formato: {id, columns: [...], sort_column: 'fecha', sort_direction: 'desc', name: '...'}
         *        null si no hay última vista o fue eliminada
         * @param {HTMLElement} [options.viewsBarContainer] - Contenedor para la barra de vistas
         */
        init: function (options) {
            options = options || {};

            // ─── Determinar configuración inicial ──────────────────────────────────
            var initialColumns = DEFAULT_COLUMNS.slice();
            var initialSortCol = 'fecha';
            var initialSortDir = 'desc';
            var initialViewId = null;

            if (options.lastView && typeof options.lastView === 'object') {
                // Caso 1: Última vista usada proporcionada por el servidor (Req 4.1, 4.2)
                var lv = options.lastView;

                if (Array.isArray(lv.columns) && lv.columns.length > 0) {
                    // Filtrar solo columnas válidas (ignorar columnas que ya no existen - Error Handling)
                    var validCols = lv.columns.filter(function (col) {
                        return COLUMNS_ORDER.indexOf(col) !== -1;
                    });
                    if (validCols.length > 0) {
                        // Asegurar que 'acciones' esté incluida
                        if (validCols.indexOf('acciones') === -1) {
                            validCols.push('acciones');
                        }
                        initialColumns = validCols;
                    }
                }

                // Aplicar sort de la vista si es válido
                if (lv.sort_column && SORTABLE_COLUMNS.indexOf(lv.sort_column) !== -1) {
                    initialSortCol = lv.sort_column;
                }
                if (lv.sort_direction && (lv.sort_direction === 'asc' || lv.sort_direction === 'desc')) {
                    initialSortDir = lv.sort_direction;
                }

                // Guardar ID de la vista activa
                if (lv.id) {
                    initialViewId = lv.id;
                }
            } else {
                // Caso 2 y 3: No hay última vista → intentar localStorage (Req 4.3)
                var savedCols = this.Persistence.loadColumns();
                var savedSort = this.Persistence.loadSortState();

                // loadColumns() ya retorna DEFAULT_COLUMNS si no hay datos válidos
                initialColumns = savedCols;

                // Usar sort de localStorage si existe, sino default Fecha desc
                if (savedSort.column && savedSort.direction) {
                    initialSortCol = savedSort.column;
                    initialSortDir = savedSort.direction;
                }
            }

            // ─── Aplicar configuración determinada ─────────────────────────────────
            activeColumns = initialColumns.slice();
            TableManager.applyColumns(activeColumns);

            // Inicializar selector en el primer surface-header encontrado
            var header = document.getElementById('column-selector-container-general');
            if (header) {
                ColumnSelector.init(header);
            }

            // Inicializar SortManager (establece default Fecha desc internamente)
            SortManager.init();

            // Aplicar el sort determinado a ambas pestañas
            SortManager.applyToBoth(initialSortCol, initialSortDir);

            // ─── Sincronizar localStorage con la configuración aplicada (Req 4.3) ──
            this.Persistence.saveColumns(activeColumns);
            this.Persistence.saveSortState(initialSortCol, initialSortDir);

            // ─── Inicializar ViewManager ───────────────────────────────────────────
            var viewsContainer = options.viewsBarContainer || document.querySelector('.dashboard-content');
            if (this.ViewManager && viewsContainer) {
                this.ViewManager.init(viewsContainer);

                // Cargar vistas desde la API para poblar el dropdown
                this.ViewManager.loadViews();

                // Si hay última vista usada, marcar como activa en el dropdown
                if (initialViewId) {
                    this.ViewManager.setActiveViewId(initialViewId);
                }

                // Actualizar estado del botón Guardar
                this.ViewManager._updateSaveButton();
            }
        },

        /**
         * Obtiene las columnas activas actualmente.
         * @returns {string[]}
         */
        getActiveColumns: function () {
            return TableManager.getActiveColumns();
        },

        /**
         * Establece las columnas activas (para carga de vistas o reset).
         * Aplica a ambas tablas y sincroniza el selector.
         * @param {string[]} columns
         */
        setActiveColumns: function (columns) {
            TableManager.setActiveColumns(columns);
            ColumnSelector.syncCheckboxes();
        }
    };
})();
