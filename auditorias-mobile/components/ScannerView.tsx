import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, Alert } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Colors, Spacing, BorderRadius, FontSizes } from '../constants/Colors';

interface ScannerViewProps {
    onScan: (barcode: string) => void;
    isProcessing?: boolean;
}

export const ScannerView: React.FC<ScannerViewProps> = ({ onScan, isProcessing = false }) => {
    const [permission, requestPermission] = useCameraPermissions();
    const [scanned, setScanned] = useState(false);
    const [manualEntry, setManualEntry] = useState(false);
    const [manualCode, setManualCode] = useState('');

    const handleBarCodeScanned = ({ data }: { data: string }) => {
        if (!scanned && !isProcessing) {
            setScanned(true);
            onScan(data);

            // Reset after 2 seconds to allow next scan
            setTimeout(() => {
                setScanned(false);
            }, 2000);
        }
    };

    const handleManualSubmit = () => {
        if (manualCode.trim()) {
            onScan(manualCode.trim());
            setManualCode('');
            setManualEntry(false);
        } else {
            Alert.alert('Error', 'Por favor ingrese un código válido');
        }
    };

    if (!permission) {
        return (
            <View style={styles.container}>
                <Text style={styles.message}>Solicitando permiso de cámara...</Text>
            </View>
        );
    }

    if (!permission.granted) {
        return (
            <View style={styles.container}>
                <Text style={styles.message}>
                    No se tiene acceso a la cámara. Por favor habilite los permisos en la configuración.
                </Text>
                <TouchableOpacity style={styles.button} onPress={requestPermission}>
                    <Text style={styles.buttonText}>Solicitar Permiso</Text>
                </TouchableOpacity>
            </View>
        );
    }

    if (manualEntry) {
        return (
            <View style={styles.manualEntryContainer}>
                <Text style={styles.manualTitle}>Ingreso Manual</Text>
                <TextInput
                    style={styles.input}
                    placeholder="Ingrese código del activo"
                    value={manualCode}
                    onChangeText={setManualCode}
                    autoFocus={true}
                    autoCapitalize="characters"
                />
                <View style={styles.manualButtons}>
                    <TouchableOpacity
                        style={[styles.button, styles.cancelButton]}
                        onPress={() => {
                            setManualEntry(false);
                            setManualCode('');
                        }}
                    >
                        <Text style={styles.buttonText}>Cancelar</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                        style={[styles.button, styles.submitButton]}
                        onPress={handleManualSubmit}
                        disabled={isProcessing}
                    >
                        <Text style={styles.buttonText}>
                            {isProcessing ? 'Procesando...' : 'Confirmar'}
                        </Text>
                    </TouchableOpacity>
                </View>
            </View>
        );
    }

    return (
        <View style={styles.scannerContainer}>
            {/* Placeholder for camera during debugging */}
            <View style={[StyleSheet.absoluteFillObject, { backgroundColor: '#000', justifyContent: 'center', alignItems: 'center' }]}>
                <Text style={{ color: '#fff' }}>[ Cámara en depuración ]</Text>
            </View>
            {/* 
            <CameraView
                style={StyleSheet.absoluteFillObject}
                onBarcodeScanned={handleBarCodeScanned}
            />
            */}

            <View style={styles.overlay}>
                <View style={styles.scanArea}>
                    <View style={[styles.corner, styles.topLeft]} />
                    <View style={[styles.corner, styles.topRight]} />
                    <View style={[styles.corner, styles.bottomLeft]} />
                    <View style={[styles.corner, styles.bottomRight]} />
                </View>

                <View style={styles.instructionsContainer}>
                    <Text style={styles.instructions}>
                        {scanned || isProcessing
                            ? 'Procesando...'
                            : 'Apunte la cámara al código de barras'}
                    </Text>
                </View>

                <TouchableOpacity
                    style={styles.manualButton}
                    onPress={() => setManualEntry(true)}
                    disabled={isProcessing}
                >
                    <Text style={styles.manualButtonText}>⌨ Ingreso Manual</Text>
                </TouchableOpacity>
            </View>
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        padding: Spacing.lg,
        backgroundColor: Colors.background,
    },
    message: {
        fontSize: FontSizes.md,
        color: Colors.text,
        textAlign: 'center',
        marginBottom: Spacing.lg,
    },
    scannerContainer: {
        flex: 1,
        position: 'relative',
    },
    overlay: {
        ...StyleSheet.absoluteFillObject,
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingVertical: Spacing.xxl,
    },
    scanArea: {
        width: 250,
        height: 250,
        position: 'relative',
        marginTop: Spacing.xxl,
    },
    corner: {
        position: 'absolute',
        width: 40,
        height: 40,
        borderColor: Colors.primary,
        borderWidth: 4,
    },
    topLeft: {
        top: 0,
        left: 0,
        borderRightWidth: 0,
        borderBottomWidth: 0,
    },
    topRight: {
        top: 0,
        right: 0,
        borderLeftWidth: 0,
        borderBottomWidth: 0,
    },
    bottomLeft: {
        bottom: 0,
        left: 0,
        borderRightWidth: 0,
        borderTopWidth: 0,
    },
    bottomRight: {
        bottom: 0,
        right: 0,
        borderLeftWidth: 0,
        borderTopWidth: 0,
    },
    instructionsContainer: {
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        paddingHorizontal: Spacing.lg,
        paddingVertical: Spacing.md,
        borderRadius: BorderRadius.lg,
    },
    instructions: {
        color: Colors.background,
        fontSize: FontSizes.md,
        fontWeight: '600',
        textAlign: 'center',
    },
    manualButton: {
        backgroundColor: Colors.primary,
        paddingHorizontal: Spacing.lg,
        paddingVertical: Spacing.md,
        borderRadius: BorderRadius.lg,
        marginBottom: Spacing.lg,
    },
    manualButtonText: {
        color: Colors.background,
        fontSize: FontSizes.md,
        fontWeight: '600',
    },
    manualEntryContainer: {
        flex: 1,
        justifyContent: 'center',
        padding: Spacing.lg,
        backgroundColor: Colors.background,
    },
    manualTitle: {
        fontSize: FontSizes.xxl,
        fontWeight: '700',
        color: Colors.text,
        marginBottom: Spacing.lg,
        textAlign: 'center',
    },
    input: {
        backgroundColor: Colors.surface,
        borderWidth: 2,
        borderColor: Colors.border,
        borderRadius: BorderRadius.md,
        padding: Spacing.md,
        fontSize: FontSizes.lg,
        marginBottom: Spacing.lg,
    },
    manualButtons: {
        flexDirection: 'row',
        gap: Spacing.md,
    },
    button: {
        flex: 1,
        paddingVertical: Spacing.md,
        borderRadius: BorderRadius.md,
        alignItems: 'center',
    },
    cancelButton: {
        backgroundColor: Colors.textSecondary,
    },
    submitButton: {
        backgroundColor: Colors.primary,
    },
    buttonText: {
        color: Colors.background,
        fontSize: FontSizes.md,
        fontWeight: '600',
    },
});
