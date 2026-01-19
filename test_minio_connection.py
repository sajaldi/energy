# Script para probar la conexión con MinIO y crear el bucket
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

# Configuración MinIO
MINIO_ENDPOINT = 'http://181.115.47.107:9000'  # IP Pública
MINIO_ACCESS_KEY = 'rootminio'
MINIO_SECRET_KEY = 'PasswordRoot07'

BUCKET_NAME = 'energia-media'

print("🔗 Conectando a MinIO...")
print(f"   Endpoint: {MINIO_ENDPOINT}")
print(f"   Access Key: {MINIO_ACCESS_KEY}")

import datetime

print(f"   Local Time: {datetime.datetime.now()}")

try:
    # Crear cliente S3
    s3_client = boto3.client(
        's3',
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        verify=False, # Ignorar SSL para pruebas
        config=Config(signature_version='s3')
    )
    
    print("✅ Cliente S3 creado exitosamente")
    
    # Listar buckets existentes
    print("\n📦 Buckets existentes:")
    response = s3_client.list_buckets()
    for bucket in response.get('Buckets', []):
        print(f"   - {bucket['Name']}")
    
    # Verificar si existe el bucket que queremos usar
    bucket_exists = any(b['Name'] == BUCKET_NAME for b in response.get('Buckets', []))
    
    if not bucket_exists:
        print(f"\n🆕 Creando bucket '{BUCKET_NAME}'...")
        s3_client.create_bucket(Bucket=BUCKET_NAME)
        
        # Configurar política de acceso público para lectura (opcional)
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{BUCKET_NAME}/*"]
                }
            ]
        }
        
        print(f"✅ Bucket '{BUCKET_NAME}' creado")
    else:
        print(f"\n✅ Bucket '{BUCKET_NAME}' ya existe")
    
    # Probar subida de archivo de prueba
    print(f"\n📤 Probando subida de archivo...")
    test_content = b"Archivo de prueba desde Django"
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key='test/prueba.txt',
        Body=test_content,
        ContentType='text/plain'
    )
    print("✅ Archivo de prueba subido exitosamente")
    
    # Generar URL del archivo
    url = f"{MINIO_ENDPOINT}/{BUCKET_NAME}/test/prueba.txt"
    print(f"🔗 URL del archivo: {url}")
    
    print("\n" + "="*50)
    print("✅ CONFIGURACIÓN DE MINIO EXITOSA")
    print("="*50)
    print(f"\nEndpoint: {MINIO_ENDPOINT}")
    print(f"Bucket: {BUCKET_NAME}")
    print(f"Access Key: {MINIO_ACCESS_KEY}")
    print("\nYa puedes configurar Django para usar MinIO.")
    
except ClientError as e:
    print(f"\n❌ Error de cliente S3: {e}")
    print(f"   Código de error: {e.response['Error']['Code']}")
    print(f"   Mensaje: {e.response['Error']['Message']}")
except Exception as e:
    print(f"\n❌ Error inesperado: {type(e).__name__}: {e}")
