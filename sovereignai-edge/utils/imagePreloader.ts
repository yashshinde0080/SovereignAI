export class ImagePreloader {
  private images: HTMLImageElement[] = [];
  private totalFrames: number;
  private framePrefix: string;
  
  constructor(totalFrames: number, framePrefix: string = '/sovereignaiframes/frame-') {
    this.totalFrames = totalFrames;
    this.framePrefix = framePrefix;
  }

  private getFramePath(index: number): string {
    const frameNumber = String(index).padStart(4, '0');
    return `${this.framePrefix}${frameNumber}.jpg`;
  }

  async preloadImages(onProgress?: (progress: number) => void): Promise<HTMLImageElement[]> {
    const loadPromises = Array.from({ length: this.totalFrames }, (_, i) => {
      return new Promise<HTMLImageElement>((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
          if (onProgress) {
            const progress = ((i + 1) / this.totalFrames) * 100;
            onProgress(progress);
          }
          resolve(img);
        };
        img.onerror = reject;
        img.src = this.getFramePath(i + 1);
        this.images[i] = img;
      });
    });

    await Promise.all(loadPromises);
    return this.images;
  }

  getImages(): HTMLImageElement[] {
    return this.images;
  }
}