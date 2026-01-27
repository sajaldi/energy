import React, { useState, useEffect, useCallback } from 'react';
import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    TouchableOpacity,
    Alert,
    ActivityIndicator,
} from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { RootStackParamList } from '../App';
import { ScannerView } from '../components/ScannerView';
import { StatsBar } from '../components/StatsBar';
import { ResultCard } from '../components/ResultCard';
import {
    getAuditoriaStats,
    inicializarAuditoria,
    procesarEscaneo,
    finalizarAuditoria,
} from '../services/api';
import { ScanResult, AuditoriaStats } from '../types';
import { Colors, Spacing, FontSizes, BorderRadius } from '../constants/Colors';

type Props = NativeStackScreenProps<RootStackParamList, 'AuditExecution'>;

export const AuditExecutionScreen: React.FC<Props> = ({ route, navigation }) => {
    const { auditoriaId, auditoriaNombre } = route.params;

    const [stats, setStats] = useState<AuditoriaStats>({
        pendientes: 0,
        encontrados: 0,
        total: 0,
    });
    const [recentResults, setRecentResults] = useState<ScanResult[]>([]);
    const [isProcessing, setIsProcessing] = useState(false);
    const [isInitialized, setIsInitialized] = useState(false);
    const [loading, setLoading] = useState(true);

    const loadStats = useCallback(async () => {
        try {
            const data = await getAuditoriaStats(auditoriaId);
            setStats(data);
            setIsInitialized(data.total > 0);
        } catch (error) {
            console.error('Error loading stats:', error);
        } finally {
            setLoading(false);
        }
    }, [auditoriaId]);

    useEffect(() => {
        loadStats();
    }, [loadStats]);

    const handleInitialize = async () => {
        Alert.alert(
            'Inicializar Auditoría',
            '¿Está seguro de inicializar la auditoría? Esto generará los registros pendientes para todos los activos en el alcance seleccionado.',
            [
                { text: 'Cancelar', style: 'cancel' },
                {
                    text: 'Inicializar',
                    onPress: async () => {
                        setIsProcessing(true);
                        try {
                            const response = await inicializarAuditoria(auditoriaId);
                            if (response.status === 'success') {
                                Alert.alert('Éxito', response.message);
                                await loadStats();
                                setIsInitialized(true);
                            } else {
                                Alert.alert('Error', response.error || 'Error al inicializar');
                            }
                        } catch (error: any) {
                            Alert.alert('Error', error.message || 'Error al inicializar');
                        } finally {
                            setIsProcessing(false);
                        }
                    },
                },
            ]
        );
    };

    const handleScan = async (barcode: string) => {
        setIsProcessing(true);
        try {
            const result = await procesarEscaneo(auditoriaId, barcode);

            if (result.status === 'success' && result.activo) {
                // Add to recent results
                setRecentResults((prev) => [result, ...prev.slice(0, 9)]);

                // Update stats
                if (result.stats) {
                    setStats({
                        pendientes: result.stats.total - result.stats.encontrados,
                        encontrados: result.stats.encontrados,
                        total: result.stats.total,
                    });
                }

                // Show feedback based on status
                const statusMessages: Record<string, { title: string; icon: string }> = {
                    ENCONTRADO: { title: '✓ Encontrado', icon: '✓' },
                    UBICACION_ERRONEA: { title: '⚠ Ubicación Errónea', icon: '⚠' },
                    NO_PERTENECE: { title: 'ℹ No pertenece', icon: 'ℹ' },
                };

                const status = statusMessages[result.resultado_estado || ''] || {
                    title: 'Escaneado',
                    icon: '○'
                };

                Alert.alert(
                    status.title,
                    `${result.activo.nombre}\nCódigo: ${result.activo.codigo}`,
                    [{ text: 'OK' }]
                );
            } else {
                Alert.alert('Error', result.error || 'Activo no encontrado');
            }
        } catch (error: any) {
            Alert.alert('Error', error.message || 'Error al procesar escaneo');
        } finally {
            setIsProcessing(false);
        }
    };

    const handleFinalize = async () => {
        Alert.alert(
            'Finalizar Auditoría',
            '¿Está seguro de FINALIZAR la auditoría? Los equipos no encontrados se marcarán como EXTRAVIADOS y no se podrán realizar más escaneos.',
            [
                { text: 'Cancelar', style: 'cancel' },
                {
                    text: 'Finalizar',
                    style: 'destructive',
                    onPress: async () => {
                        setIsProcessing(true);
                        try {
                            const response = await finalizarAuditoria(auditoriaId);
                            if (response.status === 'success') {
                                Alert.alert('Éxito', response.message, [
                                    {
                                        text: 'OK',
                                        onPress: () => navigation.goBack(),
                                    },
                                ]);
                            } else {
                                Alert.alert('Error', response.error || 'Error al finalizar');
                            }
                        } catch (error: any) {
                            Alert.alert('Error', error.message || 'Error al finalizar');
                        } finally {
                            setIsProcessing(false);
                        }
                    },
                },
            ]
        );
    };

    if (loading) {
        return (
            <View style={styles.centerContainer}>
                <ActivityIndicator size="large" color={Colors.primary} />
                <Text style={styles.loadingText}>Cargando auditoría...</Text>
            </View>
        );
    }

    if (!isInitialized) {
        return (
            <View style={styles.centerContainer}>
                <Text style={styles.emptyIcon}>🚀</Text>
                <Text style={styles.emptyTitle}>Auditoría no inicializada</Text>
                <Text style={styles.emptySubtitle}>
                    Inicialice la auditoría para comenzar a escanear activos
                </Text>
                <TouchableOpacity
                    style={styles.initButton}
                    onPress={handleInitialize}
                    disabled={isProcessing}
                >
                    <Text style={styles.buttonText}>
                        {isProcessing ? 'Inicializando...' : '🚀 Inicializar Auditoría'}
                    </Text>
                </TouchableOpacity>
            </View>
        );
    }

    return (
        <View style={styles.container}>
            <StatsBar
                pendientes={stats.pendientes}
                encontrados={stats.encontrados}
                total={stats.total}
            />

            <View style={styles.scannerContainer}>
                <ScannerView onScan={handleScan} isProcessing={isProcessing} />
            </View>

            {recentResults.length > 0 && (
                <View style={styles.resultsContainer}>
                    <Text style={styles.resultsTitle}>Escaneos Recientes</Text>
                    <ScrollView style={styles.resultsList}>
                        {recentResults.map((result, index) => (
                            <ResultCard key={index} result={result} />
                        ))}
                    </ScrollView>
                </View>
            )}

            <View style={styles.actionsContainer}>
                <TouchableOpacity
                    style={[styles.actionButton, styles.finalizeButton]}
                    onPress={handleFinalize}
                    disabled={isProcessing}
                >
                    <Text style={styles.buttonText}>🏁 Finalizar Auditoría</Text>
                </TouchableOpacity>
            </View>
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.backgroundSecondary,
    },
    centerContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: Colors.backgroundSecondary,
        padding: Spacing.lg,
    },
    loadingText: {
        marginTop: Spacing.md,
        fontSize: FontSizes.md,
        color: Colors.textSecondary,
    },
    emptyIcon: {
        fontSize: 64,
        marginBottom: Spacing.md,
    },
    emptyTitle: {
        fontSize: FontSizes.xl,
        fontWeight: '600',
        color: Colors.text,
        marginBottom: Spacing.sm,
    },
    emptySubtitle: {
        fontSize: FontSizes.md,
        color: Colors.textSecondary,
        textAlign: 'center',
        marginBottom: Spacing.xl,
    },
    initButton: {
        backgroundColor: Colors.success,
        paddingHorizontal: Spacing.xl,
        paddingVertical: Spacing.md,
        borderRadius: BorderRadius.lg,
    },
    scannerContainer: {
        flex: 1,
        minHeight: 300,
    },
    resultsContainer: {
        maxHeight: 250,
        backgroundColor: Colors.surface,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
    },
    resultsTitle: {
        fontSize: FontSizes.md,
        fontWeight: '600',
        color: Colors.text,
        padding: Spacing.md,
        backgroundColor: Colors.backgroundSecondary,
    },
    resultsList: {
        flex: 1,
    },
    actionsContainer: {
        padding: Spacing.md,
        backgroundColor: Colors.surface,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
    },
    actionButton: {
        paddingVertical: Spacing.md,
        borderRadius: BorderRadius.md,
        alignItems: 'center',
    },
    finalizeButton: {
        backgroundColor: Colors.error,
    },
    buttonText: {
        color: Colors.background,
        fontSize: FontSizes.md,
        fontWeight: '600',
    },
});
