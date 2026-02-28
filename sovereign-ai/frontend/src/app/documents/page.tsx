'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Upload, FileText, Database } from 'lucide-react'

interface DocumentItem {
  id: string
  name: string
  size: number
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([])

  const fetchDocs = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/v1/rag/documents')
      const data = await res.json()
      setDocuments(data)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    fetchDocs()
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">RAG Engine</h2>
          <p className="text-sm text-muted-foreground">Upload and index documents for offline retrieval-augmented generation.</p>
        </div>
        <Button className="bg-blue-600 hover:bg-blue-700">
          <Upload className="mr-2 h-4 w-4" /> Upload Document
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {documents.map(doc => (
          <Card key={doc.id} className="border-slate-800 bg-slate-900">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">
                {doc.name}
              </CardTitle>
              <FileText className="h-4 w-4 text-slate-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{Math.round(doc.size / 1024)} KB</div>
              <p className="text-xs text-muted-foreground mt-1">
                Indexed in FAISS Vector Store
              </p>
            </CardContent>
          </Card>
        ))}

        {documents.length === 0 && (
          <div className="col-span-full border-2 border-dashed border-slate-800 rounded-lg p-12 text-center text-slate-500">
            <Database className="mx-auto h-12 w-12 text-slate-600 mb-4" />
            <h3 className="text-lg font-medium text-slate-300">No documents indexed</h3>
            <p className="text-sm mt-2 max-w-sm mx-auto">Upload PDFs, text, or markdown files to enable context-aware chat queries securely offline.</p>
          </div>
        )}
      </div>
    </div>
  )
}
