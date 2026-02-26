'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import { Download } from 'lucide-react';

interface DownloadModalProps {
  open: boolean;
  onClose: () => void;
  onDownload: (model: string, quant: string) => Promise<void>;
  downloadStatus: any;
}

const popularModels = [
  { id: 'llama3:8b', name: 'Llama 3 8B' },
  { id: 'llama3:70b', name: 'Llama 3 70B' },
  { id: 'mistral:7b', name: 'Mistral 7B' },
  { id: 'phi-2', name: 'Phi-2' },
  { id: 'tinyllama:1b', name: 'TinyLlama 1B' },
];

const quantOptions = [
  { id: 'Q4_K_M', name: 'Q4_K_M (Recommended)' },
  { id: 'Q4_K_S', name: 'Q4_K_S (Smaller)' },
  { id: 'Q5_K_M', name: 'Q5_K_M (Better quality)' },
  { id: 'Q8_0', name: 'Q8_0 (Best quality)' },
];

export function DownloadModal({ open, onClose, onDownload, downloadStatus }: DownloadModalProps) {
  const [model, setModel] = useState('');
  const [quant, setQuant] = useState('Q4_K_M');
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    if (!model) return;

    setDownloading(true);
    try {
      await onDownload(model, quant);
    } finally {
      setDownloading(false);
    }
  };

  const isDownloading = downloadStatus?.status === 'downloading';
  const progress = downloadStatus?.progress || 0;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Download Model</DialogTitle>
          <DialogDescription>
            Download a model from HuggingFace
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Model</Label>
            <Select value={model} onValueChange={setModel}>
              <SelectTrigger>
                <SelectValue placeholder="Select a model" />
              </SelectTrigger>
              <SelectContent>
                {popularModels.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Or enter model name</Label>
            <Input
              placeholder="e.g., llama3:8b"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label>Quantization</Label>
            <Select value={quant} onValueChange={setQuant}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {quantOptions.map((q) => (
                  <SelectItem key={q.id} value={q.id}>
                    {q.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isDownloading && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Downloading...</span>
                <span>{progress.toFixed(1)}%</span>
              </div>
              <Progress value={progress} />
              <p className="text-xs text-muted-foreground">
                {downloadStatus?.downloaded_gb?.toFixed(2) || 0} / {downloadStatus?.total_gb?.toFixed(2) || 0} GB
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleDownload} disabled={!model || downloading || isDownloading}>
            <Download className="h-4 w-4 mr-2" />
            {isDownloading ? 'Downloading...' : 'Download'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}