import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { ScanResult } from '../types';
import { Colors, Spacing, BorderRadius, FontSizes } from '../constants/Colors';

interface ResultCardProps {
    result: ScanResult;
}

export const ResultCard: React.FC<ResultCardProps> = ({ result }) => {
    if (!result.activo) return null;

    const getStatusColor = (estado?: string) => {
        switch (estado) {
            case 'ENCONTRADO':
                return Colors.statusEncontrado;
            case 'UBICACION_ERRONEA':
                return Colors.statusUbicacionErronea;
            case 'EXTRAVIADO':
                return Colors.statusExtraviado;
            case 'NO_PERTENECE':
                return Colors.statusNoPertenece;
            default:
                return Colors.statusPendiente;
        }
    };

    const getStatusIcon = (estado?: string) => {
        switch (estado) {
            case 'ENCONTRADO':
                return '✓';
            case 'UBICACION_ERRONEA':
                return '⚠';
            case 'EXTRAVIADO':
                return '✗';
            case 'NO_PERTENECE':
                return 'ℹ';
            default:
                return '○';
        }
    };

    const statusColor = getStatusColor(result.resultado_estado);
    const statusIcon = getStatusIcon(result.resultado_estado);

    return (
        <View style={[styles.card, { borderLeftColor: statusColor }]}>
            <View style={styles.header}>
                <View style={[styles.iconContainer, { backgroundColor: statusColor }]}>
                    <Text style={styles.icon}>{statusIcon}</Text>
                </View>
                <View style={styles.content}>
                    <Text style={styles.title} numberOfLines={1}>
                        {result.activo.nombre}
                    </Text>
                    <Text style={styles.code}>Código: {result.activo.codigo}</Text>
                    {result.activo.ubicacion && (
                        <Text style={styles.location}>📍 {result.activo.ubicacion}</Text>
                    )}
                </View>
            </View>

            <View style={styles.footer}>
                <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
                    <Text style={styles.statusText}>{result.display_estado}</Text>
                </View>
            </View>
        </View>
    );
};

const styles = StyleSheet.create({
    card: {
        backgroundColor: Colors.surface,
        borderRadius: BorderRadius.md,
        padding: Spacing.md,
        marginHorizontal: Spacing.md,
        marginVertical: Spacing.sm,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.1,
        shadowRadius: 2,
        elevation: 2,
        borderLeftWidth: 4,
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: Spacing.sm,
    },
    iconContainer: {
        width: 40,
        height: 40,
        borderRadius: BorderRadius.full,
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: Spacing.md,
    },
    icon: {
        fontSize: FontSizes.xl,
        color: Colors.background,
        fontWeight: '700',
    },
    content: {
        flex: 1,
    },
    title: {
        fontSize: FontSizes.md,
        fontWeight: '600',
        color: Colors.text,
        marginBottom: Spacing.xs,
    },
    code: {
        fontSize: FontSizes.sm,
        color: Colors.textSecondary,
        marginBottom: Spacing.xs,
    },
    location: {
        fontSize: FontSizes.sm,
        color: Colors.textLight,
    },
    footer: {
        flexDirection: 'row',
        justifyContent: 'flex-end',
    },
    statusBadge: {
        paddingHorizontal: Spacing.sm,
        paddingVertical: Spacing.xs,
        borderRadius: BorderRadius.sm,
    },
    statusText: {
        fontSize: FontSizes.xs,
        color: Colors.background,
        fontWeight: '600',
    },
});
