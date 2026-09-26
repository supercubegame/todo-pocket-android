package com.supercubegame.pockettodo;

import java.util.ArrayList;
import java.util.List;

/**
 * Pure ARGB crop/redaction kernel. No source files, codecs, metadata, DB or UI.
 * Android adapters must separately validate/decode originals and persist derivatives.
 * Rectangles are integer pixels, left/top inclusive and right/bottom exclusive.
 * Masks use OUTPUT coordinates, after cropping. They replace pixels with opaque black;
 * no blur, alpha overlay, source metadata or reversible layers are returned.
 */
public final class ExportRenderer {
    private ExportRenderer() {}
    // Provisional resource policy, not a measured Android capacity guarantee.
    private static final long MAX_PIXELS = 20000000L;
    private static final int MAX_EDGE = 16384;

    public static final class Rect {
        public final int left, top, right, bottom;
        public Rect(int left, int top, int right, int bottom) {
            this.left = left;
            this.top = top;
            this.right = right;
            this.bottom = bottom;
        }
    }

    /** Owns only derived pixels. It never retains the source array or mask list. */
    public static final class Raster {
        public final int width, height;
        private final int[] pixels;
        private Raster(int width, int height, int[] pixels) {
            this.width = width;
            this.height = height;
            this.pixels = pixels;
        }
        public int[] copyPixels() { return pixels.clone(); }
    }

    private static void requireRect(Rect rect, int width, int height) {
        if (rect == null || rect.left < 0 || rect.top < 0 ||
            rect.right <= rect.left || rect.bottom <= rect.top ||
            rect.right > width || rect.bottom > height) {
            throw new IllegalArgumentException("Rectangle must be nonempty and inside its coordinate space");
        }
    }

    /**
     * Does not modify source, including when rejecting any argument.
     * Caller owns source exclusively for this synchronous call (not thread-safe against
     * concurrent mutation of caller data). Returned pixels are independent afterwards.
     * Unmasked ARGB values are preserved exactly, including alpha; masks are always opaque.
     * Explicit crop and mask list required. Invalid bounds are rejected, never clamped.
     */
    public static Raster render(int[] source, int width, int height, Rect crop,
                                List<Rect> masks, long maxOutputPixels) {
        if (source == null || width <= 0 || height <= 0 ||
            width > MAX_EDGE || height > MAX_EDGE ||
            (long) width * height > MAX_PIXELS || (long) width * height != source.length) {
            throw new IllegalArgumentException("Invalid source dimensions or pixel budget");
        }
        requireRect(crop, width, height);
        int outWidth = crop.right - crop.left;
        int outHeight = crop.bottom - crop.top;
        if (maxOutputPixels <= 0 || maxOutputPixels > MAX_PIXELS ||
            (long) outWidth * outHeight > maxOutputPixels) {
            throw new IllegalArgumentException("Invalid output pixel budget");
        }
        if (masks == null) throw new IllegalArgumentException("Explicit mask list required");
        List<Rect> checked = new ArrayList<>(masks);
        // Validate every mask before allocating or processing derived pixels.
        for (Rect rect : checked) requireRect(rect, outWidth, outHeight);
        int[] result = new int[outWidth * outHeight];
        for (int y = 0; y < outHeight; y++) {
            System.arraycopy(source, (crop.top + y) * width + crop.left,
                             result, y * outWidth, outWidth);
        }
        for (Rect rect : checked) {
            for (int y = rect.top; y < rect.bottom; y++) {
                for (int x = rect.left; x < rect.right; x++) {
                    result[y * outWidth + x] = 0xff000000;
                }
            }
        }
        return new Raster(outWidth, outHeight, result);
    }
}
