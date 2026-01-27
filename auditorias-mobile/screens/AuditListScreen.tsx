import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { RootStackParamList } from '../App';

type Props = NativeStackScreenProps<RootStackParamList, 'AuditList'>;

export const AuditListScreen: React.FC<Props> = ({ navigation }) => {
    return (
        <View style={styles.container}>
            <Text style={styles.text}>Lista de Auditorías (Simplificada)</Text>
            <TouchableOpacity
                style={styles.button}
                onPress={() => navigation.navigate('AuditExecution', { auditoriaId: 1, auditoriaNombre: 'Test' })}
            >
                <Text style={styles.buttonText}>Ir a Ejecución (Test)</Text>
            </TouchableOpacity>
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: '#f3f4f6',
    },
    text: {
        fontSize: 18,
        marginBottom: 20,
        color: '#374151',
    },
    button: {
        backgroundColor: '#2563eb',
        padding: 15,
        borderRadius: 8,
    },
    buttonText: {
        color: '#ffffff',
        fontWeight: 'bold',
    },
});
