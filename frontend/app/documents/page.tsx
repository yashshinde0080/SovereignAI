'use client';

import { useState, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { api } from '@/lib/api';
import { Upload, Trash2, Search, FileText } from 'lucide-react';

interface Document {
  id: string;
  filename: string;
  chunks: number;
  created_at: string;
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [query, setQuery] = useState('');
  const [queryResult, setQueryResult] = useState<any>(null);
  const [querying, setQuerying] = useState(false);

  const loadDocuments = async () => {
    try {
      const res = await api.listDocuments();
      setDocuments(res.documents || []);
    } catch (error) {
      console.error('Failed to load documents:', error);
    }
  };

  useState(() => {
    loadDocuments();
  });

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      await api.uploadDocument(file);
      await loadDocuments();
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId: string) => {
    try {
      await api.deleteDocument(docId);
      await loadDocuments();
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  const handleQuery = async () => {
    if (!query.trim()) return;

    setQuerying(true);
    try {
      const res = await api.queryDocuments(query);
      setQueryResult(res);
    } catch (error) {
      console.error('Query failed:', error);
    } finally {
      setQuerying(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Documents</h1>
          <p className="text-muted-foreground">
            Upload documents for RAG (Retrieval-Augmented Generation)
          </p>
        </div>
        <div>
          <input
            type="file"
            id="file-upload"
            className="hidden"
            accept=".txt,.pdf"
            onChange={handleUpload}
          />
          <label htmlFor="file-upload">
            <Button asChild disabled={uploading}>
              <span>
                <Upload className="h-4 w-4 mr-2" />
                {uploading ? 'Uploading...' : 'Upload Document'}
              </span>
            </Button>
          </label>
        </div>
      </div>

      {/* Query Section */}
      <Card>
        <CardHeader>
          <CardTitle>Query Documents</CardTitle>
          <CardDescription>
            Search through your uploaded documents
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Enter your question..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleQuery()}
            />
            <Button onClick={handleQuery} disabled={querying}>
              <Search className="h-4 w-4 mr-2" />
              {querying ? 'Searching...' : 'Search'}
            </Button>
          </div>

          {queryResult && (
            <div className="mt-4 space-y-4">
              {queryResult.generated_response && (
                <Alert>
                  <AlertDescription>
                    <p className="font-semibold mb-2">Answer:</p>
                    <p>{queryResult.generated_response}</p>
                  </AlertDescription>
                </Alert>
              )}

              <div>
                <p className="text-sm font-semibold mb-2">Sources:</p>
                <div className="space-y-2">
                  {queryResult.results?.map((result: any, i: number) => (
                    <div key={i} className="p-3 bg-muted rounded-lg">
                      <p className="text-sm">{result.text}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Score: {(result.score * 100).toFixed(1)}%
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Documents List */}
      <Card>
        <CardHeader>
          <CardTitle>Uploaded Documents</CardTitle>
          <CardDescription>
            {documents.length} document{documents.length !== 1 ? 's' : ''} indexed
          </CardDescription>
        </CardHeader>
        <CardContent>
          {documents.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No documents uploaded yet</p>
              <p className="text-sm">Upload PDF or TXT files to get started</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Filename</TableHead>
                  <TableHead className="text-right">Chunks</TableHead>
                  <TableHead className="text-right">Uploaded</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="font-medium">{doc.filename}</TableCell>
                    <TableCell className="text-right">{doc.chunks}</TableCell>
                    <TableCell className="text-right">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(doc.id)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}