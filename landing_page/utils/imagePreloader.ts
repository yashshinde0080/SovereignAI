/**
 * High-performance frame preloader for scroll-driven canvas animation.
 * Loads 240 frames in batches to avoid browser connection exhaustion.
 * File naming: S (1).jpg through S (240).jpg (with space before parenthesis)
 */
export class ImagePreloader {
  private images: HTMLImageElement[] = [];
  private totalFrames: number;

  constructor(totalFrames: number) {
    this.totalFrames = totalFrames;
  }

  private getFramePath(frameNumber: number): string {
    // Actual files: "S (1).jpg" ... "S (240).jpg" — URL-encode the space
    return `/sovereignaiframes/S%20(${frameNumber}).jpg`;
  }

  async preloadImages(onProgress?: (progress: number) => void): Promise<HTMLImageElement[]> {
    this.images = new Array(this.totalFrames);
    let loaded = 0;

    // Batch loading: 12 concurrent requests at a time
    const batchSize = 12;

    for (let batchStart = 0; batchStart < this.totalFrames; batchStart += batchSize) {
      const batchEnd = Math.min(batchStart + batchSize, this.totalFrames);
      const batchPromises: Promise<void>[] = [];

      for (let i = batchStart; i < batchEnd; i++) {
        const frameNumber = i + 1;
        batchPromises.push(
          new Promise<void>((resolve) => {
            const img = new Image();
            img.onload = () => {
              this.images[i] = img;
              loaded++;
              onProgress?.((loaded / this.totalFrames) * 100);
              resolve();
            };
            img.onerror = () => {
              console.warn(`Frame ${frameNumber} failed to load`);
              loaded++;
              onProgress?.((loaded / this.totalFrames) * 100);
              resolve();
            };
            img.src = this.getFramePath(frameNumber);
          })
        );
      }

      await Promise.all(batchPromises);
    }

    return this.images.filter(Boolean);
  }

  getImages(): HTMLImageElement[] {
    return this.images.filter(Boolean);
  }
}