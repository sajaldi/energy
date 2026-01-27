import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Spacing, BorderRadius, FontSizes } from '../constants/Colors';

interface StatsBarProps {
    pendientes: number;
    encontrados: number;
    total: number;
}

export const StatsBar: React.FC<StatsBarProps> = ({ pendientes, encontrados, total }) => {
    const progress = total > 0 ? (encontrados / total) * 100 : 0;

    return (
        <View style={styles.container}>
            <View style={styles.statsGrid}>
                <View style={styles.statItem}>
                    <Text style={styles.statValue}>{total}</Text>
                    <Text style={styles.statLabel}>Total</Text>
                </View>
                <View style={styles.statItem}>
                    <Text style={[styles.statValue, { color: Colors.success }]}>{encontrados}</Text>
                    <Text style={styles.statLabel}>Escaneados</Text>
                </View>
                <View style={styles.statItem}>
                    <Text style={[styles.statValue, { color: Colors.warning }]}>{pendientes}</Text>
                    <Text style={styles.statLabel}>Pendientes</Text>
                </View>
            </View>

            <View style={styles.progressContainer}>
                <View style={styles.progressBarBackground}>
                    <View
                        style={[
                            styles.progressBarFill,
                            { width: `${progress}%` }
                        ]}
                    />
                </View>
                <Text style={styles.progressText}>{Math.round(progress)}% Completado</Text>
            </View>
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
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
    },
    statsGrid: {
        flexDirection: 'row',
        justifyContent: 'space-around',
        marginBottom: Spacing.md,
    },
    statItem: {
        alignItems: 'center',
    },
    statValue: {
        fontSize: FontSizes.xxl,
        fontWeight: '700',
        color: Colors.primary,
    },
    statLabel: {
        fontSize: FontSizes.sm,
        color: Colors.textSecondary,
        marginTop: Spacing.xs,
    },
    progressContainer: {
        marginTop: Spacing.sm,
    },
    progressBarBackground: {
        height: 12,
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
    progressText: {
        fontSize: FontSizes.sm,
        color: Colors.textSecondary,
        textAlign: 'center',
        fontWeight: '600',
    },
});
