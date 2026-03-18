/**
 * Phase 844 v3 — Server-side photo upload proxy + Image Policy Enforcement
 *
 * Locked image policy:
 *   - Allowed formats: jpg, jpeg, png, webp
 *   - Hard size limit: 15 MB (pre-checked client-side before upload)
 *   - Backend auto-compresses to ~2 MB + generates 400px thumbnail
 *
 * Uploads to: POST /properties/{propertyId}/upload-photo
 * Returns: { url, thumb_url } — full optimized image + thumbnail CDN URLs
 */

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001').replace(/\/$/, '');

const ALLOWED_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp']);
const MAX_BYTES = 15 * 1024 * 1024; // 15 MB

export interface UploadResult {
    url: string;
    thumb_url: string;
    original_size_bytes: number;
    optimized_size_bytes: number;
    thumb_size_bytes: number;
}

export async function uploadPropertyPhoto(
    file: File,
    propertyId: string,
    photoType: 'reference' | 'gallery' = 'reference',
    token: string,
): Promise<UploadResult> {
    // --- Client-side format check ---
    const mimeType = file.type || '';
    if (!ALLOWED_TYPES.has(mimeType)) {
        const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
        throw new Error(
            `Unsupported file format "${ext || mimeType}". Only JPG, PNG, and WebP images are allowed.`
        );
    }

    // --- Client-side 15 MB pre-check ---
    if (file.size > MAX_BYTES) {
        const mb = (file.size / (1024 * 1024)).toFixed(1);
        throw new Error(
            `Image is too large (${mb} MB). Maximum allowed is 15 MB. Please choose a smaller image.`
        );
    }

    // --- Upload via backend proxy ---
    const form = new FormData();
    form.append('file', file);
    form.append('photo_type', photoType);

    const resp = await fetch(
        `${API_URL}/properties/${encodeURIComponent(propertyId)}/upload-photo`,
        {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${token}`,
                // Do NOT set Content-Type — browser sets multipart boundary automatically
            },
            body: form,
        },
    );

    if (!resp.ok) {
        let detail = `HTTP ${resp.status}`;
        try {
            const err = await resp.json();
            detail = err?.detail ?? err?.message ?? detail;
        } catch { /* ignore */ }
        throw new Error(`Upload failed: ${detail}`);
    }

    const data = await resp.json();
    if (!data?.url) throw new Error('Upload succeeded but no URL returned from server.');

    return {
        url: data.url as string,
        thumb_url: (data.thumb_url ?? data.url) as string,
        original_size_bytes: data.original_size_bytes ?? file.size,
        optimized_size_bytes: data.optimized_size_bytes ?? 0,
        thumb_size_bytes: data.thumb_size_bytes ?? 0,
    };
}

/**
 * Accepted file types string for <input accept="..."> attribute.
 * Matches the locked image policy.
 */
export const ACCEPTED_IMAGE_TYPES = '.jpg,.jpeg,.png,.webp';
