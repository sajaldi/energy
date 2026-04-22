/**
 * Compressor.js - Client-side image compression
 */
window.ImageCompressor = {
    compress: function(file, maxWidth = 1280, quality = 0.7) {
        return new Promise((resolve, reject) => {
            if (!file.type.startsWith('image/')) {
                return resolve(file);
            }

            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = event => {
                const img = new Image();
                img.src = event.target.result;
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    let width = img.width;
                    let height = img.height;

                    if (width > maxWidth) {
                        height = Math.round((height * maxWidth) / width);
                        width = maxWidth;
                    }

                    canvas.width = width;
                    canvas.height = height;

                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);

                    canvas.toBlob(blob => {
                        if (!blob) {
                            return reject(new Error('Canvas to Blob failed'));
                        }
                        const compressedFile = new File([blob], file.name, {
                            type: 'image/jpeg',
                            lastModified: Date.now()
                        });
                        resolve(compressedFile);
                    }, 'image/jpeg', quality);
                };
                img.onerror = err => reject(err);
            };
            reader.onerror = err => reject(err);
        });
    }
};
