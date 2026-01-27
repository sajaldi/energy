import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Auditoria } from '../types';
import { Colors, Spacing, BorderRadius, FontSizes } from '../constants/Colors';

interface AuditCardProps {
    auditoria: Auditoria;
    onPress: () => void;
    stats?: {
        pendientes: number;
        encontrados: number;
        total: number;
    };
}

export const AuditCard: React.FC<AuditCardProps> = ({ auditoria, onPress, stats }) => {
    const getStatusColor = (estado: string) => {
        switch (estado) {
            case 'BORRADOR':
                return Colors.estadoBorrador;
            case 'EN_CURSO':
                return Colors.estadoEnCurso;
            case 'FINALIZADA':
                return Colors.estadoFinalizada;
            default:
                return Colors.textSecondary;
        }
    };

    const getStatusText = (estado: string) => {
        switch (estado) {
            case 'BORRADOR':
                return 'Borrador';
            case 'EN_CURSO':
                return 'En Curso';
            case 'FINALIZADA':
                return 'Finalizada';
            default:
                return estado;
        }
    };

    const progress = stats && stats.total > 0
        ? (stats.encontrados / stats.total) * 100
        : 0;

    return (
        <TouchableOpacity
            style={styles.card}
            onPress={onPress}
            activeOpacity={0.7}
        >
            <View style={styles.header}>
                <Text style={styles.title} numberOfLines={2}>
                    {auditoria.nombre}
                </Text>
                <View style={[styles.badge, { backgroundColor: getStatusColor(auditoria.estado) }]}>
                    <Text style={styles.badgeText}>{getStatusText(auditoria.estado)}</Text>
                </View>
            </View>

            {stats && stats.total > 0 && (
                <View style={styles.statsContainer}>
                    <View style={styles.progressBarBackground}>
                        <View
                            style={[
                                styles.progressBarFill,
                                { width: `${progress}%` }
                            ]}
                        />
                    </View>
                    <View style={styles.statsRow}>
                        <Text style={styles.statsText}>
                            {stats.encontrados} / {stats.total} escaneados
                        </Text>
                        <Text style={styles.statsPercentage}>
                            {Math.round(progress)}%
                        </Text>
                    </View>
                </View>
            )}

            <View style={styles.footer}>
                <Text style={styles.dateText}>
                    Inicio: {new Date(auditoria.fecha_inicio).toLocaleDateString('es-MX')}
                </Text>
                {auditoria.fecha_fin && (
                    <Text style={styles.dateText}>
                        Fin: {new Date(auditoria.fecha_fin).toLocaleDateString('es-MX')}
                    </Text>
                )}
            </View>
        </TouchableOpacity>
    );
};

const styles = StyleSheet.create({
    card: {
        backgroundColor: Colors.surface,
        borderRadius: BorderRadius.lg,
        padding: Spacing.md,
        marginHorizontal: Spacing.md,
        marginVertical: Spacing.sm,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.1,
        shadowRadius: 4,
        elevation: 3,
        borderWidth: 1,
        borderColor: Colors.borderLight,
    },
    header: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: Spacing.md,
    },
    title: {
        flex: 1,
        fontSize: FontSizes.lg,
        fontWeight: '600',
        color: Colors.text,
        marginRight: Spacing.sm,
    },
    badge: {
        paddingHorizontal: Spacing.sm,
        paddingVertical: Spacing.xs,
        borderRadius: BorderRadius.sm,
    },
    badgeText: {
        color: Colors.background,
        fontSize: FontSizes.xs,
        fontWeight: '600',
    },
    statsContainer: {
        marginBottom: Spacing.md,
    },
    progressBarBackground: {
        height: 8,
        backgroundColor: Colors.borderLight,
        borderRadius: BorderRadius.full,
        overflow: 'hidden',
        marginBottom: Spacing.sm,
    },
    progressBarFill: {
        height: '100%',
        backgroundColor: Colors.success,
        borderRadius: BorderRadius.full,
    },
    statsRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
    },
    statsText: {
        fontSize: FontSizes.sm,
        color: Colors.textSecondary,
    },
    statsPercentage: {
        fontSize: FontSizes.sm,
        color: Colors.success,
        fontWeight: '600',
    },
    footer: {
        borderTopWidth: 1,
        borderTopColor: Colors.borderLight,
        paddingTop: Spacing.sm,
    },
    dateText: {
        fontSize: FontSizes.xs,
        color: Colors.textLight,
        marginTop: Spacing.xs,
    },
});
