export interface Auditoria {
    id: number;
    nombre: string;
    estado: 'BORRADOR' | 'EN_CURSO' | 'FINALIZADA';
    fecha_inicio: string;
    fecha_fin: string | null;
    creado_por: number;
}

export interface Activo {
    id: number;
    nombre: string;
    codigo_interno: string;
    epc: string | null;
    serie: string | null;
    ubicacion: string | null;
}

export interface ResultadoAuditoria {
    id: number;
    auditoria: number;
    activo: Activo;
    estado: 'PENDIENTE' | 'ENCONTRADO' | 'UBICACION_ERRONEA' | 'EXTRAVIADO' | 'NO_PERTENECE';
    ubicacion_esperada: string | null;
    ubicacion_encontrada: string | null;
    fecha_escaneo: string | null;
    observaciones: string | null;
}

export interface ScanResult {
    status: 'success' | 'error';
    activo?: {
        id: number;
        nombre: string;
        codigo: string;
        ubicacion: string;
    };
    resultado_estado?: string;
    display_estado?: string;
    stats?: {
        encontrados: number;
        total: number;
    };
    error?: string;
    barcode?: string;
}

export interface AuditoriaStats {
    pendientes: number;
    encontrados: number;
    total: number;
}

export interface InitializeResponse {
    status: 'success' | 'error';
    message: string;
    total_activos?: number;
    error?: string;
}
