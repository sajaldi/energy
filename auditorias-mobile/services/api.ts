import axios from 'axios';
import { Auditoria, ScanResult, InitializeResponse, ResultadoAuditoria } from '../types';

// TODO: Update this with your actual Django server URL
// For local development, use your computer's IP address on the same network
// Example: 'http://192.168.1.100:8000' or 'http://localhost:8000'
const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    // Add timeout for better error handling
    timeout: 10000,
});

/**
 * Fetch all audits
 */
export const getAuditorias = async (): Promise<Auditoria[]> => {
    try {
        const response = await api.get('/auditorias/');
        return response.data;
    } catch (error) {
        console.error('Error fetching auditorias:', error);
        throw error;
    }
};

/**
 * Get audit details with statistics
 */
export const getAuditoriaDetail = async (id: number) => {
    try {
        const response = await api.get(`/auditorias/ejecutar/${id}/`);
        return response.data;
    } catch (error) {
        console.error('Error fetching auditoria detail:', error);
        throw error;
    }
};

/**
 * Initialize an audit (create pending results for all assets in scope)
 */
export const inicializarAuditoria = async (id: number): Promise<InitializeResponse> => {
    try {
        const response = await api.post(`/auditorias/api/inicializar/${id}/`);
        return response.data;
    } catch (error: any) {
        console.error('Error initializing auditoria:', error);
        if (error.response?.data) {
            return error.response.data;
        }
        throw error;
    }
};

/**
 * Process a scanned barcode
 */
export const procesarEscaneo = async (
    auditoriaId: number,
    barcode: string,
    ubicacionId?: number
): Promise<ScanResult> => {
    try {
        const formData = new FormData();
        formData.append('barcode', barcode);
        if (ubicacionId) {
            formData.append('ubicacion_id', ubicacionId.toString());
        }

        const response = await api.post(
            `/auditorias/api/procesar-escaneo/${auditoriaId}/`,
            formData,
            {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            }
        );
        return response.data;
    } catch (error: any) {
        console.error('Error processing scan:', error);
        if (error.response?.data) {
            return error.response.data;
        }
        throw error;
    }
};

/**
 * Finalize an audit (mark all pending assets as missing)
 */
export const finalizarAuditoria = async (id: number): Promise<InitializeResponse> => {
    try {
        const response = await api.post(`/auditorias/api/finalizar/${id}/`);
        return response.data;
    } catch (error: any) {
        console.error('Error finalizing auditoria:', error);
        if (error.response?.data) {
            return error.response.data;
        }
        throw error;
    }
};

/**
 * Get audit results/statistics
 */
export const getAuditoriaStats = async (id: number) => {
    try {
        // This would need a dedicated endpoint in Django, for now we'll use the detail view
        const response = await api.get(`/auditorias/ejecutar/${id}/`);
        return {
            pendientes: response.data.pendientes || 0,
            encontrados: response.data.encontrados || 0,
            total: response.data.total || 0,
        };
    } catch (error) {
        console.error('Error fetching stats:', error);
        return { pendientes: 0, encontrados: 0, total: 0 };
    }
};

export default api;
